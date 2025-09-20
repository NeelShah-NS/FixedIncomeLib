from __future__ import annotations
from typing import Iterable, List, Dict, Any
import pandas as pd
from conventions.data_conventions import DataConventionRegistry
from yield_curve.calibration_basket import CalibItem, CalibrationBasket
from . import instrument_builders                       
from .product_builder_registry import ProductBuilderRegistry
from data import DataCollection
from data.yc_market_loader import build_yc_data_collection  


def build_yc_calibration_basket(*, value_date: str, data_objs: Iterable) -> CalibrationBasket:
    basket = CalibrationBasket()
    reg = ProductBuilderRegistry()  

    for d in data_objs:
        conv = DataConventionRegistry().get(str(d.data_convention))
        for axis, quote in zip(d.axis, d.values):
            prod = reg.new_product(
                conv,
                value_date=value_date,
                axis_entry=axis,
                value=float(quote),
                notional=None,
                long_or_short="LONG",
            )
            basket.add(CalibItem(
                product=prod,
                quote=float(quote),
                data_type=getattr(d, "data_type", ""),
                data_convention=str(d.data_convention),
                axis=axis,
            ))
    return basket


# ---------------------------------------------------------------------------
# Helpers to build a basket directly from DataCollection using the build method
# ---------------------------------------------------------------------------

def _filtered_market_df(dc: DataCollection, target: str, bm: Dict[str, Any]) -> pd.DataFrame:
    if "INSTRUMENTS" not in bm or not bm["INSTRUMENTS"]:
        raise ValueError("build_method must include a non-empty 'INSTRUMENTS' list.")

    df = dc.get('market_quote', target)
    df = df if isinstance(df, pd.DataFrame) else pd.DataFrame(df)

    inst = [str(x) for x in bm["INSTRUMENTS"]]
    mask = df["DATA CONVENTION"].isin(inst) | df["DATA TYPE"].isin(inst)
    df = df[mask].reset_index(drop=True)

    if df.empty:
        raise ValueError("No market rows found for requested INSTRUMENTS.")
    return df


def build_yc_calibration_basket_from_dc(*,
    value_date: str,
    data_collection: DataCollection,
    build_method: Dict[str, Any]
) -> CalibrationBasket:
    target = str(build_method.get("TARGET", ""))
    mdf = _filtered_market_df(data_collection, target, build_method)

    data_objs, _ = build_yc_data_collection(mdf)

    return build_yc_calibration_basket(value_date=value_date, data_objs=data_objs)
