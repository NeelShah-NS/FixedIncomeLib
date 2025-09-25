from date import Date, Period, accrued

def make_default_pillars(value_date, target_index):
    cal = target_index.fixingCalendar()
    bdc = target_index.businessDayConvention()

    dates = []
    # 3M → 3Y
    for m in range(3, 36 + 1, 3):
        dates.append(Date(cal.advance(value_date, Period(f"{m}M"), bdc)))
    # annual 4Y → 10Y
    for y in range(4, 10 + 1):
        dates.append(Date(cal.advance(value_date, Period(f"{y}Y"), bdc)))
    # long end
    for y in [15, 20, 25, 30, 40, 50, 60]:
        dates.append(Date(cal.advance(value_date, Period(f"{y}Y"), bdc)))

    seen, uniq = set(), []
    for d in dates:
        if not hasattr(d, "serialNumber"):
            d = Date(d)
        k = int(d.serialNumber())
        if k not in seen:
            seen.add(k)
            uniq.append(d)
    uniq.sort(key=lambda d: accrued(value_date, d))

    times = [accrued(value_date, d) for d in uniq]
    if not times:
        one_day = Date(cal.advance(value_date, Period("1D"), bdc))
        uniq = [one_day]
        times = [accrued(value_date, one_day)]
    return uniq, times
