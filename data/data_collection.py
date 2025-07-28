from typing import Dict, Tuple, Union, Iterable
import numpy as np
import pandas as pd
from .base import MarketData
from .data1d import Data1D
from .data2d import Data2D
from date import Date, Period, accrued
from market.indices import IndexRegistry

class DataCollection:
    def __init__(self, data_objs: Union[MarketData, Iterable[MarketData]] = ()):
        self._store: Dict[Tuple[str, str], MarketData] = {}
        if isinstance(data_objs, MarketData):
            data_objs = [data_objs]
        for d in data_objs:
            self.add(d)

    def add(self, data: MarketData) -> None:
        key = data.key()
        if key in self._store:
            raise KeyError(f"Duplicate data for key {key}")
        self._store[key] = data
    
    def clear(self) -> None:
        self._store.clear()

    def get(self, data_type: str, data_convention: str) -> MarketData:
        key = (data_type, data_convention)
        if key not in self._store:
            raise KeyError(f"No data for key {key}")
        return self._store[key]

    def keys(self):
        return list(self._store.keys())

    def register_zero_rate_dataframe(
        self,
        df: pd.DataFrame,
        value_date: Union[Date, str]
    ) -> None:
        
        for index_key, sub in df.groupby("INDEX"):
            tenors = sub["AXIS1"].astype(str).tolist()
            rates  = sub["VALUES"].astype(float).tolist()

            self.add(Data1D(
                data_type       = "zero_rate",
                data_convention = index_key,
                axis            = tenors,
                values          = rates
            ))

    def register_sabr_dataframe(
        self,
        df: pd.DataFrame,
        axis1_col: str,
        axis2_col: str,
        param_cols: list[str],
        data_convention_col: str = "INDEX"
    ) -> None:
        for index_key, sub in df.groupby(data_convention_col):
            ax1 = sorted(sub[axis1_col].astype(float).unique())
            ax2 = sorted(sub[axis2_col].astype(float).unique())

            for param in param_cols:
                grid_df = sub.pivot(index=axis1_col, columns=axis2_col, values=param)
                grid = grid_df.reindex(index=ax1, columns=ax2).values.tolist()

                self.add(Data2D(
                    data_type       = param.lower(),
                    data_convention = index_key,
                    axis1           = ax1,
                    axis2           = ax2,
                    values          = grid
                ))

    def register_surface_dataframe(
        self,
        df: pd.DataFrame,
        axis1_col: str,
        axis2_col: str,
        value_cols: list[str],
        data_convention_col: str = "INDEX"
    ) -> None:
        self.register_sabr_dataframe(
            df,
            axis1_col=axis1_col,
            axis2_col=axis2_col,
            param_cols=value_cols,
            data_convention_col=data_convention_col
        )
