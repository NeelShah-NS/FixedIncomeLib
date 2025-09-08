# FixedIncomeLib/builders/basket_builders.py
from __future__ import annotations
from typing import Iterable
from conventions.data_conventions import DataConventionRegistry
from .instrument_builders import _build_product
from yield_curve.calibration_basket import CalibItem, CalibrationBasket

def build_yc_calibration_basket(*, value_date: str, data_objs: Iterable) -> CalibrationBasket:
    basket = CalibrationBasket()
    for d in data_objs:
        conv = DataConventionRegistry().get(str(d.data_convention))
        for axis, quote in zip(d.axis, d.values):
            prod = _build_product(
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
