from deepwrap import Client

BEARER_TOKEN = "YOUR_TOKEN"
MODEL        = "expert"

client = Client(api_key = BEARER_TOKEN)
chat   = client.chats.create_session(model = MODEL)

for chunk in chat.respond(
    "Hello, introduce yourself in one short sentence.",
    thinking = True,
    search   = True,
    stream   = True,
):
    print(chunk, end = "", flush = True)

print()

# <think> We are asked: "Hello, introduce yourself in one short sentence." I need to introduce myself in one short sentence. I'm DeepSeek, an AI assistant created by DeepSeek Company. So a short sentence: "I'm DeepSeek, an AI assistant created by DeepSeek Company." That's one short sentence. Make sure it's friendly and concise.</think>
# 
# I'm DeepSeek, an AI assistant created by DeepSeek Company.