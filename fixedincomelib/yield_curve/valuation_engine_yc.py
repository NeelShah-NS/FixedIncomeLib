from typing import Optional
import numpy as np
import pandas as pd
from fixedincomelib.yield_curve.yield_curve_model import YieldCurve
from fixedincomelib.product import (LongOrShort, ProductIborCashflow, ProductBulletCashflow, ProductFuture, ProductRfrFuture,ProductIborSwap,ProductOvernightSwap,
                        ProductOvernightIndexCashflow, ProductPortfolio)
from fixedincomelib.valuation import (ValuationEngine, ValuationEngineRegistry, IndexManager)
from fixedincomelib.date.utilities import accrued, business_day_schedule

class ValuationEngineProductBulletCashflow(ValuationEngine):

    def __init__(self, model : YieldCurve, valuationParameters : dict, product : ProductBulletCashflow):
            super().__init__(model, valuationParameters, product)
            self.currency     = product.currency
            self.maturity     = product.paymentDate_
            self.buyOrSell    = 1. if product.longOrShort.value == LongOrShort.LONG else -1.
            self.notional     = product.notional
            self.fundingIndex = valuationParameters['FUNDING INDEX']
            
    def calculateValue(self):
            discountFactor = self.model.discountFactor(self.fundingIndex, self.maturity)
            self.value_ = [self.currency.value.code(), self.notional * self.buyOrSell * discountFactor]
    
    def calculateFirstOrderRisk(self, gradient=None, scaler=1.0, accumulate=False):
            if gradient is None:
                gradient = self.model.gradient_
                if not accumulate:
                    self.model.clearGradient()

            undiscounted = self.buyOrSell * float(self.notional)
            pay_date = self.maturity

            if pay_date is None:
                pay_date = self.lastDate
                
            scale = float(scaler) * undiscounted
            self.model.discountFactorGradientWrtModelParameters(index=self.fundingIndex,
                                                                    to_date=pay_date,
                                                                    gradient=gradient,
                                                                    scaler=scale,
                                                                    accumulate=accumulate)
            self.firstOrderRisk_ = gradient

class ValuationEngineProductIborCashflow(ValuationEngine):
    "Returns undiscounted value"
        
    def __init__(
        self,
        model: YieldCurve,
        valuation_parameters: dict,
        product: ProductIborCashflow
    ):
        super().__init__(model, valuation_parameters, product)
        self.currency        = product.currency
        self.start_date      = product.accrualStart
        self.end_date        = product.accrualEnd
        self.index_name      = product.index
        self.notional        = product.notional
        self.direction       = 1.0 if product.longOrShort.value == LongOrShort.LONG else -1.0
        self.accrualFactor   = product.accrualFactor
        self.funding_index   = valuation_parameters["FUNDING INDEX"]
        self.payment_date    = product.paymentDate
        self.spread          = float(product.spread)

    def calculateValue(self):
        forward_rate   = float(self.model.forward(self.index_name, self.start_date, self.end_date))
        coupon_rate   = forward_rate + self.spread
        pnl            = coupon_rate * self.accrualFactor *self.notional * self.direction
        self.value_    = [self.currency.value.code(), pnl]

    def calculateFirstOrderRisk(self, gradient=None, scaler = 1.0, accumulate = False):
        if gradient is None:
            gradient = self.model.gradient_
            if not accumulate:
                self.model.clearGradient()
        
        self.calculateValue()
        _, undiscounted = self.value_
        undiscounted = float(undiscounted)

        pay_date = self.payment_date
        
        #dDF term
        scale = float(scaler) * undiscounted
        self.model.discountFactorGradientWrtModelParameters(index=self.funding_index,
                                                                    to_date=pay_date,
                                                                    gradient=gradient,
                                                                    scaler=scale,
                                                                    accumulate=accumulate)
        
        #dF term
        dFactor = float(self.model.discountFactor(self.funding_index, pay_date))
        forward_scaler = float(scaler) * dFactor * self.direction * self.notional * self.accrualFactor
        self.model.forwardRateGradientWrtModelParameters(index= self.index_name,
                                                         start_time = self.start_date,
                                                         end_time = self.end_date,
                                                         gradient = gradient,
                                                         scaler = forward_scaler,
                                                         accumulate = True) 
        self.firstOrderRisk_ = gradient

