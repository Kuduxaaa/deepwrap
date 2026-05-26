from deepwrap import Client

BEARER_TOKEN = "YOUR_TOKEN"
MODEL        = "expert"

client = Client(api_key = BEARER_TOKEN)
chat   = client.chats.create_session(model = MODEL)

response = chat.respond(
    "Explain quantum computing in one short sentence.",
    thinking = True,
    search   = True,
    stream   = False,
)

print(response)

# <think># We need to produce a one-sentence explanation of quantum computing. The user asked: "Explain quantum computing in one short sentence." So we need a concise, clear, and accurate single sentence that captures the essence. It should be short, not a run-on. I'll craft something like: "Quantum computing harnesses the principles of quantum mechanics, such as superposition and entanglement, to process information in ways that can solve certain problems exponentially faster than classical computers." But that's a bit long. Could shorten: "Quantum computing uses qubits that can exist in multiple states simultaneously, enabling massively parallel computation for specific tasks." But need to mention quantum mechanics? "Quantum computing leverages quantum superposition and entanglement to perform calculations that are intractable for classical computers." Might be too generic. "Quantum computing is a type of computation that exploits quantum phenomena like superposition and entanglement to solve complex problems much faster than traditional computers." I think "much faster" is not specific, but okay. Need one short sentence. Maybe: "Quantum computing processes information using quantum bits, or qubits, which can represent 0 and 1 simultaneously, unlocking exponential speedups for certain calculations." That's clear. I'll produce a final answer with just that sentence, no extra commentary. The user asked to explain in one short sentence, so I'll output only the sentence. Ensure it's short: "Quantum computing harnesses superposition and entanglement to let qubits perform many calculations at once, solving specific problems far faster than classical computers." That's one sentence, but it's a bit long. "Quantum computing uses qubits that can be in multiple states at once, enabling exponentially faster solutions for certain problems." That's shorter. I'll deliver: "Quantum computing harnesses quantum superposition and entanglement to process information in qubits, enabling exponential speedups for specific problems." That's concise and captures the essence. I'll output that.</think># Quantum computing harnesses quantum superposition and entanglement to process information in qubits, enabling exponential speedups for specific problems.