"""Phase 5.1 - the first ADK agent, with a single hand-written tool.

No MCP, no BigQuery: the point is to see the framework run the same loop that
scripts/raw_tool_calling.py ran by hand, and nothing else.
"""

from dotenv import load_dotenv
from google.adk.agents import Agent

# The API key lives in the repo-root .env, next to the Strava credentials.
# Loaded at import time, before the model is ever called.
load_dotenv()


def km_effort(distance_km: float, elevation_gain_m: float) -> dict:
    """Convert a distance and elevation gain into "km-effort".

    The French trail convention:
    km-effort = distance_km + elevation_gain_m / 100.
    A linear convention, not a measurement. It ignores descent and
    underestimates the cost of very steep ground.

    Args:
      distance_km: Horizontal distance covered, in kilometers.
      elevation_gain_m: Total elevation gain, in meters.

    Returns:
      The km-effort value, and the two inputs it was computed from.
    """
    return {
        "km_effort": round(distance_km + elevation_gain_m / 100, 2),
        "distance_km": distance_km,
        "elevation_gain_m": elevation_gain_m,
    }


# Pinned, not "gemini-flash-latest": that alias moves without notice, and an
# evaluation harness aimed at a moving model measures nothing. On 2026-08-26
# the alias resolved to 3.7-flash, which answered a trivial prompt in 108 s
# under load, when it answered at all. Revisit deliberately, never silently.
MODEL = "gemini-3.5-flash"

root_agent = Agent(
    name="trail_coach",
    model=MODEL,
    description="Explains trail-running training figures.",
    instruction=(
        "You explain trail-running figures. When a computation is needed, "
        "call the tool rather than doing arithmetic yourself, and report the "
        "figure it returns verbatim. Answer in the language of the question."
    ),
    tools=[km_effort],
)
