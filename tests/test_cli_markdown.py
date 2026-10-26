import unittest

from io import StringIO

from rich.console import Console

from deepwrap.interfaces.cli import MarkdownStreamRenderer


class MarkdownStreamRendererTests(unittest.TestCase):
    def make_renderer(self):
        output = StringIO()
        console = Console(file=output, force_terminal=False, width=100)
        return MarkdownStreamRenderer(console), output

    def test_renders_inline_markdown_without_raw_markers(self):
        renderer, output = self.make_renderer()
        renderer.feed("The **important** value is `42`.\n\n")
        renderer.finish()

        rendered = output.getvalue()
        self.assertIn("important", rendered)
        self.assertIn("42", rendered)
        self.assertNotIn("**", rendered)

    def test_waits_for_complete_fenced_code_block(self):
        renderer, output = self.make_renderer()
        renderer.feed("```python\nprint('hello')\n\n")
        self.assertEqual(output.getvalue(), "")

        renderer.feed("```\n\n")
        renderer.finish()
        self.assertIn("print", output.getvalue())
        self.assertNotIn("```", output.getvalue())

    def test_long_paragraph_is_flushed_before_it_ends(self):
        renderer, output = self.make_renderer()
        line = "This answer keeps going and never reaches a blank line.\n"
        renderer.feed(line * 40)

        self.assertNotEqual(output.getvalue(), "")

    def test_soft_flush_leaves_lists_alone(self):
        renderer, output = self.make_renderer()
        renderer.feed("".join(f"- item {index}\n" for index in range(200)))

        self.assertEqual(output.getvalue(), "")
        renderer.finish()
        self.assertIn("item 199", output.getvalue())

    def test_finish_renders_trailing_block_without_blank_line(self):
        renderer, output = self.make_renderer()
        renderer.feed("### Result\nEverything completed.")
        renderer.finish()

        rendered = output.getvalue()
        self.assertIn("Result", rendered)
        self.assertIn("Everything completed.", rendered)


if __name__ == "__main__":
    unittest.main()
