import pandas as pd
from .yield_curve_model import YieldCurve
from product import (LongOrShort, ProductIborCashflow, ProductBulletCashflow, ProductFuture, ProductRfrFuture,ProductIborSwap,ProductOvernightSwap,
                        ProductOvernightIndexCashflow, ProductPortfolio)
from valuation import (ValuationEngine, ValuationEngineRegistry, IndexManager)
from date.utilities import accrued

class ValuationEngineProductBulletCashflow(ValuationEngine):

    def __init__(self, model : YieldCurve, valuationParameters : dict, product : ProductBulletCashflow):
            super().__init__(model, valuationParameters, product)
            self.currency = product.currency
            self.maturity = product.terminationDate
            self.buyOrSell = 1. if product.longOrShort.value == LongOrShort.LONG else -1.
            self.notional = product.notional
            self.fundingIndex = valuationParameters['FUNDING INDEX']
            
    def calculateValue(self):
            discountFactor = self.model.discountFactor(self.fundingIndex, self.maturity)
            self.value_ = [self.currency.value.code(), self.notional * self.buyOrSell * discountFactor]

ValuationEngineRegistry().insert(
    YieldCurve.modelType,
    ProductBulletCashflow.prodType,
    ValuationEngineProductBulletCashflow
)

class ValuationEngineProductIborCashflow(ValuationEngine):
        
    def __init__(
        self,
        model: YieldCurve,
        valuation_parameters: dict,
        product: ProductIborCashflow
    ):
        super().__init__(model, valuation_parameters, product)
        self.currency    = product.currency
        self.start_date  = product.accrualStart
        self.end_date    = product.accrualEnd
        self.index_name  = product.index
        self.notional    = product.notional
        self.direction   = 1.0 if product.longOrShort.value == LongOrShort.LONG else -1.0
        self.accrualFactor = product.accrualFactor

    def calculateValue(self):
        forward_rate   = self.model.forward(self.index_name, self.start_date, self.end_date)
        pnl            = forward_rate * self.accrualFactor * self.notional * self.direction
        self.value_    = [self.currency.value.code(), pnl]

ValuationEngineRegistry().insert(
    YieldCurve.modelType,
    ProductIborCashflow.prodType,
    ValuationEngineProductIborCashflow
)

class ValuationEngineProductOvernightIndexCashflow(ValuationEngine):
    def __init__(
        self,
        model: YieldCurve,
        valuation_parameters: dict,
        product: ProductOvernightIndexCashflow
    ):
        super().__init__(model, valuation_parameters, product)
        self.currency           = product.currency
        self.effective_date     = product.effectiveDate
        self.termination_date   = product.terminationDate
        self.index_name         = product.index
        self.compounding_type   = product.compounding.upper()  # “COMPOUND” or “AVERAGE”
        self.notional           = product.notional
        self.direction          = (1.0 if product.longOrShort.value == LongOrShort.LONG else -1.0)
        self.valuation_date     = valuation_parameters.get("valuation_date", model.valueDate)
        self.index_manager     = IndexManager.instance()

    def calculateValue(self):
        realized_end_date    = min(self.valuation_date, self.termination_date)
        historical_fixings   = self.index_manager.get_fixings(
            self.index_name,
            self.effective_date,
            realized_end_date
        )

        compound_factor      = 1.0
        realized_accrual     = 0.0
        previous_accrual_date= self.effective_date

        for fixing_date, fixing_rate in sorted(historical_fixings.items()):
            period_fraction = accrued(previous_accrual_date, fixing_date)
            if self.compounding_type == "COMPOUND":
                compound_factor *= (1.0 + fixing_rate * period_fraction)
            else:
                realized_accrual += fixing_rate * period_fraction
            previous_accrual_date = fixing_date

        if self.compounding_type == "COMPOUND":
            realized_accrual = compound_factor - 1.0

        forward_accrual = 0.0
        if self.valuation_date < self.termination_date:
            forward_rate    = self.model.forward(
                self.index_name,
                self.valuation_date,
                self.termination_date
            )
            stub_fraction   = accrued(self.valuation_date, self.termination_date)

            if self.compounding_type == "COMPOUND":
                total_factor    = compound_factor * (1.0 + forward_rate * stub_fraction)
                forward_accrual = (total_factor - 1.0) - realized_accrual
            else:
                # simple average
                forward_accrual = forward_rate * stub_fraction

        total_accrual = realized_accrual + forward_accrual
        present_value = self.notional * self.direction * total_accrual
        self.value_    = [self.currency.value.code(), present_value]


ValuationEngineRegistry().insert(
    YieldCurve.modelType,
    ProductOvernightIndexCashflow.prodType,
    ValuationEngineProductOvernightIndexCashflow
)

class ValuationEngineProductFuture(ValuationEngine):

    def __init__(self,
            model: YieldCurve,
            valuation_parameters: dict,
            product: ProductFuture):
        super().__init__(model, valuation_parameters, product)
        self._ccy       = product.currency.value.code()
        self._strike    = product.strike
        self._dir       = 1.0 if product.longOrShort.value == LongOrShort.LONG else -1.0
        self._notional  = product.notional
        self._accrualFactor = product.accrualFactor

        ibor_leg = ProductIborCashflow(
            startDate   = product.effectiveDate,
            endDate     = product.maturityDate,
            index       = product.index,
            spread      = 0.0,
            notional    = 1.0,
            longOrShort = "Long"
        )
        self._ibor_engine = ValuationEngineRegistry().new_valuation_engine(model, valuation_parameters, ibor_leg)

    def calculateValue(self):
        
        self._ibor_engine.calculateValue()
        _, pv_unit = self._ibor_engine.value_
        forward_rate = pv_unit / self._accrualFactor
        futures_price = 100.0 * (1.0 - forward_rate)
        pnl = (futures_price - self._strike) * self._notional * self._dir
        self.value_ = [self._ccy, pnl]

