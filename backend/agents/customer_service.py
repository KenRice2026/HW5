"""Customer Service: drafts messages for customers (and the landlord or vendors). Drafts are never sent."""

from backend.agents.base import make_agent
from backend.models import AgentName, AgentReport

agent = make_agent(AgentName.CUSTOMER_SERVICE, AgentReport)
