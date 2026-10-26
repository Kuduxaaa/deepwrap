import unittest

from io import StringIO

from rich.console import Console

from deepwrap.interfaces.cli import ThinkingView


class ThinkingViewTests(unittest.TestCase):
    def make_view(self, height=12, width=40):
        output = StringIO()
        console = Console(
            file=output,
            force_terminal=True,
            width=width,
            height=height,
        )
        return ThinkingView(console), output

    def test_visible_text_is_capped_to_the_console_height(self):
        view, _ = self.make_view(height=12)
        view.feed("".join(f"line {index}\n" for index in range(200)))

        visible_lines = view.visible_text.splitlines()
        self.assertLessEqual(len(visible_lines), 12)
        self.assertGreater(len(visible_lines), 1)

    def test_newest_thinking_stays_visible(self):
        view, _ = self.make_view(height=12)
        view.feed("".join(f"line {index}\n" for index in range(200)))

        self.assertIn("line 199", view.visible_text)
        self.assertNotIn("line 0\n", view.visible_text)

    def test_long_unwrapped_line_is_counted_by_wrapped_height(self):
        view, _ = self.make_view(height=10, width=40)
        view.feed("x" * 4000)

        visible_lines = view.visible_text.splitlines()
        self.assertLessEqual(len(visible_lines), 10)
        for line in visible_lines:
            self.assertLessEqual(len(line), 40)

    def test_full_text_is_preserved_for_scrollback(self):
        view, _ = self.make_view(height=8)
        view.feed("".join(f"line {index}\n" for index in range(50)))

        self.assertIn("line 0", view.text)
        self.assertIn("line 49", view.text)

    def test_short_thinking_is_shown_in_full(self):
        view, _ = self.make_view(height=20)
        view.feed("one\ntwo\nthree")

        self.assertEqual(view.visible_text, "one\ntwo\nthree")

    def test_each_agent_round_gets_a_fresh_panel(self):
        view, _ = self.make_view(height=20)
        view.start()
        view.feed("first round thought")
        view.finish()
        view.start()
        view.feed("second round thought")

        self.assertEqual(view.text, "second round thought")
        self.assertEqual(view.visible_text, "second round thought")

    def test_finish_prints_the_whole_panel_to_scrollback(self):
        view, output = self.make_view(height=8)
        view.start()
        view.feed("".join(f"line {index}\n" for index in range(40)))
        view.finish()

        rendered = output.getvalue()
        self.assertIn("line 39", rendered)
        self.assertFalse(view.active)


if __name__ == "__main__":
    unittest.main()
