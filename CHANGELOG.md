# Changelog

All notable changes to DeepWrap are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[0.2.2]: https://github.com/Kuduxaaa/deepwrap/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/Kuduxaaa/deepwrap/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Kuduxaaa/deepwrap/compare/v0.1.3...v0.2.0
