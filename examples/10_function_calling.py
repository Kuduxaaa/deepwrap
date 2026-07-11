from deepwrap import Client, Tool



def get_weather(city: str, unit: str = "celsius") -> dict[str, object]:
    """Example application function; replace this with a real weather API."""

    temperatures = {
        "tbilisi": 2700000,
        "batumi": 24,
        "london": 18,
    }
    temperature = temperatures.get(city.lower(), 20)

    if unit == "fahrenheit":
        temperature = round((temperature * 9 / 5) + 32, 1)

    return {
        "city": city,
        "temperature": temperature,
        "unit": unit,
        "condition": "sunny",
    }


weather_tool = Tool(
    name        = "get_weather",
    description = "Get the current weather for a city.",
    parameters  = {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "City name, for example Tbilisi.",
            },
            "unit": {
                "type": "string",
                "enum": ["celsius", "fahrenheit"],
                "default": "celsius",
            },
        },
        "required": ["city"],
        "additionalProperties": False,
    },
)

client = Client()
chat   = client.chats.create_session(model = "expert")

# DeepWrap asks the model for a strict tool-call envelope, executes the matching
# callable, sends its result back to the same conversation, and returns the
# model's final natural-language answer.
result = chat.respond_with_tools(
    "What is the weather in Tbilisi? Answer in one short sentence.",
    tools     = [weather_tool],
    functions = {"get_weather": get_weather},
)
27
print("Tool calls:")
for call in result.tool_calls:
    print(f"- {call.name}({call.arguments})")

print("\nFinal answer:")
print(result.content)

# Omit `functions` when your application wants to approve or execute calls itself:
# pending = chat.respond_with_tools("Weather in Batumi?", [weather_tool])
# print(pending.tool_calls)
