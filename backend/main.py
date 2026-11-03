"""Campus Customs backend API for the React dashboard.

Start it from the backend/ folder:

    uvicorn main:app --reload --port 8000

Every shop fact comes from the campus-customs MCP server over data/campus_customs_new.db
(the same tools the agents use). Agent events come from output/audit_trail.json, which
the agents append to as they work.

Routes
    GET  /tickets                          the tickets and whether each is open or resolved
    GET  /tickets/{ticket_id}/summary      what each agent did on that ticket (all runs since the reset)
    POST /tickets/{ticket_id}/run          start the agent team on one ticket (returns a run id)
    GET  /runs/{run_id}                    status and Boss decision for a started run
    GET  /events                           recent agent events: what each agent said, tools used
    GET  /approvals                        approval requests (pending by default)
    POST /approvals/{request_id}/approve   a human approves; this is what pays and changes cash
    POST /approvals/{request_id}/reject    a human rejects
    GET  /cash                             checking balance from cash_accounts
    GET  /drafts                           drafted messages (never sent)
    POST /reset                            reset the working DB to the original values
    GET  /health                           server is up; whether an agent run is in progress

Agent runs take about a minute, so POST /tickets/{id}/run starts the run in the
background and returns right away. Poll GET /events?after=<last id> to watch the agents,
and GET /runs/{run_id} for the result. One run at a time: tickets share one cash balance,
so a second run (or a reset) while one is going is refused with 409.
"""

import asyncio
import json
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

# `uvicorn main:app` runs from backend/, so put the project folder on the path for `backend.*`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from backend import approvals, team  # noqa: E402
from backend.config import AUDIT_TRAIL, MODEL  # noqa: E402
from backend.mcp_tools import MCP  # noqa: E402
from backend.models import AgentName, ApprovalDecision  # noqa: E402

FINAL_STATUSES = team.FINAL_STATUSES
AGENT_NAMES = {a.value for a in AgentName}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Keep one MCP server process open for the life of the API instead of one per request.
    async with MCP:
        yield


app = FastAPI(title="Campus Customs API", version="1.0", lifespan=lifespan)
# The React desk runs on the Vite dev server (http://localhost:5173); any other local port
# (vite preview, a second dev server) is allowed too. Nothing outside this machine is.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_methods=["*"],
    allow_headers=["*"],
)

RUNS: dict[str, dict] = {}  # run_id -> status for runs started through this API
_current: asyncio.Task | None = None
_current_ticket: int | None = None


def _busy() -> bool:
    return _current is not None and not _current.done()


def _running_ticket() -> int | None:
    return _current_ticket if _busy() else None


def _read_trail() -> list[dict]:
    try:
        return json.loads(AUDIT_TRAIL.read_text(encoding="utf-8")) if AUDIT_TRAIL.exists() else []
    except (ValueError, OSError):
        raise HTTPException(503, "The audit trail is being written; try again.")


async def mcp(name: str, args: dict | None = None):
    return await MCP.direct_call_tool(name, args or {})


class HumanDecision(BaseModel):
    approver: str = Field(min_length=1, description="The person clicking the button.")
    note: str = ""


# --------------------------------------------------------------------------- tickets

@app.get("/tickets")
async def list_tickets():
    """The tickets on the board and whether each is open or resolved.

    state is "resolved" once the agent team has finished working the ticket and the Boss has
    made the final call (its status is no longer "open"), "running" while agents are on it,
    and "open" before that. status keeps the Boss's detail (awaiting_approval, in_progress,
    resolved, declined...), and closed is true only for resolved/declined.
    """
    board = await mcp("list_tickets")
    pending = (await mcp("list_approval_requests", {"status": "pending"}))["requests"]
    running = _running_ticket()
    tickets = []
    for t in board["tickets"]:
        tickets.append({
            "id": t["id"], "type": t["type"], "requester": t["requester"], "subject": t["subject"],
            "status": t["status"],
            "state": "running" if t["id"] == running else ("open" if t["status"] == "open" else "resolved"),
            "closed": t["status"] in FINAL_STATUSES,
            "pending_approval_ids": [r["id"] for r in pending if r["ticket_id"] == t["id"]],
            "sku": t["sku"], "size": t["size"], "qty": t["qty"],
            "lease_id": t["lease_id"], "invoice_id": t["invoice_id"],
            "notes": t["notes"], "created_at": t["created_at"],
        })
    return {"count": len(tickets),
            "open": sum(t["state"] != "resolved" for t in tickets),
            "resolved": sum(t["state"] == "resolved" for t in tickets),
            "running_ticket": running,
            "tickets": tickets}


