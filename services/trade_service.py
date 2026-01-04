from typing import Optional

from sqlalchemy.orm import Session

from schemas.offer import TrackedOffer
from schemas.trade import Trade


class TradeService:
    """Service for persisting trade records to the database.

    Handles creation and storage of trade transactions with immediate
    commit for real-time database updates.

    Attributes:
        session: SQLAlchemy database session for persistence operations.
    """

    def __init__(self, session: Session):
        """Initialize the TradeService.

        Args:
            session: Active database session for trade operations.
        """
        self.session = session

    def create_trade_db_registry(
        self,
        buyer_name: str,
        offer: TrackedOffer,
        seller_name: Optional[str] = None,
    ) -> Trade:
        """Create and persist a trade record to the database.

        Converts an accepted offer into a trade record. For buy offers,
        seller_name overrides the offer's supplier field.

        Args:
            buyer_name: Name of the agent buying items.
            offer: The offer being accepted.
            seller_name: Optional seller name (for buy offers where seller
                differs from offer creator).

        Returns:
            The created and persisted Trade instance.
        """
        offer_data = offer.model_dump(exclude={'id'})
        offer_data['buyer'] = buyer_name
        if seller_name:
            offer_data['supplier'] = seller_name

        trade = Trade(**offer_data)
        self.session.add(trade)
        self.session.commit()
        return trade
