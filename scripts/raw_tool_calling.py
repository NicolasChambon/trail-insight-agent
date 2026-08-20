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
    },
    {
        "name": "list_activities",
        "description": (
            "List the dates of all recorded trail-running activities."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
]

# Fake data store. In phase 3, this becomes a curated BigQuery view.
ACTIVITIES = {
    "2026-08-16": {
        "distance_km": 18.4,
        "elevation_gain_m": 1120,
        "duration_min": 158,
        "average_heart_rate": 148,
    },
    "2026-06-21": {
        "distance_km": 24.0,
        "elevation_gain_m": 1450,
        "duration_min": 212,
        "average_heart_rate": 145,
    },
    "2026-05-17": {
        "distance_km": 18.1,
        "elevation_gain_m": 1090,
        "duration_min": 141,
        "average_heart_rate": 151,
    },
    "2026-05-03": {
        "distance_km": 12.2,
        "elevation_gain_m": 430,
        "duration_min": 78,
        "average_heart_rate": 152,
    },
}


def get_activity(date: str) -> str:
    """The actual implementation. This code runs on our side, never on the
    model's."""
    activity = ACTIVITIES.get(date)
    if activity is None:
        return f"No activity recorded on {date}."
    return json.dumps(activity)


def list_activities() -> str:
    """Return every recorded activity date, most recent first."""
    return json.dumps(sorted(ACTIVITIES, reverse=True))


TOOL_IMPLEMENTATIONS = {
    "get_activity": get_activity,
    "list_activities": list_activities,
}

client = anthropic.Anthropic()


def run_conversation(question: str, max_turns: int = 10) -> str:
    """Run the agent loop by hand until the model stops asking for tools."""
    messages = [{"role": "user", "content": question}]

    for turn in range(max_turns):
        response = client.messages.create(
            model=MODEL, max_tokens=1024, tools=TOOLS, messages=messages
        )

        # The model is done asking: return whatever it wrote.
        if response.stop_reason != "tool_use":
            print(f"Stop reason: {response.stop_reason}")
            return "\n".join(
                block.text for block in response.content if block.type == "text"
            )

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"[turn {turn}] model asks: {block.name}({block.input})")
                # Only tools we registered can run - this dict is a gate.
                implementation = TOOL_IMPLEMENTATIONS[block.name]
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": implementation(**block.input),
                    }
                )

        messages.append({"role": "user", "content": tool_results})

    raise RuntimeError(f"Model still asking for tools after {max_turns} turns.")


print(
    run_conversation(
        "Compare my run on 2026-08-16 with the most similar one I did in May."
    )
)
