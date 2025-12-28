from schemas.offer import Offer
from typing import List


class Market:
    
    
    def __init__(self):
        self.public_board: List[Offer] = []
    
    def add_offer(self, offer: Offer) -> None:
        self.public_board.append(offer)
    
    def clean(self) -> None:
        self.public_board.clear()   