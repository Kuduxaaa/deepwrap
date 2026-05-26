from deepwrap import Client

BEARER_TOKEN = "YOUR_TOKEN"

client = Client(api_key = BEARER_TOKEN)

expert_chat = client.chats.create_session(model = "expert")
default_chat = client.chats.create_session(model = "default")

print("=== EXPERT ===")
print(
    expert_chat.respond(
        "Explain recursion in one sentence.",
        stream = False,
    )
)

print()
print("=== DEFAULT ===")
print(
    default_chat.respond(
        "Explain recursion in one sentence.",
        stream = False,
    )
)

# === EXPERT ===
# <think>We need to explain recursion in one sentence. The user asked: "Explain recursion in one sentence." So I need to craft a single concise sentence that captures the essence of recursion. Common definitions: "Recursion is a process where a function calls itself to solve smaller instances of the same problem until a base case is reached." That's one sentence. But I can make it more witty or include a classic joke: "To understand recursion, you must first understand recursion." That's a well-known humorous sentence. But the user might want a serious explanation. The prompt says "Explain recursion in one sentence." I'll provide a clear, informative one-sentence definition. I'll also consider whether they want a joke. I can give both? But the instruction is just one sentence. I'll answer with a single sentence that explains it. I'll go with: "Recursion is a programming technique where a function solves a problem by calling itself on progressively simpler subproblems until reaching a trivial base case that stops the chain." That's one sentence. I'll output that. No extra commentary needed.</think>Recursion is a problem-solving technique where a function calls itself with simpler inputs until reaching a base case that stops the chain.

# === DEFAULT ===
# <think>We need to explain recursion in one sentence. Keep it concise, clear, and accurate. Recursion: a function that calls itself to solve a problem by breaking it into smaller instances of the same problem.</think>Recursion is a programming technique where a function solves a problem by calling itself on smaller instances of the same problem until reaching a base case.
