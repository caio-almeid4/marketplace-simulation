from sqlalchemy.orm import Session

from schemas.offer import TrackedOffer
from schemas.trade import Trade


class TradeService:
    def __init__(self, session: Session):
        self.session = session

    def create_trade_db_registry(self, buyer_name: str, offer: TrackedOffer) -> Trade:
        trade = Trade(**offer.model_dump(), buyer=buyer_name)

        self.session.add(trade)
        return trade
