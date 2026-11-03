"""Builds a Campus Customs agent, the `delegate` tool that connects every agent to every
other agent, and `run_agent`, the audited agent loop all runs go through.

Each agent is a PydanticAI Agent with: its prompt from backend/prompts/<name>.md, its
filtered view of the MCP tools, a structured output type, and `delegate(to, task)`.
Delegation runs the other agent as a nested run that shares the ticket's usage budget,
limits and trace, so the dashboard sees the whole conversation. The only limits on who
can call whom are: not yourself, and not deeper than MAX_DELEGATION_DEPTH.

run_agent() steps through the agent graph node by node (agent.iter) and appends every
step to output/audit_trail.json as it happens.
"""

import uuid
from datetime import datetime, timezone

from pydantic_ai import Agent, NativeOutput, RunContext

from backend import audit
from backend.config import MAX_DELEGATION_DEPTH, MODEL, PROMPTS_DIR, TICKET_LIMITS, model_settings
from backend.mcp_tools import toolset_for
from backend.models import AgentName, TeamDeps, TraceEvent, TraceKind

# Filled by backend/agents/__init__.py once all five agents exist.
TEAM: dict[AgentName, Agent] = {}

ROSTER = """\
## Delegation

You can hand work to any teammate with `delegate(to, task)`:
- `boss`: routes tickets and makes final calls.
- `inventory`: stock by SKU and size, shortfalls, restock vendor and lead time, reserving stock.
- `accounting`: cash, invoices, margins and discounts, payment requests and purchase orders for human approval.
- `facilities`: the shop space, leases, rent amount and due dates.
- `customer_service`: drafts messages to customers, the landlord or vendors (never sent).
Write the task so it stands alone (the teammate sees only what you write): the ticket id, the exact
SKU/size/qty or invoice/lease id, and what you need back. Don't delegate what your own tools can answer.
"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def run_agent(name: AgentName, prompt: str, deps: TeamDeps, *, usage=None):
    """Run one agent's loop, auditing each step. Returns the PydanticAI run result."""
    deps.agent_run_id = deps.agent_run_id or uuid.uuid4().hex[:12]
    agent = TEAM[name]
    audit.record_prompt(deps, prompt, MODEL)
    step = 0
    async with agent.iter(prompt, deps=deps, usage=usage, usage_limits=TICKET_LIMITS) as run:
        try:
            async for node in run:
                if audit.record_node(node, deps, step + 1, run.usage):
                    step += 1
        except Exception as exc:
            audit.record_error(deps, step + 1, exc, run.usage)
            raise
        audit.record_output(deps, step + 1, run.result.output, run.usage)
        return run.result


async def delegate(ctx: RunContext[TeamDeps], to: AgentName, task: str) -> str:
    """Hand a task to another Campus Customs agent and get back its report (JSON).

    Args:
        to: The teammate: boss, inventory, accounting, facilities or customer_service.
        task: A complete, self-contained request: ticket id, the exact items or ids
            involved, and what you need back.
    """
    me = ctx.deps
    if to == me.agent:
        me.trace.append(TraceEvent(at=_now(), kind=TraceKind.REFUSED, agent=me.agent, depth=me.depth,
                                   ticket_id=me.ticket_id, target=to.value, detail="delegation to self"))
        return f"Refused: you are {to.value}; do this work with your own tools instead of delegating to yourself."
    if me.depth >= MAX_DELEGATION_DEPTH:
        me.trace.append(TraceEvent(at=_now(), kind=TraceKind.REFUSED, agent=me.agent, depth=me.depth,
                                   ticket_id=me.ticket_id, target=to.value,
                                   detail=f"delegation depth limit {MAX_DELEGATION_DEPTH} reached"))
        return (f"Refused: the delegation chain {' -> '.join(a.value for a in me.chain + [me.agent])} is already "
                f"{me.depth} deep (limit {MAX_DELEGATION_DEPTH}). Finish with the information you have.")

    me.trace.append(TraceEvent(at=_now(), kind=TraceKind.DELEGATE, agent=me.agent, depth=me.depth,
                               ticket_id=me.ticket_id, target=to.value, detail=task))
    sub = TeamDeps(ticket_id=me.ticket_id, agent=to, run_id=me.run_id, parent_agent_run_id=me.agent_run_id,
                   depth=me.depth + 1, chain=me.chain + [me.agent], trace=me.trace)
    result = await run_agent(to, task, sub, usage=ctx.usage)
    report = result.output.model_dump_json()
    me.trace.append(TraceEvent(at=_now(), kind=TraceKind.AGENT_RESULT, agent=to, depth=sub.depth,
                               ticket_id=me.ticket_id, target=me.agent.value, detail=report))
    return report


def make_agent(name: AgentName, output_type) -> Agent:
    agent = Agent(
        MODEL,
        name=name.value,
        deps_type=TeamDeps,
        output_type=NativeOutput(output_type),
        instructions=[(PROMPTS_DIR / f"{name.value}.md").read_text(encoding="utf-8"), ROSTER],
        toolsets=[toolset_for(name)],
        tools=[delegate],
        model_settings=model_settings(name),
        retries=2,
        defer_model_check=True,  # ANTHROPIC_API_KEY is only needed when an agent actually runs
    )

    @agent.instructions
    def where_am_i(ctx: RunContext[TeamDeps]) -> str:
        d = ctx.deps
        asked_by = d.chain[-1].value if d.chain else "the run loop"
        return (f"You are the {name.value} agent. Ticket in focus: {d.ticket_id}. "
                f"This task came from: {asked_by}. Delegation depth {d.depth} of {MAX_DELEGATION_DEPTH}.")

    return agent
