import json
import time

from pathlib import Path
from typing import Callable, Generator, Literal, Mapping, Optional, Sequence

from .base import BaseAPI
from deepwrap.config import Config
from deepwrap.function_calling import (
    AgentResponse,
    AgentStream,
    AgentEvent,
    Tool,
    ToolCall,
    ToolResponse,
    ToolExecution,
    build_tool_prompt,
    build_tool_result,
    execute_tool_call,
    parse_tool_calls,
)


ChunkKind = Literal["think", "response"]
AGENT_STREAM_DECISION_CHARS = 4096


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
        self.memory_session_id      = client._claim_memory_session(model_type)

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

        headers_dict = getattr(resp, "headers", {})
        content_type = headers_dict.get("content-type", "")
        if "json" in content_type:
            try:
                err_data = resp.json()
                code = err_data.get("code")
                msg = err_data.get("msg") or err_data.get("message")
                if code is not None or msg is not None:
                    raise RuntimeError(f"API Error (code={code}): {msg}")
            except Exception as exc:
                if isinstance(exc, RuntimeError):
                    raise

        current_kind: Optional[ChunkKind] = None
        first_line_checked = False

        for line in resp.iter_lines(decode_unicode = True):
            if not line:
                continue

            if not first_line_checked:
                first_line_checked = True
                if not line.startswith("data:") and not line.startswith("event:"):
                    try:
                        obj = json.loads(line)
                        code = obj.get("code")
                        msg = obj.get("msg") or obj.get("message")
                        if code is not None or msg is not None:
                            raise RuntimeError(f"API Error (code={code}): {msg}")
                    except json.JSONDecodeError:
                        pass

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
        agent: Optional[bool] = None,
        on_event: Optional[Callable[[AgentEvent], None]] = None,
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

        agent_enabled = self._client.agent_mode if agent is None else agent
        if agent_enabled:
            agent_stream = self._agent_stream(
                prompt,
                thinking=thinking,
                search=search,
                ref_file_ids=resolved_file_ids,
                on_event=on_event,
            )
            if stream:
                return agent_stream
            content = "".join(agent_stream)
            return AgentResponse(
                content,
                agent_stream.tools_used,
                agent_stream.events,
            )

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

    def _agent_stream(
        self,
        prompt: str,
        *,
        thinking: bool,
        search: bool,
        ref_file_ids: Sequence[str],
        on_event: Optional[Callable[[AgentEvent], None]],
    ) -> AgentStream:
        """Run native tools and stream the final non-tool response incrementally."""

        tools = self._client.agent_tools
        functions = self._client.agent_functions
        known_names = {tool.name for tool in tools}
        tools_used: list[ToolExecution] = []
        events: list[AgentEvent] = []
        started_at = time.monotonic()

        def emit(event: AgentEvent) -> None:
            events.append(event)
            if on_event is not None:
                try:
                    on_event(event)
                except Exception as exc:
                    import sys
                    print(f"Error in agent event handler: {exc}", file=sys.stderr)


        def generate() -> Generator[str, None, None]:
            emit(AgentEvent("started", "Agent started; preparing the task."))
            memory_context = self._client.memory_context(
                prompt,
                self.memory_session_id,
            )
            memory_prefix = f"{memory_context}\n\n" if memory_context else ""
            message = build_tool_prompt(memory_prefix + prompt, tools)
            for round_index in range(self._client.max_agent_rounds):
                emit(
                    AgentEvent(
                        "planning",
                        f"Planning agent step {round_index + 1}.",
                    )
                )
                response = ""
                is_final = False
                for kind, chunk in self.respond_structured(
                    message,
                    thinking=thinking,
                    search=search,
                    ref_file_ids=ref_file_ids if round_index == 0 else None,
                ):
                    if kind == "think":
                        if thinking:
                            emit(AgentEvent("thinking", chunk))
                        continue
                    if kind != "response":
                        continue
                    response += chunk
                    if (
                        not is_final
                        and len(response) >= AGENT_STREAM_DECISION_CHARS
                        and "<deepwrap_tool_call>" not in response
                    ):
                        is_final = True
                        emit(AgentEvent("responding", "Streaming the final response."))
                        yield response
                    elif is_final:
                        yield chunk

                if not response.strip():
                    emit(AgentEvent("completed", "Agent completed with an empty response."))
                    return

                calls = parse_tool_calls(response)
                if is_final:
                    if self._client.memory is not None and self.memory_session_id:
                        self._client.memory.add_turn(self.memory_session_id, "user", prompt)
                        self._client.memory.add_turn(self.memory_session_id, "assistant", response)
                    emit(
                        AgentEvent(
                            "completed",
                            "Agent completed the task.",
                            duration_seconds=time.monotonic() - started_at,
                        )
                    )
                    return
                if not calls:
                    emit(AgentEvent("responding", "Streaming the final response."))
                    yield response
                    if self._client.memory is not None and self.memory_session_id:
                        self._client.memory.add_turn(self.memory_session_id, "user", prompt)
                        self._client.memory.add_turn(self.memory_session_id, "assistant", response)
                    emit(
                        AgentEvent(
                            "completed",
                            "Agent completed the task.",
                            duration_seconds=time.monotonic() - started_at,
                        )
                    )
                    return

                result_messages: list[str] = []
                for call in calls:
                    tool_started_at = time.monotonic()
                    emit(
                        AgentEvent(
                            "tool_started",
                            f"Running {call.name}.",
                            tool_name=call.name,
                            arguments=dict(call.arguments),
                        )
                    )
                    if call.name not in known_names:
                        output = {"ok": False, "error": f"Unknown tool: {call.name}"}
                    else:
                        try:
                            output = execute_tool_call(call, functions)
                        except Exception as exc:
                            output = {
                                "ok": False,
                                "error": f"{type(exc).__name__}: {exc}",
                            }
                    tools_used.append(
                        ToolExecution(call.name, dict(call.arguments), output)
                    )
                    emit(
                        AgentEvent(
                            "tool_completed",
                            f"Finished {call.name}.",
                            tool_name=call.name,
                            arguments=dict(call.arguments),
                            output=output,
                            duration_seconds=time.monotonic() - tool_started_at,
                        )
                    )
                    result_messages.append(build_tool_result(call, output))
                message = "\n\n".join(result_messages)

            raise RuntimeError(
                f"Tool-call loop exceeded {self._client.max_agent_rounds} rounds."
            )

        return AgentStream(generate(), tools_used, events)

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
        search: bool = False,
        ref_file_ids: Optional[Sequence[str]] = None,
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
        execution_history: list[ToolExecution] = []

        for _ in range(max_tool_rounds):
            response = "".join(
                chunk
                for kind, chunk in self.respond_structured(
                    message,
                    thinking=thinking,
                    search=search,
                    ref_file_ids=ref_file_ids if not call_history else None,
                )
                if kind == "response"
            )
            calls = parse_tool_calls(response)
            if not calls:
                return ToolResponse(
                    content=response,
                    tool_calls=tuple(call_history),
                    tools_used=tuple(execution_history),
                )
            call_history.extend(calls)
            if functions is None:
                return ToolResponse(content="", tool_calls=tuple(call_history))

            result_messages: list[str] = []
            for call in calls:
                if call.name not in known_names:
                    result = {
                        "ok": False,
                        "error": f"Unknown tool: {call.name}",
                    }
                else:
                    try:
                        result = execute_tool_call(call, functions)
                    except Exception as exc:
                        result = {
                            "ok": False,
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                result_messages.append(build_tool_result(call, result))
                execution_history.append(
                    ToolExecution(call.name, dict(call.arguments), result)
                )
            message = "\n\n".join(result_messages)

        raise RuntimeError(f"Tool-call loop exceeded {max_tool_rounds} rounds.")
