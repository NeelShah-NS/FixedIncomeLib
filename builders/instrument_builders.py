from __future__ import annotations
from functools import singledispatch
from typing import List
from date.classes import Date
from date.utilities import addPeriod, applyOffset
from conventions.data_conventions import (
    DataConvention, DataConventionRegistry,
    DataConventionRFRSwap, DataConventionRFRFuture,
)
from product.linear_products import ProductRfrFuture, ProductOvernightSwap

@singledispatch
def _build_product(
    conv: DataConvention, *,
    value_date: str,
    axis_entry,
    value: float,
    notional: float | None,
    long_or_short: str,
):
    raise TypeError(f"Unsupported convention type: {type(conv).__name__}")

@_build_product.register
def _(
    conv: DataConventionRFRFuture, *,
    value_date: str,
    axis_entry,
    value: float,
    notional: float | None,
    long_or_short: str,
):
    start_iso, end_iso = axis_entry
    implied_rate = (100.0 - float(value)) / 100.0
    use_notional = notional if notional is not None else 1.0
    return ProductRfrFuture(
        effectiveDate=start_iso,
        termOrEnd=end_iso,
        index=conv.index_key,
        compounding="COMPOUND",
        strike=implied_rate,
        notional=use_notional,
        longOrShort=long_or_short,
    )

@_build_product.register
def _(
    conv: DataConventionRFRSwap, *,
    value_date: str,
    axis_entry,
    value: float,
    notional: float | None,
    long_or_short: str,
):
    spot: Date = applyOffset(value_date, conv.payment_offset, conv.payment_hol_conv, conv.payment_biz_day_conv)
    maturity: Date = addPeriod(spot, str(axis_entry).strip().upper(), conv.payment_biz_day_conv, conv.payment_hol_conv)
    use_notional = notional if notional is not None else 1.0
    return ProductOvernightSwap(
        effectiveDate=spot,
        maturityDate=maturity,
        frequency=conv.accrual_period,
        overnightIndex=conv.index_key,
        spread=0.0,
        fixedRate=float(value),
        notional=use_notional,
        position=("SHORT" if long_or_short.upper() == "SHORT" else "LONG"),
        holConv=conv.payment_hol_conv,
        bizConv=conv.payment_biz_day_conv,
        accrualBasis=conv.accrual_basis,
        rule="BACKWARD",
        endOfMonth=False,
    )

def create_products_from_data1d(*, value_date: str, data1d) -> List:
    if len(data1d.axis) != len(data1d.values):
        raise ValueError(f"Data1D length mismatch: axis={len(data1d.axis)} values={len(data1d.values)}")
    conv = DataConventionRegistry().get(str(data1d.data_convention))
    prods: List = []
    for axis_entry, quote in zip(data1d.axis, data1d.values):
        prods.append(_build_product(
            conv,
            value_date=value_date,
            axis_entry=axis_entry,
            value=float(quote),
            notional=None,
            long_or_short="LONG",
        ))
    return prods
