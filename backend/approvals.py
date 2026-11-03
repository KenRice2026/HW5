"""The human side of payments: a person approves or rejects a pending request.

No agent can reach this. The dashboard (or the CLI) calls decide() with a person's name;
it records the decision through the MCP tool decide_approval_request (which agents never
see and which refuses agent names), then, on approval, calls the MCP `pay` tool, which
re-checks the amount and refuses if checking can't cover it. If pay refuses, the request
stays 'approved' (but unpaid) and the refusal is returned so the person can see why.
Both steps are appended to output/audit_trail.json with the person as the actor.
"""

import uuid

from backend import audit
from backend.mcp_tools import call_tool
from backend.models import ApprovalDecision, StepType


async def decide(d: ApprovalDecision) -> dict:
    run_id = uuid.uuid4().hex[:8]
    args = {"request_id": d.request_id, "approve": d.approve, "approver": d.approver, "note": d.note}
    decision = await call_tool("decide_approval_request", args)
    ticket_id = (decision.get("request") or {}).get("ticket_id")
    audit.record_action(run_id, d.approver, "human", StepType.HUMAN_DECISION, ticket_id=ticket_id,
                        tool="decide_approval_request", args=args, result=decision)
    if not decision.get("ok"):
        return decision
    if not d.approve:
        return {"ok": True, "status": "rejected", "request_id": d.request_id}

    payment = await call_tool("pay", {"request_id": d.request_id})
    audit.record_action(run_id, d.approver, "human", StepType.PAYMENT, ticket_id=ticket_id,
                        tool="pay", args={"request_id": d.request_id}, result=payment)
    return {"ok": bool(payment.get("ok")), "status": "approved", "request_id": d.request_id, "pay_result": payment}
