from typing import Dict, Literal

from langchain.tools import BaseTool, tool

from models.agent import Agent
from models.market import Market
from schemas.offer import OfferDraft


def create_trade_tools(agent: Agent, market: Market) -> Dict[str, BaseTool]:
    """Create trading tools bound to a specific agent and market.

    Generates LangChain tool functions that allow an agent to interact with
    the market (create offers, accept offers, cancel offers).

    Args:
        agent: The agent who will use these tools.
        market: The market instance to interact with.

    Returns:
        Dictionary mapping tool names to BaseTool instances.
    """

    @tool
    def create_public_offer(
        item: Literal['apple', 'chip', 'gold'],
        quantity: int,
        price: float,
        offer_message: str,
    ) -> str:
        """Create a public SELL offer for items in the market.

        IMPORTANT: Price is the TOTAL price for ALL units, not per-unit!
        Example: To sell 10 apples at $5 each, set quantity=10 and price=50.

        Reference prices (per unit): Apple ~$5, Chip ~$50, Gold ~$200

        Args:
            item: The type of resource to sell (apple, chip, gold).
            quantity: How many units to sell.
            price: The TOTAL price for all units combined.
            offer_message: A message to include with the offer.

        Returns:
            Offer information if successful, or an error message.
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
    def accept_sell_offer(offer_id: int):
        """Accepts a sell offer (you buy items from the seller).

        Args:
            offer_id (int): The sell offer id

        Returns:
            str: Updated inventory, or an error message.
        """
        try:
            return market.evaluate_sell_transaction(
                buyer_name=agent.name, offer_id=offer_id, round_num=agent.current_round
            )
        except ValueError as e:
            return f'Error: {e}'

    @tool
    def create_buy_offer(
        item: Literal['apple', 'chip', 'gold'],
        quantity: int,
        price: float,
        offer_message: str,
    ) -> str:
        """Creates a public BUY offer - you offer cash to buy items from others.
        Your cash will be reserved until someone accepts.

        IMPORTANT: Price is the TOTAL price for ALL units, not per-unit!
        Example: To buy 10 apples at $5 each, set quantity=10 and price=50.

        Reference prices (per unit): Apple ~$5, Chip ~$50, Gold ~$200

        Args:
            item: The type of resource you want to buy.
            quantity: How many units you want to buy.
            price: The TOTAL price you're offering for all units.
            offer_message: A message to include with the offer.

        Returns:
            str: Offer information if successful, or an error message.
        """
        try:
            offer = OfferDraft(
                supplier=agent.name,
                item=item,
                quantity=quantity,
                price=price,
                message=offer_message,
                offer_type='buy',
            )
            return market.create_buy_offer(offer=offer)
        except ValueError as e:
            return f'Error: {e}'

    @tool
    def accept_buy_offer(offer_id: int):
        """Accepts a buy offer (you sell your items to the buyer).

        Args:
            offer_id (int): The buy offer id

        Returns:
            str: Updated inventory, or an error message.
        """
        try:
            return market.evaluate_buy_transaction(
                seller_name=agent.name, offer_id=offer_id, round_num=agent.current_round
            )
        except ValueError as e:
            return f'Error: {e}'

    @tool
    def cancel_offer(offer_id: int):
        """Cancels one of your own offers and returns the reserved assets.

        Use this to recover cash from buy offers or items from sell offers.

        Args:
            offer_id (int): The ID of your offer to cancel.

        Returns:
            str: Updated inventory, or an error message.
        """
        try:
            return market.cancel_offer(agent_name=agent.name, offer_id=offer_id)
        except ValueError as e:
            return f'Error: {e}'

    tools = {
        'create_public_offer': create_public_offer,
        'accept_sell_offer': accept_sell_offer,
        'create_buy_offer': create_buy_offer,
        'accept_buy_offer': accept_buy_offer,
        'cancel_offer': cancel_offer,
    }

    return tools
