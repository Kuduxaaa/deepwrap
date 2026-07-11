# Changelog

All notable changes to DeepWrap are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.2.1]: https://github.com/Kuduxaaa/deepwrap/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Kuduxaaa/deepwrap/compare/v0.1.3...v0.2.0
