from pathlib import Path
from typing import List

import yaml

from schemas.agent import AgentConfig, PersonalityInfo
from schemas.inventory import Inventory


def load_agent_config(name: str):
    """Load agent configuration from YAML file.

    Reads an agent's YAML configuration file and constructs an AgentConfig
    instance with inventory, personality, and settings.

    Args:
        name: Agent name (used to locate the config file).

    Returns:
        Fully constructed AgentConfig instance.
    """
    filepath = Path('agents/configs') / f'{name}.yaml'

    with open(filepath, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    return AgentConfig(
        name=name,
        temperature=config['temperature'],
        inventory=Inventory(**config['inventory']),
        personality_info=PersonalityInfo(**config),
        energy=config['energy'],
        operational_cost=config['operational_cost'],
        model=config['model'],
    )


def get_agents_configs(agents: List[str]):
    """Load configurations for multiple agents.

    If agents list contains '*', loads all agents from the configs folder.
    Otherwise, loads only the specified agents.

    Args:
        agents: List of agent names, or ['*'] to load all agents.

    Returns:
        Dictionary mapping agent names to AgentConfig instances.
    """
    if '*' not in agents:
        agents = [name.lower().strip().replace(' ', '_') for name in agents]

    else:
        folder = Path('agents/configs')
        agents = [
            f.name.split('.')[0]
            for f in folder.iterdir()
            if f.is_file() and f.suffix == '.yaml'
        ]

    configs = {name: load_agent_config(name) for name in agents}

    return configs
