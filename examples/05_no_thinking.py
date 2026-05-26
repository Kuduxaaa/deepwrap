from deepwrap import Client

BEARER_TOKEN = "YOUR_TOKEN"

client = Client(api_key = BEARER_TOKEN)
chat   = client.chats.create_session(model = "expert")

response = chat.respond(
    "Give me three short facts about Tbilisi.",
    thinking = False,
    search   = True,
    stream   = False,
)

print(response)

# Here are three short facts about Tbilisi, Georgia:

# 1.  **Name Origin:** The name "Tbilisi" comes from the Old Georgian word *tbili*, meaning "warm." It refers to the natural hot sulphur springs that still flow in the city's Abanotubani district, where, according to legend, King Vakhtang Gorgasali's falcon fell, leading him to found the city in the 5th century.

# 2.  **Architectural Melting Pot:** The Old Town is a unique visual timeline where you can find a Georgian Orthodox church, a synagogue, a mosque, and an Armenian church all within a few minutes' walk of each other, symbolizing the city's historic multi-ethnic fabric. This sits alongside colorful wooden houses with carved balconies and striking modern architecture like the Peace Bridge.

# 3.  **A Fortress for Two:** The iconic Narikala Fortress overlooking the city was initially built as a Persian citadel in the 4th century under the name "Shuris-tsikhe" (Invidious Fort). Later, it was expanded by the Arabs in the 8th century, giving it the name we use today, which derives from a diminutive form of the Persian word *Nari* (meaning "smaller" or "new").
