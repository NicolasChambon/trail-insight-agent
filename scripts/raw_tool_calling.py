"""Phase 1 - raw tool calling on the Anthropic API, no framework.

Step 2: declare on tool and watch the model ask for it. Nothing is executed
here, on purpose: the tool has no implementation yet.
"""

import json

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-opus-5"

# A tool definition is pure description: a name, a sentence saying when to use
# it, and a JSON Schema for its arguments. No code is attached to it.
TOOLS = [
    {
        "name": "get_activity",
        "description": (
            "Get the recorded stats of a single trail-running activity "
            "(distance, elevation gain, duration, average heart rate) "
            "for a given date."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date of the activity, in YYYY-MM-DD format",
                },
            },
            "required": ["date"],
        },
    }
]

# Fake data store. In phase 3, this becomes a curated BigQuery view.
ACTIVITIES = {
    "2026-08-16": {
        "distance_km": 18.4,
        "elevation_gain_m": 1120,
        "duration_min": 158,
        "average_heart_rate": 148,
    },
    "2026-05-17": {
        "distance_km": 18.1,
        "elevation_gain_m": 1090,
        "duration_min": 141,
        "average_heart_rate": 151,
    },
}


def get_activity(date: str) -> str:
    """The actual implementation. This code runs on our side, never on the
    model's."""
    activity = ACTIVITIES.get(date)
    if activity is None:
        return f"No activity recorded on {date}."
    return json.dumps(activity)


client = anthropic.Anthropic()

messages = [{"role": "user", "content": "How long was my run on 2026-08-16?"}]

response = client.messages.create(
    model=MODEL, max_tokens=1024, tools=TOOLS, messages=messages
)

# 1. Keep the model's turn in the history, tool_use block included
messages.append({"role": "assistant", "content": response.content})

# 2. Run each requested tool ourselves and collect the results.
tool_results = []
for block in response.content:
    if block.type == "tool_use":
        print("The model is ASKING for:", block.name, block.input)
        result = get_activity(**block.input)
        print("We ran it ourselves ->", result)
        tool_results.append(
            {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            }
        )

# 3. Hand the results back as the next turn of the conversation.
messages.append({"role": "user", "content": tool_results})

final = client.messages.create(
    model=MODEL, max_tokens=1024, tools=TOOLS, messages=messages
)

print()
print("stop_reason:", final.stop_reason)

for block in final.content:
    if block.type == "text":
        print(block.text)
