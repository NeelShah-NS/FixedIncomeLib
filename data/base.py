from abc import ABC, abstractmethod
from typing import Tuple

class MarketData(ABC):

    def __init__(self, data_type: str, data_convention: str):
        self.data_type = data_type
        self.data_convention = data_convention

    def key(self) -> Tuple[str, str]:
        return (self.data_type, self.data_convention)

    @abstractmethod
    def __repr__(self) -> str:
        raise NotImplementedError("Subclasses must implement __repr__()")
