import numpy as np
from typing import Sequence
from .base import MarketData
from utilities.numerics import Interpolator1D

class Data1D(MarketData):
    def __init__(
        self,
        data_type: str,
        data_convention: str,
        axis: Sequence[float],
        values: Sequence[float],
        method: str = "linear"
    ):
        super().__init__(data_type, data_convention)
        self.axis = np.array(axis, dtype=float)
        self.values = np.array(values, dtype=float)
        self.method = method
        self._interp = Interpolator1D(self.axis, self.values, method=method)

    def get(self, x: float) -> float:
        return self._interp.interpolate(x)