from typing import Literal

from pydantic import BaseModel, PositiveFloat, PositiveInt


class Offer(BaseModel):

    supplier: str
    item: Literal["Apple", "Chip", "Gold"]
    quantity: PositiveInt
    price: PositiveFloat
