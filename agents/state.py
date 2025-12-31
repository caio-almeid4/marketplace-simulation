from typing import Annotated, List, Literal

from langchain_core.messages import AnyMessage
from typing_extensions import TypedDict


class AgentState(TypedDict):
    internal_monologue: Annotated[str, 'Scratchpad to agent reasoning']
    messages: Annotated[
        List[AnyMessage], 'List of messages that will be passed to the agent'
    ]
    next_step: Literal['create_offer', 'manage_inbox', 'wait', '']
