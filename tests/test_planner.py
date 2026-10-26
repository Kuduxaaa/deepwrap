import unittest

from io import StringIO

from rich.console import Console

from deepwrap.function_calling import AgentEvent, ToolExecution, build_progress_recap
from deepwrap.interfaces.cli import DeepWrapCLI
from deepwrap.planner import MAX_STEPS, TaskPlan


class TaskPlanTests(unittest.TestCase):
    def setUp(self):
        self.plan = TaskPlan()

    def test_setting_a_plan_starts_the_first_step(self):
        state = self.plan.set_plan(["Read the config", "Patch it", "Verify"])

        self.assertEqual(state["total"], 3)
        self.assertEqual(state["done"], 0)
        self.assertEqual(state["steps"][0]["status"], "in_progress")
        self.assertEqual(state["current"], "Read the config")

    def test_finishing_a_step_starts_the_next_one(self):
        self.plan.set_plan(["One", "Two", "Three"])
        state = self.plan.update_plan(1, "done")

        self.assertEqual(state["done"], 1)
        self.assertEqual(state["steps"][1]["status"], "in_progress")
        self.assertEqual(state["current"], "Two")

    def test_blocked_steps_keep_the_plan_open(self):
        self.plan.set_plan(["One", "Two"])
        state = self.plan.update_plan(1, "blocked", note="no permission")

        self.assertEqual(state["steps"][0]["note"], "no permission")
        self.assertFalse(state["complete"])

    def test_plan_reports_completion(self):
        self.plan.set_plan(["One", "Two"])
        self.plan.update_plan(1, "done")
        state = self.plan.update_plan(2, "done")

        self.assertTrue(state["complete"])
        self.assertIsNone(state["current"])

    def test_unknown_step_is_rejected(self):
        self.plan.set_plan(["One"])
        with self.assertRaises(ValueError):
            self.plan.update_plan(7, "done")

    def test_unknown_status_is_rejected(self):
        self.plan.set_plan(["One"])
        with self.assertRaises(ValueError):
            self.plan.update_plan(1, "almost")

    def test_updating_without_a_plan_is_rejected(self):
        with self.assertRaises(ValueError):
            self.plan.update_plan(1, "done")

    def test_empty_and_oversized_plans_are_rejected(self):
        with self.assertRaises(ValueError):
            self.plan.set_plan([])
        with self.assertRaises(ValueError):
            self.plan.set_plan([f"step {index}" for index in range(MAX_STEPS + 1)])

    def test_summary_marks_progress_compactly(self):
        self.plan.set_plan(["Read", "Patch"])
        self.plan.update_plan(1, "done")

        summary = self.plan.summary()
        self.assertIn("[x] 1. Read", summary)
        self.assertIn("[>] 2. Patch", summary)

    def test_reset_clears_the_plan(self):
        self.plan.set_plan(["One"])
        self.plan.reset()

        self.assertEqual(self.plan.get_plan()["total"], 0)
        self.assertEqual(self.plan.summary(), "")

    def test_tool_registry_is_complete(self):
        self.assertEqual(
            {tool.name for tool in self.plan.definitions},
            {"set_plan", "update_plan", "get_plan"},
        )
        self.assertEqual(
            set(self.plan.functions), {"set_plan", "update_plan", "get_plan"}
        )


class ProgressRecapTests(unittest.TestCase):
    def test_recap_restates_task_plan_and_recent_results(self):
        plan = TaskPlan()
        plan.set_plan(["Read", "Patch"])
        plan.update_plan(1, "done")
        executions = [
            ToolExecution("read_file", {"path": "a.py"}, {"content": "x"}),
            ToolExecution("exec", {"command": "ls"}, {"exit_code": 1}),
        ]

        recap = build_progress_recap("Refactor the parser", plan.summary(), executions)

        self.assertIn("TASK: Refactor the parser", recap)
        self.assertIn("[x] 1. Read", recap)
        self.assertIn("- read_file: ok", recap)
        self.assertIn("- exec: FAILED", recap)
        self.assertIn("Do not repeat finished steps", recap)

    def test_recap_keeps_only_the_latest_calls(self):
        executions = [
            ToolExecution(f"tool_{index}", {}, {"ok": True}) for index in range(20)
        ]

        recap = build_progress_recap("task", "", executions, recent=3)

        self.assertIn("tool_19", recap)
        self.assertNotIn("tool_15", recap)

    def test_recap_works_without_a_plan(self):
        recap = build_progress_recap("task", "", [])

        self.assertIn("TASK: task", recap)
        self.assertNotIn("PLAN:", recap)


class PlanRenderingTests(unittest.TestCase):
    def render(self, plan):
        output = StringIO()
        console = Console(file=output, force_terminal=False, width=80)
        cli = DeepWrapCLI.__new__(DeepWrapCLI)
        cli.console = console
        cli._print_plan(plan)
        return output.getvalue()

    def test_plan_is_rendered_as_a_checklist(self):
        plan = TaskPlan()
        plan.set_plan(["Read the file", "Patch it"])
        plan.update_plan(1, "done")

        rendered = self.render(plan.get_plan())

        self.assertIn("plan (1/2)", rendered)
        self.assertIn("Read the file", rendered)
        self.assertIn("Patch it", rendered)

    def test_only_plan_tools_are_treated_as_plans(self):
        plan = TaskPlan()
        plan.set_plan(["One"])

        self.assertTrue(
            DeepWrapCLI._is_plan_event(
                AgentEvent(
                    "tool_completed",
                    "Finished set_plan.",
                    tool_name="set_plan",
                    output=plan.get_plan(),
                )
            )
        )
        self.assertFalse(
            DeepWrapCLI._is_plan_event(
                AgentEvent(
                    "tool_completed",
                    "Finished exec.",
                    tool_name="exec",
                    output={"steps": ["not a plan"]},
                )
            )
        )


if __name__ == "__main__":
    unittest.main()
