from __future__ import annotations
from typing import Iterable, List, Dict, Any
import pandas as pd
from fixedincomelib.conventions.data_conventions import DataConventionRegistry
from fixedincomelib.yield_curve.calibration_basket import CalibItem, CalibrationBasket
from fixedincomelib.builders import instrument_builders                       
from fixedincomelib.builders.product_builder_registry import ProductBuilderRegistry
from fixedincomelib.data import DataCollection, Data1D, build_yc_data_collection

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
def _collect_data1d_from_dc(dc: DataCollection, instruments: Iterable[str]) -> List[Data1D]:
    wanted = {str(x).strip().upper() for x in instruments}
    found: List[Data1D] = []

    dm = getattr(dc, "dataMap", {})
    for (_, dconv), obj in dm.items():
        if not isinstance(obj, Data1D):
            continue
        if str(dconv).strip().upper() in wanted:
            # Basic shape validation
            axes = getattr(obj, "axis", None)
            vals = getattr(obj, "values", None)
            if axes is None or vals is None:
                raise ValueError(f"Data1D {dconv} is missing axis/values.")
            if len(axes) != len(vals):
                raise ValueError(
                    f"Data1D length mismatch for {dconv}: {len(axes)} axes vs {len(vals)} values"
                )
            found.append(obj)

    return found


def build_yc_calibration_basket_from_dc(*,
    value_date: str,
    data_collection: DataCollection,
    build_method: Dict[str, Any]
):
    insts = build_method.get("INSTRUMENTS", [])
    if not insts:
        raise ValueError("build_method must include a non-empty 'INSTRUMENTS' list.")

    data_objs = _collect_data1d_from_dc(data_collection, insts)

    if not data_objs:
        dm = getattr(data_collection, "dataMap", {})
        available = sorted({str(k[1]).strip() for k, v in dm.items() if isinstance(v, Data1D)})
        raise KeyError(
            "No Data1D found in DataCollection for requested conventions: "
            f"{[str(x) for x in insts]}. "
            f"Available Data1D conventions: {available}. "
            "Make sure build_yc_data_collection(MARKET_DF) was called with matching 'DATA CONVENTION' values."
        )

    return build_yc_calibration_basket(value_date=value_date, data_objs=data_objs)