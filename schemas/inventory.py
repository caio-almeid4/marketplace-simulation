from pydantic import BaseModel, Field


class Inventory(BaseModel):

    cash: float = Field(description="Agent's total amount of money")
    apple: int = Field(description="Agent's total amount of apples")
    chip: int = Field(description="Agent's total amount of chips")
    gold: int = Field(description="Agent's Total amount of money")