class ValuationEngineProductOvernightIndexCashflow(ValuationEngine):    
    "Returns undiscounted value"

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
        self.index_manager      = IndexManager.instance()
        self.funding_index      = valuation_parameters["FUNDING INDEX"]
        self.payment_date       = product.paymentDate
        self.compound_factor    = 1.0
        self.stub_start         = self.effective_date
        self.spread             = float(product.spread)

    def calculateValue(self):
        component_idx        = self.model.retrieveComponent(self.index_name)
        day_counter          = component_idx.targetIndex.dayCounter()  
        realizedend_date     = min(self.valuation_date, self.termination_date)
        historical_fixings   = self.index_manager.get_fixings(
            self.index_name,
            self.effective_date,
            realizedend_date
        )

        calendar = component_idx.targetIndex.fixingCalendar()
        schedule_dates = business_day_schedule(self.effective_date, self.termination_date, calendar)

        compound_factor       = 1.0
        realized_accrual      = 0.0
        previous_accrual_date = self.effective_date

        for i in range(len(schedule_dates) - 1):
            segment_start = schedule_dates[i]
            segment_end   = schedule_dates[i + 1]

            if segment_start >= realizedend_date:
                break

            if segment_end > realizedend_date:
                segment_end = realizedend_date

            previous_accrual_date = segment_start 
            fixing_date = segment_start

            fixing_rate = historical_fixings.get(fixing_date, None)
            if fixing_rate is None:
                fixing_rate = self.model.forward(self.index_name, segment_start, segment_end)

            period_fraction = float(day_counter.yearFraction(segment_start, segment_end))

            if self.compounding_type == "COMPOUND":
                compound_factor *= (1.0 + float(fixing_rate) * period_fraction)
            else:
                realized_accrual += float(fixing_rate) * period_fraction

        if self.compounding_type == "COMPOUND":
            realized_accrual = compound_factor - 1.0

        forward_accrual = 0.0
        stubstart = max(self.valuation_date, self.effective_date)
        
        if stubstart < self.termination_date:
            if stubstart not in schedule_dates:
                stubstart = None if len(schedule_dates) == 0 else schedule_dates[-1]
                for d in schedule_dates:
                    if d >= max(self.valuation_date, self.effective_date):
                        stubstart = d
                        break

            if stubstart < self.termination_date:
                start_idx = 0
                for k, d in enumerate(schedule_dates):
                    if d == stubstart:
                        start_idx = k
                        break

                stub_fraction = float(day_counter.yearFraction(stubstart, self.termination_date))

                if self.compounding_type == "COMPOUND":
                    total_factor = float(compound_factor)

                    for i in range(start_idx, len(schedule_dates) - 1):
                        segment_start = schedule_dates[i]
                        segment_end   = schedule_dates[i + 1]

                        if segment_start >= self.termination_date:
                            break

                        forward_rate = self.model.forward(self.index_name, segment_start, segment_end)
                        period_fraction = float(day_counter.yearFraction(segment_start, segment_end))
                        total_factor *= (1.0 + float(forward_rate) * period_fraction)

                    forward_accrual = (total_factor - 1.0) - realized_accrual

                else:
                    accr_sum = 0.0
                    for i in range(start_idx, len(schedule_dates) - 1):
                        segment_start = schedule_dates[i]
                        segment_end   = schedule_dates[i + 1]

                        if segment_start >= self.termination_date:
                            break

                        forward_rate = self.model.forward(self.index_name, segment_start, segment_end)
                        period_fraction = float(day_counter.yearFraction(segment_start, segment_end))
                        accr_sum += float(forward_rate) * period_fraction

                    forward_accrual = accr_sum
        
        total_year_fraction = float(day_counter.yearFraction(self.effective_date, self.termination_date))
        spread_accrual = self.spread * total_year_fraction

        total_accrual = realized_accrual + forward_accrual + spread_accrual
        present_value = self.notional * self.direction * total_accrual
        self.value_    = [self.currency.value.code(), present_value]

        self.compound_factor = float(compound_factor)
        self.stub_start = stubstart
    
    def calculateFirstOrderRisk(self, gradient=None, scaler = 1.0, accumulate = False):
        if gradient is None:
            gradient = self.model.gradient_
            if not accumulate:
                self.model.clearGradient()
        
        self.calculateValue()
        _, undiscounted = self.value_
        undiscounted = float(undiscounted)

        pay_date = self.payment_date
        
        #dDF term
        scale = float(scaler) * undiscounted
        self.model.discountFactorGradientWrtModelParameters(index=self.funding_index,
                                                                    to_date=pay_date,
                                                                    gradient=gradient,
                                                                    scaler=scale,
                                                                    accumulate=accumulate)

        #dF term
        stub_start = self.stub_start
        if stub_start < self.termination_date:
            component_idx         = self.model.retrieveComponent(self.index_name)
            day_counter           = component_idx.targetIndex.dayCounter()
            calendar              = component_idx.targetIndex.fixingCalendar()
            schedule_dates        = business_day_schedule(self.effective_date, self.termination_date, calendar) 
            dFactor               = float(self.model.discountFactor(self.funding_index, pay_date))
            is_compound           = str(self.compounding_type).upper() == "COMPOUND"
            compoundFactor        = float(self.compound_factor) 
            start_idx = None
            for k, d in enumerate(schedule_dates):
                if d == stub_start:
                    start_idx = k
                    break

            if start_idx is None:
                start_idx = 0
                for k, d in enumerate(schedule_dates):
                    if d >= stub_start:
                        start_idx = k
                        break

            if is_compound:
                total_factor = float(compoundFactor)
                forward_rates = []
                accrual_fracs = []

                for i in range(start_idx, len(schedule_dates) - 1):
                    segment_start = schedule_dates[i]
                    segment_end   = schedule_dates[i + 1]
                    if segment_start >= self.termination_date:
                        break

                    fwd = float(self.model.forward(self.index_name, segment_start, segment_end))
                    dt  = float(day_counter.yearFraction(segment_start, segment_end))

                    forward_rates.append(fwd)
                    accrual_fracs.append(dt)
                    total_factor *= (1.0 + fwd * dt)

                for i in range(start_idx, len(schedule_dates) - 1):
                    segment_start = schedule_dates[i]
                    segment_end   = schedule_dates[i + 1]
                    if segment_start >= self.termination_date:
                        break

                    j = i - start_idx
                    fwd = forward_rates[j]
                    dt  = accrual_fracs[j]

                    denom = (1.0 + fwd * dt)
                    if denom == 0.0:
                        continue

                    compounding_parameter = float(total_factor) * float(dt) / float(denom)

                    forward_scaler = float(scaler) * dFactor * self.direction * self.notional * compounding_parameter
                    self.model.forwardRateGradientWrtModelParameters(
                        index=self.index_name,
                        start_time=segment_start,
                        end_time=segment_end,
                        gradient=gradient,
                        scaler=forward_scaler,
                        accumulate=True
                    )

            else:
                for i in range(start_idx, len(schedule_dates) - 1):
                    segment_start = schedule_dates[i]
                    segment_end   = schedule_dates[i + 1]
                    if segment_start >= self.termination_date:
                        break

                    dt = float(day_counter.yearFraction(segment_start, segment_end))
                    compounding_parameter = float(dt)

                    forward_scaler = float(scaler) * dFactor * self.direction * self.notional * compounding_parameter
                    self.model.forwardRateGradientWrtModelParameters(
                        index=self.index_name,
                        start_time=segment_start,
                        end_time=segment_end,
                        gradient=gradient,
                        scaler=forward_scaler,
                        accumulate=True
                    )
        
        self.firstOrderRisk_ = gradient

