"""Phase 6.1 - the hand-written MCP server, the agent's second tool source.

MCP Toolbox serves what the database knows, declaratively, from a YAML
file. This one serves everything else: what the machine knows now, and -
from 6.2 on - what the agent can change in the outside world. Two
servers rather than four more queries, because they are two different
jobs and only one of them is SQL.

Run it the way the agent runs it:
    uv run python -m trail_insight_agent.coach_server
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastmcp import FastMCP

# Hard-coded, not read from the host clock: the athlete trains in one place,
# and "today" must not shift because the process happened to start in a
# conatiner running UTC.
ATHLETE_TIMEZONE = "Europe/Paris"

mcp = FastMCP(
    name="trail_coach",
    instructions=(
        "Tools that do not come from the training database: what the current"
        "date is, and what the agent can act on."
    ),
)


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
def get_today() -> dict[str, str | int]:
    """Returns today's datte, in the athlete's timezone.

    Call this before any tool that takes a date, whenever the question names a
    period relative to now: "this month", "the last four weeks", "since the
    summer". You have no clock on your own, and a date you infer is a date you
    invented - the query will still run, and silently return the wrong window.

    Takes no arguments.
    """
    now = datetime.now(ZoneInfo(ATHLETE_TIMEZONE))
    year, week, weekday = now.isocalendar()
    return {
        "today": now.date().isoformat(),
        "weekday": now.strftime("%A"),
        "iso_week": f"{year}-W{week:02d}",
        "iso_weekday": weekday,
        "timezone": ATHLETE_TIMEZONE,
    }


if __name__ == "__main__":
    # stdio: one client, one child process, no port and no network. The same
    # transport ADK already uses for the Toolbow binary.
    mcp.run(transport="stdio", show_banner=False)
