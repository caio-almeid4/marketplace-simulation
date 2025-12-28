from typing import Dict

from pydantic import BaseModel, Field, PositiveInt

from schemas.agent import AgentConfig


class SimulationSettings(BaseModel):

    rounds: PositiveInt = Field(
        default=20,
        description="Number of rounds to simulate",
    )
    agents_configs: Dict[str, AgentConfig]
