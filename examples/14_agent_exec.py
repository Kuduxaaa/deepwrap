from tempfile import TemporaryDirectory

from deepwrap import Client


BEARER_TOKEN = None


with TemporaryDirectory() as directory:
    client = Client(
        api_key=BEARER_TOKEN,
        working_directory=directory,
        command_timeout=10,
        max_agent_rounds=8,
    )
    print(directory)
    chat = client.chats.create_session(model="expert")

    # The model can choose `exec`, `exec_code`, or both. The temporary working
    # directory keeps any generated files outside the repository.
    response = chat.respond(
        "Use Python to calculate the first 15 Fibonacci numbers, save them to "
        "fibonacci.txt, inspect the file, and report the final sequence.",
        stream=False,
    )

    print(response)


# Agent mode can be disabled for a plain model response:
# print(chat.respond("Explain Fibonacci numbers.", agent=False, stream=False))
