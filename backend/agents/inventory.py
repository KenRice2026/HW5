"""Inventory: checks stock by SKU and size, spots shortfalls, and finds the vendor who can restock."""

from backend.agents.base import make_agent
from backend.models import AgentName, AgentReport

agent = make_agent(AgentName.INVENTORY, AgentReport)