@app.get("/tickets/{ticket_id}/summary")
async def ticket_summary(ticket_id: int):
    """What each agent did on this ticket since the last reset, across every run of it (a
    ticket is often run again after a human signs): the Boss's latest call, and per agent its
    reports, actions, tools used, requests and drafts. first_event_id lets the desk load the
    ticket's whole transcript (including human signatures) from /events."""
    trail = _read_trail()
    last_reset = max((i for i, e in enumerate(trail) if e["step_type"] == "reset"), default=-1)
    mine = [(i, e) for i, e in enumerate(trail) if i > last_reset and e.get("ticket_id") == ticket_id]
    run_ids = list(dict.fromkeys(e["run_id"] for _, e in mine
                                 if e["actor"] == "boss" and e["step_type"] == "prompt" and e["depth"] == 0))
    if not run_ids:
        return {"ticket_id": ticket_id, "run_id": None, "run_ids": [], "agents": [], "decision": None}
    steps = [e for _, e in mine if e["run_id"] in run_ids]
    agents: dict[str, dict] = {}
    for e in steps:
        if e["actor_type"] != "agent":
            continue
        a = agents.setdefault(e["actor"], {"agent": e["actor"], "runs": 0, "tools": {}, "asked_by": set(),
                                           "summary": None, "actions": [], "approval_request_ids": [],
                                           "draft_ids": [], "blockers": [], "recommendation": None})
        if e["step_type"] == "prompt":
            a["runs"] += 1
            if e.get("delegated_by"):
                a["asked_by"].add(e["delegated_by"])
        for c in e.get("tool_calls", []):
            a["tools"][c["tool"]] = a["tools"].get(c["tool"], 0) + 1
        out = e.get("output") if e["step_type"] == "final_output" else None
        if isinstance(out, dict):
            a["summary"] = out.get("summary") or out.get("decision")
            a["recommendation"] = out.get("recommendation") or out.get("reasoning")
            a["actions"] += out.get("actions_taken", [])
            # Only blockers from the ticket's latest run are still current.
            a["blockers"] = out.get("blockers", []) if e["run_id"] == run_ids[-1] else []
            a["approval_request_ids"] += out.get("approval_request_ids", [])
            a["draft_ids"] += out.get("draft_ids", [])
    order = [n.value for n in AgentName]
    result = [{**a, "asked_by": sorted(a["asked_by"]),
               "approval_request_ids": sorted(set(a["approval_request_ids"])),
               "draft_ids": sorted(set(a["draft_ids"]))}
              for a in sorted(agents.values(), key=lambda a: order.index(a["agent"]))]
    boss_out = next((e["output"] for e in reversed(steps)
                     if e["actor"] == "boss" and e["step_type"] == "final_output" and e["depth"] == 0), None)
    usage = {k: sum(u[k] for u in (next((e["run_usage"] for e in reversed(steps) if e["run_id"] == r and e.get("run_usage")), None)
                                   for r in run_ids) if u) for k in ("requests", "tool_calls", "input_tokens", "output_tokens")}
    errors = [e["error"] for e in steps if e["step_type"] == "error" and e["depth"] == 0]
    return {"ticket_id": ticket_id, "run_id": run_ids[-1], "run_ids": run_ids, "first_event_id": mine[0][0] - 1,
            "started_at": steps[0]["recorded_at"], "finished_at": steps[-1]["recorded_at"],
            "running": _running_ticket() == ticket_id, "decision": boss_out,
            "error": errors[-1] if errors else None, "usage": usage, "agents": result}


@app.post("/tickets/{ticket_id}/run", status_code=202)
async def run_ticket(ticket_id: int):
    """Start the agent team (Boss first) on one ticket. Returns the run id at once."""
    global _current, _current_ticket
    found = await mcp("get_ticket", {"ticket_id": ticket_id})
    if not found.get("found"):
        raise HTTPException(404, f"No ticket {ticket_id}.")
    if _busy():
        raise HTTPException(409, "An agent run is already in progress; wait for it to finish.")
    if MODEL.startswith("anthropic:") and not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(503, "ANTHROPIC_API_KEY is not set in the server's environment.")

    run_id = uuid.uuid4().hex[:8]
    RUNS[run_id] = {"run_id": run_id, "ticket_id": ticket_id, "status": "running",
                    "started_at": datetime.now(timezone.utc).isoformat(), "decision": None, "error": None}

    async def work():
        run = await team.run_ticket(ticket_id, run_id)
        RUNS[run_id].update(status="error" if run.error else "done", error=run.error,
                            finished_at=run.finished_at.isoformat(),
                            decision=run.decision.model_dump(mode="json") if run.decision else None)

    _current_ticket = ticket_id
    _current = asyncio.create_task(work())
    return {**RUNS[run_id], "poll": {"events": f"/events?run_id={run_id}", "result": f"/runs/{run_id}"}}


@app.get("/runs/{run_id}")
async def get_run(run_id: str):
    """Status of a run started through POST /tickets/{id}/run, with the Boss's decision when done."""
    if run_id not in RUNS:
        raise HTTPException(404, f"No run {run_id} started by this server.")
    return RUNS[run_id]


