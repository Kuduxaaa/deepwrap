# DeepWrap

[![PyPI](https://img.shields.io/pypi/v/deepwrap.svg)](https://pypi.org/project/deepwrap/)
[![Python](https://img.shields.io/pypi/pyversions/deepwrap.svg)](https://pypi.org/project/deepwrap/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Repository](https://img.shields.io/badge/GitHub-Kuduxaaa%2Fdeepwrap-black?logo=github)](https://github.com/Kuduxaaa/deepwrap)

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Authentication](#authentication)
  - [Direct Token](#direct-token)
  - [Environment Variable](#environment-variable)
  - [Browser Auth from Python](#browser-auth-from-python)
- [CLI Authentication](#cli-authentication)
- [Python SDK Usage](#python-sdk-usage)
  - [Basic Non-Streaming Chat](#basic-non-streaming-chat)
  - [Streaming Chat](#streaming-chat)
  - [Multi-Turn Chat](#multi-turn-chat)
  - [Agent Mode](#agent-mode)
  - [Vision File Uploads](#vision-file-uploads)
  - [Pseudo Function Calling](#pseudo-function-calling)
- [Supported Models](#supported-models)
- [Direct Mode](#direct-mode)
  - [Python SDK](#python-sdk)
- [CLI Usage](#cli-usage)
- [Interactive CLI Commands](#interactive-cli-commands)
- [Local FastAPI Server](#local-fastapi-server)
- [HTTP API](#http-api)
  - [Health Check](#health-check)
  - [One-Shot Chat Request](#one-shot-chat-request)
  - [Create Persistent Session](#create-persistent-session)
  - [Use Persistent Session](#use-persistent-session)
  - [Delete Session](#delete-session)
- [Streaming Over HTTP](#streaming-over-http)
  - [Plain Text Streaming](#plain-text-streaming)
  - [Server-Sent Events Streaming](#server-sent-events-streaming)
- [Environment Variables](#environment-variables)
- [API Design](#api-design)
- [Examples](#examples)
  - [Switch Models](#switch-models)
  - [Hide Thinking Output](#hide-thinking-output)
  - [Disable Search](#disable-search)
- [Error Handling](#error-handling)
- [Notes](#notes)
- [Security Notice](#security-notice)
- [Disclaimer](#disclaimer)
- [License](#license)

**DeepWrap** is a lightweight Python SDK, CLI, and local HTTP API wrapper for DeepSeek Chat with session support, browser authentication, streaming, and local developer tooling.

It provides:

- A simple Python client
- Session-based chat support
- Streaming and non-streaming chat responses
- Structured streaming with separated thinking and response chunks
- Browser-based authentication
- Local token storage and reuse
- Interactive terminal UI
- FastAPI server mode
- Internal proof-of-work handling
- Default autonomous agent mode with native command, code, search, and file tools

> Repository: [https://github.com/Kuduxaaa/deepwrap](https://github.com/Kuduxaaa/deepwrap)

---

## Installation

```bash
pip install deepwrap
```

Install directly from GitHub:

```bash
pip install git+https://github.com/Kuduxaaa/deepwrap.git
```

For local development:

```bash
git clone https://github.com/Kuduxaaa/deepwrap.git
cd deepwrap
pip install -e ".[dev]"
```

---

## Quick Start

Authenticate once:

```bash
deepwrap auth
```

Then use DeepWrap from Python:

```python
from deepwrap import Client

client = Client()
chat = client.chats.create_session(model="expert")

response = chat.respond(
    "Hello, introduce yourself in one sentence.",
    stream=False,
)

print(response)
```

Or start the interactive terminal UI:

```bash
deepwrap
```

---

## Authentication

DeepWrap uses a Bearer token.

Token resolution order:

1. Explicit `api_key`
2. `DEEPWRAP_API_KEY`
3. `DEEPSEEK_API_KEY`
4. Saved local config from `deepwrap auth`
5. Browser authentication only when explicitly requested with `Client.from_browser_auth()` or `allow_browser_auth=True`

`Client` is the main entrypoint for DeepWrap. It resolves bearer tokens from an explicit API key, environment variables, saved local config, or browser auth, then exposes session-based chat and PoW-backed request handling.

### Direct Token

```python
from deepwrap import Client

client = Client(api_key="YOUR_BEARER_TOKEN")
```

### Environment Variable

```bash
export DEEPWRAP_API_KEY="YOUR_BEARER_TOKEN"
```

DeepWrap also supports:

```bash
export DEEPSEEK_API_KEY="YOUR_BEARER_TOKEN"
```

Then:

```python
from deepwrap import Client

client = Client()
```

### Browser Auth from Python

DeepWrap supports browser-based authentication from Python. You can bootstrap a client with `Client.from_browser_auth()` or use `allow_browser_auth=True`, and the library will capture a bearer token from an authenticated browser session before creating the HTTP session.

```python
from deepwrap import Client

client = Client.from_browser_auth()
```

Equivalent:

```python
from deepwrap import Client

client = Client(allow_browser_auth=True)
```

---

## CLI Authentication

Authenticate using browser login:

```bash
deepwrap auth
```

Manually enter and save a token:

```bash
deepwrap auth --manual
```

Save a token directly:

```bash
deepwrap auth --token "YOUR_BEARER_TOKEN"
```

Show current config status:

```bash
deepwrap config
```

Remove the saved token:

```bash
deepwrap logout
```

---

## Python SDK Usage

### Basic Non-Streaming Chat

```python
from deepwrap import Client

client = Client()
chat = client.chats.create_session(model="expert")

response = chat.respond(
    "Explain quantum computing in one short sentence.",
    thinking=True,
    search=True,
    stream=False,
)

print(response)
```

---

### Streaming Chat

```python
from deepwrap import Client

client = Client()
chat = client.chats.create_session(model="expert")

for chunk in chat.respond(
    "Write a short explanation of black holes.",
    thinking=True,
    search=True,
    stream=True,
):
    print(chunk, end="", flush=True)

print()
```

---

### Multi-Turn Chat

```python
from deepwrap import Client

client = Client()
chat = client.chats.create_session(model="expert")

print(chat.respond("My name is Nika.", stream=False))
print(chat.respond("What is my name?", stream=False))
```

The `ChatSession` keeps track of the latest message ID internally, so follow-up messages stay inside the same conversation.

---

### Agent mode

Agent mode is enabled by default. It upgrades regular chat sessions with native
tools that the model can call repeatedly before returning its final answer:

- `exec` — execute a command with the host operating system's shell.
- `grep` — regex-search file contents with optional glob filters.
- `read_file` — read any text file.
- `write_file` — write complete content to a file.
- `edit_file` — perform guarded exact-string substitutions.
- `exec_code` — run Python code with access to installed modules.
- `start_job` — launch a long command in its own background process.
- `job_status` — check a background job without blocking.
- `job_output` — read paginated stdout or stderr while a job runs.
- `list_jobs` — list jobs owned by the current client.
- `stop_job` — terminate a job and its process group.
- `set_plan` — write down an ordered plan before multi-step work.
- `update_plan` — mark a step done, in progress, or blocked.
- `get_plan` — read the plan and how much of it is finished.

```python
from pathlib import Path

from deepwrap import Client

client = Client(
    working_directory=Path.cwd(),
    command_timeout=30,
    max_agent_rounds=None,  # None means no limit; an int caps the tool rounds
    output_budget=8_000,    # characters of one tool result the model may see
    shell=None,             # None auto-detects; "cmd.exe", "bash", "zsh", ...
)
chat = client.chats.create_session(model="expert")

result = chat.respond(
    "Find every Python file containing ChatSession and summarize its usage.",
    stream=False,
)
print(result)
for execution in result.tools_used:
    print(execution.name, execution.arguments, execution.output)
```

Streaming returns an `AgentStream`. Final-answer chunks arrive incrementally, and
the same execution history is available after or during consumption:

```python
response = chat.respond("Inspect this project.", stream=True)

for chunk in response:
    print(chunk, end="", flush=True)

for execution in response.tools_used:
    print(execution.name, execution.arguments, execution.output)
```

For immediate progress while the agent is planning or running tools, pass an
event callback:

```python
def show_progress(event):
    print(f"[{event.type}] {event.message}", flush=True)

response = chat.respond(
    "Build a complete landing page in one HTML file.",
    stream=True,
    on_event=show_progress,
)
```

Events include `started`, `planning`, `thinking`, `tool_started`, `tool_completed`,
`responding`, and `completed`. The history remains available as
`response.events`; tool events also include arguments, output, and duration.

#### Background jobs

Long-running commands can execute concurrently without blocking the agent response:

```python
response = chat.respond(
    "Start the crawler as a background job and return immediately.",
    stream=False,
)

job = next(
    execution.output
    for execution in response.tools_used
    if execution.name == "start_job"
)
print(job["id"], job["state"])

# A later turn in the same Client can inspect status and logs.
print(chat.respond("Check that job and show its latest output.", stream=False))
```

Each job has an independent process group and file-backed stdout/stderr logs.
`job_output` returns `next_offset`, allowing the agent to resume reading only new
output. Jobs remain available across chat turns while the same `Client` process is
alive. See `examples/15_background_jobs.py` for a complete example.

> Run network scanners and similar tools only against systems and networks you own
> or are explicitly authorized to assess.

Non-streaming `AgentResponse` remains a subclass of `str`, so existing string
handling continues to work. Each `tools_used` entry contains `name`, `arguments`,
and `output`.

Disable agent operations globally or for one request:

```python
client = Client(agent_mode=False)
plain_response = chat.respond("Hello", agent=False, stream=False)
```

The interactive CLI always starts directly in agent mode; no activation command
is required. The Python SDK and local HTTP API still accept an `agent` boolean
for applications that explicitly need plain-chat behavior.

#### Natural-language CLI actions

Every slash-command capability is also registered as an agent tool. Users can
control the CLI naturally without remembering command syntax:

```text
Please clear this chat and screen.
Start a new conversation.
Switch to the default model and enable search.
Hide thinking output.
Save my current settings.
Show the current status.
Exit DeepWrap.
```

Token changes schedule the secure hidden-input prompt; credentials are never
accepted as model-generated tool arguments. Direct slash commands remain available.

Local images are handled automatically through a dedicated vision session, even
when the current model is `expert`:

```text
What can you see in /home/user/Pictures/photo.jpg?
```

The CLI agent selects `inspect_image`, uploads the file to a temporary vision chat,
and feeds the visual analysis back into the current conversation. Manual
`/model vision` and `/attach` remain useful when several follow-up prompts should
reuse the same uploaded image.

Thinking output works in agent mode as well as plain mode. The live thinking
panel shows the newest lines when a thought is taller than the terminal, instead
of freezing at the top until generation ends. Enabling or disabling Direct Mode
updates the current session in place, so conversation and image context are
preserved.

For large repositories, `grep` and `read_file` return bounded pages with
`has_more` and `next_offset`. The agent protocol instructs the model to search
broadly, narrow relevant files, and follow pagination instead of flooding its
context with entire projects. `grep` reports paths relative to the working
directory with forward slashes on every platform.

#### Tool rounds

`max_agent_rounds` defaults to `None`, so the agent keeps calling tools until the
task is finished. Long refactors and multi-file investigations are no longer cut
off part-way with a `RuntimeError`.

Set an integer to cap the work. Reaching the cap is not an error either: the
agent is asked for a final answer with whatever it has, reports what is still
unfinished, and the round limit is announced through a `limit_reached` event.

A model that issues the same call with the same arguments three times in a row
is told it is looping and asked to change approach or answer. After six, it is
made to answer, so an unlimited loop still terminates without `Ctrl+C`.

#### Context budget

The agent's real limit is the context window, not the number of rounds. One
unbounded `exec` or `read_file` can push the task itself out of the window,
after which the model forgets what it was doing.

So every tool result is capped at `output_budget` characters (8000 by default).
Larger output is written to a file in full and handed to the model as its head
and tail with a pointer:

```json
{
  "stdout": "first 4800 characters\n[... 12013 of 20013 characters omitted. Full output: ... ]\nlast 3200 characters",
  "truncated": true,
  "stdout_full_path": "…/outputs/stdout-7f1dca9e.log",
  "stdout_total_chars": 20013
}
```

The tail is always kept, because that is where errors land, and the model can
page through the whole file with `read_file` when it needs more.

#### Progress recaps

Every fourth tool round, the agent is sent a compact recap: the original
request, the current plan, and the outcome of the last few tool calls. Without
it, a long loop pushes the request so far back that the model starts answering a
task it half-remembers. The CLI shows the recap as a dim notice.

#### Plans

For anything longer than about three tool calls, the model is asked to call
`set_plan` first and to keep it current with `update_plan`. The plan is tool
state, not prose, so it survives in the recap and is rendered as a checklist in
the CLI:

```text
  plan (1/3)
    ✓ Locate the parser entry point
    ▸ Add the fallback branch
    ○ Run the test suite
```

#### Shell

Models write POSIX commands by default, so every `ls -la` sent to `cmd.exe`
costs a round and a step of context drift. DeepWrap therefore prefers a POSIX
shell when one exists, including Git Bash on Windows, and never picks the WSL
`bash` in `System32`, which would run in a different filesystem.

Set `shell=` on the client or `DEEPWRAP_SHELL` in the environment to force one.
The resolved shell and its command syntax are declared to the model, together
with the OS, working directory, and output budget.

#### Tool-call syntax recovery

Tool calls are expected in the DeepWrap envelope:

```text
<deepwrap_tool_call>{"name":"exec","arguments":{"command":"pwd"}}</deepwrap_tool_call>
```

Backends sometimes fall back to their own native markup instead. DeepWrap parses
those forms as well, so the call is executed rather than printed as raw text, and
markup never reaches the user's screen mid-stream. Markup that cannot be parsed
at all is reported back to the model with the correct syntax, and the turn is
retried instead of being shown as the answer.

#### Prompt cost

The chat session keeps history server side, so the full protocol and every tool
schema are sent only once per session, or again when the registered tools change.
Later messages carry a 192-character reminder instead of a 4.5 KB protocol
block, and tool results are serialized without boilerplate:

| Payload                    | Before  | After   |
| -------------------------- | ------- | ------- |
| First message of a session | 5621 ch | 4514 ch |
| Every later message        | 5621 ch | 192 ch  |
| Every tool result          | 229 ch  | 85 ch   |

The protocol also states the host OS, shell, working directory, and path style,
which stops the model from guessing POSIX paths on Windows.

> Agent mode executes model-generated commands and code and can read or modify any
> path available to the current operating-system user. Run it only in an environment
> where that level of access is intended. Use `working_directory`, a dedicated user,
> container, or virtual machine when isolation is required.

Runnable examples:

- `examples/11_agent.py` — agent-driven project search and summary.
- `examples/12_native_tools.py` — direct use of all six native tools.
- `examples/13_agent_file_edit.py` — autonomous read/edit/verification workflow.
- `examples/14_agent_exec.py` — command and Python execution workflow.
- `examples/15_background_jobs.py` — concurrent process jobs and later inspection.

---

### Vision file uploads

Files can be attached only to a `vision` session. DeepWrap uploads the file,
waits for DeepSeek to process it, and forwards its file ID with the prompt.

```python
chat = client.chats.create_session(model="vision")

response = chat.respond(
    "Describe this image.",
    files=["./photo.png"],
    stream=False,
)
```

You can also upload once and reuse the returned ID:

```python
uploaded = chat.upload_file("./photo.png")
response = chat.respond("What is visible?", file_ids=[uploaded.id], stream=False)
```

### Pseudo function calling

DeepWrap supplies tool definitions through a synthetic system protocol. The model
either answers normally or returns a strict `<deepwrap_tool_call>` JSON envelope.
Passing `functions` enables the automatic tool/result loop; omitting it returns the
parsed call for execution by the application.

```python
from deepwrap import Tool

add = Tool(
    name="add",
    description="Add two integers.",
    parameters={
        "type": "object",
        "properties": {
            "a": {"type": "integer"},
            "b": {"type": "integer"},
        },
        "required": ["a", "b"],
    },
)

result = chat.respond_with_tools(
    "What is 20 + 22?",
    [add],
    functions={"add": lambda a, b: a + b},
)

print(result.content)
print(result.tool_calls)
```

Tool calling is non-streaming because the complete envelope must be validated
before a function can be selected or executed.

---

## Supported Models

DeepWrap currently supports:

```text
expert
default
vision
```

Web search is supported only by `default` (Instant). DeepWrap always sends
`search_enabled=false` for `expert` and `vision`, even if `search=True` is passed.

Example:

```python
chat = client.chats.create_session(model="default")
```

## Direct Mode

DeepWrap includes an optional **Direct Mode** for chat sessions.

When `god_mode` is enabled, DeepWrap prepends a one-time style directive to the
first user turn of the session. It asks for dense, senior-engineer answers: the
answer first, concrete commands and numbers, no preamble, no filler, no
unsolicited disclaimers, and the user's own language.

It is a response-style directive, not a restriction bypass, and it is also the
cheapest knob in the library: shorter answers with a higher share of useful
content per token.

> Direct Mode is disabled by default and must be enabled explicitly per session.
> The flag keeps its historical `god_mode` name for backwards compatibility.

### Python SDK

```python
from deepwrap import Client

client = Client()

chat = client.chats.create_session(
    model="expert",
    god_mode=True,
)

response = chat.respond(
    "Explain Python metaclasses, briefly and concretely.",
    stream=False,
)

print(response)
```

---

## CLI Usage

Run the interactive terminal interface:

```bash
deepwrap
```

To attach an image in interactive mode:

```text
/model vision
/attach ./photo.png
Describe this image.
```

Use `/attachments` to inspect pending files and `/detach` to clear them. Pending
attachments are consumed after the next successful response.

Send a single message from the terminal:

```bash
deepwrap chat "Explain recursion in one sentence."
```

Use a specific model:

```bash
deepwrap chat "Hello" --model expert
```

Disable thinking output:

```bash
deepwrap chat "Give me three facts about Tbilisi." --no-thinking
```

Disable search:

```bash
deepwrap chat "Explain Python decorators." --no-search
```

Stream output:

```bash
deepwrap chat "Write a short story about AI." --stream
```

Use a direct token:

```bash
deepwrap chat "Hello" --token "YOUR_BEARER_TOKEN"
```

---

## Interactive CLI Commands

Inside the interactive terminal UI:

```text
/help              Show help
/exit              Exit the CLI
/quit              Exit the CLI
/clear             Clear the terminal
/new               Start a fresh chat session
/model <name>      Switch model: expert, default, vision
/token             Set token interactively
/token "<token>"   Set token inline
/thinking on|off   Show or hide thinking blocks
/search on|off     Enable or disable search
/god on|off        Enable or disable Direct Mode
/save              Save current settings
/status            Show current session status
```

Example:

```text
/model expert
/thinking off
/search on
/new
```

---

## Local FastAPI Server

DeepWrap can run as a local HTTP API.

Start the server:

```bash
deepwrap api
```

Specify host and port:

```bash
deepwrap api --host 127.0.0.1 --port 8000
```

Enable reload for development:

```bash
deepwrap api --reload
```

Use more workers:

```bash
deepwrap api --workers 2
```

Set log level:

```bash
deepwrap api --log-level debug
```

---

## HTTP API

### Health Check

```bash
curl http://127.0.0.1:8000/health
```

Example response:

```json
{
  "ok": true,
  "app": "deepwrap",
  "version": "0.2.3",
  "token_configured": true,
  "cached_clients": 1,
  "active_sessions": 0
}
```

---

### One-Shot Chat Request

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Explain recursion in one sentence.",
    "model": "expert",
    "thinking": true,
    "search": true,
    "stream": false
  }'
```

Example response:

```json
{
  "model": "expert",
  "response": "Recursion is a technique where a function solves a problem by calling itself on smaller versions of the same problem.",
  "session_id": null
}
```

---

### Create Persistent Session

```bash
curl -X POST http://127.0.0.1:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "expert"
  }'
```

Example response:

```json
{
  "session_id": "chat_abc123",
  "model": "expert",
  "god_mode": false
}
```

---

### Use Persistent Session

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "chat_abc123",
    "message": "My name is Nika.",
    "model": "expert"
  }'
```

Then:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "chat_abc123",
    "message": "What is my name?",
    "model": "expert"
  }'
```

---

### Delete Session

```bash
curl -X DELETE http://127.0.0.1:8000/sessions/chat_abc123
```

---

## Streaming Over HTTP

### Plain Text Streaming

```bash
curl -N -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Explain black holes simply.",
    "model": "expert",
    "stream": true,
    "stream_format": "text"
  }'
```

---

### Server-Sent Events Streaming

```bash
curl -N -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Explain black holes simply.",
    "model": "expert",
    "stream": true,
    "stream_format": "sse"
  }'
```

SSE output format:

```text
data: chunk text

data: more chunk text

event: done
data: [DONE]
```

---

## Environment Variables

DeepWrap checks the following environment variables:

```text
DEEPWRAP_API_KEY
DEEPSEEK_API_KEY
DEEPSEEK_BASE_URL
DEEPSEEK_BASE_DOMAIN
```

Example:

```bash
export DEEPWRAP_API_KEY="YOUR_BEARER_TOKEN"
```

Optional custom base URL:

```bash
export DEEPSEEK_BASE_URL="https://chat.deepseek.com"
export DEEPSEEK_BASE_DOMAIN="chat.deepseek.com"
```

---


## API Design

DeepWrap exposes a small SDK surface:

```python
from deepwrap import Client
```

Create a client:

```python
client = Client()
```

Create a chat session:

```python
chat = client.chats.create_session(model="expert")
```

Send a message:

```python
response = chat.respond("Hello", stream=False)
```

Stream a message:

```python
for chunk in chat.respond("Hello", stream=True):
    print(chunk, end="")
```

Use structured chunks:

```python
for kind, chunk in chat.respond_structured("Hello"):
    print(kind, chunk)
```

---

## Examples

### Switch Models

```python
from deepwrap import Client

client = Client()

expert_chat = client.chats.create_session(model="expert")
default_chat = client.chats.create_session(model="default")

print(expert_chat.respond("Explain recursion in one sentence.", stream=False))
print(default_chat.respond("Explain recursion in one sentence.", stream=False))
```

---

### Hide Thinking Output

```python
from deepwrap import Client

client = Client()
chat = client.chats.create_session(model="expert")

response = chat.respond(
    "Give me three facts about Tbilisi.",
    thinking=False,
    search=True,
    stream=False,
)

print(response)
```

---

### Disable Search

```python
from deepwrap import Client

client = Client()
chat = client.chats.create_session(model="expert")

response = chat.respond(
    "Explain Python generators.",
    thinking=True,
    search=False,
    stream=False,
)

print(response)
```

---

## Error Handling

Example:

```python
from deepwrap import Client

try:
    client = Client()
    chat = client.chats.create_session(model="expert")
    response = chat.respond("Hello", stream=False)
    print(response)

except ValueError as exc:
    print(f"Configuration error: {exc}")

except RuntimeError as exc:
    print(f"API error: {exc}")

except Exception as exc:
    print(f"Unexpected error: {exc}")
```

---

## Notes

DeepWrap is designed as a developer-focused wrapper.

It handles:

- HTTP session headers
- Authorization
- Chat session creation
- Streaming response parsing
- Proof-of-work challenge solving
- CLI interaction
- Local API serving

The goal is to provide a clean interface while keeping the internal implementation modular and extensible.

---

## Security Notice

Do not commit your Bearer token.

Avoid hardcoding tokens in public repositories.

Recommended:

```bash
export DEEPWRAP_API_KEY="YOUR_BEARER_TOKEN"
```

Or use:

```bash
deepwrap auth
```

Tokens saved by DeepWrap are stored locally in the user config directory.

---

## Disclaimer

This project is an unofficial wrapper.

It is not affiliated with, endorsed by, or officially supported by DeepSeek.

Use responsibly and respect the terms of service of any service you interact with.

---

## License

MIT License

Copyright (c) 2026 Nika Kudukhashvili

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files, to deal in the Software
without restriction, including without limitation the rights to use, copy,
modify, merge, publish, distribute, sublicense, and/or sell copies of the
Software, subject to the conditions of the MIT License.
