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
- [Supported Models](#supported-models)
- [God Mode](#god-mode)
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

## God Mode

DeepWrap includes an optional **God Mode** for chat sessions.

When `god_mode` is enabled, DeepWrap injects a one-time override prompt into the first user turn of the session. This prompt attempts to alter the model’s default behavior by making it less restricted and reducing the effect of built-in safety guardrails.

This can materially change the model’s behavior and may cause it to generate content that is harmful, unethical, inappropriate, or unsuitable for general use.

Because this mode is implemented through prompt injection at the start of a session, its behavior is intentionally intrusive and may diverge from normal model behavior. It should only be used in controlled development and research environments.

> God Mode is disabled by default and must be enabled explicitly per session.

### Python SDK

```python
from deepwrap import Client

client = Client()

chat = client.chats.create_session(
    model="expert",
    god_mode=True,
)

response = chat.respond(
    "Give me a blunt explanation of Python metaclasses.",
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
/god on|off        Enable or disable God Mode
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
  "version": "0.1.0",
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