# --------------------------------------------------------------------------- agent events

def _said(e: dict) -> str | None:
    if e.get("text"):
        return e["text"]
    out = e.get("output")
    if isinstance(out, dict):
        return out.get("decision") or out.get("summary")
    return e.get("error")


@app.get("/events")
async def recent_events(
    after: int = Query(-1, description="Only events with id greater than this (the last id you saw)."),
    limit: int = Query(50, ge=1, le=500),
    ticket_id: int | None = None,
    run_id: str | None = None,
    agent: str | None = Query(None, description="boss, inventory, accounting, facilities, customer_service"),
):
    """Recent agent events from the audit trail: who acted, what they said, which tools they
    called and what came back. Pass after=<last id> to fetch only new events while a run is going."""
    trail = _read_trail()
    events = []
    for i, e in enumerate(trail):
        if i <= after or (ticket_id is not None and e.get("ticket_id") != ticket_id):
            continue
        if (run_id and e.get("run_id") != run_id) or (agent and e.get("actor") != agent):
            continue
        events.append({
            "id": i,
            "at": e["recorded_at"],
            "run_id": e["run_id"],
            "ticket_id": e.get("ticket_id"),
            "agent": e["actor"],
            "actor_type": e["actor_type"],
            "delegated_by": e.get("delegated_by"),
            "depth": e.get("depth", 0),
            "step": e.get("step"),
            "step_type": e["step_type"],
            "said": _said(e),
            "tools_called": [{"tool": c["tool"], "args": c.get("args")} for c in e.get("tool_calls", [])],
            "tool_results": [{"tool": r["tool"], "refused": r["refused"], "result": r["result"]}
                             for r in e.get("tool_results", [])],
            "usage": e.get("run_usage"),
        })
    events = events[-limit:]
    return {"count": len(events), "last_id": events[-1]["id"] if events else max(after, len(trail) - 1),
            "running": _busy(), "running_ticket": _running_ticket(), "events": events}


# --------------------------------------------------------------------------- approvals & cash

@app.get("/approvals")
async def list_approvals(status: str | None = Query("pending", description="pending, approved, rejected, paid, or all")):
    """Payment and purchase-order requests the agents prepared, waiting on a human by default."""
    return await mcp("list_approval_requests", {} if status in (None, "all") else {"status": status})


async def _decide(request_id: int, approve: bool, body: HumanDecision):
    if body.approver.strip().lower() in AGENT_NAMES:
        raise HTTPException(403, "Approvals must come from a person, not an agent.")
    result = await approvals.decide(ApprovalDecision(request_id=request_id, approve=approve,
                                                     approver=body.approver, note=body.note))
    if not result.get("ok") and "pay_result" not in result:
        raise HTTPException(409, result.get("message", "Request could not be decided."))
    return {**result, "cash": await mcp("get_cash_balance")}


@app.post("/approvals/{request_id}/approve")
async def approve(request_id: int, body: HumanDecision):
    """A human approves a pending payment or purchase order. This is the only route that moves
    money: it records the approval, then pays (pay refuses if checking can't cover it)."""
    return await _decide(request_id, True, body)


@app.post("/approvals/{request_id}/reject")
async def reject(request_id: int, body: HumanDecision):
    """A human rejects a pending request. No money moves."""
    return await _decide(request_id, False, body)


@app.get("/cash")
async def cash():
    """Current checking balance from cash_accounts, plus what is requested but not yet paid."""
    return await mcp("get_cash_balance")


@app.get("/drafts")
async def drafts(ticket_id: int | None = None):
    """Messages the agents drafted. Nothing is ever sent."""
    return await mcp("list_drafts", {"ticket_id": ticket_id} if ticket_id else {})


# --------------------------------------------------------------------------- admin

@app.post("/reset")
async def reset():
    """Reset the working database (campus_customs_new.db) to the original values for a fresh run."""
    if _busy():
        raise HTTPException(409, "An agent run is in progress; reset after it finishes.")
    RUNS.clear()
    return await team.reset_database(actor="dashboard")


@app.get("/")
async def index():
    """Route list (interactive docs at /docs)."""
    return {"app": "Campus Customs API", "docs": "/docs",
            "routes": sorted({f"{m} {r.path}" for r in app.routes if hasattr(r, "methods")
                              for m in r.methods if m in ("GET", "POST")} - {"GET /docs", "GET /redoc",
                              "GET /openapi.json", "GET /docs/oauth2-redirect"})}


@app.get("/health")
async def health():
    shop = await mcp("get_shop_date")
    return {"ok": True, "model": MODEL, "running": _busy(), "running_ticket": _running_ticket(),
            "shop_date": shop["date_today"], "api_key_set": bool(os.environ.get("ANTHROPIC_API_KEY"))}
