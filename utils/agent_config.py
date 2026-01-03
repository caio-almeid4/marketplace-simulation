from pathlib import Path
from typing import List

import yaml

from schemas.agent import AgentConfig, PersonalityInfo
from schemas.inventory import Inventory


def load_agent_config(name: str):

    filepath = Path('agents/configs') / f'{name}.yaml'

    with open(filepath, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    return AgentConfig(
        name=name,
        temperature=config['temperature'],
        inventory=Inventory(**config['inventory']),
        personality_info=PersonalityInfo(**config),
        energy=config['energy'],
        operational_cost=config['operational_cost']
    )


def get_agents_configs(agents: List[str]):

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
