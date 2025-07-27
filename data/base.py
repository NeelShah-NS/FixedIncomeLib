from abc import ABC, abstractmethod
from typing import Dict, Any

class MarketData(ABC):
    
    def __init__(
        self,
        data_type: str,
        data_convention: str,
        metadata: Dict[str, Any] = None
    ):
        self.data_type = data_type
        self.data_convention = data_convention
        self.metadata = metadata or {}

    @abstractmethod
    def get(self, *args) -> float:
        raise NotImplementedError("Must implement get() in subclasses")