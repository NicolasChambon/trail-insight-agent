"""Phase 5.2 - the ADK agent, wired tot he four BigQuery tools over MCP.

The tools are not defined here. They live in mcp/tools.yaml and are served by
the MCP Toolbox binary, which ADK starts as a child process and talks to over
stdio - exactly the way Claude Code reaches the same server through .mcp.json.
One server, one servervice account, one security surface to audit.
"""

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

root_agent = Agent(
    name="trail_coach",
    model=MODEL,
    description="Answers questions about my trail-running history.",
    instruction=(
        "You answer questions about the user's trail-running history. "
        "Never answer from memory when a tool can answer: every figure you "
        "report comes from a tool call. Call describe_dataset first in a "
        "conversation, then follow the guidance carried by each tool's own "
        "description. Answer in the language of the question."
    ),
    tools=[trail_insight],
)
