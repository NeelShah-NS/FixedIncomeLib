from __future__ import annotations
import pandas as pd
from fixedincomelib.data import Data1D, DataCollection

def _axis_pair(s: str) -> tuple[str, str]:
    a, b = (p.strip() for p in str(s).replace("X", "x").split("x", 1))
    if not a or not b:
        raise ValueError(f"Bad futures AXIS: {s}")
    return a, b

def _axis_future(col: pd.Series) -> list[tuple[str, str]]:
    return [_axis_pair(x) for x in col]

def _axis_swap(col: pd.Series) -> list[str]:
    return [str(x).strip().upper() for x in col]

def _axis_date(col: pd.Series) -> list[str]:
    return [str(x).strip() for x in col]

_AX_BUILDERS = {
    "RFR FUTURE":  _axis_future,  # still pair
    "RFR SWAP":    _axis_swap,
    "IBOR FUTURE": _axis_date,    # single date
    "IBOR SWAP":   _axis_swap,
}

def build_yc_data_collection(market_df: pd.DataFrame):
    data_objs: list[Data1D] = []
    for (dtype, dconv), sub in market_df.groupby(["DATA TYPE", "DATA CONVENTION"], sort=False):
        kind = str(dtype).strip().upper()
        axes = _AX_BUILDERS[kind](sub["AXIS"])
        vals = sub["VALUE"].astype(float).tolist()
        data_objs.append(Data1D(
            data_convention=dconv,
            axis=axes,
            values=vals,
            data_type=str(dtype),
        ))
    return data_objs, DataCollection(data_objs)
