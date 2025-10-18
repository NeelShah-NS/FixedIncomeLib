from typing import Sequence, Union
import numpy as np
import pandas as pd
from fixedincomelib.data.base import MarketData

class Data2D(MarketData):

    def __init__(
        self,
        data_type: str,
        data_convention: str,
        axis1: Sequence[float],
        axis2: Sequence[float],
        values: Sequence[Sequence[float]]
    ):
        super().__init__(data_type, data_convention)

        if len(values) != len(axis1):
            raise ValueError("Number of rows in `values` must match length of `axis1`")
        if any(len(row) != len(axis2) for row in values):
            raise ValueError("Each row in `values` must match length of `axis2`")

        self.axis1 = list(axis1)
        self.axis2 = list(axis2)
        self.values = np.array(values, dtype=float)

    def __repr__(self) -> str:
        return (
            f"Data2D(type={self.data_type!r}, "
            f"conv={self.data_convention!r}, "
            f"shape={self.values.shape})"
        )

    @classmethod
    def createDataObject(
        cls,
        data_type: str,
        data_convention: str,
        df: Union[pd.DataFrame]
    ) -> "Data2D":
        
        if not isinstance(df, pd.DataFrame):
            raise TypeError("Input must be a pandas DataFrame")

        axis1 = df.index.tolist()
        axis2 = df.columns.tolist()
        values = df.values.tolist()

        dt = data_type.lower()
        return cls(dt, data_convention, axis1, axis2, values)