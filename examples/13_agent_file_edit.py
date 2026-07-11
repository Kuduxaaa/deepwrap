from pathlib import Path
from tempfile import TemporaryDirectory

from deepwrap import Client


BEARER_TOKEN = None


with TemporaryDirectory() as directory:
    workspace = Path(directory)
    config_path = workspace / "settings.json"
    config_path.write_text(
        '{\n  "debug": false,\n  "timeout": 10\n}\n',
        encoding="utf-8",
    )

    client = Client(
        api_key=BEARER_TOKEN,
        working_directory=workspace,
        command_timeout=10,
        max_agent_rounds=8,
    )
    chat = client.chats.create_session(model="expert")

    response = chat.respond(
        "Read settings.json, change debug to true and timeout to 30, then verify "
        "the resulting file and summarize what you changed.",
        stream=False,
    )

    print("=== AGENT RESPONSE ===")
    print(response)
    print("\n=== RESULTING FILE ===")
    print(config_path.read_text(encoding="utf-8"))
