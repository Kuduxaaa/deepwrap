from pathlib import Path

from deepwrap import Client


BEARER_TOKEN = None
IMAGE_PATH  = Path("/home/kuduxaaa/Pictures/Screenshot from 2026-07-11 18-02-06.png")

if not IMAGE_PATH.is_file():
    raise FileNotFoundError(
        f"Set IMAGE_PATH to an existing image before running this example: {IMAGE_PATH}"
    )

client = Client(api_key = BEARER_TOKEN)
chat   = client.chats.create_session(model = "vision")

# DeepWrap uploads the image, waits until DeepSeek finishes processing it,
# and includes the resulting file ID in this prompt.
response = chat.respond(
    "Describe this image and mention any visible text.",
    files    = [IMAGE_PATH],
    thinking = True,
    stream   = False,
)

print(response)

# To reuse the same upload in more than one prompt:
# uploaded = chat.upload_file(IMAGE_PATH)
# print(chat.respond("Describe the image.", file_ids = [uploaded.id], stream = False))
# print(chat.respond("Now focus on its colors.", file_ids = [uploaded.id], stream = False))
