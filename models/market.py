from typing import Dict

from loguru import logger

from models.agent import Agent
from schemas.offer import OfferDraft, TrackedOffer
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

    def clear_repository(self) -> None:
        self._repository.clear()

    def format_repository(self) -> str:
        return render_template('market', {'repository': self._repository})

    def _update_repository(self, offer: TrackedOffer):
        self._repository[offer.id] = offer

    def create_offer(self, offer: OfferDraft) -> str:

        current_qty = getattr(
            self.agents[offer.supplier].inventory, offer.item.lower(), None
        )
        if current_qty is None:
            raise ValueError(f"The item {offer.item} doesn't exist.")

        if current_qty < offer.quantity:
            raise ValueError(
                f"""Unsuficient items. You have {current_qty} {offer.item}, 
                tried to sell {offer.quantity}"""
            )

        tracked_offer = TrackedOffer(**offer.model_dump(), id=self._id_gen.generate())
        self._update_repository(tracked_offer)
        return f'{tracked_offer.model_dump()}'

    def evaluate_transaction(self, buyer_name: str, offer_id: int) -> str:

        offer = self._repository.get(offer_id, None)
        if not offer:
            raise ValueError(f"The offer with ID {offer_id} doens'nt exist")

        if buyer_name == offer.supplier:
            raise ValueError("You can't accept your own offer")

        buyer_inventory = self.agents[buyer_name].inventory
        supplier_inventory = self.agents[offer.supplier].inventory
        buyer_current_cash = buyer_inventory.cash

        if buyer_current_cash < offer.price:
            raise ValueError(
                f"""You don\'t have enough money to accept this offer.
                             Your amount: {buyer_current_cash}
                             Offer price: {offer.price}"""
            )

        current_supplier_qty = getattr(supplier_inventory, offer.item.lower())
        del self._repository[offer.id]
        if current_supplier_qty < offer.quantity:
            raise ValueError(
                f"""
                Can't accept the offer. The supplier doens't have enough {offer.item}
                 """
            )

        buyer_item_quantity = getattr(buyer_inventory, offer.item)
        buyer_inventory.cash -= offer.price
        setattr(buyer_inventory, offer.item, buyer_item_quantity + offer.quantity)
        new_buyer_item_quantity = getattr(buyer_inventory, offer.item)

        supplier_inventory.cash += offer.price
        supplier_item_quantity = getattr(supplier_inventory, offer.item)
        setattr(supplier_inventory, offer.item, supplier_item_quantity - offer.quantity)

        self.trade_service.create_trade_registry(buyer_name=buyer_name, offer=offer)

        logger.info(f"""
            {buyer_name} bought {offer.quantity} {offer.item} from {offer.supplier} 
            for {offer.price} dollars.')""")
        return f'Offer accepted. Now you have {new_buyer_item_quantity} {offer.item}'
