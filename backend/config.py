"""Settings shared by the Campus Customs backend: paths, model, and which MCP tools each
agent may use.

All five agents reach the database only through the campus-customs MCP server
(mcp_server/server.py), started once per process over stdio. Each agent sees a filtered
view of that server's tools (ROLE_TOOLS), so, for example, only Accounting can file
payment requests and only Customer Service can save drafts.
"""

import os
import sys
from pathlib import Path

from pydantic_ai import UsageLimits
from pydantic_ai.models.anthropic import AnthropicModelSettings

from backend.models import AgentName

PROJECT_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = PROJECT_DIR / "backend" / "prompts"
MCP_SERVER_SCRIPT = PROJECT_DIR / "mcp_server" / "server.py"
WORKING_DB = Path(os.environ.get("CC_DB_PATH", PROJECT_DIR / "data" / "campus_customs_new.db"))
RUNS_DIR = PROJECT_DIR / "output" / "runs"
AUDIT_TRAIL = Path(os.environ.get("CC_AUDIT_PATH", PROJECT_DIR / "output" / "audit_trail.json"))
PYTHON = sys.executable

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")  # keep CLI output to the results

MODEL = os.environ.get("CC_MODEL", "anthropic:claude-opus-5-5")

# The Boss weighs trade-offs across the whole ticket; specialists do narrower lookups.
EFFORT = {
    AgentName.BOSS: "high",
    AgentName.INVENTORY: "medium",
    AgentName.ACCOUNTING: "high",
    AgentName.FACILITIES: "medium",
    AgentName.CUSTOMER_SERVICE: "medium",
}

# Longest delegation chain (Boss -> A -> B -> C). Deeper requests are refused, which keeps
# full connectivity from turning into an endless loop.
MAX_DELEGATION_DEPTH = 3
# Token budget for one ticket, all agents combined. Going over ends the run with an error,
# which is recorded in the audit trail; nothing half-done is paid, because paying needs a human.
TICKET_LIMITS = UsageLimits(
    request_limit=60,            # model requests
    tool_calls_limit=120,        # MCP + delegate calls
    total_tokens_limit=600_000,  # input + output tokens
)
MAX_OUTPUT_TOKENS = 8000         # per model response; reports are short structured JSON


def model_settings(agent: AgentName) -> AnthropicModelSettings:
    # Cache the long, unchanging prefix (prompt + tool list) so repeated steps and
    # delegations re-read it at the cached rate.
    return AnthropicModelSettings(
        max_tokens=MAX_OUTPUT_TOKENS,
        anthropic_effort=EFFORT[agent],
        anthropic_cache_instructions=True,
        anthropic_cache_tool_definitions=True,
    )


_BOARD = {"get_shop_date", "get_ticket", "list_tickets"}

ROLE_TOOLS: dict[AgentName, set[str]] = {
    AgentName.BOSS: _BOARD | {
        "list_approval_requests", "list_purchase_orders", "list_drafts", "get_cash_balance",
        "list_payments",
    },
    AgentName.INVENTORY: _BOARD | {
        "check_stock", "list_inventory", "reserve_stock", "list_vendors", "get_vendor_status",
        "list_purchase_orders",
    },
    AgentName.ACCOUNTING: _BOARD | {
        "get_cash_balance", "list_invoices", "get_invoice", "get_pricing", "quote_discount",
        "list_vendors", "get_vendor_status", "get_lease", "request_payment_approval",
        "create_purchase_order", "list_purchase_orders", "list_approval_requests", "list_payments", "pay",
    },
    AgentName.FACILITIES: _BOARD | {
        "get_lease", "list_leases", "get_cash_balance", "list_approval_requests",
    },
    AgentName.CUSTOMER_SERVICE: _BOARD | {
        "check_stock", "get_pricing", "quote_discount", "get_vendor_status", "draft_message",
        "list_drafts",
    },
}

# update_ticket is called by the run loop to record the Boss's final decision, so ticket
# status always matches the decision shown on the dashboard.
LOOP_TOOLS = {"update_ticket"}

# Called only on a person's behalf (dashboard / CLI). No agent may ever see these.
HUMAN_ONLY_TOOLS = {"decide_approval_request", "reset_working_database"}
assert not any(HUMAN_ONLY_TOOLS & tools for tools in ROLE_TOOLS.values()), "human-only tool given to an agent"