class ValuationEngineProductFuture(ValuationEngine):

    def __init__(self,
            model: YieldCurve,
            valuation_parameters: dict,
            product: ProductFuture):
        super().__init__(model, valuation_parameters, product)
        self.currency      = product.currency.value.code()
        self.strike        = product.strike
        self.direction     = 1.0 if product.longOrShort.value == LongOrShort.LONG else -1.0
        self.notional      = product.notional
        self.accrualFactor = product.accrualFactor
        self.start_date    = product.effectiveDate
        self.end_date      = product.maturityDate
        self.index_name    = product.index    
        self.funding_index = valuation_parameters["FUNDING INDEX"] 

        ibor_leg = ProductIborCashflow(
            startDate   = product.effectiveDate,
            endDate     = product.maturityDate,
            index       = self.index_name,
            spread      = 0.0,
            notional    = 1.0,
            longOrShort = "Long"
        )
        self._ibor_engine = ValuationEngineRegistry().new_valuation_engine(model, valuation_parameters, ibor_leg)

    def calculateValue(self):
        
        self._ibor_engine.calculateValue()
        _, pv_unit = self._ibor_engine.value_
        forward_rate = pv_unit / self.accrualFactor
        futures_price = 100.0 * (1.0 - forward_rate)
        discount_factor = self.model.discountFactor(self.funding_index, self.end_date)
        pnl = (futures_price - self.strike) * self.notional * self.direction * discount_factor
        self.value_ = [self.currency, pnl]

    def calculateFirstOrderRisk(self, gradient: Optional[np.ndarray] = None, scaler: float = 1.0, accumulate: bool = False):
        if gradient is None:
            gradient = self.model.gradient_
            if not accumulate:
                self.model.clearGradient()
        
        self._ibor_engine.calculateValue()
        _, undiscounted_unit = self._ibor_engine.value_
        forward_rate = float(undiscounted_unit)/ float(self.accrualFactor)
        undiscounted = (100.0 * (1.0 - forward_rate) - float(self.strike)) * float(self.notional) * float(self.direction)
        scale = float(undiscounted) * float(scaler)
        dFactor = float(self.model.discountFactor(self.funding_index, self.end_date))

        #dDF term
        self.model.discountFactorGradientWrtModelParameters(
            index=self.funding_index,
            to_date=self.end_date,
            gradient=gradient,
            scaler=scale,
            accumulate=True
        )

        #dF term
        scale_fwd = float(scaler) * dFactor * (-100.0 * self.direction * self.notional)
        self.model.forwardRateGradientWrtModelParameters(index = self.index_name,
                                                         start_time = self.start_date,
                                                         end_time = self.end_date,
                                                         gradient = gradient,
                                                         scaler = scale_fwd,
                                                         accumulate = True)
        
        self.firstOrderRisk_ = gradient

