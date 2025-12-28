from pydantic import BaseModel, Field


class Message(BaseModel):
    sender: str = Field(description="The name of the sender agent")
    content: str = Field(description="Content of the message")
