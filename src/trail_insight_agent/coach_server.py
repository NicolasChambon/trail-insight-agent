"""Phase 6.2 - the hand-written MCP server, the agent's second tool source.

MCP Toolbox serves what the database knows, declaratively, from a YAML file,
under a service account: the data belongs to the project. This one serves
everything else - what the machine knows now, and what the agent can change in
the outside world. Two servers rather than four more queries, because they are
two different jobs and only one of them is SQL.

It also carries the project's second identity. The calendar is the athlete's,
not the project's, so every call below rides on a consent he gave in a browser
(see google_auth). The blast radius of this server is therefore the widest in
the repo, and it is bounded three times over: by the scope on the token, by the
two constants below, and by the tool_filter in the agent.

Run it the way the agent runs it:
    uv run python -m trail_insight_agent.coach_server
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from trail_insight_agent import google_auth

# Hard-coded, not read from the host clock: the athlete trains in one place,
# and "today" must not shift because the process happened to start in a
# container running UTC.
ATHLETE_TIMEZONE = "Europe/Paris"

CALENDAR_API = "https://www.googleapis.com/calendar/v3"

# "primary", and not a calendar id taken as an argument: the token can write to
# every calendar the athlete owns; the agent may write to one. This is the
# boundary the OAuth scope is not fine-grained enough to express.
CALENDAR_ID = "primary"

# Bounds on a single read, so a wide date range cannot return a payload that
# crowds out the conversation.
MAX_EVENTS = 50

mcp = FastMCP(
    name="trail_coach",
    instructions=(
        "Tools that do not come from the training database: what the current "
        "date is, and what the agent can act on."
    ),
)


def _authorization() -> dict[str, str]:
    """The bearer header, or a tool error the human can act on.

    MissingConsent means the browser step has to be redone; nothing the model
    tries next will help. Re-raised as ToolError so FastMCP passes the
    sentence through instead of masking it behind a generic tool failure.
    """
    try:
        return {"Authorization": f"Bearer {google_auth.get_access_token()}"}
    except google_auth.MissingConsent as error:
        raise ToolError(str(error)) from error


def _checked(response: httpx.Response) -> dict:
    """Return the parsed body, or raise with the API's own explanation.

    httpx reports the status and the URL; Google puts the reason in the body
    ("Insufficient Permission", "Invalid start time"). That sentence is what
    tells the model whether a different argument would work, or whether
    nothing will.
    """
    if response.is_error:
        raise ToolError(f"{response.status_code} {response.text[:300]}")
    return response.json()


def _day_start(date: str) -> str:
    """ISO date -> RFC 3339 timestamp at midnight, athlete's timezone."""
    day = datetime.fromisoformat(date)
    return day.replace(tzinfo=ZoneInfo(ATHLETE_TIMEZONE)).isoformat()


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
def get_today() -> dict[str, str | int]:
    """Returns today's date, in the athlete's timezone.

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


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
def find_planned_sessions(start_date: str, end_date: str) -> dict:
    """Returns what is already in the athlete's calendar over a period.

    The calendar holds races, planned sessions, and everything else the athlete
    put there - it is his own, not a training log. Read it before proposing or
    scheduling anything, so you do not plan a hard session on top of a race, or
    add a second copy of a session that is already there.

    This reads the calendar; it never reports past training. Training that
    happened is in the database - use the BigQuery tools for that.

    Args:
        start_date: first day to cover, YYYY-MM-DD.
        end_date: first day NOT covered, YYYY-MM-DD. Exclusive, so a single day
            is start_date plus one.

    Both come from get_today when the question names a period relative to now.
    """
    response = httpx.get(
        f"{CALENDAR_API}/calendars/{CALENDAR_ID}/events",
        headers=_authorization(),
        params={
            "timeMin": _day_start(start_date),
            "timeMax": _day_start(end_date),
            # Expand a recurring event into its occurrences. Without this a
            # weekly club session comes back once, carrying a reccurence rule
            # the model would have to interpret -  and would interpret wrong.
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": MAX_EVENTS,
        },
        timeout=15.0,
    )
    events = _checked(response).get("items", [])

    # Four fields out of the forty the API returns. Same reasoning as
    # v_activities over activities_raw: the model reads what it needs, and
    # etags, ids of attendees and conferencing data are not it.
    return {
        "period": f"{start_date} to {end_date} (end exclusive)",
        "count": len(events),
        "truncated": len(events) == MAX_EVENTS,
        "events": [
            {
                "event_id": event["id"],
                "title": event.get("summary", "(no title)"),
                "start": event["start"].get(
                    "dateTime", event["start"].get("date")
                ),
                "end": event["end"].get("dateTime", event["end"].get("date")),
            }
            for event in events
        ],
    }


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    }
)
def schedule_session(
    title: str,
    date: str,
    start_time: str,
    duration_minutes: int,
    description: str = "",
) -> dict:
    """Creates one training session in the athlete's calendar.

    This writes to a real calendar the athlete reads every day. Call it only
    when he has asked for it in the conversation, in as many words - never as a
    helpful extra after an analysis, and never twice for one request: nothing
    here can delete what it wrote, so a wrong event is removed by hand. Call
    find_planned_sessions over the same day first.

    Args:
        title: what shows in the calendar. Short, e.g. "Seuil 3x8 min".
        date: YYYY-MM-DD, today or later.
        start_time: HH:MM, 24-hour, athlete's local time.
        duration_minutes: between 15 and 600.
        description: optional detail - the session's structure, or the figures
            that justify it. Plain text, no Markdown.
    """
    if not 15 <= duration_minutes <= 600:
        raise ToolError("duration_minutes must be between 15 and 600")

    timezone = ZoneInfo(ATHLETE_TIMEZONE)
    start = datetime.fromisoformat(f"{date}T{start_time}").replace(
        tzinfo=timezone
    )
    # A model with a shaky sense of "now" writing into a calendar is how you
    # get a session scheduled last March. get_today exists so this never
    # triggers; the check is here because "never" is a claim, not a guarantee.
    if start < datetime.now(timezone) - timedelta(hours=1):
        raise ToolError(
            f"{date} {start_time} is in the past. Call get_today and use a "
            "date from it."
        )

    end = start + timedelta(minutes=duration_minutes)
    created = _checked(
        httpx.post(
            f"{CALENDAR_API}/calendars/{CALENDAR_ID}/events",
            headers=_authorization(),
            json={
                "summary": title,
                "description": description,
                "start": {
                    "dateTime": start.isoformat(),
                    "timeZone": ATHLETE_TIMEZONE,
                },
                "end": {
                    "dateTime": end.isoformat(),
                    "timeZone": ATHLETE_TIMEZONE,
                },
            },
            timeout=15.0,
        )
    )

    return {
        "event_id": created["id"],
        "title": title,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "link": created.get("htmlLink", ""),
    }


if __name__ == "__main__":
    # stdio: one client, one child process, no port and no network. The same
    # transport ADK already uses for the Toolbox binary.
    mcp.run(transport="stdio", show_banner=False)
