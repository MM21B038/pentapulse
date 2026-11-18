from penta.agents.discovery.directory_agent import directory_discovery_agent, directory_discovery_agent_card
from penta.agents.discovery.forms_agent import form_discovery_agent, form_discovery_agent_card
from penta.agents.discovery.priority_agent import priority_assigning_agent, priority_assigning_agent_card
from typing import Dict, Callable

agents: Dict[str, Callable] = {
    "directory_discovery_agent": directory_discovery_agent,
    "form_discovery_agent": form_discovery_agent,
    "priority_assigning_agent": priority_assigning_agent,
}

__all__ = [
    "agents",
    "directory_discovery_agent_card",
    "form_discovery_agent_card",
    "priority_assigning_agent_card"
]