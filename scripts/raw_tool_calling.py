"""Phase 1 - raw tool calling on the Anthropic API, no framework.

Step 1: a bare call, no tools. Goal: see that a response is a list of types
content blocks plus a stop_reason explaining why the model stopped.
"""

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-opus-5"

client = anthropic.Anthropic()

messages = [
    {
        "role": "user",
        "content": (
            "What is the average slope of a 12 km trail run "
            "with 800 m of elevation gain? Answer in one sentence."
        ),
    }
]

response = client.messages.create(
    model=MODEL, max_tokens=1024, messages=messages
)

# The API is stateless, we grow the history ourselves and resend it every time.e
messages.append({"role": "assistant", "content": response.content})
messages.append(
    {"role": "user", "content": ("and for 25 km ? Answer in one sentence.")}
)

response2 = client.messages.create(
    model=MODEL, max_tokens=1024, messages=messages
)

for block in response.content:
    if block.type == "text":
        print(block.text)

for block in response2.content:
    if block.type == "text":
        print(block.text)
