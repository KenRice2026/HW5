"""The one connection to the campus-customs MCP server, shared by every agent.

`MCP` is a PydanticAI MCPToolset over stdio. Each agent gets `toolset_for(agent)`, a
filtered view limited to that role's tools. Every tool call an agent makes is written to
the ticket's trace (and refusals from the server, like an unapproved payment, are marked
as such). `call_tool` lets the run loop and the human-approval code call a tool directly.
"""

import json
import os
from datetime import datetime, timezone

from fastmcp.client.transports import PythonStdioTransport
from pydantic_ai import RunContext
from pydantic_ai.mcp import MCPToolset

from backend.config import MCP_SERVER_SCRIPT, PROJECT_DIR, PYTHON, ROLE_TOOLS, WORKING_DB
from backend.models import AgentName, TeamDeps, TraceEvent, TraceKind

RESULT_CHARS = 600


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _summarize(value) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= RESULT_CHARS else text[:RESULT_CHARS] + "..."


def _refused(result) -> bool:
    return isinstance(result, dict) and (result.get("ok") is False or result.get("found") is False)


async def _trace_tool_call(ctx: RunContext[TeamDeps], call_tool, name: str, args: dict):
    deps = ctx.deps
    deps.trace.append(TraceEvent(at=_now(), kind=TraceKind.TOOL_CALL, agent=deps.agent, depth=deps.depth,
                                 ticket_id=deps.ticket_id, target=name, detail=_summarize(args)))
    result = await call_tool(name, args)
    deps.trace.append(TraceEvent(at=_now(), kind=TraceKind.REFUSED if _refused(result) else TraceKind.TOOL_RESULT,
                                 agent=deps.agent, depth=deps.depth, ticket_id=deps.ticket_id,
                                 target=name, detail=_summarize(result)))
    return result


MCP = MCPToolset(
    PythonStdioTransport(
        MCP_SERVER_SCRIPT,
        python_cmd=PYTHON,
        cwd=str(PROJECT_DIR),
        env={**os.environ, "CC_DB_PATH": str(WORKING_DB)},
    ),
    id="campus-customs",
    process_tool_call=_trace_tool_call,
)


def toolset_for(agent: AgentName):
    allowed = ROLE_TOOLS[agent]
    return MCP.filtered(lambda ctx, tool_def: tool_def.name in allowed)


async def call_tool(name: str, args: dict | None = None):
    """Call an MCP tool outside any agent (run loop bookkeeping, human approvals)."""
    async with MCP:
        return await MCP.direct_call_tool(name, args or {})
