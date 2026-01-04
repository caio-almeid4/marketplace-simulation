from pydantic import BaseModel


class BroadcastEvent(BaseModel):
    id: str
    title: str
    content: str
    category: str
