import unittest
import sys
import time

from pathlib import Path
from tempfile import TemporaryDirectory

from deepwrap.native_tools import NativeTools


class NativeToolsTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.tools = NativeTools(self.root, timeout=2)

    def tearDown(self):
        self.directory.cleanup()

    def test_write_read_and_edit_file(self):
        written = self.tools.write_file("nested/test.txt", "hello world\n")
        self.assertEqual(written["bytes_written"], 12)

        read = self.tools.read_file("nested/test.txt")
        self.assertEqual(read["content"], "hello world\n")

        edited = self.tools.edit_file("nested/test.txt", "world", "agent")
        self.assertEqual(edited["replacements"], 1)
        self.assertEqual((self.root / "nested/test.txt").read_text(), "hello agent\n")

    def test_edit_rejects_ambiguous_target(self):
        (self.root / "test.txt").write_text("x x")
        with self.assertRaises(ValueError):
            self.tools.edit_file("test.txt", "x", "y")

    def test_grep_finds_regex_with_glob(self):
        (self.root / "nested").mkdir()
        (self.root / "nested/match.py").write_text("answer = 42\n")
        (self.root / "skip.txt").write_text("answer = 42\n")

        result = self.tools.grep(r"answer\s*=\s*\d+", glob=["*.py"])

        self.assertEqual(result["count"], 1)
        self.assertIn("match.py", result["matches"][0])

    def test_exec_returns_structured_result(self):
        result = self.tools.exec("printf deepwrap")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["stdout"], "deepwrap")

    def test_exec_code_uses_python_interpreter(self):
        result = self.tools.exec_code("import json; print(json.dumps({'ok': True}))")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["stdout"].strip(), '{"ok": true}')

    def test_definitions_match_function_registry(self):
        definitions = {tool.name for tool in self.tools.definitions}
        self.assertEqual(definitions, set(self.tools.functions))

    def test_read_file_paginates_large_files(self):
        content = "".join(f"line {index}\n" for index in range(1000))
        (self.root / "large.py").write_text(content)

        first = self.tools.read_file("large.py")
        second = self.tools.read_file(
            "large.py",
            offset=first["next_offset"],
            limit=400,
        )

        self.assertEqual(first["lines_returned"], 400)
        self.assertTrue(first["has_more"])
        self.assertEqual(first["next_offset"], 400)
        self.assertIn("line 400", second["content"])
        self.assertEqual(second["offset"], 400)

    def test_grep_paginates_many_project_matches(self):
        for index in range(25):
            (self.root / f"module_{index}.py").write_text(f"class Shared{index}:\n    pass\n")

        first = self.tools.grep("class Shared", glob=["*.py"], max_results=10)
        second = self.tools.grep(
            "class Shared",
            glob=["*.py"],
            max_results=10,
            offset=first["next_offset"],
        )

        self.assertEqual(first["count"], 10)
        self.assertTrue(first["has_more"])
        self.assertEqual(first["next_offset"], 10)
        self.assertEqual(second["offset"], 10)
        self.assertEqual(second["count"], 10)

    def wait_for_job(self, job_id, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status = self.tools.job_status(job_id)
            if status["state"] != "running":
                return status
            time.sleep(0.02)
        self.fail(f"Job did not finish: {job_id}")

    def python_job(self, code):
        escaped = code.replace('"', '\\"')
        return f'"{sys.executable}" -u -c "{escaped}"'

    def test_background_job_starts_immediately_and_completes(self):
        job = self.tools.start_job(
            self.python_job("import time; print('started'); time.sleep(0.2); print('done')")
        )
        self.assertIn(job["state"], {"running", "completed"})
        self.assertTrue(job["id"].startswith("job_"))

        completed = self.wait_for_job(job["id"])
        output = self.tools.job_output(job["id"])
        self.assertEqual(completed["state"], "completed")
        self.assertIn("started", output["content"])
        self.assertIn("done", output["content"])

    def test_multiple_background_jobs_have_independent_processes(self):
        first = self.tools.start_job(self.python_job("import time; time.sleep(0.2); print(1)"))
        second = self.tools.start_job(self.python_job("import time; time.sleep(0.2); print(2)"))
        self.assertNotEqual(first["id"], second["id"])
        self.assertNotEqual(first["pid"], second["pid"])
        self.assertEqual(self.tools.list_jobs()["count"], 2)
        self.wait_for_job(first["id"])
        self.wait_for_job(second["id"])

    def test_background_output_is_paginated(self):
        job = self.tools.start_job(self.python_job("print('abcdefghij')"))
        self.wait_for_job(job["id"])
        first = self.tools.job_output(job["id"], limit=5)
        second = self.tools.job_output(job["id"], offset=first["next_offset"] or 5, limit=20)
        self.assertEqual(first["content"], "abcde")
        self.assertTrue(first["has_more"])
        self.assertTrue(second["content"].startswith("fghij"))

    def test_background_stderr_is_available(self):
        job = self.tools.start_job(
            self.python_job("import sys; print('problem', file=sys.stderr)")
        )
        self.wait_for_job(job["id"])
        output = self.tools.job_output(job["id"], stream="stderr")
        self.assertIn("problem", output["content"])

    def test_background_job_can_be_stopped(self):
        job = self.tools.start_job(self.python_job("import time; time.sleep(30)"))
        stopped = self.tools.stop_job(job["id"], force=True)
        self.assertTrue(stopped["stopped"])
        self.assertNotEqual(stopped["state"], "running")


class OutputBudgetTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.tools = NativeTools(self.directory.name, timeout=20, output_budget=2000)

    def tearDown(self):
        self.directory.cleanup()

    def test_oversized_output_is_clipped_for_the_model(self):
        result = self.tools.exec_code("print('A' * 20000)")

        self.assertTrue(result["truncated"])
        self.assertLess(len(result["stdout"]), 2500)
        self.assertEqual(result["stdout_total_chars"], 20001)

    def test_clipped_output_keeps_the_end_where_errors_land(self):
        result = self.tools.exec_code(
            "print('A' * 20000); print('FINAL-LINE-MATTERS')"
        )

        self.assertIn("FINAL-LINE-MATTERS", result["stdout"])
        self.assertIn("characters omitted", result["stdout"])

    def test_full_output_stays_readable_on_disk(self):
        result = self.tools.exec_code("print('A' * 20000)")
        spilled = Path(result["stdout_full_path"])

        self.assertTrue(spilled.is_file())
        self.assertEqual(len(spilled.read_text(encoding="utf-8")), 20001)

    def test_small_output_is_untouched(self):
        result = self.tools.exec_code("print('small')")

        self.assertEqual(result["stdout"], "small\n")
        self.assertFalse(result["truncated"])
        self.assertNotIn("stdout_full_path", result)

    def test_read_file_reports_the_shell_syntax_it_runs(self):
        summary = self.tools.environment_summary()

        self.assertIn("command_syntax=", summary)
        self.assertIn(f"max_output_chars={self.tools.output_budget}", summary)

    def test_an_explicit_shell_is_honoured(self):
        tools = NativeTools(self.directory.name, shell="cmd.exe")

        self.assertIn("cmd", Path(tools.shell).name.lower())
        self.assertFalse(tools.shell_is_posix)

    def test_wsl_bash_is_never_chosen_automatically(self):
        resolved = NativeTools._resolve_shell(None)

        self.assertNotIn("system32", resolved.lower())


class ShellSelectionTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.root = self.directory.name

    def tearDown(self):
        self.directory.cleanup()

    def test_posix_shell_runs_commands_through_itself(self):
        tools = NativeTools(self.root, shell="bash")

        self.assertEqual(tools._argv("echo hi")[1:], ["-c", "echo hi"])

    def test_powershell_is_not_handed_to_cmd(self):
        tools = NativeTools(self.root, shell="powershell")
        argv = tools._argv("Get-Location")

        self.assertIn("powershell", argv[0].lower())
        self.assertEqual(argv[1:], ["-NoProfile", "-Command", "Get-Location"])
        self.assertFalse(tools.shell_is_posix)

    def test_cmd_gets_its_own_invocation(self):
        tools = NativeTools(self.root, shell="cmd.exe")
        argv = tools._argv("echo hi")

        self.assertIn("cmd", argv[0].lower())
        self.assertEqual(argv[1:], ["/d", "/s", "/c", "echo hi"])

    def test_shell_operators_work_in_a_foreground_command(self):
        tools = NativeTools(self.root, timeout=20)
        result = tools.exec("echo first && echo second")

        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["stdout"].split(), ["first", "second"])

    def test_shell_operators_work_in_a_background_job(self):
        tools = NativeTools(self.root, timeout=20)
        job = tools.start_job("echo first && echo second")
        deadline = time.time() + 20
        while time.time() < deadline:
            if tools.job_status(job["id"])["state"] != "running":
                break
            time.sleep(0.2)

        output = tools.job_output(job["id"])["content"]
        self.assertEqual(output.split(), ["first", "second"])


if __name__ == "__main__":
    unittest.main()
