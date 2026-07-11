from __future__ import annotations

import json
import re

from dataclasses import dataclass
from typing import Any, Callable, Iterator, Mapping, Sequence


TOOL_CALL_PATTERN = re.compile(
    r"<deepwrap_tool_call>\s*(\{.*?\})\s*</deepwrap_tool_call>", re.DOTALL
)


@dataclass(frozen=True)
class Tool:
    """Description of a callable function exposed to the model."""

    name: str
    description: str
    parameters: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolExecution:
    name: str
    arguments: dict[str, Any]
    output: Any


@dataclass(frozen=True)
class AgentEvent:
    type: str
    message: str
    tool_name: str | None = None
    arguments: dict[str, Any] | None = None
    output: Any = None
    duration_seconds: float | None = None


@dataclass(frozen=True)
class ToolResponse:
    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    tools_used: tuple[ToolExecution, ...] = ()


class AgentResponse(str):
    """String-compatible final response with agent execution telemetry."""

    tools_used: list[ToolExecution]
    events: list[AgentEvent]

    def __new__(
        cls,
        content: str,
        tools_used: Sequence[ToolExecution] = (),
        events: Sequence[AgentEvent] = (),
    ) -> "AgentResponse":
        instance = super().__new__(cls, content)
        instance.tools_used = list(tools_used)
        instance.events = list(events)
        return instance


class AgentStream(Iterator[str]):
    """Streaming agent response whose telemetry fills as it is consumed."""

    def __init__(
        self,
        iterator: Iterator[str],
        tools_used: list[ToolExecution],
        events: list[AgentEvent],
    ) -> None:
        self._iterator = iterator
        self.tools_used = tools_used
        self.events = events

    def __iter__(self) -> "AgentStream":
        return self

    def __next__(self) -> str:
        return next(self._iterator)


def build_tool_prompt(prompt: str, tools: Sequence[Tool]) -> str:
    """Create the synthetic system protocol prepended to a user message."""

    definitions = json.dumps(
        [tool.as_dict() for tool in tools], ensure_ascii=False, separators=(",", ":")
    )
    return (
        "[DEEPWRAP SYSTEM TOOL PROTOCOL]\n"
        "You have access to the tools listed below. If tools are required, the "
        "FIRST character of your response must be '<' from the tool envelope. "
        "Do not explain, narrate, announce, or summarize before or after tool calls. "
        "Reply with one or more calls and no other text. Emit a separate envelope "
        "for each call:\n"
        '<deepwrap_tool_call>{"name":"tool_name","arguments":{}}</deepwrap_tool_call>\n'
        "Arguments must be valid JSON and conform to the tool's parameters schema. "
        "Never invent a tool. If no tool is required, answer the user normally and "
        "do not emit a tool-call tag. Work autonomously: inspect relevant context, "
        "use tools for actions instead of claiming they were performed, continue "
        "through as many tool-result turns as needed, recover from tool errors when "
        "possible, and return a concise final answer only when the task is complete. "
        "For large projects, search broadly with grep first, narrow the relevant "
        "files, then read them in bounded chunks using offset/limit. Follow has_more "
        "and next_offset until enough evidence is collected. Avoid reading every "
        "large file in full when targeted search and pagination are sufficient. "
        "After write_file, edit_file, exec, or exec_code changes state, verify the "
        "result with an appropriate read, grep, or command before claiming success. "
        "Never invent paths, command results, file contents, or completed actions. "
        "Clearly distinguish verified observations from reasonable inferences.\n"
        "For commands expected to run for a long time, or when the user explicitly "
        "asks for background execution, use start_job instead of exec. Return the "
        "job ID and running state promptly; do not block or repeatedly poll unless "
        "the user asks you to wait. On later turns use job_status and job_output, "
        "following output pagination, and use stop_job only when requested. "
        "When an inspect_image tool is available and the user asks about a local "
        "image path, use inspect_image; do not use read_file on binary image data. "
        "A short acknowledgement such as okay, great, thanks, yes I know, or damn "
        "is not permission to start, restart, replace, or stop a job. Never retry a "
        "failed background command with changed arguments unless the user explicitly "
        "asks to retry or previously authorized automatic recovery. Report the exact "
        "failure and ask first. Before launching commands, validate paths, targets, "
        "and syntax from verified tool output; never silently truncate or invent IP "
        "addresses, host lists, filenames, or flags. Do not claim a command covers "
        "targets or options that are absent from the actual executed command.\n"
        f"TOOLS={definitions}\n"
        "[END DEEPWRAP SYSTEM TOOL PROTOCOL]\n\n"
        f"USER MESSAGE:\n{prompt}"
    )


def parse_tool_calls(text: str) -> tuple[ToolCall, ...]:
    """Parse and validate DeepWrap tool-call envelopes from model output."""

    calls: list[ToolCall] = []
    for match in TOOL_CALL_PATTERN.finditer(text):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Model returned invalid tool-call JSON: {exc}") from exc
        name = payload.get("name")
        arguments = payload.get("arguments", {})
        if not isinstance(name, str) or not name:
            raise ValueError("Tool call must contain a non-empty string 'name'.")
        if not isinstance(arguments, dict):
            raise ValueError("Tool call 'arguments' must be a JSON object.")
        calls.append(ToolCall(name=name, arguments=arguments))
    return tuple(calls)


def execute_tool_call(
    call: ToolCall, functions: Mapping[str, Callable[..., Any]]
) -> Any:
    """Execute a parsed call against an explicit name-to-callable mapping."""

    function = functions.get(call.name)
    if function is None:
        raise ValueError(f"No function registered for tool: {call.name}")
    return function(**call.arguments)


def build_tool_result(call: ToolCall, result: Any) -> str:
    """Serialize a tool result for the next model turn."""

    encoded = json.dumps(result, ensure_ascii=False, default=str)
    return (
        "[DEEPWRAP TOOL RESULT]\n"
        f"name={call.name}\n"
        f"result={encoded}\n"
        "Use this result to answer the original user request. Call another tool only "
        "if it is necessary.\n"
        "[END DEEPWRAP TOOL RESULT]"
    )
