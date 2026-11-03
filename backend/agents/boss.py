"""Boss: reads each ticket, decides who works it, and makes the final call (BossDecision)."""

from backend.agents.base import make_agent
from backend.models import AgentName, BossDecision

agent = make_agent(AgentName.BOSS, BossDecision)
