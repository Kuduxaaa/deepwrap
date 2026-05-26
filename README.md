# DeepWrap

**DeepWrap** is a lightweight Python SDK, CLI, and local HTTP API wrapper for interacting with DeepSeek Chat through a clean developer-friendly interface.

It provides:

- A simple Python client
- Streaming and non-streaming chat responses
- Structured streaming with separated thinking and response chunks
- Browser-based authentication
- Local token storage
- Interactive terminal UI
- FastAPI server mode
- Session-based chat support
- Proof-of-work handling internally

> Repository: [https://github.com/Kuduxaaa/deepwrap](https://github.com/Kuduxaaa/deepwrap)

---

## Installation

```bash
pip install deepwrap
````

Or install directly from GitHub:

```bash
pip install git+https://github.com/Kuduxaaa/deepwrap.git
```

For local development:

```bash
git clone https://github.com/Kuduxaaa/deepwrap.git
cd deepwrap
pip install -e .
```

---

## Quick Start

```bash
deepwrap
```

or

```python
from deepwrap import Client

client = Client(api_key="YOUR_BEARER_TOKEN")
chat = client.chats.create_session(model="expert")

response = chat.respond(
    "Hello, introduce yourself in one sentence.",
    stream=False,
)

print(response)
```

---

## Authentication

DeepWrap uses a Bearer token.

You can provide the token directly:

```python
from deepwrap import Client

client = Client(api_key="YOUR_BEARER_TOKEN")
```

Or use environment variables:

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

---

## CLI Authentication

Authenticate using browser login:

```bash
deepwrap auth
```

Manually save a token:

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

Remove saved token:

```bash
deepwrap logout
```

---

## Python SDK Usage

### Basic Non-Streaming Chat

```python
from deepwrap import Client

client = Client(api_key="YOUR_BEARER_TOKEN")
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

client = Client(api_key="YOUR_BEARER_TOKEN")
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

client = Client(api_key="YOUR_BEARER_TOKEN")
chat = client.chats.create_session(model="expert")

print(chat.respond("My name is Nika.", stream=False))
print(chat.respond("What is my name?", stream=False))
```

The `ChatSession` keeps track of the latest message ID internally, so follow-up messages stay inside the same conversation.

---

### Structured Streaming

If you want to separate thinking chunks from final response chunks:

```python
from deepwrap import Client

client = Client(api_key="YOUR_BEARER_TOKEN")
chat = client.chats.create_session(model="expert")

for kind, chunk in chat.respond_structured(
    "Explain how neural networks learn.",
    thinking=True,
    search=True,
):
    if kind == "think":
        print(f"[THINK] {chunk}", end="", flush=True)

    elif kind == "response":
        print(f"[RESPONSE] {chunk}", end="", flush=True)

print()
```

Possible chunk kinds:

```text
think
response
```

---

## Supported Models

DeepWrap currently supports:

```text
expert
default
vision
```

Example:

```python
chat = client.chats.create_session(model="default")
```

---

## CLI Usage

Run the interactive terminal interface:

```bash
deepwrap
```

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
deepwrap api --host 127.0.0.1 --port 7070
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
curl http://127.0.0.1:7070/health
```

Example response:

```json
{
  "ok": true,
  "app": "deepwrap",
  "version": "0.1.0",
  "token_configured": true,
  "cached_clients": 1,
  "active_sessions": 0
}
```

---

### One-Shot Chat Request

```bash
curl -X POST http://127.0.0.1:7070/chat \
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
curl -X POST http://127.0.0.1:7070/sessions \
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
curl -X POST http://127.0.0.1:7070/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "chat_abc123",
    "message": "My name is Nika.",
    "model": "expert"
  }'
```

Then:

```bash
curl -X POST http://127.0.0.1:7070/chat \
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
curl -X DELETE http://127.0.0.1:7070/sessions/chat_abc123
```

---

## Streaming Over HTTP

### Plain Text Streaming

```bash
curl -N -X POST http://127.0.0.1:7070/chat \
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
curl -N -X POST http://127.0.0.1:7070/chat \
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

```bash
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

## Project Structure

```text
deepwrap/
  __init__.py
  __main__.py
  client.py
  config.py

  api/
    __init__.py
    base.py
    chats.py
    chat_session.py
    pow.py

  core/
    __init__.py
    auth.py
    session_manager.py

  interfaces/
    cli.py
    api.py

  modules/
    ...

  utils/
    ...

examples/
  01_basic_stream.py
  02_basic_non_stream.py
  03_multi_turn_chat.py
  04_god_mode.py
  05_no_thinking.py
  06_structured_chunks.py
  07_separate_thinking_and_answer.py
  08_switch_model.py
```

---

## API Design

DeepWrap exposes a small SDK surface:

```python
from deepwrap import Client
```

Create a client:

```python
client = Client(api_key="YOUR_BEARER_TOKEN")
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

## Development Setup

Clone the repository:

```bash
git clone https://github.com/Kuduxaaa/deepwrap.git
cd deepwrap
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it:

Windows:

```bash
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Install in editable mode:

```bash
pip install -e .
```

Install development dependencies:

```bash
pip install -e ".[dev]"
```

---

---

## Examples

### Switch Models

```python
from deepwrap import Client

client = Client(api_key="YOUR_BEARER_TOKEN")

expert_chat = client.chats.create_session(model="expert")
default_chat = client.chats.create_session(model="default")

print(expert_chat.respond("Explain recursion in one sentence.", stream=False))
print(default_chat.respond("Explain recursion in one sentence.", stream=False))
```

---

### Hide Thinking Output

```python
from deepwrap import Client

client = Client(api_key="YOUR_BEARER_TOKEN")
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

client = Client(api_key="YOUR_BEARER_TOKEN")
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
    client = Client(api_key="YOUR_BEARER_TOKEN")
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

* HTTP session headers
* Authorization
* Chat session creation
* Streaming response parsing
* Proof-of-work challenge solving
* CLI interaction
* Local API serving

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
