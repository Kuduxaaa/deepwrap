import unittest

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock

from deepwrap.interfaces.cli import DeepWrapCLI
from deepwrap.utils.config_store import AppConfig


class CLIAgentToolsTests(unittest.TestCase):
    def setUp(self):
        self.cli = DeepWrapCLI.__new__(DeepWrapCLI)
        self.cli.config = AppConfig(token="token", agent_mode=True)
        self.cli._pending_files = []
        self.cli._exit_requested = False
        self.cli._clear_requested = False
        self.cli._token_setup_requested = False
        self.cli.store = Mock()
        self.cli.store.path = Path("/tmp/deepwrap-config.json")
        self.cli.client = Mock()
        self.cli.chat = Mock()

        self.registered = {}

        def register_tool(tool, function, **kwargs):
            self.registered[tool.name] = (tool, function)

        self.cli.client.register_tool.side_effect = register_tool
        self.cli._register_cli_tools()

    def test_registers_every_slash_command_capability(self):
        expected = {
            "cli_clear",
            "cli_new_chat",
            "cli_switch_model",
            "cli_set_thinking",
            "cli_set_search",
            "cli_set_god_mode",
            "cli_save_config",
            "cli_status",
            "cli_help",
            "cli_exit",
            "cli_token_setup",
            "cli_attach_file",
            "cli_list_attachments",
            "cli_detach_files",
            "inspect_image",
        }
        self.assertEqual(set(self.registered), expected)

    def test_clear_exit_and_token_actions_are_safely_deferred(self):
        self.registered["cli_clear"][1]()
        self.registered["cli_exit"][1]()
        self.registered["cli_token_setup"][1]()
        self.assertTrue(self.cli._clear_requested)
        self.assertTrue(self.cli._exit_requested)
        self.assertTrue(self.cli._token_setup_requested)

    def test_status_and_settings_match_slash_commands(self):
        self.registered["cli_set_thinking"][1](enabled=False)
        status = self.registered["cli_status"][1]()
        self.assertFalse(status["thinking"])
        self.assertTrue(status["agent"])

    def test_god_mode_toggle_preserves_current_conversation(self):
        original_chat = self.cli.chat
        result = self.registered["cli_set_god_mode"][1](enabled=True)
        self.assertTrue(result["god_mode"])
        self.assertIs(self.cli.chat, original_chat)
        self.assertTrue(original_chat.god_mode)
        self.assertFalse(original_chat._is_god_mode_triggered)

    def test_search_rejects_non_default_model(self):
        result = self.registered["cli_set_search"][1](enabled=True)
        self.assertFalse(result["ok"])
        self.assertIn("default model", result["error"])

    def test_inspect_image_uses_dedicated_vision_session(self):
        vision = Mock()
        vision.respond.return_value = "A small landscape image."
        self.cli.client.chats.create_session.return_value = vision

        with TemporaryDirectory() as directory:
            path = Path(directory) / "image.jpg"
            path.write_bytes(b"image")
            result = self.registered["inspect_image"][1](
                path=str(path),
                question="What is visible?",
            )

        self.cli.client.chats.create_session.assert_called_once_with(model="vision")
        call = vision.respond.call_args
        self.assertEqual(call.args[0], "What is visible?")
        self.assertEqual(call.kwargs["files"], [path])
        self.assertFalse(call.kwargs["agent"])
        self.assertEqual(result["analysis"], "A small landscape image.")

    def test_attach_and_detach_manage_pending_vision_files(self):
        self.cli.config.model = "vision"
        self.cli.chat.upload_file.return_value = SimpleNamespace(id="file-1", name="photo.jpg")
        attached = self.registered["cli_attach_file"][1](path="photo.jpg")
        listed = self.registered["cli_list_attachments"][1]()
        detached = self.registered["cli_detach_files"][1]()

        self.assertTrue(attached["ok"])
        self.assertEqual(listed["attachments"][0]["id"], "file-1")
        self.assertEqual(detached["detached"], 1)
        self.assertEqual(self.cli._pending_files, [])


if __name__ == "__main__":
    unittest.main()
