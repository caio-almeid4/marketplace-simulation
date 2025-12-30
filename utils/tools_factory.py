from typing import Dict, Literal

from langchain.tools import BaseTool, tool

from models.agent import Agent
from models.market import Market
from schemas.offer import Offer


def create_trade_tools(agent: Agent, market: Market) -> Dict[str, BaseTool]:

    @tool
    def create_public_offer(
        item: Literal["apple", "chip", "gold"], quantity: int, price: float
    ) -> str:
        """Creates a public offer for a specific item in the market.

        Args:
            item (Literal["apple", "chip", "gold"]): The type of resource to be offered.
            quantity (int): The total amount of the item available for sale.
            price (float): The unit price of the item.

        Returns:
            str: The created offer object if successful, or an error message string if
            a ValueError occurs.
        """

        offer = Offer(supplier=agent.name, item=item, quantity=quantity, price=price)

        try:
            return market.create_offer(offer=offer)

        except ValueError as e:
            return f"Error: {e}"

    tools = {"create_public_offer": create_public_offer}

    return tools
