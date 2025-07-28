from typing import Sequence
from .base import MarketData

class Data1D(MarketData):
    
    def __init__(
        self,
        data_type: str,
        data_convention: str,
        axis: Sequence[float],
        values: Sequence[float]
    ):
        
        super().__init__(data_type, data_convention)

        if len(axis) != len(values):
            raise ValueError("`axis` and `values` must be the same length")

        self.axis = list(axis)
        self.values = list(values)

    def __repr__(self) -> str:
        return (
            f"Data1D(type={self.data_type!r}, "
            f"conv={self.data_convention!r}, "
            f"points={len(self.axis)})"
        )
