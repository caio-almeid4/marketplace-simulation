import random
from pathlib import Path
from typing import List, Optional

import yaml

from schemas.broadcast import BroadcastEvent


class BroadcastService:
    """Service for loading and providing random market events.

    Loads broadcast events from a YAML configuration file and provides
    random events to be sent to all agents each round.

    Attributes:
        events: List of available broadcast events loaded from config.
    """

    def __init__(self, events_file: str = 'config/broadcast_events.yaml'):
        """Initialize the BroadcastService.

        Args:
            events_file: Path to YAML file containing broadcast events.
        """
        self.events: List[BroadcastEvent] = []
        self._load_events(events_file)

    def _load_events(self, filepath: str) -> None:
        """Load broadcast events from YAML configuration file.

        Args:
            filepath: Path to the events YAML file.
        """
        path = Path(filepath)
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                self.events = [
                    BroadcastEvent(**event) for event in data.get('events', [])
                ]

    def get_random_event(self) -> Optional[BroadcastEvent]:
        """Select and return a random broadcast event.

        Returns:
            A randomly selected BroadcastEvent, or None if no events loaded.
        """
        if not self.events:
            return None
        return random.choice(self.events)
