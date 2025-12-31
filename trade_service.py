from sqlalchemy.orm import Session
from schemas.trade import Trade
from schemas.offer import TrackedOffer


class TradeService:
    
    
    def __init__(self, session: Session):
        self.session = session
        
    def create_trade_registry(self, buyer_name: str, offer: TrackedOffer) -> Trade:
        trade = Trade(
            **offer.model_dump(),
            buyer=buyer_name    
        )
        
        self.session.add(trade)
        return trade