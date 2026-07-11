import sys

from pathlib import Path

from deepwrap import AgentEvent, Client


BEARER_TOKEN = None
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def progress(event: AgentEvent) -> None:
    print(f"[{event.type}] {event.message}", flush=True)


client = Client(
    api_key=BEARER_TOKEN,
    working_directory=PROJECT_ROOT,
)
chat = client.chats.create_session(model="expert")

# Use a portable Python command as the long-running example. The same workflow
# works for curl/wget, an authorized nmap scan, crawlers, build commands, etc.
command = (
    f'"{sys.executable}" -u -c "import time; '
    "print('job started'); time.sleep(10); print('job finished')\""
)

response = chat.respond(
    f"Start this command as a background job and return immediately: {command}",
    stream=False,
    on_event=progress,
)
print(response)

for execution in response.tools_used:
    if execution.name == "start_job":
        print("Background job:", execution.output)

# In a later turn, the same agent can inspect it:
# print(chat.respond("Check the background job and show its latest output.", stream=False))
