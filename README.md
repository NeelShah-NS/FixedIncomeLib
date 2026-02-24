# FixedIncomeLib

End-to-end fixed-income analytics in Python: market data ingestion -> curve calibration -> product valuation -> risk.
Includes a SABR volatility layer for IR options.

**Repo:** NYU-QuantLab/FixedIncomeLib  
**License:** MIT

---

## What’s inside

- **Data layer:** `Data1D`, `Data2D`, `DataCollection`
- **Dates & conventions:** day-count, calendars, business-day rules, schedules
- **Interpolation:** 1D/2D interpolators for curves & surfaces
- **Yield curves:** OIS / IBOR-style bootstrapping and curve engines
- **SABR:** bottom-up + top-down parameter aggregation
- **Products:** swaps, cap/floorlets, swaptions, futures, portfolios
- **Valuation + risk:** registry-driven engines, PV + first-order risk helpers

---

## Installation

**Python:** 3.11+ (required)

From the repo root:

```bash
python -m pip install -U pip setuptools wheel
pip install -r requirements.txt
pip install -e .

```
## Contributing

Contributions are welcome! Please open issues or pull requests for bugfixes, enhancements, or new instruments and engines.

---

