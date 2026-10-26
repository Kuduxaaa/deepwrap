# Changelog

All notable changes to DeepWrap are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Tolerant tool-call parsing: native backend markup and a lone JSON call object
  are executed instead of being printed to the user as raw text.
- Automatic recovery round when tool markup cannot be parsed, with the correct
  syntax sent back to the model.
- Streaming markup guard, so a turn that switches to tool markup mid-answer is
  never partially printed.
- Loop detection that tells the model when it repeats an identical tool call,
  and makes it answer after six identical calls so unlimited rounds still
  terminate.
- A two-attempt cap on tool-syntax recovery, after which the message is treated
  as the answer.
- `limit_reached` and `recovering` agent events.
- Host environment line (OS, shell, working directory, path style) in the tool
  protocol, and translation of shell-style drive paths such as `/c/Users` on
  Windows.
- `MemoryStore.close()`, `Client.close()`, and context-manager support for both.
- Task plans: `set_plan`, `update_plan`, and `get_plan` tools, rendered as a
  checklist in the CLI and replayed in every progress recap.
- Progress recaps every fourth tool round, restating the request, the plan, and
  the latest tool outcomes so a long loop cannot drift off the task.
- A per-result context budget: tool output over `output_budget` characters
  (8000 by default) is written to a file in full and passed to the model as its
  head and tail with a pointer, instead of spending the whole context window.
- Shell resolution that prefers a POSIX shell, including Git Bash on Windows,
  skips the WSL `bash` in `System32`, and is overridable with `shell=` or
  `DEEPWRAP_SHELL`. `exec` reports which shell ran the command.
- `Client(shell=..., output_budget=...)`.
- `ThinkingView` in the CLI, plus tests for panel height and Markdown flushing.

### Changed

- `max_agent_rounds` now defaults to `None`, meaning unlimited tool rounds.
  Reaching an explicit limit asks the model for a final answer instead of
  raising `RuntimeError`.
- Agent requests send the full tool protocol and schemas once per session, or
  again when the registered tools change, and a 192-character reminder
  afterwards. Later messages shrink from 5621 to 192 characters, the first
  message from 5621 to 4514, and each tool result from 229 to 85.
- The tool protocol and tool-result envelopes were rewritten to be denser.
- God Mode is now Direct Mode: a response-style directive for terse,
  high-density expert answers. The previous override prompt, which asked the
  model to ignore its safety guidelines, was removed. The `god_mode` flag name
  is unchanged.
- The CLI thinking panel renders only the lines that fit the terminal, so long
  thinking stays visible instead of freezing at the top until generation ends.
- Long Markdown blocks are flushed at a line break instead of waiting for the
  blank line that ends them. Lists, tables, headings, and quotes are untouched.
- Failed tools are shown with a red mark in the CLI instead of a green check.
- `grep` reports paths relative to the working directory, POSIX style, on every
  platform.
- Memory queries break ties by insertion order, making results deterministic.
- `job_output` defaults to the context budget instead of 50000 characters.
- The CLI prints `limit_reached`, `recovering`, and `recap` notices instead of
  silently dropping them once the spinner has stopped.

### Fixed

- Raw `DSML` tool markup leaking into the terminal as the final answer.
- Generation aborting with `Tool-call loop exceeded 8 rounds.` part-way through
  a task.
- Long thinking and long answers staying invisible until generation finished on
  short terminals.
- `write_file` and the other file tools resolving POSIX paths from shell output
  to the wrong Windows location.
- SQLite handles kept open by `MemoryStore`, which blocked temporary directory
  cleanup on Windows.
- A single large tool result filling the context window and making the agent
  lose the task it was given.
- POSIX commands being sent to `cmd.exe` on Windows, which wasted a tool round
  on every attempt.

## [0.2.3]

### Added

- Default integrated agent mode with autonomous multi-round native tool usage.
- Built-in `exec`, `grep`, `read_file`, `write_file`, `edit_file`, and
  `exec_code` tools.
- Configurable agent working directory, command timeout, and maximum tool rounds.
- Agent controls for the Python SDK, interactive CLI, and local HTTP API.
- Native agent examples and tests for command, Python, search, and filesystem tools.
- A 20-case agent acceptance suite covering streaming, telemetry, multi-call
  execution, error recovery, round limits, plain-mode fallback, and all native tools.
