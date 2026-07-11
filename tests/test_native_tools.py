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


if __name__ == "__main__":
    unittest.main()