ValuationEngineRegistry().insert(
    YieldCurve.modelType,
    ProductFuture.prodType,
    ValuationEngineProductFuture
)

class ValuationEngineProductRfrFuture(ValuationEngine):

    def __init__(self,
                model: YieldCurve,
                valuation_parameters: dict,
                product: ProductRfrFuture):
        super().__init__(model, valuation_parameters, product)
        self._ccy       = product.currency.value.code()
        self._strike    = product.strike
        self._dir       = 1.0 if product.longOrShort.value == LongOrShort.LONG else -1.0
        self._notional  = product.notional
        self._start    = product.effectiveDate
        self._end      = product.maturityDate

        overnight_leg = ProductOvernightIndexCashflow(
            effectiveDate = product.effectiveDate,
            termOrEnd     = product.maturityDate,
            index         = product.index,
            compounding   = product.compounding,
            spread        = 0.0,
            notional      = 1.0,
            longOrShort   = "Long"
        )
        self._ois_engine = ValuationEngineRegistry().new_valuation_engine(model, valuation_parameters, overnight_leg)

    def calculateValue(self):
        self._ois_engine.calculateValue()
        _, total_index = self._ois_engine.value_

        tau = accrued(self._start, self._end)
        r_ann = total_index / tau
        futures_price = 100.0 * (1.0 - r_ann)
        pnl = (futures_price - self._strike) * self._notional * self._dir
        self.value_ = [self._ccy, pnl]

ValuationEngineRegistry().insert(
    YieldCurve.modelType,
    ProductRfrFuture.prodType,
    ValuationEngineProductRfrFuture
)

class ValuationEngineProductPortfolio(ValuationEngine):
    
    def __init__(
        self,
        model: YieldCurve,
        valuation_parameters: dict,
        product: ProductPortfolio
    ):
        super().__init__(model, valuation_parameters, product)
        # build one engine per element in the portfolio
        self._engines = [
            ValuationEngineRegistry().new_valuation_engine(model, valuation_parameters, product.element(i))
            for i in range(product.numProducts)]

    def calculateValue(self):
        total_pv = 0.0
        currency = None

        for eng in self._engines:
            eng.calculateValue()
            currency, pv = eng.value_
            total_pv += pv

        self.value_ = [currency, total_pv]

ValuationEngineRegistry().insert(
    YieldCurve.modelType,
    ProductPortfolio.prodType,
    ValuationEngineProductPortfolio
)

class ValuationEngineInterestRateStream(ValuationEngine):
    def __init__(self, model: YieldCurve, valuation_parameters: dict, product):
        super().__init__(model, valuation_parameters, product)

        if "FUNDING INDEX" not in valuation_parameters:
            raise KeyError(
                "When valuing swaps, 'FUNDING INDEX' must be provided in valuation_parameters"
            )
        self.funding_index = valuation_parameters["FUNDING INDEX"]
        child_vp = dict(valuation_parameters)

        self._float_engine = ValuationEngineRegistry().new_valuation_engine(
            model, child_vp, product.floatingLeg
        )
        self._fixed_engine = ValuationEngineRegistry().new_valuation_engine(
            model, child_vp, product.fixedLeg
        )

    def calculateValue(self):
        self._float_engine.calculateValue()
        currency, pv_float = self._float_engine.value_
        self._fixed_engine.calculateValue()
        _, pv_fixed = self._fixed_engine.value_
        self.value_ = [currency, pv_float + pv_fixed]
        self._pv_float = pv_float
        self._pv_fixed = pv_fixed

    def annuity(self) -> float:
        fixed_rate = self.product.fixedRate
        notional   = self.product.notional
        if fixed_rate == 0 or notional == 0:
            raise RuntimeError(f"Cannot compute annuity: fixedRate={fixed_rate}, notional={notional}")
        return self._pv_fixed / (fixed_rate * notional)

    def parRateOrSpread(self) -> float:
        notional   = self.product.notional
        return - self._pv_float / (notional * self.annuity())


# register for both IBOR and OIS swaps
ValuationEngineRegistry().insert(
    YieldCurve.MODEL_TYPE,
    ProductIborSwap.prodType,
    ValuationEngineInterestRateStream
)
ValuationEngineRegistry().insert(
    YieldCurve.MODEL_TYPE,
    ProductOvernightSwap.prodType,
    ValuationEngineInterestRateStream
)



_ENGINE_MAP = {
    ProductBulletCashflow.prodType:          ValuationEngineProductBulletCashflow,
    ProductIborCashflow.prodType:            ValuationEngineProductIborCashflow,
    ProductOvernightIndexCashflow.prodType:  ValuationEngineProductOvernightIndexCashflow,
    ProductFuture.prodType:                  ValuationEngineProductFuture,
    ProductRfrFuture.prodType:               ValuationEngineProductRfrFuture,
    ProductPortfolio.prodType:               ValuationEngineProductPortfolio,
    ProductIborSwap.prodType:                ValuationEngineInterestRateStream,
    ProductOvernightSwap.prodType:           ValuationEngineInterestRateStream,
}

for prod_type, eng_cls in _ENGINE_MAP.items():
    ValuationEngineRegistry().insert(
        YieldCurve.MODEL_TYPE,
        prod_type,
        eng_cls
    )