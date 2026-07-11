import unittest

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from deepwrap.api.chat_session import ChatSession
from deepwrap.api.files import FilesAPI
from deepwrap.function_calling import Tool, parse_tool_calls


class FakeResponse:
    def __init__(self, payload=None, lines=None):
        self._payload = payload or {}
        self._lines = lines or []

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None

    def iter_lines(self, decode_unicode=False):
        return iter(self._lines)


class ChatSessionTests(unittest.TestCase):
    def make_chat(self, model="expert"):
        client = Mock()
        client.session = Mock()
        client.pow.build_header.return_value = "pow"
        return ChatSession(client, "session-id", model)

    def test_search_is_disabled_for_expert(self):
        chat = self.make_chat("expert")
        response = FakeResponse(lines=["event: close"])
        chat._session.post.return_value = response

        list(chat.respond_structured("hello", search=True))

        body = chat._session.post.call_args.kwargs["json"]
        self.assertFalse(body["search_enabled"])

    def test_search_remains_available_for_default(self):
        chat = self.make_chat("default")
        chat._session.post.return_value = FakeResponse(lines=["event: close"])

        list(chat.respond_structured("hello", search=True))

        body = chat._session.post.call_args.kwargs["json"]
        self.assertTrue(body["search_enabled"])

    def test_file_ids_are_forwarded_for_vision(self):
        chat = self.make_chat("vision")
        chat._session.post.return_value = FakeResponse(lines=["event: close"])

        list(chat.respond_structured("describe", ref_file_ids=["file-1"]))

        body = chat._session.post.call_args.kwargs["json"]
        self.assertEqual(body["ref_file_ids"], ["file-1"])
        self.assertFalse(body["search_enabled"])

    def test_file_ids_are_rejected_for_non_vision_models(self):
        chat = self.make_chat("default")
        with self.assertRaises(ValueError):
            list(chat.respond_structured("describe", ref_file_ids=["file-1"]))

    def test_automatic_tool_loop(self):
        chat = self.make_chat()
        outputs = iter(
            [
                '<deepwrap_tool_call>{"name":"add","arguments":{"a":2,"b":3}}</deepwrap_tool_call>',
                "The result is 5.",
            ]
        )

        def respond_structured(*args, **kwargs):
            yield "response", next(outputs)

        chat.respond_structured = respond_structured
        tool = Tool(
            name="add",
            description="Add two integers.",
            parameters={
                "type": "object",
                "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                "required": ["a", "b"],
            },
        )
        result = chat.respond_with_tools(
            "What is 2 + 3?",
            [tool],
            functions={"add": lambda a, b: a + b},
        )

        self.assertEqual(result.content, "The result is 5.")
        self.assertEqual(result.tool_calls[0].name, "add")


class FilesAPITests(unittest.TestCase):
    def test_upload_uses_har_protocol_headers_and_multipart_field(self):
        client = Mock()
        client.session = Mock()
        client.pow.build_header.return_value = "encoded-pow"
        client.session.post.return_value = FakeResponse(
            {
                "code": 0,
                "data": {
                    "biz_code": 0,
                    "biz_data": {
                        "id": "file-1",
                        "status": "PENDING",
                        "file_name": "image.png",
                        "file_size": 3,
                        "model_kind": "VISION",
                        "is_image": True,
                    },
                },
            }
        )
        api = FilesAPI(client)

        with TemporaryDirectory() as directory:
            path = Path(directory) / "image.png"
            path.write_bytes(b"png")
            uploaded = api.upload(path)

        call = client.session.post.call_args
        self.assertEqual(uploaded.id, "file-1")
        self.assertIn("file", call.kwargs["files"])
        self.assertEqual(call.kwargs["headers"]["x-model-type"], "vision")
        self.assertEqual(call.kwargs["headers"]["x-file-size"], "3")
        client.pow.build_header.assert_called_once_with("/api/v0/file/upload_file")

    def test_wait_treats_parsing_as_an_intermediate_status(self):
        client = Mock()
        client.session = Mock()
        api = FilesAPI(client)
        parsing = api._to_uploaded_file(
            {
                "id": "file-1",
                "status": "PARSING",
                "file_name": "image.png",
                "file_size": 3,
                "model_kind": "VISION",
                "is_image": True,
            }
        )
        success = api._to_uploaded_file(
            {
                "id": "file-1",
                "status": "SUCCESS",
                "file_name": "image.png",
                "file_size": 3,
                "model_kind": "VISION",
                "is_image": True,
            }
        )
        api.fetch = Mock(side_effect=[[parsing], [success]])

        result = api.wait_until_ready("file-1", timeout=1, poll_interval=0)

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(api.fetch.call_count, 2)


class FunctionProtocolTests(unittest.TestCase):
    def test_parser_supports_nested_arguments(self):
        calls = parse_tool_calls(
            '<deepwrap_tool_call>{"name":"weather","arguments":{"location":{"city":"Tbilisi"}}}</deepwrap_tool_call>'
        )
        self.assertEqual(calls[0].arguments["location"]["city"], "Tbilisi")

    def test_parser_rejects_non_object_arguments(self):
        with self.assertRaises(ValueError):
            parse_tool_calls(
                '<deepwrap_tool_call>{"name":"weather","arguments":[]}</deepwrap_tool_call>'
            )


if __name__ == "__main__":
    unittest.main()
