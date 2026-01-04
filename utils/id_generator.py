from itertools import count


class SerialIDGenerator:
    """Generator for sequential unique IDs.

    Uses itertools.count to generate monotonically increasing integers
    for use as offer IDs in the market.

    Attributes:
        _counter: Internal counter iterator.
    """

    def __init__(self, start: int = 1):
        """Initialize the ID generator.

        Args:
            start: Starting value for the ID sequence (default: 1).
        """
        self._counter = count(start)

    def generate(self) -> int:
        """Generate the next unique ID.

        Returns:
            The next sequential integer ID.
        """
        return next(self._counter)