class ValuationEngineProductRfrFuture(ValuationEngine):

    def __init__(self,
                model: YieldCurve,
                valuation_parameters: dict,
                product: ProductRfrFuture):
        super().__init__(model, valuation_parameters, product)
        self.currency      = product.currency.value.code()
        self.strike        = product.strike
        self.direction     = 1.0 if product.longOrShort.value == LongOrShort.LONG else -1.0
        self.notional      = product.notional
        self.start         = product.effectiveDate
        self.end           = product.maturityDate
        self.index_name    = product.index
        self.funding_index = valuation_parameters["FUNDING INDEX"]
        self.accrualFactor = product.accrualFactor

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

        r_ann = total_index / self.accrualFactor
        futures_price = 100.0 * (1.0 - r_ann)
        discount_factor = self.model.discountFactor(self.funding_index, self.end)
        pnl = (futures_price - self.strike) * self.notional * self.direction * discount_factor
        self.value_ = [self.currency, pnl]
    
    def calculateFirstOrderRisk(self, gradient: Optional[np.ndarray] = None, scaler: float = 1.0, accumulate: bool = False):
        if gradient is None:
            gradient = self.model.gradient_
            if not accumulate:
                self.model.clearGradient()

        self._ois_engine.calculateValue()
        _, undiscounted_unit = self._ois_engine.value_
        forward_rate = float(undiscounted_unit)/float(self.accrualFactor)
        undiscounted = (100.0 * (1.0 - forward_rate) - float(self.strike)) * float(self.notional) * float(self.direction)
        dFactor = float(self.model.discountFactor(self.funding_index, self.end))
        scale = float(undiscounted) * float(scaler)

        #dDF term
        self.model.discountFactorGradientWrtModelParameters(
            index=self.funding_index,
            to_date=self.end,
            gradient=gradient,
            scaler=scale,
            accumulate=accumulate
        )

        #dF term
        scale_fwd = float(scaler) * dFactor * (-100.0 * self.direction * self.notional)
        self.model.forwardRateGradientWrtModelParameters(index = self.index_name,
                                                         start_time = self.start,
                                                         end_time = self.end,
                                                         gradient = gradient,
                                                         scaler = scale_fwd,
                                                         accumulate = True)
        
        self.firstOrderRisk_ = gradient

