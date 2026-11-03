"""Accounting: watches cash and invoices, checks margins, and prepares payments and purchase
orders for human approval."""

from backend.agents.base import make_agent
from backend.models import AgentName, AgentReport

agent = make_agent(AgentName.ACCOUNTING, AgentReport)
