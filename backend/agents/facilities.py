"""Facilities: the shop space - leases, rent and landlord notices."""

from backend.agents.base import make_agent
from backend.models import AgentName, AgentReport

agent = make_agent(AgentName.FACILITIES, AgentReport)
