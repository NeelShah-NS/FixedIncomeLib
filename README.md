# FixedIncomeLib

**FixedIncomeLib** is a library for end‑to‑end fixed‑income analytics. It covers everything from raw market data ingestion through yield‑curve calibration to SABR‐based volatility modeling and instrument valuation and risk calculation.

---

## Features

- **Data Layer**: Load and validate 1D (curves) and 2D (surfaces) market data via `Data1D` and `Data2D`.
- **Date Utilities**: Unified `Date` subclass, tenor arithmetic, business‑day adjustments, and accrual calculations.
- **Market Conventions**: Pluggable day‑count, business‑day, holiday calendars, and index definitions.
- **Interpolation**: Fast piecewise‑constant (`Interpolator1D`) and bilinear (`Interpolator2D`) routines.
- **Yield‑Curve Modeling**: Bootstrap discount and forward curves for both IBOR and OIS indices.
- **SABR Modeling**: Grid‑based parameter storage with both bottom‐up and top‐down aggregation approaches.
- **Products**: Atomic cashflows, swaps, cap/floorlets, swaptions, futures, and composite portfolios.
- **Valuation Engines**: Modular, registry‑driven engines for discounting, forward accrual, and SABR option pricing.
- **Analytics**: Helper functions, volatility conversions, correlation surfaces, and a unified `SABRCalculator`.

---

## Repository Structure

```
├── data/                  # Data1D, Data2D, DataCollection
├── date/                  # Date wrapper and utils (addPeriod, moveToBusinessDay, accrued)
├── market/                # Conventions (day‑count, calendars, indices)
├── utilities/             # Numerics (interpolators) and other helpers
├── model/                 # Abstract Model & ModelComponent interfaces
├── product/               # Instrument classes and display visitors
├── valuation/             # ValuationEngine base, registry, and fixing manager
├── yield_curve/           # YieldCurve model, calibration, and YC engines
├── sabr/                  # SABR model, components, and SABR engines
├── analytics/             # Pricing helpers and SABR calculators
├── tests/                 # Jupyter notebooks and unit tests
└── docs/                  # LaTeX report and diagrams
```

---

## Getting Started

1. **Clone the repo**

   ```bash
   git clone https://github.com/your-org/FixedIncomeLib.git
   cd FixedIncomeLib
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Run examples**

   - Launch the Jupyter notebooks in `tests/` to see end‑to‑end workflows.

---

## Usage

```python
from data import Data1D, DataCollection
from date import Date
from yield_curve import YieldCurve

# 1. Load zero rates
d1 = Data1D.createDataObject("zero_rate", "USD-LIBOR-BBA-3M", df_zero)

# 2. Build data collection and yield curve
dc = DataCollection([d1])
yc = YieldCurve("2025-08-01", dc, [{"TARGET":"USD-LIBOR-BBA-3M"}])

# 3. Compute a discount factor
df_6m = yc.discountFactor("USD-LIBOR-BBA-3M", "2025-02-01")
```

For SABR pricing, see `tests/SABR_demo.ipynb`.

---

## Contributing

Contributions are welcome! Please open issues or pull requests for bugfixes, enhancements, or new instruments and engines.

---

## License

This project is licensed under the MIT License.