class ValuationEngineProductPortfolio(ValuationEngine):
    
    def __init__(
        self,
        model: YieldCurve,
        valuation_parameters: dict,
        product: ProductPortfolio
    ):
        super().__init__(model, valuation_parameters, product)
        # build one engine per element in the portfolio
        self._engines = [ValuationEngineRegistry().new_valuation_engine(model, valuation_parameters, product.element(i))
            for i in range(product.numProducts)]

    def calculateValue(self):
        total_pv = 0.0
        currency = None

        for eng in self._engines:
            eng.calculateValue()
            currency, pv = eng.value_
            total_pv += pv

        self.value_ = [currency, total_pv]
    
    def calculateFirstOrderRisk(self, gradient=None, scaler: float = 1.0, accumulate: bool = False) -> None:
        if gradient is None:
            grad = self.model.gradient_
        else:
            grad = gradient

        if not accumulate:
            if gradient is None:
                self.model.clearGradient()
            else:
                grad[:] = 0.0

        for eng in self._engines:
            eng.calculateFirstOrderRisk(gradient=grad, scaler=float(scaler), accumulate=True)

        self.firstOrderRisk_ = grad


class ValuationEngineInterestRateStream(ValuationEngine):
    def __init__(self, model: YieldCurve, valuation_parameters: dict, product):
        super().__init__(model, valuation_parameters, product)

        if "FUNDING INDEX" not in valuation_parameters:
            raise KeyError(
                "When valuing swaps, 'FUNDING INDEX' must be provided in valuation_parameters"
            )
        self.funding_index = valuation_parameters["FUNDING INDEX"]
        self.currency = product.currency.value.code()
        self.direction = 1.0 if product.longOrShort.value == LongOrShort.LONG else -1.0
        self.notional = float(product.notional)
        child_vp = dict(valuation_parameters)

        self._float_engine = ValuationEngineRegistry().new_valuation_engine(model, child_vp, product.floatingLeg)
        self._fixed_engine = ValuationEngineRegistry().new_valuation_engine(model, child_vp, product.fixedLeg)

    def calculateValue(self):
        
        self._fixed_engine.calculateValue()
        ccy_fixed, pv_fixed = self._fixed_engine.value_

        pv_float = 0.0
        ccy_float = ccy_fixed

        if hasattr(self._float_engine, "_engines"):
            for eng in self._float_engine._engines:
                eng.calculateValue()
                ccy, amt = eng.value_
                ccy_float = ccy

                prod = eng.product
                prod_type = getattr(prod, "prodType", "")

                if prod_type in ("ProductOvernightIndexCashflow", "ProductIborCashflow"):
                    pay_dt = prod.paymentDate_
                    if pay_dt is None:
                        raise AttributeError(f"{prod_type} missing paymentDate/paymentDate_")
                    df = self.model.discountFactor(self.funding_index, pay_dt)
                    pv_float += amt * df
                else:
                    pv_float += amt
        else:
            self._float_engine.calculateValue()
            ccy_float, pv_float = self._float_engine.value_

        total = pv_fixed + pv_float
        self._pv_fixed = pv_fixed
        self._pv_float = pv_float
        self.value_ = [ccy_float, total]

    def annuity(self) -> float:
        fixed_rate = self.product.fixedRate
        notional   = self.product.notional
        if fixed_rate == 0 or notional == 0:
            raise RuntimeError(f"Cannot compute annuity: fixedRate={fixed_rate}, notional={notional}")
        return self._pv_fixed / (fixed_rate * notional)

    def parRateOrSpread(self) -> float:
        notional = self.product.notional
        return - self._pv_float / (notional * self.annuity())
    
    def calculateFirstOrderRisk(self, gradient=None, scaler=1.0, accumulate=False):

        if gradient is None:
            gradient = self.model.gradient_
            if not accumulate:
                self.model.clearGradient()
        
        #FIXED LEG
        if hasattr(self._fixed_engine, "_engines"):
            for eng in self._fixed_engine._engines:
                eng.calculateFirstOrderRisk(gradient=gradient, scaler=scaler, accumulate=True)
        else:
            self._fixed_engine.calculateFirstOrderRisk(gradient=gradient, scaler=scaler, accumulate=True)

        #FLOATING LEG
        if hasattr(self._float_engine, "_engines"):
            for eng in self._float_engine._engines:
                eng.calculateFirstOrderRisk(gradient=gradient, scaler=scaler, accumulate=True)
        else:
            self._float_engine.calculateFirstOrderRisk(gradient=gradient, scaler=scaler, accumulate=True)
                        
        self.firstOrderRisk_ = gradient

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