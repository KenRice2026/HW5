"""The agent loop: work one ticket, or pass over the whole board.

run_ticket(id): the Boss reads the ticket, delegates to teammates (who may delegate to
each other), and returns a BossDecision. The loop then writes that decision to the ticket
(status + note) through the MCP update_ticket tool and saves the full trace to
output/runs/. Every step of every agent is appended to output/audit_trail.json.

run_board(): resets the working database to the original first (the rule for a full run),
then works every ticket that isn't resolved or declined, one at a time, so each ticket
sees the cash and stock left by the ones before it. Pass reset=False to continue after a
human has approved requests.

All shop data, including the reset, goes through the MCP server.
"""

import uuid
from datetime import datetime, timezone

from backend import audit
from backend.agents import base
from backend.config import RUNS_DIR
from backend.mcp_tools import MCP, call_tool
from backend.models import AgentName, BoardRun, StepType, TeamDeps, TicketRun, TraceEvent, TraceKind

FINAL_STATUSES = {"resolved", "declined"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _run_id() -> str:
    return uuid.uuid4().hex[:8]


async def reset_database(run_id: str | None = None, actor: str = "operator") -> dict:
    """Copy the untouched original over the working database (MCP reset_working_database)."""
    result = await call_tool("reset_working_database")
    audit.record_action(run_id or _run_id(), actor, "system", StepType.RESET,
                        tool="reset_working_database", args={}, result=result)
    if not result.get("ok"):
        raise RuntimeError(result.get("message", "reset failed"))
    return result


def _save(name: str, model) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    (RUNS_DIR / f"{name}.json").write_text(model.model_dump_json(indent=2), encoding="utf-8")


async def run_ticket(ticket_id: int, run_id: str | None = None) -> TicketRun:
    run_id = run_id or _run_id()
    started = _now()
    deps = TeamDeps(ticket_id=ticket_id, agent=AgentName.BOSS, run_id=run_id)
    deps.trace.append(TraceEvent(at=started, kind=TraceKind.RUN_START, agent=AgentName.BOSS, depth=0,
                                 ticket_id=ticket_id, detail=f"run {run_id}"))
    decision, error = None, None
    try:
        async with MCP:
            result = await base.run_agent(
                AgentName.BOSS,
                f"Work ticket {ticket_id}. Read it, delegate to the right teammates, and make the final call.",
                deps,
            )
            decision = result.output
            args = {"ticket_id": ticket_id, "agent": "boss", "status": decision.final_status.value,
                    "note": decision.decision}
            update = await MCP.direct_call_tool("update_ticket", args)
            audit.record_action(run_id, "run_loop", "system", StepType.TICKET_UPDATE, ticket_id=ticket_id,
                                tool="update_ticket", args=args, result=update)
    except Exception as exc:  # the run is still recorded, with what happened before the failure
        error = f"{type(exc).__name__}: {exc}"
    deps.trace.append(TraceEvent(at=_now(), kind=TraceKind.RUN_END, agent=AgentName.BOSS, depth=0,
                                 ticket_id=ticket_id, detail=error or (decision.final_status.value if decision else "")))
    run = TicketRun(run_id=run_id, ticket_id=ticket_id, started_at=started, finished_at=_now(),
                    decision=decision, error=error, trace=deps.trace)
    _save(f"ticket_{ticket_id}_{run_id}", run)
    return run


async def run_board(reset: bool = True) -> BoardRun:
    run_id = _run_id()
    started = _now()
    if reset:
        await reset_database(run_id, actor="run_loop")
    board = await call_tool("list_tickets")
    todo = [t["id"] for t in board["tickets"] if t["status"] not in FINAL_STATUSES]
    runs = [await run_ticket(tid, run_id) for tid in todo]
    board_run = BoardRun(run_id=run_id, reset_first=reset, started_at=started, finished_at=_now(), tickets=runs)
    _save(f"board_{run_id}", board_run)
    return board_run
