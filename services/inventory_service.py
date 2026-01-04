from typing import List

from sqlalchemy.orm import Session

from models.agent import Agent
from schemas.inventory_history import InventorySnapshot


class InventoryService:
    """Service for persisting inventory snapshots to the database.

    Creates timestamped records of agent inventories at the end of each
    round for historical tracking and analysis.

    Attributes:
        session: SQLAlchemy database session for persistence operations.
    """

    def __init__(self, session: Session):
        """Initialize the InventoryService.

        Args:
            session: Active database session for inventory operations.
        """
        self.session = session

    def create_snapshot(self, agent: Agent, round_number: int) -> InventorySnapshot:
        """Create an inventory snapshot for a single agent.

        Args:
            agent: Agent to snapshot.
            round_number: Current round number.

        Returns:
            The created InventorySnapshot instance (not yet committed).
        """
        snapshot = InventorySnapshot(
            agent_name=agent.name,
            round_number=round_number,
            cash=agent.inventory.cash,
            apple=agent.inventory.apple,
            chip=agent.inventory.chip,
            gold=agent.inventory.gold,
            energy=agent.energy,
            is_alive=agent.is_alive,
        )
        self.session.add(snapshot)
        return snapshot

    def create_all_snapshots(
        self, agents: List[Agent], round_number: int
    ) -> List[InventorySnapshot]:
        """Create and persist inventory snapshots for all agents.

        Creates snapshots for all agents in a batch and commits them
        together for efficiency.

        Args:
            agents: List of all agents to snapshot.
            round_number: Current round number.

        Returns:
            List of created and persisted InventorySnapshot instances.
        """
        snapshots = []
        for agent in agents:
            snapshot = self.create_snapshot(agent, round_number)
            snapshots.append(snapshot)
        self.session.commit()
        return snapshots
