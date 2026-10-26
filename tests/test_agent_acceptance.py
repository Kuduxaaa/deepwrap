import json
import unittest

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from deepwrap import AgentResponse, AgentStream, Tool
from deepwrap.api.chat_session import ChatSession
from deepwrap.native_tools import NativeTools
from deepwrap.planner import TaskPlan


def tool_call(name, arguments):
    payload = json.dumps({"name": name, "arguments": arguments})
    return f"<deepwrap_tool_call>{payload}</deepwrap_tool_call>"


def native_tool_call(name, arguments):
    """Reproduce the backend's own tool markup that sometimes replaces ours."""

    payload = json.dumps(arguments)
    return (
        f"<｜｜DSML｜｜ calls> <｜｜DSML｜｜ invoke name=\"{name}\"> "
        f"<｜｜DSML｜｜ parameter name=\"arguments\" string=\"false\">"
        f"{payload}</｜｜DSML｜｜ parameter> "
        f"</｜｜DSML｜｜ invoke> </｜｜DSML｜｜ calls>"
    )


class AgentAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.client = Mock()
        self.client.session = Mock()
        self.client.agent_mode = True
        self.client.max_agent_rounds = 8
        self.client.native_tools = NativeTools(self.root, timeout=2)
        self.client.plan = TaskPlan()
        self.client.agent_tools = (
            self.client.native_tools.definitions + self.client.plan.definitions
        )
        self.client.agent_functions = {
            **self.client.native_tools.functions,
            **self.client.plan.functions,
        }
        self.chat = ChatSession(self.client, "session-id", "expert")

    def tearDown(self):
        self.directory.cleanup()

    @staticmethod
    def chat_event_messages(response):
        return " ".join(event.message for event in response.events)

    def set_turns(self, *turns):
        pending = iter(turns)
        prompts = []

        def respond_structured(prompt, **kwargs):
            prompts.append(prompt)
            turn = next(pending)
            for item in turn:
                if isinstance(item, tuple):
                    yield item
                else:
                    yield "response", item

        self.chat.respond_structured = respond_structured
        return prompts

    def run_single_tool(self, name, arguments, final="done"):
        self.set_turns([tool_call(name, arguments)], [final])
        return self.chat.respond("perform the task", stream=False)

    def test_01_agent_is_enabled_by_client_default(self):
        self.set_turns(["normal answer"])
        response = self.chat.respond("hello", stream=False)
        self.assertIsInstance(response, AgentResponse)
        self.assertEqual(response, "normal answer")
        self.assertEqual(response.events[0].type, "started")
        self.assertEqual(response.events[-1].type, "completed")

    def test_02_non_stream_response_is_string_compatible(self):
        self.set_turns(["answer"])
        response = self.chat.respond("hello", stream=False)
        self.assertIsInstance(response, str)
        self.assertEqual(response.upper(), "ANSWER")

    def test_03_stream_response_has_agent_stream_type(self):
        self.set_turns(["answer"])
        response = self.chat.respond("hello", stream=True)
        self.assertIsInstance(response, AgentStream)
        self.assertEqual("".join(response), "answer")

    def test_04_short_final_answer_is_not_lost(self):
        self.set_turns([("response", "short "), ("response", "answer")])
        response = self.chat.respond("hello", stream=True)
        self.assertEqual(list(response), ["short answer"])

    def test_05_long_final_answer_streams_in_multiple_chunks(self):
        chunks = [("response", "x" * 100) for _ in range(50)]
        self.set_turns(chunks)
        response = self.chat.respond("hello", stream=True)
        received = list(response)
        self.assertGreaterEqual(len(received), 2)
        self.assertEqual("".join(received), "x" * 5000)

    def test_06_narration_before_tool_call_is_not_leaked(self):
        self.set_turns(
            [
                (
                    "response",
                    "I will inspect it first. " * 50
                    + "\n"
                    + tool_call("exec_code", {"code": "print(1)"}),
                )
            ],
            ["finished"],
        )
        response = self.chat.respond("run it", stream=False)
        self.assertEqual(response, "finished")
        self.assertNotIn("deepwrap_tool_call", response)

    def test_07_multiple_calls_in_one_turn_are_executed(self):
        self.set_turns(
            [
                tool_call("write_file", {"path": "a.txt", "content": "A"})
                + tool_call("write_file", {"path": "b.txt", "content": "B"})
            ],
            ["both written"],
        )
        response = self.chat.respond("write files", stream=False)
        self.assertEqual([item.name for item in response.tools_used], ["write_file", "write_file"])
        self.assertEqual((self.root / "a.txt").read_text(), "A")
        self.assertEqual((self.root / "b.txt").read_text(), "B")

    def test_08_tool_arguments_are_preserved_in_telemetry(self):
        response = self.run_single_tool("write_file", {"path": "x.txt", "content": "hello"})
        self.assertEqual(
            response.tools_used[0].arguments,
            {"path": "x.txt", "content": "hello"},
        )

    def test_09_tool_output_is_preserved_in_telemetry(self):
        response = self.run_single_tool("exec_code", {"code": "print('ok')"})
        output = response.tools_used[0].output
        self.assertEqual(output["exit_code"], 0)
        self.assertEqual(output["stdout"], "ok\n")

    def test_10_tool_result_is_sent_to_the_next_model_turn(self):
        prompts = self.set_turns(
            [tool_call("exec_code", {"code": "print(42)"})],
            ["42"],
        )
        self.chat.respond("calculate", stream=False)
        self.assertIn("[TOOL RESULT] exec_code", prompts[1])
        self.assertIn("42", prompts[1])

    def test_11_unknown_tool_becomes_recoverable_error(self):
        self.set_turns([tool_call("missing_tool", {})], ["I recovered."])
        response = self.chat.respond("call missing", stream=False)
        self.assertEqual(response, "I recovered.")
        self.assertIn("Unknown tool", response.tools_used[0].output["error"])

    def test_12_tool_exception_becomes_recoverable_error(self):
        self.set_turns(
            [tool_call("read_file", {"path": "missing.txt"})],
            ["The file does not exist."],
        )
        response = self.chat.respond("read missing", stream=False)
        self.assertFalse(response.tools_used[0].output["ok"])
        self.assertIn("FileNotFoundError", response.tools_used[0].output["error"])

    def test_13_max_round_limit_asks_for_a_final_answer(self):
        self.client.max_agent_rounds = 2
        rounds = []

        def endless_turns(prompt, **kwargs):
            rounds.append(prompt)
            if len(rounds) > self.client.max_agent_rounds:
                yield "response", "I stopped and here is what I found."
            else:
                yield "response", tool_call("exec_code", {"code": "print('again')"})

        self.chat.respond_structured = endless_turns
        response = self.chat.respond("loop", stream=False)
        self.assertEqual(response, "I stopped and here is what I found.")
        self.assertIn("limit", self.chat_event_messages(response).lower())
        self.assertEqual(len(rounds), 3)

    def test_13b_round_limit_is_unlimited_by_default(self):
        self.client.max_agent_rounds = None
        rounds = []

        def many_turns(prompt, **kwargs):
            rounds.append(prompt)
            if len(rounds) > 12:
                yield "response", "finished after many rounds"
            else:
                yield "response", tool_call(
                    "exec_code", {"code": f"print({len(rounds)})"}
                )

        self.chat.respond_structured = many_turns
        response = self.chat.respond("long task", stream=False)
        self.assertEqual(response, "finished after many rounds")
        self.assertEqual(len(response.tools_used), 12)

    def test_13c_native_markup_tool_call_is_executed(self):
        self.set_turns(
            [native_tool_call("exec_code", {"code": "print('native')"})],
            ["done"],
        )
        response = self.chat.respond("use native markup", stream=False)
        self.assertEqual(response, "done")
        self.assertEqual(response.tools_used[0].name, "exec_code")
        self.assertEqual(response.tools_used[0].output["stdout"], "native\n")

    def test_13d_leaked_markup_never_reaches_the_final_answer(self):
        self.set_turns(
            ["Here you go.\n" + native_tool_call("exec_code", {"code": "print(1)"})],
            ["all done"],
        )
        response = self.chat.respond("mixed output", stream=False)
        self.assertNotIn("DSML", response)
        self.assertNotIn("invoke name", response)

    def test_13e_repeated_identical_calls_get_a_loop_warning(self):
        self.client.max_agent_rounds = 8
        prompts = []

        def repeating(prompt, **kwargs):
            prompts.append(prompt)
            if len(prompts) > 5:
                yield "response", "stopping"
            else:
                yield "response", tool_call("exec_code", {"code": "print(1)"})

        self.chat.respond_structured = repeating
        self.chat.respond("repeat", stream=False)
        self.assertTrue(
            any("same tool call" in prompt.lower() for prompt in prompts),
            prompts,
        )

    def test_13f_an_endlessly_repeating_agent_still_terminates(self):
        self.client.max_agent_rounds = None
        rounds = []

        def always_the_same(prompt, **kwargs):
            rounds.append(prompt)
            if "Do not call any more tools" in prompt:
                yield "response", "I kept repeating one check; here is what I know."
            else:
                yield "response", tool_call("exec_code", {"code": "print(1)"})

        self.chat.respond_structured = always_the_same
        response = self.chat.respond("spin forever", stream=False)
        self.assertEqual(response, "I kept repeating one check; here is what I know.")
        self.assertLess(len(rounds), 10)

    def test_13g_unparseable_syntax_is_not_retried_forever(self):
        self.client.max_agent_rounds = None
        rounds = []

        def never_valid(prompt, **kwargs):
            rounds.append(prompt)
            yield "response", (
                "The envelope looks like "
                '<deepwrap_tool_call>{"name":}</deepwrap_tool_call> in general.'
            )

        self.chat.respond_structured = never_valid
        response = self.chat.respond("explain the syntax", stream=False)
        self.assertEqual(len(rounds), 3)
        self.assertIn("The envelope looks like", response)

    def test_14_agent_can_execute_system_command(self):
        response = self.run_single_tool("exec", {"command": "printf agent-ok"})
        self.assertEqual(response.tools_used[0].output["stdout"], "agent-ok")

    def test_15_agent_can_execute_python_code(self):
        response = self.run_single_tool("exec_code", {"code": "print(6 * 7)"})
        self.assertEqual(response.tools_used[0].output["stdout"], "42\n")

    def test_16_agent_can_write_and_read_file(self):
        self.set_turns(
            [tool_call("write_file", {"path": "note.txt", "content": "hello"})],
            [tool_call("read_file", {"path": "note.txt"})],
            ["verified"],
        )
        response = self.chat.respond("write and verify", stream=False)
        self.assertEqual(response, "verified")
        self.assertEqual(response.tools_used[1].output["content"], "hello")

    def test_17_agent_can_edit_file_safely(self):
        (self.root / "config.txt").write_text("debug=false\n")
        response = self.run_single_tool(
            "edit_file",
            {"path": "config.txt", "old": "false", "new": "true"},
        )
        self.assertEqual((self.root / "config.txt").read_text(), "debug=true\n")
        self.assertEqual(response.tools_used[0].output["replacements"], 1)

    def test_18_agent_can_grep_nested_files_with_simple_glob(self):
        (self.root / "nested").mkdir()
        (self.root / "nested/code.py").write_text("class Target:\n    pass\n")
        response = self.run_single_tool(
            "grep",
            {"pattern": "class Target", "glob": ["*.py"]},
        )
        matches = response.tools_used[0].output["matches"]
        self.assertTrue(any("nested/code.py" in match for match in matches))

    def test_19_plain_mode_bypasses_native_agent(self):
        self.chat._respond_stream = Mock(return_value=iter(["plain", " answer"]))
        response = self.chat.respond("hello", agent=False, stream=False)
        self.assertEqual(response, "plain answer")
        self.chat._respond_stream.assert_called_once()

    def test_20_stream_telemetry_is_available_after_consumption(self):
        self.set_turns(
            [
                ("think", "I should run the requested code."),
                (
                    "response",
                    tool_call("exec_code", {"code": "print('telemetry')"}),
                ),
            ],
            [("response", "final "), ("response", "answer")],
        )
        live_events = []
        response = self.chat.respond("run", stream=True, on_event=live_events.append)
        self.assertEqual("".join(response), "final answer")
        self.assertEqual(len(response.tools_used), 1)
        self.assertEqual(response.tools_used[0].name, "exec_code")
        self.assertEqual(response.tools_used[0].output["stdout"], "telemetry\n")
        self.assertEqual(live_events, response.events)
        self.assertIn("tool_started", [event.type for event in response.events])
        self.assertIn("tool_completed", [event.type for event in response.events])
        self.assertIn("thinking", [event.type for event in response.events])


    def test_21_agent_can_write_and_advance_a_plan(self):
        self.set_turns(
            [tool_call("set_plan", {"steps": ["Read it", "Patch it", "Verify"]})],
            [tool_call("update_plan", {"step": 1, "status": "done"})],
            ["Plan started."],
        )
        response = self.chat.respond("do the multi-step task", stream=False)

        plan = response.tools_used[1].output
        self.assertEqual(plan["done"], 1)
        self.assertEqual(plan["current"], "Patch it")
        self.assertEqual(self.client.plan.get_plan()["total"], 3)

    def test_22_progress_recap_replays_the_task_and_plan(self):
        self.client.plan.set_plan(["Read it", "Patch it"])
        prompts = []

        def five_rounds(prompt, **kwargs):
            prompts.append(prompt)
            if len(prompts) > 5:
                yield "response", "done"
            else:
                yield "response", tool_call(
                    "exec_code", {"code": f"print({len(prompts)})"}
                )

        self.chat.respond_structured = five_rounds
        self.chat.respond("investigate the parser", stream=False)

        recaps = [item for item in prompts if "[DEEPWRAP PROGRESS]" in item]
        self.assertEqual(len(recaps), 1)
        self.assertIn("TASK: investigate the parser", recaps[0])
        self.assertIn("[>] 1. Read it", recaps[0])
        self.assertIn("exec_code: ok", recaps[0])

    def test_23_recap_is_announced_as_an_event(self):
        prompts = []

        def five_rounds(prompt, **kwargs):
            prompts.append(prompt)
            if len(prompts) > 5:
                yield "response", "done"
            else:
                yield "response", tool_call(
                    "exec_code", {"code": f"print({len(prompts)})"}
                )

        self.chat.respond_structured = five_rounds
        response = self.chat.respond("long investigation", stream=False)

        self.assertIn("recap", [event.type for event in response.events])


    def test_24_repeats_separated_by_other_work_are_not_a_loop(self):
        self.client.max_agent_rounds = None
        rounds = []

        def polling(prompt, **kwargs):
            rounds.append(prompt)
            if len(rounds) > 12:
                yield "response", "The job finished."
            elif len(rounds) % 2:
                # Polling the same job between real work is normal progress.
                yield "response", tool_call("list_jobs", {})
            else:
                yield "response", tool_call(
                    "exec_code", {"code": f"print({len(rounds)})"}
                )

        self.chat.respond_structured = polling
        response = self.chat.respond("watch the job", stream=False)

        self.assertEqual(response, "The job finished.")
        self.assertEqual(len(response.tools_used), 12)
        self.assertNotIn(
            "limit_reached", [event.type for event in response.events]
        )

    def test_25_only_consecutive_repeats_trigger_the_loop_warning(self):
        self.client.max_agent_rounds = None
        prompts = []

        def alternating(prompt, **kwargs):
            prompts.append(prompt)
            if len(prompts) > 8:
                yield "response", "done"
            elif len(prompts) % 2:
                yield "response", tool_call("list_jobs", {})
            else:
                yield "response", tool_call("get_plan", {})

        self.chat.respond_structured = alternating
        self.chat.respond("alternate", stream=False)

        self.assertFalse(
            any("same tool call" in prompt.lower() for prompt in prompts),
            "alternating calls must not be reported as a loop",
        )


if __name__ == "__main__":
    unittest.main()
