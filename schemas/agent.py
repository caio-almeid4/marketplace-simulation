from typing import List, Literal

from pydantic import BaseModel, Field, PositiveInt

from schemas.inventory import Inventory


class PersonalityInfo(BaseModel):
    personality: str
    background: str
    objective: str
    strategy: str
    custom_instructions: List[str]
    decision_biases: List[str]


class AgentConfig(BaseModel):
    name: str
    temperature: float = Field(ge=0, le=1)
    inventory: Inventory
    personality_info: PersonalityInfo
    energy: PositiveInt
    operational_cost: float = Field(ge=0)


class AgentResponse:
    next_step: Literal['manage_offers', 'manage_inbox', 'wait']


class AgentAnalysis(AgentResponse):
    updated_monologue: str
