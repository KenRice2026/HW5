"""The Campus Customs agent team. Importing this package builds all five agents and
registers them in TEAM, which is what lets any agent delegate to any other."""

from backend.agents import accounting, boss, customer_service, facilities, inventory
from backend.agents.base import TEAM
from backend.models import AgentName

TEAM.update({
    AgentName.BOSS: boss.agent,
    AgentName.INVENTORY: inventory.agent,
    AgentName.ACCOUNTING: accounting.agent,
    AgentName.FACILITIES: facilities.agent,
    AgentName.CUSTOMER_SERVICE: customer_service.agent,
})

__all__ = ["TEAM"]
