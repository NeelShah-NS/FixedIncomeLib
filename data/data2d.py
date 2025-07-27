import numpy as np
from typing import Sequence
from .base import MarketData
from utilities.numerics import Interpolator2D

class Data2D(MarketData):
    def __init__(
        self,
        data_type: str,
        data_convention: str,
        axis1: Sequence[float],
        axis2: Sequence[float],
        grid: Sequence[Sequence[float]],
        method: str = "linear"
    ):
        super().__init__(data_type, data_convention)
        self.axis1 = np.array(axis1, dtype=float)
        self.axis2 = np.array(axis2, dtype=float)
        self.grid = np.array(grid, dtype=float)
        self.method = method
        self._interp2d = Interpolator2D(
            axis1=self.axis1,
            axis2=self.axis2,
            values=self.grid,
            method=method
        )

    def get(self, x: float, y: float) -> float:
        return self._interp2d.interpolate(x, y)
