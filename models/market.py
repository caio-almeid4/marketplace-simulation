from typing import Dict

from loguru import logger

from models.agent import Agent
from schemas.inventory import Inventory
from schemas.offer import OfferDraft, TrackedOffer
from schemas.trade import UnitTrade
from trade_service import TradeService
from utils.id_generator import SerialIDGenerator
from utils.render_template import render_template


class Market:
    def __init__(
        self,
        agents: Dict[str, Agent],
        id_gen: SerialIDGenerator,
        trade_service: TradeService,
    ):
        self._repository: Dict[int, TrackedOffer] = {}
        self.agents = agents
        self._id_gen = id_gen
        self.trade_service = trade_service
        self._trade_history = []

    def clear_repository(self) -> None:
        self._repository.clear()

    def get_market_data(self) -> str:
        return render_template(
            'market',
            {'repository': self._repository, 'recent_trades': self._trade_history},
        )

    def _update_repository(self, offer: TrackedOffer):
        self._repository[offer.id] = offer

    def _update_trade_history(self, trade: UnitTrade) -> None:
        self._trade_history.append(trade)

    def clear_trade_history(self) -> None:
        self._trade_history.clear()

    def create_offer(self, offer: OfferDraft) -> str:

        supplier_inventory = self.agents[offer.supplier].inventory
        supplier_inventory = self._check_available_item(
            supplier_inventory=supplier_inventory, offer=offer
        )
        self._update_inventory(supplier_inventory=supplier_inventory, offer=offer)
        tracked_offer = TrackedOffer(**offer.model_dump(), id=self._id_gen.generate())
        self._update_repository(tracked_offer)
        return f'{tracked_offer.model_dump()}'

    def evaluate_transaction(self, buyer_name: str, offer_id: int) -> str:

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
        self.trade_service.create_trade_db_registry(buyer_name=buyer_name, offer=offer)

        trade = UnitTrade(**offer.model_dump(), buyer=buyer_name)
        self._update_trade_history(trade)

        logger.info(f"""
        {buyer_name}:{offer.supplier}|{offer.quantity}|{offer.item}|{offer.price}.""")

        return f'Offer accepted. Updated inventory: {buyer_inventory.model_dump()}'

    @staticmethod
    def _update_inventory(
        supplier_inventory: Inventory,
        offer: OfferDraft,
        buyer_inventory: Inventory | None = None,
    ) -> None:

        if buyer_inventory:
            buyer_item_quantity = getattr(buyer_inventory, offer.item)
            buyer_inventory.cash -= offer.price
            setattr(buyer_inventory, offer.item, buyer_item_quantity + offer.quantity)

            supplier_inventory.cash += offer.price
        
        else:
            supplier_item_quantity = getattr(supplier_inventory, offer.item)
            setattr(supplier_inventory, offer.item, supplier_item_quantity - offer.quantity)

    @staticmethod
    def _check_available_cash(current_cash: float, price: float) -> None:

        if current_cash < price:
            raise ValueError(
                f"""You don\'t have enough money to accept this offer.
                             Your amount: {current_cash}
                             Offer price: {price}"""
            )

    def _check_available_item(
        self, supplier_inventory: Inventory, offer: OfferDraft
    ) -> Inventory:

        current_qty = getattr(supplier_inventory, offer.item.lower(), None)
        if current_qty is None:
            raise ValueError(f"The item {offer.item} doesn't exist.")

        if current_qty < offer.quantity:
            raise ValueError(
                f"""Unsuficient items. You have {current_qty}, tried to sell {offer.quantity}
                """
            )

        return supplier_inventory
    
    def delete_agent_offers(self, agent_name: str):
        
        agent_offers = []
        for id, offer in self._repository.items():
            if offer.supplier == agent_name:
                agent_offers.append(id)
                
        for id in agent_offers:
            del self._repository[id] 