from pathlib import Path

from deepwrap import AgentEvent, Client


BEARER_TOKEN = None

# Agent mode is enabled by default. Relative tool paths and commands use this
# working directory; absolute paths remain available.
client = Client(
    api_key=BEARER_TOKEN,
    working_directory=Path(__file__).resolve().parents[1],
    command_timeout=30,
    max_agent_rounds=8,
)
chat = client.chats.create_session(model="expert")


def show_progress(event: AgentEvent) -> None:
    if event.type == "tool_started":
        arguments = {
            key: value
            for key, value in (event.arguments or {}).items()
            if key != "content"
        }
        print(f"\n[agent] {event.message} arguments={arguments}", flush=True)
    elif event.type == "tool_completed":
        print(
            f"[agent] {event.message} ({event.duration_seconds:.2f}s)",
            flush=True,
        )
    else:
        print(f"\n[agent] {event.message}", flush=True)


response = chat.respond(
    "Create single HTML file which includes CSS and JS and are landing page, for Japanes culture it should be minimal and aesthetic.",
    stream=True,
    on_event=show_progress,
)

for chunk in response:
    print(chunk, end="", flush=True)

print()

print("\nTools used:")
for execution in response.tools_used:
    print(f"\n- {execution.name}")
    print(f"  arguments: {execution.arguments}")
    print(f"  output: {execution.output}")

# To use DeepWrap as a plain chat wrapper for one request:
# response = chat.respond("Hello", agent=False, stream=False)
