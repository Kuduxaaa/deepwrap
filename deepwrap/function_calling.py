from __future__ import annotations

import json
import re

from dataclasses import dataclass
from typing import Any, Callable, Iterator, Mapping, Optional, Sequence


TOOL_CALL_PATTERN = re.compile(
    r"<deepwrap_tool_call>\s*(\{.*?\})\s*</deepwrap_tool_call>", re.DOTALL
)

# Backends occasionally ignore the DeepWrap envelope and fall back to their own
# native tool markup, such as `<|DSML| invoke name="exec">`. The tag prefix is
# sanitized differently depending on the transport, so only the tag word, the
# name attribute, and the matching close tag are matched.
NATIVE_INVOKE_PATTERN = re.compile(
    r"<[^<>]{0,40}?invoke\s+name\s*=\s*[\"']([\w.\-]+)[\"'][^<>]{0,60}?>"
    r"(.*?)"
    r"</[^<>]{0,40}?invoke\s*>",
    re.DOTALL | re.IGNORECASE,
)
NATIVE_PARAMETER_PATTERN = re.compile(
    r"<[^<>]{0,40}?parameter\s+name\s*=\s*[\"']([\w.\-]+)[\"'][^<>]{0,80}?>"
    r"(.*?)"
    r"</[^<>]{0,40}?parameter\s*>",
    re.DOTALL | re.IGNORECASE,
)
NATIVE_CALLS_WRAPPER_PATTERN = re.compile(
    r"</?[^<>]{0,40}?(?:tool[_\s▁-]*)?calls?\s*>", re.IGNORECASE
)

# Last-resort format: a lone JSON object, optionally fenced, that describes one
# call. Only accepted when it is the entire message, so JSON discussed inside a
# normal answer is never executed.
LONE_JSON_PATTERN = re.compile(r"\A(?:```(?:json)?\s*)?(\{.*\})\s*(?:```)?\Z", re.DOTALL)

TOOL_MARKUP_HINT_PATTERN = re.compile(
    r"<\s*/?\s*(?:deepwrap_tool_call|[^<>]{0,40}?(?:invoke|parameter)\s+name\s*=)"
    r"|<[^<>]{0,20}?(?:DSML|tool[_\s▁-]*calls?)[^<>]{0,20}?>",
    re.IGNORECASE,
)

TOOL_PROTOCOL_HEADER = "[DEEPWRAP TOOLS]"


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


def build_tool_prompt(
    prompt: str,
    tools: Sequence[Tool],
    *,
    environment: Optional[str] = None,
) -> str:
    """Create the synthetic tool protocol prepended to the first user message."""

    definitions = json.dumps(
        [tool.as_dict() for tool in tools], ensure_ascii=False, separators=(",", ":")
    )
    environment_line = f"ENV: {environment}\n" if environment else ""
    return (
        f"{TOOL_PROTOCOL_HEADER}\n"
        "To use a tool, reply with envelopes only, nothing before or after, one per call:\n"
        '<deepwrap_tool_call>{"name":"tool","arguments":{}}</deepwrap_tool_call>\n'
        "Arguments must be valid JSON for that tool's schema. Never use another "
        "call syntax and never invent a tool.\n"
        "Rules:\n"
        "1. Act with tools instead of describing or claiming actions; keep working "
        "through tool results until the task is done, recovering from errors yourself.\n"
        "2. Locate with grep first, then read in offset/limit chunks, following "
        "has_more and next_offset. Never read whole large files when a targeted "
        "search is enough.\n"
        "3. After write_file, edit_file, exec, or exec_code, verify with a read, "
        "grep, or command before claiming success.\n"
        "4. Never invent paths, command output, file contents, or finished work. "
        "Separate what you verified from what you infer.\n"
        "5. Use start_job for long-running or explicitly backgrounded commands, "
        "then job_status and job_output; stop_job only on request.\n"
        "6. Use inspect_image for local image paths, never read_file.\n"
        "7. Ask before starting, restarting, replacing, or stopping a job, and "
        "before retrying a failed command with changed arguments. A short "
        "acknowledgement is not permission.\n"
        "8. Repeat a failed approach at most twice, then change strategy or ask.\n"
        "9. For work that needs more than about three tool calls, call set_plan "
        "first with 3 to 7 concrete steps, then update_plan the moment a step "
        "is done or blocked. Follow the plan instead of improvising.\n"
        "10. Answer in the user's language, briefly, with no preamble and no "
        "restating of the tool work.\n"
        f"{environment_line}"
        f"TOOLS={definitions}\n\n"
        f"USER MESSAGE:\n{prompt}"
    )


def build_tool_reminder(prompt: str, tools: Sequence[Tool]) -> str:
    """Create the cheap follow-up header for later messages in a session."""

    names = ",".join(tool.name for tool in tools)
    return (
        f"{TOOL_PROTOCOL_HEADER} active. Same envelope syntax and rules as before.\n"
        f"TOOLS={names}\n\n"
        f"USER MESSAGE:\n{prompt}"
    )


def _coerce_value(raw: str) -> Any:
    text = raw.strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return text


