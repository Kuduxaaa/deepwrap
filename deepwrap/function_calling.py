from __future__ import annotations

import json
import re

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence


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
class ToolResponse:
    content: str
    tool_calls: tuple[ToolCall, ...] = ()


def build_tool_prompt(prompt: str, tools: Sequence[Tool]) -> str:
    """Create the synthetic system protocol prepended to a user message."""

    definitions = json.dumps(
        [tool.as_dict() for tool in tools], ensure_ascii=False, separators=(",", ":")
    )
    return (
        "[DEEPWRAP SYSTEM TOOL PROTOCOL]\n"
        "You have access to the tools listed below. If a tool is required, reply "
        "with exactly one call and no other text:\n"
        '<deepwrap_tool_call>{"name":"tool_name","arguments":{}}</deepwrap_tool_call>\n'
        "Arguments must be valid JSON and conform to the tool's parameters schema. "
        "Never invent a tool. If no tool is required, answer the user normally and "
        "do not emit a tool-call tag.\n"
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
