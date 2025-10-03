from typing import List, Tuple
import numpy as np
from date import Date, accrued

def _num_products(portfolio) -> int:
    num = getattr(portfolio, "numProducts", getattr(portfolio, "count", None))
    if num is None:
        raise AttributeError("Portfolio missing numProducts/count.")
    return int(num() if callable(num) else num)

def anchor_date(product) -> Date:
    return product.lastDate

def fixed_leg_dates_alphas(product, value_date: Date) -> Tuple[List[Date], np.ndarray]:
    fixed_leg = product.fixedLeg
    num_cfs   = fixed_leg.numProducts
    if num_cfs <= 0:
        raise RuntimeError("Fixed leg is empty.")

    swap_start: Date = product.effectiveDate
    payment_dates: List[Date] = []
    accrual_factors: List[float] = []

    period_start = swap_start
    for i in range(num_cfs):
        payment_date = fixed_leg.element(i).lastDate
        accrual_factors.append(float(accrued(period_start, payment_date)))
        payment_dates.append(payment_date)
        period_start = payment_date

    return payment_dates, np.asarray(accrual_factors, dtype=float)

def build_anchor_pillars(items: List, value_date: Date) -> Tuple[List[Date], List[float], List]:
    candidates = []
    for basket_item in items:
        anchor_dt = anchor_date(basket_item.product)
        t_anchor  = float(accrued(value_date, anchor_dt))
        candidates.append((t_anchor, int(anchor_dt.serialNumber()), anchor_dt, basket_item))
    candidates.sort(key=lambda x: (x[0], x[1]))

    pillar_dates: List[Date] = []
    pillar_times: List[float] = []
    kept_items: List = []
    last_time = None
    last_serial = None
    for t_anchor, serial, anchor_dt, basket_item in candidates:
        if last_time is not None and (t_anchor <= last_time or serial <= last_serial):
            prev_dt = pillar_dates[-1]
            raise RuntimeError(f"Non-increasing anchors: {anchor_dt} after {prev_dt}.")
        pillar_dates.append(anchor_dt)
        pillar_times.append(t_anchor)
        kept_items.append(basket_item)
        last_time, last_serial = t_anchor, serial

    if not pillar_times:
        raise RuntimeError("No pillars produced.")
    return pillar_dates, pillar_times, kept_items
