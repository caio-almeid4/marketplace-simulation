from typing import Dict, List

from loguru import logger

from models.agent import Agent
from schemas.inventory import Inventory
from schemas.offer import OfferDraft, TrackedOffer
from schemas.trade import UnitTrade
from services.trade_service import TradeService
from utils.id_generator import SerialIDGenerator
from utils.render_template import render_template


class Market:
    """Central marketplace authority that manages all trading operations.

    The Market class acts as the supreme authority for all economic transactions
    in the simulation. It validates offers, executes trades, maintains order books,
    and ensures all transactions follow the rules (agents can't sell what they
    don't have, can't buy without cash, etc.).

    Attributes:
        agents: Dictionary mapping agent names to Agent instances.
        trade_service: Service for persisting trades to database.
        _repository: Internal dictionary storing active offers by ID.
        _id_gen: Generator for unique offer IDs.
        _trade_history: List of recent trades for display purposes.
    """

    def __init__(
        self,
        agents: Dict[str, Agent],
        id_gen: SerialIDGenerator,
        trade_service: TradeService,
    ):
        """Initialize the Market.

        Args:
            agents: Dictionary of all participating agents.
            id_gen: ID generator for creating unique offer IDs.
            trade_service: Service for database persistence of trades.
        """
        self._repository: Dict[int, TrackedOffer] = {}
        self.agents = agents
        self._id_gen = id_gen
        self.trade_service = trade_service
        self._trade_history: List[UnitTrade] = []

    def clear_repository(self) -> None:
        """Clear all offers from the repository."""
        self._repository.clear()

    def get_market_data(self) -> str:
        """Generate formatted market data for agents.

        Returns:
            Rendered template string containing active offers and recent trades.
        """
        return render_template(
            'market',
            {'repository': self._repository, 'recent_trades': self._trade_history},
        )

    def _update_repository(self, offer: TrackedOffer):
        """Add or update an offer in the repository.

        Args:
            offer: The tracked offer to store.
        """
        self._repository[offer.id] = offer

    def _update_trade_history(self, trade: UnitTrade) -> None:
        """Add a completed trade to the history log.

        Args:
            trade: The completed trade to record.
        """
        self._trade_history.append(trade)

    def clear_trade_history(self) -> None:
        """Clear the trade history (typically at round end)."""
        self._trade_history.clear()

    def create_offer(self, offer: OfferDraft) -> str:
        """Create a sell offer by reserving items from supplier's inventory.

        Validates that the supplier has sufficient items, then deducts them
        from inventory and creates a tracked offer in the repository.

        Args:
            offer: The offer draft containing item, quantity, price, and supplier.

        Returns:
            String representation of the created tracked offer.

        Raises:
            ValueError: If supplier doesn't have enough items to sell.
        """
        supplier_inventory = self.agents[offer.supplier].inventory
        self._check_available_item(inventory=supplier_inventory, offer=offer)
        self._update_inventory(supplier_inventory=supplier_inventory, offer=offer)
        tracked_offer = TrackedOffer(**offer.model_dump(), id=self._id_gen.generate())
        self._update_repository(tracked_offer)
        logger.info(
            f'     [SELL #{tracked_offer.id}] {offer.supplier} offers '
            f'{offer.quantity} {offer.item.upper()} @ ${offer.price:.2f}'
        )
        return f'{tracked_offer.model_dump()}'

    def create_buy_offer(self, offer: OfferDraft) -> str:
        """Create a buy offer by reserving cash from buyer's inventory.

        Validates that the buyer has sufficient cash, then deducts the offer
        price from their cash and creates a tracked offer in the repository.

        Args:
            offer: The offer draft containing item, quantity, price, and buyer.

        Returns:
            String representation of the created tracked offer.

        Raises:
            ValueError: If buyer doesn't have enough cash.
        """
        buyer_inventory = self.agents[offer.supplier].inventory
        self._check_available_cash(current_cash=buyer_inventory.cash, price=offer.price)
        buyer_inventory.cash -= offer.price

        tracked_offer = TrackedOffer(**offer.model_dump(), id=self._id_gen.generate())
        self._update_repository(tracked_offer)
        logger.info(
            f'     [BUY #{tracked_offer.id}] {offer.supplier} wants '
            f'{offer.quantity} {offer.item.upper()} for ${offer.price:.2f}'
        )
        return f'{tracked_offer.model_dump()}'

    def evaluate_sell_transaction(self, buyer_name: str, offer_id: int, round_num: int) -> str:
        """Execute a sell transaction (buyer accepts a sell offer).

        Validates the offer exists and buyer has sufficient cash, then transfers
        items to buyer and cash to seller. Records the trade in history and database.

        Args:
            buyer_name: Name of the agent accepting the offer.
            offer_id: ID of the sell offer to accept.
            round_num: Current simulation round number.

        Returns:
            Success message with updated buyer inventory.

        Raises:
            ValueError: If offer doesn't exist, buyer is accepting own offer,
                or buyer doesn't have enough cash.
        """
        offer = self._repository.get(offer_id, None)
        if not offer:
            raise ValueError(f"The offer with ID {offer_id} doesn't exist")

        if buyer_name == offer.supplier:
            raise ValueError("You can't accept your own offer")

        buyer_inventory = self.agents[buyer_name].inventory
        supplier_inventory = self.agents[offer.supplier].inventory
        self._check_available_cash(current_cash=buyer_inventory.cash, price=offer.price)
        self._update_inventory(
            buyer_inventory=buyer_inventory,
            supplier_inventory=supplier_inventory,
            offer=offer,
        )
        del self._repository[offer.id]
        self.trade_service.create_trade_db_registry(
            buyer_name=buyer_name, offer=offer, round_number=round_num
        )

        trade = UnitTrade(**offer.model_dump(), buyer=buyer_name)
        self._update_trade_history(trade)

        logger.success(
            f'     TRADE: {buyer_name} bought {offer.quantity} {offer.item.upper()} '
            f'from {offer.supplier} @ ${offer.price:.2f}'
        )

        return f'Offer accepted. Updated inventory: {buyer_inventory.model_dump()}'

    def evaluate_buy_transaction(self, seller_name: str, offer_id: int, round_num: int) -> str:
        """Execute a buy transaction (seller accepts a buy offer).

        Validates the offer exists, is a buy offer, and seller has sufficient items.
        Then transfers items to buyer and reserved cash to seller. Records the
        trade in history and database.

        Args:
            seller_name: Name of the agent accepting the buy offer.
            offer_id: ID of the buy offer to accept.
            round_num: Current simulation round number.

        Returns:
            Success message with updated seller inventory.

        Raises:
            ValueError: If offer doesn't exist, is not a buy offer, seller is
                accepting own offer, or seller doesn't have enough items.
        """
        offer = self._repository.get(offer_id, None)
        if not offer:
            raise ValueError(f"The offer with ID {offer_id} doesn't exist")

        if offer.offer_type != 'buy':
            raise ValueError('This is not a buy offer')

        if seller_name == offer.supplier:
            raise ValueError("You can't accept your own offer")

        seller_inventory = self.agents[seller_name].inventory
        buyer_inventory = self.agents[offer.supplier].inventory

        self._check_available_item(inventory=seller_inventory, offer=offer)

        current_seller_qty = getattr(seller_inventory, offer.item)
        setattr(seller_inventory, offer.item, current_seller_qty - offer.quantity)
        seller_inventory.cash += offer.price

        current_buyer_qty = getattr(buyer_inventory, offer.item)
        setattr(buyer_inventory, offer.item, current_buyer_qty + offer.quantity)

        del self._repository[offer.id]

        trade = UnitTrade(
            supplier=seller_name,
            buyer=offer.supplier,
            item=offer.item,
            quantity=offer.quantity,
            price=offer.price,
        )
        self._update_trade_history(trade)
        self.trade_service.create_trade_db_registry(
            buyer_name=offer.supplier, offer=offer, round_number=round_num, seller_name=seller_name
        )

        logger.success(
            f'     TRADE: {seller_name} sold {offer.quantity} {offer.item.upper()} '
            f'to {offer.supplier} @ ${offer.price:.2f}'
        )

        return f'Buy offer accepted. Updated inventory: {seller_inventory.model_dump()}'

    @staticmethod
    def _update_inventory(
        supplier_inventory: Inventory,
        offer: OfferDraft,
        buyer_inventory: Inventory | None = None,
    ) -> None:
        """Update inventories for a transaction or offer creation.

        If buyer_inventory is provided, executes a full transaction (transfer
        items and cash). Otherwise, only reserves items from supplier inventory.

        Args:
            supplier_inventory: Inventory of the seller/offer creator.
            offer: The offer being processed.
            buyer_inventory: Optional inventory of the buyer (for transactions).
        """
        if buyer_inventory:
            buyer_item_quantity = getattr(buyer_inventory, offer.item)
            buyer_inventory.cash -= offer.price
            setattr(buyer_inventory, offer.item, buyer_item_quantity + offer.quantity)

            supplier_inventory.cash += offer.price

        else:
            supplier_item_quantity = getattr(supplier_inventory, offer.item)
            setattr(
                supplier_inventory, offer.item, supplier_item_quantity - offer.quantity
            )

    @staticmethod
    def _check_available_cash(current_cash: float, price: float) -> None:
        """Validate that an agent has sufficient cash for a transaction.

        Args:
            current_cash: The agent's current cash balance.
            price: The price of the offer being accepted.

        Raises:
            ValueError: If current_cash is less than price.
        """
        if current_cash < price:
            raise ValueError(
                f"""You don\'t have enough money to accept this offer.
                             Your amount: {current_cash}
                             Offer price: {price}"""
            )

    @staticmethod
    def _check_available_item(inventory: Inventory, offer: OfferDraft) -> Inventory:
        """Validate that an agent has sufficient items for a transaction.

        Args:
            inventory: The agent's inventory to check.
            offer: The offer specifying item type and quantity needed.

        Returns:
            The validated inventory object.

        Raises:
            ValueError: If item doesn't exist or quantity is insufficient.
        """
        current_qty = getattr(inventory, offer.item.lower(), None)
        if current_qty is None:
            raise ValueError(f"The item {offer.item} doesn't exist.")

        if current_qty < offer.quantity:
            raise ValueError(
                f'Insufficient items. You have {current_qty}, tried to sell {offer.quantity}'
            )

        return inventory

    def cancel_offer(self, agent_name: str, offer_id: int) -> str:
        """Cancel an offer and return reserved assets to the agent.

        Removes the offer from repository and returns reserved items (for sell
        offers) or cash (for buy offers) to the agent's inventory.

        Args:
            agent_name: Name of the agent cancelling the offer.
            offer_id: ID of the offer to cancel.

        Returns:
            Success message with updated inventory.

        Raises:
            ValueError: If offer doesn't exist or agent doesn't own the offer.
        """
        offer = self._repository.get(offer_id)
        if not offer:
            raise ValueError(f"Offer #{offer_id} doesn't exist")

        if offer.supplier != agent_name:
            raise ValueError("You can only cancel your own offers")

        agent_inventory = self.agents[agent_name].inventory
        if offer.offer_type == 'sell':
            current_qty = getattr(agent_inventory, offer.item)
            setattr(agent_inventory, offer.item, current_qty + offer.quantity)
            recovered = f'{offer.quantity} {offer.item.upper()}'
        else:
            agent_inventory.cash += offer.price
            recovered = f'${offer.price:.2f}'

        del self._repository[offer_id]
        logger.info(
            f'     [CANCEL #{offer_id}] {agent_name} cancelled {offer.offer_type} offer '
            f'(recovered {recovered})'
        )
        return f'Offer #{offer_id} cancelled. Updated inventory: {agent_inventory.model_dump()}'

    def delete_agent_offers(self, agent_name: str, return_assets: bool = True):
        """Delete all offers belonging to an agent (used on death/bankruptcy).

        Removes all of the agent's offers from the repository. Optionally
        returns reserved assets to the agent's inventory.

        Args:
            agent_name: Name of the agent whose offers should be deleted.
            return_assets: Whether to return reserved assets to inventory.
        """
        agent_offers = []
        for id, offer in self._repository.items():
            if offer.supplier == agent_name:
                agent_offers.append(id)

        for id in agent_offers:
            offer = self._repository[id]
            if return_assets:
                agent_inventory = self.agents[agent_name].inventory
                if offer.offer_type == 'sell':
                    current_qty = getattr(agent_inventory, offer.item)
                    setattr(agent_inventory, offer.item, current_qty + offer.quantity)
                else:
                    agent_inventory.cash += offer.price
            del self._repository[id]

    def get_trade_history(self):
        return self._trade_history