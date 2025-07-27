from typing import Any, Dict, List, Tuple
import numpy as np
from .data2d import Data2D
from .base import MarketData
import pandas as pd
from .data1d import Data1D
from date import Date, Period, accrued
from market.indices import IndexRegistry

class DataCollection:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DataCollection, cls).__new__(cls)
            cls._instance._store: Dict[Tuple[str, str], MarketData] = {} # type: ignore
        return cls._instance

    @classmethod
    def instance(cls) -> "DataCollection":
        return cls()

    def add(self, md: MarketData):
        key = (md.data_type, md.data_convention)
        if key in self._store:
            raise KeyError(f"Duplicate market data for {key}")
        self._store[key] = md

    def get(self, data_type: str, data_convention: str) -> MarketData:
        try:
            return self._store[(data_type, data_convention)]
        except KeyError:
            raise KeyError(
                f"Market data not found for (data_type={data_type}, "
                f"data_convention={data_convention})"
            )
    
    def clear(self):
        self._store.clear()
    
    def register_zero_rate_dataframe(
        self,
        df: pd.DataFrame,
        value_date: Date,
        method: str = "PIECEWISE_CONSTANT"
    ) -> None:
        if isinstance(value_date, str):
            value_date = Date(value_date)

        for index_key, sub in df.groupby("INDEX"):
            if index_key.endswith("1B"):
                idx_obj = IndexRegistry().get(index_key)
            else:
                parts    = index_key.split("-")
                tenor    = parts[-1]
                base_key = "-".join(parts[:-1])
                idx_obj  = IndexRegistry().get(base_key, tenor)

            cal = idx_obj.fixingCalendar()
            bdc = idx_obj.businessDayConvention()

            year_fracs: list[float] = []
            for tenor_str in sub["AXIS1"]:
                p  = Period(tenor_str)
                dt = Date(cal.advance(value_date, p, bdc))
                year_fracs.append(accrued(value_date, dt))

            rates = sub["VALUES"].to_numpy()

            self.add(Data1D(
                data_type       = "ZERO_RATE",
                data_convention = index_key,
                axis            = year_fracs,
                values          = rates,
                method          = method,
            ))
    
    def register_sabr_dataframe(
        self,
        df: pd.DataFrame,
        axis1_col: str,
        axis2_col: str,
        param_cols: list[str],
        data_convention_col: str = "INDEX",
        method: str = "LINEAR"
    ) -> None:
        for index_key, sub in df.groupby(data_convention_col):
            ax1 = np.sort(sub[axis1_col].astype(float).unique())
            ax2 = np.sort(sub[axis2_col].astype(float).unique())

            for param in param_cols:
                grid = (
                    sub
                    .pivot_table(
                        index=axis1_col,
                        columns=axis2_col,
                        values=param
                    )
                    .reindex(index=ax1, columns=ax2)
                    .values
                )
                self.add(Data2D(
                    data_type       = param,
                    data_convention = index_key,
                    axis1           = ax1,
                    axis2           = ax2,
                    grid            = grid,
                    method          = method,
                ))
    
    def register_zero_rate_for_target(
        self,
        df: pd.DataFrame,
        value_date: Date,
        target: str,
        method: str = "PIECEWISE_CONSTANT"
    ) -> None:
        
        if isinstance(value_date, str):
            value_date = Date(value_date)

        sub = df[df["INDEX"] == target]
        if sub.empty:
            raise KeyError(f"No zero‐rate data for {target}")

        if target.endswith("1B"):
            ql_idx = IndexRegistry().get(target)
        else:
            base, tenor = target.rsplit("-", 1)
            ql_idx       = IndexRegistry().get(base, tenor)

        cal = ql_idx.fixingCalendar()
        bdc = ql_idx.businessDayConvention()

        year_fracs: list[float] = []
        for tenor_str in sub["AXIS1"]:
            p  = Period(tenor_str)                      
            dt = cal.advance(value_date, p, bdc)
            year_fracs.append(accrued(value_date, dt))

        rates = sub["VALUES"].to_numpy()

        md = Data1D(
            data_type       = "ZERO_RATE",
            data_convention = target,
            axis            = year_fracs,
            values          = rates,
            method          = method.upper(),
        )

        self._store[(md.data_type, md.data_convention)] = md

    def register_surface_dataframe(
        self,
        df: pd.DataFrame,
        axis1_col: str,
        axis2_col: str,
        value_cols: list[str],
        data_convention_col: str = "INDEX",
        method: str = "LINEAR"
    ) -> None:
        
        for index_key, sub in df.groupby(data_convention_col):
            ax1 = np.sort(sub[axis1_col].astype(float).unique())
            ax2 = np.sort(sub[axis2_col].astype(float).unique())
            for param in value_cols:
                grid = (
                    sub
                    .pivot_table(index=axis1_col, columns=axis2_col, values=param)
                    .reindex(index=ax1, columns=ax2)
                    .values
                )
                self.add(Data2D(
                    data_type       = param,
                    data_convention = index_key,
                    axis1           = ax1,
                    axis2           = ax2,
                    grid            = grid,
                    method          = method.upper(),
                ))
        