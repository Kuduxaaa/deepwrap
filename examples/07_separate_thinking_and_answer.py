from deepwrap import Client

BEARER_TOKEN = None

client = Client(api_key = BEARER_TOKEN)
chat   = client.chats.create_session(model = "expert")

think_parts    = []
response_parts = []

for kind, chunk in chat.respond_structured(
    "How does a neural network learn?",
    thinking = True,
    search   = True,
):
    if kind == "think":
        think_parts.append(chunk)

    elif kind == "response":
        response_parts.append(chunk)

print("<think>")
print("".join(think_parts))
print("</think>")
print()
print("ANSWER:")
print("".join(response_parts))

# <think>
# We need to explain how a neural network learns. This is a broad question, could be answered in various levels of detail. The user likely wants an accessible yet technically sound explanation. I should structure the answer: start with a high-level analogy, then go into the mathematical framework (forward pass, loss, backpropagation, gradient descent). I'll cover supervised learning as the typical context. Mention the iterative process, weights updating, learning rate, etc. Keep it clear, maybe break into sections. The answer should be comprehensive but not overly technical jargon-heavy. I'll explain the core ideas: forward propagation computes predictions, loss function measures error, backpropagation calculates gradients via chain rule, optimizer updates weights. I'll also touch on concepts like epochs, batches, and generalization. Use plain language, with some analogies (like adjusting knobs). The final answer should feel educational. I'll write in a friendly, explanatory tone.
# </think>

# ANSWER:
# At its heart, a neural network learns by **making a guess, measuring how wrong it is, and then carefully adjusting its internal knobs to be less wrong next time.** It repeats this millions of times over many examples until it becomes reliably good at the task.

# Here’s the process broken down step by step, from the simple intuition to the key mechanics.

# ---

# ### 1. The “Guess” — Forward Propagation
# Imagine a network designed to recognize handwritten digits. It’s made of layers of artificial neurons, each connected by numbers called **weights** (the knobs) and **biases** (shifters).

# You show it an image of a “5”. The pixels flow through the layers, getting multiplied by the weights and passed through activation functions. At the final layer, the network outputs a set of scores—one per possible digit (0–9). It might, for example, give:
# - 5: 0.2 probability
# - 6: 0.7 probability
# - 3: 0.05 probability
# … and so on.

# Clearly, it’s guessing “6”, but the correct label is “5”. The network has made an error.

# ---

# ### 2. Measuring the Error — The Loss Function
# To know *how much* to change, we need a single number that measures the network’s mistake. This is the **loss function** (or cost function).

# For classification, a common loss is **cross-entropy**: it heavily penalizes being confident and wrong. If the true label is “5”, the loss will be large because the network gave that class only 0.2 probability. If it had given “5” a 0.9 probability, the loss would be small.

# Now we have a clear goal: **find the set of weights and biases that minimizes this loss across all training examples.**

# ---

# ### 3. Figuring Out Which Way to Turn the Knobs — Backpropagation
# This is the magic. We need to know: if I slightly increase this one particular weight deep in layer 2, does the final loss go up or down? And by how much?

# **Backpropagation** (short for “backward propagation of errors”) calculates the **gradient** of the loss with respect to every single weight and bias in the network. A gradient is simply a multi-dimensional slope: it tells you the direction and steepness of the steepest increase.

# It works by applying the **chain rule** of calculus from the output layer back to the input layer:
# 1. Compute how much the loss changes when we nudge the output predictions.
# 2. Use that to compute how much the loss changes when we nudge the weights and biases in the last layer.
# 3. Then propagate those error signals backward through the layers, reusing computations, until we have the gradient for the very first weight.

# After one forward and backward pass, we know the slope of the loss landscape for every single parameter in the network.

# ---

# ### 4. Updating the Knobs — Gradient Descent
# Now that we have the gradients, we update every weight and bias using an **optimizer**. The simplest optimizer is **Gradient Descent**:

# ```
# new_weight = old_weight - learning_rate × gradient
# ```

# - The **gradient** points uphill (direction of increasing loss).
# - We subtract a tiny step in that direction, so we move **downhill**.
# - The **learning rate** controls the size of the step. Too small → slow learning. Too large → you might overshoot the minimum or diverge.

# Modern optimizers like **Adam** or **SGD with momentum** are more sophisticated: they adapt the learning rate per parameter, accumulate velocity to smooth out zig-zags, and generally find a good minimum faster.

# ---

# ### 5. Rinse and Repeat — Epochs and Batches
# The network rarely learns from one example at a time. Instead:
# - The training data is divided into **mini-batches** (e.g., 32 images at a time).
# - For each batch, the network does forward pass → loss → backpropagation → weight update.
# - A full pass through the entire dataset is called an **epoch**.

# Over many epochs, the loss gradually drops, and the network’s guesses become more accurate. The weights slowly settle into a configuration that captures the patterns in the data—edges in early layers, shapes in middle layers, and entire object-like features in deeper layers.

# ---

# ### 6. Why It Generalizes (and Doesn’t Just Memorize)
# Crucially, the network isn’t just storing the training examples. Because of the random initialization of weights, the loss landscape, and the fact that we update in small steps, the network tends to find **general patterns** that explain the data. Techniques like regularization, dropout, and early stopping further prevent it from simply memorizing.

# ---

# ### Summary in One Sentence
# A neural network learns by repeatedly:
# 1. Forward-propagating an input to get a prediction,
# 2. Calculating a loss to measure error,
# 3. Backpropagating to compute how each weight contributed to that error,
# 4. And tweaking those weights slightly in the opposite direction of the gradient,

# …until the predictions are good enough.

# If you’d like, I can dive deeper into any specific part—like the chain rule in backpropagation, what activation functions do, or how modern optimizers improve on basic gradient descent.