def _parse_envelopes(text: str) -> Iterator[ToolCall]:
    for match in TOOL_CALL_PATTERN.finditer(text):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Model returned invalid tool-call JSON: {exc}") from exc
        yield _call_from_payload(payload)


def _call_from_payload(payload: Any) -> ToolCall:
    if not isinstance(payload, dict):
        raise ValueError("Tool call payload must be a JSON object.")
    name = payload.get("name")
    arguments = payload.get("arguments", {})
    if not isinstance(name, str) or not name:
        raise ValueError("Tool call must contain a non-empty string 'name'.")
    if not isinstance(arguments, dict):
        raise ValueError("Tool call 'arguments' must be a JSON object.")
    return ToolCall(name=name, arguments=arguments)


def _parse_native_markup(text: str) -> Iterator[ToolCall]:
    for match in NATIVE_INVOKE_PATTERN.finditer(text):
        name = match.group(1)
        body = match.group(2)
        arguments: dict[str, Any] = {}
        malformed = False
        for item in NATIVE_PARAMETER_PATTERN.finditer(body):
            key = item.group(1)
            value = _coerce_value(item.group(2))
            if key == "arguments":
                # The whole payload arrives as one JSON blob. A blob that does
                # not parse is skipped instead of executed with wrong arguments.
                if not isinstance(value, dict):
                    malformed = True
                    break
                arguments.update(value)
            else:
                arguments[key] = value
        if malformed:
            continue
        yield ToolCall(name=name, arguments=arguments)


def _parse_lone_json(
    text: str, known_names: Optional[Sequence[str]]
) -> Iterator[ToolCall]:
    match = LONE_JSON_PATTERN.match(text.strip())
    if match is None:
        return
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return
    if not isinstance(payload, dict) or "name" not in payload:
        return
    try:
        call = _call_from_payload(payload)
    except ValueError:
        return
    if known_names is not None and call.name not in set(known_names):
        return
    yield call


def parse_tool_calls(
    text: str, known_names: Optional[Sequence[str]] = None
) -> tuple[ToolCall, ...]:
    """Parse tool calls from model output, tolerating native markup fallbacks."""

    calls = list(_parse_envelopes(text))
    calls.extend(_parse_native_markup(text))
    if not calls:
        calls.extend(_parse_lone_json(text, known_names))
    return tuple(calls)


def looks_like_tool_call(text: str) -> bool:
    """Report whether the text contains any recognized tool-call markup."""

    return TOOL_MARKUP_HINT_PATTERN.search(text) is not None


def strip_tool_markup(text: str) -> str:
    """Remove tool-call markup that leaked into a user-facing answer."""

    cleaned = TOOL_CALL_PATTERN.sub("", text)
    cleaned = NATIVE_INVOKE_PATTERN.sub("", cleaned)
    cleaned = NATIVE_CALLS_WRAPPER_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


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
    return f"[TOOL RESULT] {call.name}\n{encoded}"


def build_loop_warning(call: ToolCall, repeats: int) -> str:
    """Warn the model that it is repeating itself instead of making progress."""

    return (
        f"[DEEPWRAP NOTICE] You issued the same tool call ({call.name}) "
        f"{repeats} times with identical arguments. Stop repeating it: change "
        "approach, or answer the user with what you already know."
    )


def build_progress_recap(
    task: str,
    plan: str,
    executions: Sequence[ToolExecution],
    recent: int = 6,
) -> str:
    """Restate the task, the plan, and the latest results near the context end.

    Tool results push the original request further and further back in the
    conversation. A model that can no longer see the request starts inventing
    one, so it is replayed, cheaply, as the loop goes on.
    """

    lines = [
        "[DEEPWRAP PROGRESS]",
        f"TASK: {task.strip()[:400]}",
    ]
    if plan:
        lines.append("PLAN:")
        lines.append(plan)
    tail = list(executions)[-recent:]
    if tail:
        lines.append("RECENT TOOL CALLS:")
        for execution in tail:
            failed = isinstance(execution.output, dict) and (
                execution.output.get("ok") is False
                or execution.output.get("error")
                or execution.output.get("exit_code") not in (0, None)
            )
            lines.append(f"- {execution.name}: {'FAILED' if failed else 'ok'}")
    lines.append(
        "Continue from here. Do not repeat finished steps, and do not restart "
        "the task."
    )
    return "\n".join(lines)


def build_malformed_call_notice(detail: Optional[str] = None) -> str:
    """Tell the model its tool markup could not be parsed, and how to fix it."""

    reason = f" ({detail})" if detail else ""
    return (
        f"[DEEPWRAP NOTICE] Your last message looked like a tool call but could "
        f"not be parsed{reason}. Nothing was executed and the user saw nothing. "
        "Reissue it using exactly this syntax, with no other text:\n"
        '<deepwrap_tool_call>{"name":"tool","arguments":{}}</deepwrap_tool_call>'
    )


def build_final_answer_request(rounds: int) -> str:
    """Ask the model to finish without further tool calls."""

    return (
        f"[DEEPWRAP NOTICE] The tool-round limit ({rounds}) was reached. Do not "
        "call any more tools. Answer the user now with what you have, and state "
        "clearly what is still unfinished."
    )
