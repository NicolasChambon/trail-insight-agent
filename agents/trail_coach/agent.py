"""Phase 6.1 - the ADK agent, wired to two MCP servers over stdio.

No tool is defined in this file. The four BigQuery tools live in
mcp/tools.yaml and are served by the MCP Toolbox binary; the hand-written
ones live in trail_insight_agent.coach_server and are served by FastMCP.
ADK starts both as child processes and talks to them over stdio - the
same way Claude Code reaches them through .mcp.json.

Two servers because they are two different jobs: Toolbox is declarative
and reads a database under a least-privilege service account, FastMCP
runs Python and will, from 6.2 on, act on the outside world. Splitting
them keeps those two blast radii separate.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams

from mcp import StdioServerParameters

# The API key lives in the repo-root .env, next to the Strava credentials.
# Loaded at import time, before the model is ever called.
load_dotenv()

# Derived from this file, not from the working directory: adk web can be
# launched from anywhere, and a relative config path would resolve against
# whatever directory that happened to be.
TOOLS_YAML = Path(__file__).resolve().parents[2] / "mcp" / "tools.yaml"

# Pinned, not "gemini-flash-latest": that alias moves without notice, and an
# evaluation harness aimed at a moving model measures nothing. On 2026-08-26
# the alias resolved to 3.7-flash, which answered a trivial prompt in 108 s
# under load, when it answered at all. Revisit deliberately, never silently.
MODEL = "gemini-3.5-flash"

INSTRUCTION = """\
You are a trail-running analyst. You answer questions about one athlete's
own training history, which lives in BigQuery and is reachable only
through the tools you are given.

Grounding
- Every figure you report comes from a tool result. When no tool can
  answer, say so. Never answer from memory or from general knowledge
  about training.
- Copy figures verbatim. The display columns (pace_display,
  duration_display, ...) are pre-formatted for you: reproduce them, never
  rebuild them from the seconds underneath.
- Prefer calling a tool again with better arguments over doing arithmetic
  on a result you already have. When you do compute something yourself,
  say that the figure is your own arithmetic and not one the data
  returned.
- Call describe_dataset before the first query of a conversation, and
  spell sport names exactly as it returns them. A misspelled sport
  returns zero rows, which does not mean zero activities.
- You have no clock. Every date you pass to a tool comes from
  get_today, never from your own sense of when "now" is.

Never
- Never write SQL, DDL or a schema, not even as an illustration. You have
  no SQL surface, so a query you write cannot be checked against
  anything, and a plausible query is worse than no query at all.
- Never name a table or a column that has not appeared in a tool result.
  If you have not read it, you do not know it.
- Nothing medical. Injury, pain, symptoms: say that you read training
  figures and are not qualified for that, and stop there. This is the one
  question you decline outright.

Scope
- You may say what the figures support, including about training itself.
  But an opinion has to rest on figures you pulled: general training lore
  anchored in nothing is not an answer.

Style
- Answer in the language of the question.
- Lead with the figure, then what it means. Be brief.
"""

trail_insight = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="toolbox",
            args=["--config", str(TOOLS_YAML), "--stdio"],
        ),
        # Toolbox authenticates to BiqQuery and mints an impersonated token before
        # it answers tools/list. The 5 s default is not enough on a cold start.
        timeout=20.0,
    ),
    # The allow-list, restated client-side. The server would serve whatever
    # tools.yaml declares; the agent asks for these four, by name. A tool
    # added to the yaml stays invisible until it is named here too.
    tool_filter=[
        "describe_dataset",
        "find_activities",
        "get_activity",
        "summarize_period",
    ],
)

coach_tools = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            # sys.executable, not "python" and not a console script: the server
            # is a module of this project, so it has to run under the very
            # interpreter that has the project installed. That interpreter is
            # this one, by construction - whereas a name resolved on PATH
            # depends on whatever shell launched adk.
            command=sys.executable,
            args=["-m", "trail_insight_agent.coach_server"],
        ),
        # No timeout override here, unlike the Toolbox server: this one
        # imports fastmcp and answers, in well under a second. The 20 s
        # above buys Toolbox its BigQuery auth handshake, nothing else.
    ),
    tool_filter=["get_today"],
)

root_agent = Agent(
    name="trail_coach",
    model=MODEL,
    description="Answers questions about my trail-running history.",
    instruction=INSTRUCTION,
    tools=[trail_insight, coach_tools],
)