- Live agent progress events for planning, tool execution, final response, and
  completion, available through callbacks and `response.events`.
- Always-on agent behavior in the interactive CLI, plus paginated recursive
  search and file reading for large-project analysis.
- Concurrent process-backed background jobs with lifecycle management and
  paginated file-backed stdout/stderr logs.
- Block-aware streaming Markdown rendering and persistent, concise tool progress
  in the interactive CLI.
- Application-specific tool registration and natural-language equivalents for
  all CLI slash-command capabilities.
- Automatic local-image inspection through dedicated vision sessions without a
  manual model switch or attachment step.

### Fixed

- Agent turns can now emit and execute multiple tool calls instead of failing
  when the model requests more than one operation at once.
- Agent final answers now stream incrementally and expose structured tool
  execution telemetry through `response.tools_used`.
- Narration before a tool envelope no longer leaks raw tool-call markup into the
  final response, and Python fallback globs now search subdirectories recursively.
- Agent instructions now require post-action verification and clear separation
  between verified observations and inferences.
- Agent-mode thinking is now surfaced in the CLI when thinking display is enabled.
- God Mode toggles preserve the current conversation instead of silently replacing
  it, and natural-language chat clearing resets both display and session.
- Background acknowledgements no longer authorize automatic job restarts; failed
  jobs must be reported and explicitly retried with validated arguments.
- The tool-call decision buffer now tolerates longer model narration without
  leaking raw tool envelopes into CLI output.

## [0.2.3] - 2026-07-11

### Added

- Long-term memory query to fetch and inject the last 20 memories with an importance score of 0.9 or greater on the initial session load.
- Unit tests covering priority memory loading, SQLite count checks, and client-level context integration.

### Changed

- Compressed thinking panel card layout in the CLI by removing all vertical/horizontal extra margin padding (`padding=(0, 0)`).

## [0.2.2] - 2026-07-11

### Added

- Streamed reasoning (thinking) blocks in the interactive CLI are now rendered inside full-width, borderless card-like panels with `on #1e293b` background and tight padding.

### Changed

- Disabled R1 thinking display by default in configuration preferences.
- Modified SDK calls in the CLI to dynamically request thinking only when `show_thinking` is enabled.
- Simplified CLI boot banner layout by removing the status summary details line from `_render_intro`.

### Fixed

- Prevented rate-limits and server errors returning as JSON payloads from being swallowed by raising descriptive `RuntimeError` exceptions.
- Resolved coordinate-drift and console-clearing issues with the Rich Live spinner, keeping final streamed thinking histories permanently in terminal scrollback buffers.

## [0.2.1] - 2026-07-11

### Fixed

- Vision uploads now treat `PARSING` and other non-terminal server states as
  in-progress instead of failing before processing reaches `SUCCESS`.

## [0.2.0] - 2026-07-11

### Added

- Vision file uploads based on DeepSeek's multipart upload and proof-of-work flow.
- File processing status polling and reusable uploaded file IDs.
- Python SDK support for `files` and `file_ids` in vision prompts.
- Interactive CLI commands `/attach`, `/attachments`, and `/detach`.
- Pseudo function calling with JSON-schema-style tool definitions.
- Strict `<deepwrap_tool_call>` response protocol, parsing, and validation.
- Optional automatic function execution and multi-turn tool-result handling.
- Tool and vision support in the local FastAPI interface.
- Runnable vision and function-calling examples.
- Unit coverage for model search rules, vision uploads, and function calling.

### Changed

- Web search is now sent only for the `default` (Instant) model.
- Expert and vision requests always disable `search_enabled`.
- CLI responses are rendered incrementally to preserve terminal scrolling and
  scrollback for long streamed responses.
- Documentation now covers vision uploads, model search behavior, and function
  calling.

[0.2.3]: https://github.com/Kuduxaaa/deepwrap/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/Kuduxaaa/deepwrap/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/Kuduxaaa/deepwrap/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Kuduxaaa/deepwrap/compare/v0.1.3...v0.2.0
