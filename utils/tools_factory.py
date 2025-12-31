from typing import Dict, Literal

from langchain.tools import BaseTool, tool

from models.agent import Agent
from models.market import Market
from schemas.offer import OfferDraft


def create_trade_tools(agent: Agent, market: Market) -> Dict[str, BaseTool]:

    @tool
    def create_public_offer(
        item: Literal['apple', 'chip', 'gold'],
        quantity: int,
        price: float,
        offer_message: str,
    ) -> str:
        """Creates a public offer for a specific item in the market.

        Args:
            item (Literal['apple', 'chip', 'gold']): The type of resource to be offered.
            quantity (int): The total amount of the item available for sale.
            price (float): The unit price of the item.

        Returns:
            str: Offer information if successful, or an error message string if
            a ValueError occurs.
        """
        try:
            offer = OfferDraft(
                supplier=agent.name,
                item=item,
                quantity=quantity,
                price=price,
                message=offer_message,
            )
            return market.create_offer(offer=offer)

        except ValueError as e:
            return f'Error: {e}'

    @tool
    def accept_offer(offer_id: int):
        """Accepts an offer

        Args:
            offer_id (int): The offer id

        Returns:
            str: New amount of purchased item, or an error message string if
            a ValueError occurs.
        """
        try:
            return market.evaluate_transaction(buyer_name=agent.name, offer_id=offer_id)
        except ValueError as e:
            return f'Error: {e}'

    tools = {'create_public_offer': create_public_offer, 'accept_offer': accept_offer}

    return tools
