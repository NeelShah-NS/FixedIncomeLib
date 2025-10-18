from typing import Sequence, Union
import pandas as pd
from fixedincomelib.data.base import MarketData

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

    @classmethod
    def createDataObject(
        cls,
        data_type: str,
        data_convention: str,
        df: pd.DataFrame
    ) -> "Data1D":

        if not isinstance(df, pd.DataFrame):
            raise TypeError("Input must be a pandas DataFrame")

        if not {"AXIS1","VALUES"}.issubset(df.columns):
            raise ValueError("DataFrame must have 'AXIS1' and 'VALUES' columns")

        axis  = df["AXIS1"].tolist()
        values = df["VALUES"].tolist()

        dt = data_type.lower()
        return cls(dt, data_convention, axis, values)
