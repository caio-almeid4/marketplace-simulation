from pydantic import BaseModel, Field

from agents.states.agent import AgentState


class AgentConfig(BaseModel):

    temperature: float = Field(ge=0, le=1)
    state: AgentState
