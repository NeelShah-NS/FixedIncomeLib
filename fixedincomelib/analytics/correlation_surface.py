from typing import Sequence, Optional, Union
import numpy as np
from fixedincomelib.utilities.numerics import Interpolator2D
from fixedincomelib.data.data2d import Data2D

class CorrSurface:

    def __init__(
        self,
        axis1: Sequence[float],
        axis2: Sequence[float],
        values: Sequence[Sequence[float]],
        method: str = "LINEAR"
    ):
        a1 = np.asarray(axis1, dtype=float)
        a2 = np.asarray(axis2, dtype=float)
        v  = np.asarray(values, dtype=float)

        self.axis1 = a1
        self.axis2 = a2
        self.values = v
        self._interp2d = Interpolator2D(
            axis1=self.axis1,
            axis2=self.axis2,
            values=self.values,
            method=method
        )

    @classmethod
    def from_data2d(
        cls,
        md: Data2D,
        method: str = "LINEAR"
    ) -> "CorrSurface":

        return cls(md.axis1, md.axis2, md.values, method)

    def corr(self, expiry: float, tenor: float) -> float:
        return self._interp2d.interpolate(expiry, tenor)

    def __call__(
        self,
        expiry: float,
        tenor: float
    ) -> float:
        return self.corr(expiry, tenor)
