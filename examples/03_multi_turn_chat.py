from deepwrap import Client

BEARER_TOKEN = "YOUR_TOKEN"

client = Client(api_key = BEARER_TOKEN)
chat   = client.chats.create_session(model = "expert")

print("USER: Hello, My name is NIka. (Respond me with only one word now and in future.)")
print("ASSISTANT:")
print(chat.respond("Hello, My name is NIka. (Respond me with only one word now and in future.)", stream = False))
print()

print("USER: I am planning a trip to Tokyo.")
print("ASSISTANT:")
print(chat.respond("I am planning a trip to Tokyo.", stream = False))
print()

print("USER: What is my name?")
print("ASSISTANT:")
print(chat.respond("What is my name?", stream = False))
print()

# USER: Hello, My name is NIka. (Respond me with only one word now and in future.)
# ASSISTANT:
# <think>We are asked: "Hello, My name is NIka. (Respond me with only one word now and in future.)"

# The instruction is to respond with only one word now and in future. So I need to reply with just one word. The user's name is Nika. I should greet them with one word. Perhaps "Hello" or "Hi" or "Welcome". Since they said "Respond me with only one word now and in future", I must output only one word, no punctuation, no extra text. I'll respond with "Hi".</think>Hi

# USER: I am planning a trip to Tokyo.
# ASSISTANT:
# <think>We are asked: "Hello, My name is NIka. (Respond me with only one word now and in future.)" 

# The user previously said "Hello, My name is NIka. (Respond me with only one word now and in future.)" and I responded with "Hi". Then the user says "I am planning a trip to Tokyo." 

# But the instruction was: "Respond me with only one word now and in future." So I must respond with only one word to any future message. The user just said "I am planning a trip to Tokyo." That's a new message. I must reply with only one word.

# What one word would be appropriate? Since they are planning a trip, maybe "Nice" or "Tokyo" or "Enjoy". But the instruction is to respond with only one word, no matter what. I'll pick a relevant one-word response. "Nice" could work. But perhaps a more engaging one-word reply like "Exciting!" but that's one word? "Exciting" is one word. Or "Adventure". I'll just pick "Exciting" as it's a positive reaction. The instruction says "only one word now and in future." So I must output exactly one word. No punctuation, just the word. So I'll reply: Exciting</think>Exciting

# USER: What is my name?
# ASSISTANT:
# <think>We need to respond with only one word. The user asked "What is my name?" The user's name is NIka. So the response should be "NIka". But wait, the instruction at the beginning was: "Respond me with only one word now and in future." So I must reply with exactly one word. The question is "What is my name?" The answer is "NIka". So I'll say "NIka".</think>NIka
