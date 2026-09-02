"""List what the FastMCP server would send a model, without running one.

The Toolbox server has `toolbox ... invoke <tool>`; this one had nothing. It
connects an in-process MCP client straight to the server object - no
subprocess, no stdio, no network, no Google - and prints the contract that
tools/list publishes.

It reads the contract, it does not exercise it. The annotations are the point:
they do nothing today and will be read by the phase 7 callbacks, so a wrong one
is a guardrail that lets a write through while looking like it worked. This is
where you see that schedule_session says WRITES.

Usage: uv run scripts/mcp_smoke.py
"""

import asyncio

from fastmcp import Client

from trail_insight_agent.coach_server import mcp


async def main() -> None:
    async with Client(mcp) as client:
        for tool in await client.list_tools():
            hints = tool.annotations
            kind = "reads " if hints and hints.readOnlyHint else "WRITES"
            print(f"{kind}  {tool.name:24}  {hints}")


if __name__ == "__main__":
    asyncio.run(main())
