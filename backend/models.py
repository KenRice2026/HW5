"""Structured data types for the Campus Customs agent team.

`AgentName` names the five roles. Specialists (Inventory, Accounting, Facilities,
Customer Service) answer with an `AgentReport`; the Boss answers with a `BossDecision`
for the ticket it was given. `TeamDeps` is what every agent run carries: which ticket
it is working, who asked it, how deep the delegation chain is, and the shared trace.
`TraceEvent` is one line of that trace (a delegation, an MCP tool call, a result), so
the dashboard can show the agents at work. `TicketRun` and `BoardRun` are what one
ticket run / one pass over the board return, and `ApprovalDecision` is a human's
yes/no on a pending payment or purchase order. `AuditRecord` is one entry in
output/audit_trail.json: one step of one agent's loop (or a loop/human action).
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentName(str, Enum):
    BOSS = "boss"
    INVENTORY = "inventory"
    ACCOUNTING = "accounting"
    FACILITIES = "facilities"
    CUSTOMER_SERVICE = "customer_service"


class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    AWAITING_APPROVAL = "awaiting_approval"  # a payment or PO is waiting on a human
    WAITING_ON_VENDOR = "waiting_on_vendor"  # ordered; waiting for the vendor's lead time
    RESOLVED = "resolved"
    DECLINED = "declined"


class Fact(BaseModel):
    """One number or fact an agent read from the database, with where it came from."""

    label: str = Field(description="What this is, e.g. 'CC-TEE-WHITE S on hand'.")
    value: str = Field(description="The value exactly as the tool returned it.")
    source: str = Field(description="MCP tool (and table) it came from, e.g. 'check_stock / inventory'.")


class AgentReport(BaseModel):
    """What a specialist hands back to whoever delegated to it."""

    agent: AgentName
    ticket_id: int | None = None
    summary: str = Field(description="Two or three sentences: what was asked and what was found or done.")
    facts: list[Fact] = Field(default_factory=list, description="Database facts the summary relies on.")
    actions_taken: list[str] = Field(default_factory=list,
                                     description="Changes made through tools (requests filed, drafts saved, stock reserved).")
    approval_request_ids: list[int] = Field(default_factory=list,
                                            description="Approval requests created or found that a human must decide.")
    draft_ids: list[int] = Field(default_factory=list, description="Drafts saved on the board.")
    blockers: list[str] = Field(default_factory=list,
                                description="What stops progress (out of stock, vendor blocked, not enough cash).")
    recommendation: str = Field(description="What this agent recommends the Boss decide or do next.")


class BossDecision(BaseModel):
    """The Boss's final call on one ticket."""

    ticket_id: int
    ticket_type: str
    assigned_to: list[AgentName] = Field(description="Agents the Boss delegated to, in order.")
    decision: str = Field(description="The final call in plain words, e.g. 'Approve 10% bulk discount...'.")
    final_status: TicketStatus
    approval_request_ids: list[int] = Field(default_factory=list,
                                            description="Requests now waiting on a human on the dashboard.")
    draft_ids: list[int] = Field(default_factory=list, description="Drafts saved for a human to review and send.")
    waiting_on_human: bool = Field(description="True if anything on this ticket needs a person before it can move.")
    reasoning: str = Field(description="Why, citing the database facts behind the call.")
    next_steps: list[str] = Field(default_factory=list,
                                  description="What happens next, including what to do after approvals.")


class TraceKind(str, Enum):
    RUN_START = "run_start"
    DELEGATE = "delegate"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    AGENT_RESULT = "agent_result"
    REFUSED = "refused"
    RUN_END = "run_end"


class TraceEvent(BaseModel):
    at: datetime
    kind: TraceKind
    agent: AgentName
    depth: int
    ticket_id: int | None = None
    target: str | None = Field(default=None, description="Delegated-to agent or MCP tool name.")
    detail: str = ""


@dataclass
class TeamDeps:
    """Carried by every agent run. A delegated run gets a copy with agent/depth/chain updated
    and the same trace list, so one ticket's whole conversation lands in one trace.
    agent_run_id / parent_agent_run_id link each run to the one that delegated to it."""

    ticket_id: int | None
    agent: AgentName
    run_id: str = ""
    agent_run_id: str = ""
    parent_agent_run_id: str | None = None
    depth: int = 0
    chain: list[AgentName] = field(default_factory=list)
    trace: list[TraceEvent] = field(default_factory=list)


class TicketRun(BaseModel):
    run_id: str
    ticket_id: int
    started_at: datetime
    finished_at: datetime
    decision: BossDecision | None
    error: str | None = None
    trace: list[TraceEvent]


class BoardRun(BaseModel):
    run_id: str
    reset_first: bool
    started_at: datetime
    finished_at: datetime
    tickets: list[TicketRun]


class ApprovalDecision(BaseModel):
    """A human's decision on one pending approval request (from the dashboard or CLI)."""

    request_id: int
    approve: bool
    approver: str = Field(min_length=1, description="The person deciding. Agent names are not accepted.")
    note: str = ""


class StepType(str, Enum):
    PROMPT = "prompt"                  # the task an agent was given
    MODEL_REQUEST = "model_request"    # what was sent back to the model (tool results, retries)
    MODEL_RESPONSE = "model_response"  # the model's reply: text and/or tool calls
    FINAL_OUTPUT = "final_output"      # the agent's validated structured answer
    ERROR = "error"                    # the agent run failed (limits, API, validation)
    TICKET_UPDATE = "ticket_update"    # run loop wrote the Boss's decision to the ticket
    RESET = "reset"                    # working DB reset from the original
    HUMAN_DECISION = "human_decision"  # a person approved or rejected a request
    PAYMENT = "payment"                # pay() result after a human approval


class AuditToolCall(BaseModel):
    tool: str
    tool_call_id: str | None = None
    args: Any = None


class AuditToolResult(BaseModel):
    tool: str
    tool_call_id: str | None = None
    result: str = Field(description="Tool output as JSON text, truncated if very long.")
    refused: bool = Field(description="The tool said no (ok=false / not found / 'Refused...').")
    retry: bool = Field(default=False, description="The framework asked the model to retry this call.")


class StepUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


class RunUsageSnapshot(BaseModel):
    """Cumulative usage for the whole ticket (all agents) at the time of this step."""

    requests: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class AuditRecord(BaseModel):
    """One entry in output/audit_trail.json. Entries are only ever appended."""

    recorded_at: datetime
    run_id: str
    ticket_id: int | None = None
    actor: str = Field(description="Agent name, 'run_loop', or the approving person's name.")
    actor_type: Literal["agent", "system", "human"]
    agent_run_id: str | None = None
    parent_agent_run_id: str | None = Field(default=None, description="The agent run that delegated this one.")
    delegated_by: str | None = None
    depth: int = 0
    step: int = 0
    step_type: StepType
    model: str | None = None
    prompt_version: str | None = Field(default=None, description="sha256 prefix of the agent's prompt file.")
    text: str | None = None
    thinking: str | None = None
    tool_calls: list[AuditToolCall] = Field(default_factory=list)
    tool_results: list[AuditToolResult] = Field(default_factory=list)
    output: Any = None
    usage: StepUsage | None = None
    run_usage: RunUsageSnapshot | None = None
    error: str | None = None
