
from pydantic import BaseModel, Field


class Inventory(BaseModel):
    cash: float = Field(description="Agent's total amount of money", ge=0)
    apple: int = Field(description="Agent's total amount of apples", ge=0)
    chip: int = Field(description="Agent's total amount of chips", ge=0)
    gold: int = Field(description="Agent's Total amount of money", ge=0)
