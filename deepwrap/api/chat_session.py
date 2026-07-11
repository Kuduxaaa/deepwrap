import json

from pathlib import Path
from typing import Callable, Generator, Literal, Mapping, Optional, Sequence

from .base import BaseAPI
from deepwrap.config import Config
from deepwrap.function_calling import (
    Tool,
    ToolCall,
    ToolResponse,
    build_tool_prompt,
    build_tool_result,
    execute_tool_call,
    parse_tool_calls,
)


ChunkKind = Literal["think", "response"]


class ChatSession(BaseAPI):
    """
    Represents a single chat session.

    This object stores session-specific state such as the session ID, selected
    model, and the last received message ID. It is responsible for sending
    prompts to the DeepSeek chat completion endpoint and streaming back the
    assistant's thoughts and final response.
    """

    CHAT_COMPLETION_ENDPOINT = (
        f"{Config.base_url}{Config.api_prefix}/chat/completion"
    )

    def __init__(self, client, session_id: str, model_type: str, god_mode: bool = False) -> None:
        """
        Initialize a chat session wrapper.

        Args:
            client:
                The root DeepWrap client instance.

            session_id:
                The server-issued chat session identifier.

            model_type:
                The model bound to this chat session, such as "expert" or
                "default".
            god_mode:
                Whether to enable god mode for this session.
        """

        super().__init__(client)

        self.session_id             = session_id
        self.model_type             = model_type
        self.god_mode               = god_mode
        self._is_god_mode_triggered = False
        self._last_message_id       = None

    @staticmethod
    def _normalize_fragment_type(fragment_type: Optional[str]) -> Optional[ChunkKind]:
        """
        Convert DeepSeek fragment types into internal normalized names.

        Args:
            fragment_type:
                The fragment type from the stream payload, such as "THINK" or
                "RESPONSE".

        Returns:
            "think" for THINK fragments, "response" for RESPONSE fragments,
            otherwise None.
        """

        if fragment_type == "THINK":
            return "think"

        if fragment_type == "RESPONSE":
            return "response"

        return None

    def respond_structured(
        self,
        prompt: str,
        thinking: bool = True,
        search: bool = True,
        ref_file_ids: Optional[Sequence[str]] = None,
    ) -> Generator[tuple[ChunkKind, str], None, None]:
        """
        Send a prompt and stream structured response chunks.

        This method preserves the distinction between the model's internal
        thinking stream and its final response stream.

        Args:
            prompt:
                The user prompt to send.

            thinking:
                Whether the model's thinking stream should be enabled.

            search:
                Whether search should be enabled for this request.

        Yields:
            Tuples of (kind, chunk), where kind is either:
                - "think"
                - "response"
        """

        if self.god_mode and not self._is_god_mode_triggered:
            prompt = "\n".join(Config.god_mode).format(prompt)
            self._is_god_mode_triggered = True

        if ref_file_ids and self.model_type != "vision":
            raise ValueError("File attachments are supported only by the vision model.")

        body = {
            "chat_session_id":   self.session_id,
            "parent_message_id": self._last_message_id,
            "model_type":        self.model_type if self._last_message_id is None else None,
            "prompt":            prompt,
            "ref_file_ids":      list(ref_file_ids or ()),
            "thinking_enabled":  thinking,
            "search_enabled":    search if self.model_type == "default" else False,
            "action":            None,
            "preempt":           False,
        }

        headers = {
            "content-type":      "application/json",
            "accept":            "text/event-stream",
            "x-ds-pow-response": self._client.pow.build_header(
                "/api/v0/chat/completion"
            ),
        }

        resp = self._post(
            self.CHAT_COMPLETION_ENDPOINT,
            json    = body,
            headers = headers,
            stream  = True,
        )

        resp.raise_for_status()

        current_kind: Optional[ChunkKind] = None

        for line in resp.iter_lines(decode_unicode = True):
            if not line:
                continue

            if line.startswith("event: close"):
                return

            if not line.startswith("data:"):
                continue

            raw = line[5:].strip()

            if not raw:
                continue

            try:
                obj = json.loads(raw)

            except json.JSONDecodeError:
                continue

            v = obj.get("v")
            p = obj.get("p")
            o = obj.get("o")

            # Response metadata payload that may already contain fragments.
            if isinstance(v, dict):
                response = v.get("response", {})
                mid      = response.get("message_id")

                if mid is not None:
                    self._last_message_id = mid

                fragments = response.get("fragments", [])

                for fragment in fragments:
                    kind    = self._normalize_fragment_type(fragment.get("type"))
                    content = fragment.get("content") or ""

                    if kind:
                        current_kind = kind

                        if content:
                            yield kind, content

                continue

            # A whole fragment object was appended.
            if p == "response/fragments" and o == "APPEND" and isinstance(v, list):
                for fragment in v:
                    kind    = self._normalize_fragment_type(fragment.get("type"))
                    content = fragment.get("content") or ""

                    if kind:
                        current_kind = kind

                        if content:
                            yield kind, content

                continue

            # Content appended to the latest fragment.
            if p == "response/fragments/-1/content" and isinstance(v, str):
                if current_kind is not None:
                    yield current_kind, v

                continue

            # Plain token chunk like: {"v":" ..."}
            if isinstance(v, str) and "p" not in obj and "o" not in obj:
                if current_kind is not None:
                    yield current_kind, v

                continue

    def _respond_stream(
        self,
        prompt: str,
        thinking: bool = True,
        search: bool = True,
        ref_file_ids: Optional[Sequence[str]] = None,
    ) -> Generator[str, None, None]:
        """
        Internal flat streaming generator.

        Thinking content is wrapped in <think>...</think> tags, while final
        response content is yielded as plain text.

        Args:
            prompt:
                The user prompt to send.

            thinking:
                Whether the model's thinking stream should be enabled.

            search:
                Whether search should be enabled for this request.

        Yields:
            Text chunks in the order they are received from the stream.
        """

        active_kind: Optional[ChunkKind] = None

        for kind, chunk in self.respond_structured(
            prompt   = prompt,
            thinking = thinking,
            search   = search,
            ref_file_ids = ref_file_ids,
        ):
            if kind != active_kind:
                if active_kind == "think":
                    yield "</think>"

                if kind == "think":
                    yield "<think>"

                active_kind = kind

            yield chunk

        if active_kind == "think":
            yield "</think>"

    def respond(
        self,
        prompt: str,
        thinking: bool = True,
        search: bool = True,
        stream: bool = True,
        files: Optional[Sequence[str | Path]] = None,
        file_ids: Optional[Sequence[str]] = None,
    ) -> str | Generator[str, None, None]:
        """
        Send a prompt and return either a stream or the full response.

        Args:
            prompt:
                The user prompt to send.

            thinking:
                Whether the model's thinking stream should be enabled.

            search:
                Whether search should be enabled for this request.

            stream:
                If True, returns a generator of text chunks.
                If False, returns the full response as a single string.

        Returns:
            Either:
                - a `Generator[str, None, None]` when `stream=True`
                - a `str` when `stream=False`
        """

        resolved_file_ids = list(file_ids or ())
        if files:
            if self.model_type != "vision":
                raise ValueError("File attachments are supported only by the vision model.")
            resolved_file_ids.extend(self.upload_file(path).id for path in files)

        if stream:
            return self._respond_stream(
                prompt   = prompt,
                thinking = thinking,
                search   = search,
                ref_file_ids = resolved_file_ids,
            )

        return "".join(
            self._respond_stream(
                prompt   = prompt,
                thinking = thinking,
                search   = search,
                ref_file_ids = resolved_file_ids,
            )
        )

    def upload_file(self, path: str | Path, *, timeout: float = 60.0):
        """Upload and process a file for use by this vision session."""

        if self.model_type != "vision":
            raise ValueError("File attachments are supported only by the vision model.")
        return self._client.files.upload_and_wait(
            path,
            model=self.model_type,
            timeout=timeout,
        )

    def respond_with_tools(
        self,
        prompt: str,
        tools: Sequence[Tool],
        *,
        functions: Optional[Mapping[str, Callable[..., object]]] = None,
        thinking: bool = True,
        max_tool_rounds: int = 4,
    ) -> ToolResponse:
        """Ask for tool calls and optionally execute them until a final answer."""

        if not tools:
            raise ValueError("At least one tool definition is required.")
        if max_tool_rounds < 1:
            raise ValueError("max_tool_rounds must be at least 1.")

        known_names = {tool.name for tool in tools}
        message = build_tool_prompt(prompt, tools)
        call_history: list[ToolCall] = []

        for _ in range(max_tool_rounds):
            response = "".join(
                chunk
                for kind, chunk in self.respond_structured(
                    message,
                    thinking=thinking,
                    search=False,
                )
                if kind == "response"
            )
            calls = parse_tool_calls(response)
            if not calls:
                return ToolResponse(content=response, tool_calls=tuple(call_history))
            if len(calls) != 1:
                raise ValueError("The model must return exactly one tool call per turn.")

            call = calls[0]
            if call.name not in known_names:
                raise ValueError(f"Model requested an unknown tool: {call.name}")
            call_history.append(call)
            if functions is None:
                return ToolResponse(content="", tool_calls=tuple(call_history))

            result = execute_tool_call(call, functions)
            message = build_tool_result(call, result)

        raise RuntimeError(f"Tool-call loop exceeded {max_tool_rounds} rounds.")
