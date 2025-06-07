import pandas as pd
from .yield_curve_model import YieldCurve
from product import (LongOrShort, ProductBulletCashflow, ProductFuture, ProductRfrFuture,ProductIborSwap,ProductOvernightSwap)
from valuation import (ValuationEngine)
from date import TermOrTerminationDate, Date
from date.utilities import makeSchedule

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

class ValuationEngineProductFuture(ValuationEngine):

    def __init__(self, model: YieldCurve, valuationParameters: dict, product: ProductFuture):
        super().__init__(model, valuationParameters, product)
        self.currency      = product.currency
        self.effectiveDate = product.effectiveDate
        self.indexKey      = product.index
        self.strike        = product.strike
        self.buyOrSell     = 1.0 if product.longOrShort.value == LongOrShort.LONG else -1.0
        self.notional      = product.notional

    def calculateValue(self):
        forwardRate = self.model.forward(self.indexKey, self.effectiveDate)
        #Futures are quoted as Price = 1 − forwardRate
        futuresPrice = 1.0 - forwardRate
        pnl = (futuresPrice - self.strike) * self.notional * self.buyOrSell
        self.value_ = [self.currency.value.code(), pnl ]

class ValuationEngineProductRfrFuture(ValuationEngine):
    def __init__(self, model: YieldCurve, valuationParameters: dict, product: ProductRfrFuture):
        super().__init__(model, valuationParameters, product)
        self.currency       = product.currency
        self.expirationDate = product.expirationDate
        self.indexKey       = product.index
        self.strike         = product.strike
        self.buyOrSell      = 1.0 if product.longOrShort.value == LongOrShort.LONG else -1.0
        self.notional       = product.notional
        self.maturityDate   = product.maturityDate

    def calculateValue(self):
        maturity_str = self.maturityDate.ISO()
        forwardOis = self.model.forward(
            self.indexKey,
            self.expirationDate,
            maturity_str
        )

        futuresPrice = 1.0 - forwardOis
        pnl = (futuresPrice - self.strike) * self.notional * self.buyOrSell
        self.value_ = [ self.currency.value.code(), pnl ]



class ValuationEngineProductIborSwap(ValuationEngine):
    def __init__(
        self,
        model: YieldCurve,
        valuationParameters: dict,
        product: ProductIborSwap
    ):
        super().__init__(model, valuationParameters, product)

        self.currency       = product.currency
        self.effectiveDate  = product.effectiveDate
        self.terminationDate = product.terminationDate
        self.payFixed       = product.payFixed
        self.fixedRate      = product.fixedRate
        self.indexKey       = product.index
        self.notional       = product.notional

        # Assuming `valuationParameters` has exactly: "FIXED FREQUENCY", "HOL CONV", "BIZ CONV", "ACC BASIS" (all strings) in order to build the fixed‐leg schedule.
        required_keys = ["FIXED FREQUENCY", "HOL CONV", "BIZ CONV", "ACC BASIS"]
        for k in required_keys:
            if k not in self.valParams:
                raise KeyError(f"ValuationEngineProductIborSwap: missing parameter '{k}'")

    def calculateValue(self):
        freq      = self.valParams["FIXED FREQUENCY"]
        hol_conv  = self.valParams["HOL CONV"]
        biz_conv  = self.valParams["BIZ CONV"]
        acc_basis = self.valParams["ACC BASIS"]

        schedule_df: pd.DataFrame = makeSchedule(
            self.effectiveDate.ISO(),
            self.terminationDate.ISO(),
            freq,
            hol_conv,
            biz_conv,
            acc_basis
        )
        
        pv_fixed = 0.0
        for _, row in schedule_df.iterrows():
            pay_dt: Date = row["PaymentDate"]
            accrual: float = row["Accrued"]
            df_i   = self.model.discountFactor(self.indexKey, pay_dt)
            pv_fixed += self.fixedRate * self.notional * accrual * df_i

        df_T = self.model.discountFactor(self.indexKey, self.terminationDate)
        pv_float = self.notional * (1.0 - df_T)

        if self.payFixed:
            net_pv = pv_float - pv_fixed
        else:
            net_pv = pv_fixed - pv_float

        self.value_ = [ self.currency.value.code(), net_pv ]


class ValuationEngineProductOvernightSwap(ValuationEngine):
    def __init__(
        self,
        model: YieldCurve,
        valuationParameters: dict,
        product: ProductOvernightSwap
    ):
        super().__init__(model, valuationParameters, product)

        self.currency        = product.currency
        self.effectiveDate   = product.effectiveDate
        self.terminationDate = product.terminationDate
        self.payFixed        = product.payFixed
        self.fixedRate       = product.fixedRate
        self.indexKey        = product.index
        self.notional        = product.notional

        required_keys = ["FIXED FREQUENCY", "HOL CONV", "BIZ CONV", "ACC BASIS"]
        for k in required_keys:
            if k not in self.valParams:
                raise KeyError(f"ValuationEngineProductOvernightSwap: missing parameter '{k}'")

    def calculateValue(self):
        freq      = self.valParams["FIXED FREQUENCY"]
        hol_conv  = self.valParams["HOL CONV"]
        biz_conv  = self.valParams["BIZ CONV"]
        acc_basis = self.valParams["ACC BASIS"]

        schedule_df: pd.DataFrame = makeSchedule(
            self.effectiveDate.ISO(),
            self.terminationDate.ISO(),
            freq,
            hol_conv,
            biz_conv,
            acc_basis
        )

        pv_fixed = 0.0
        for _, row in schedule_df.iterrows():
            pay_dt: Date = row["PaymentDate"]
            accrual: float = row["Accrued"]
            df_i   = self.model.discountFactor(self.indexKey, pay_dt)
            pv_fixed += self.fixedRate * self.notional * accrual * df_i

        df_T = self.model.discountFactor(self.indexKey, self.terminationDate)
        pv_float = self.notional * (1.0 - df_T)

        if self.payFixed:
            net_pv = pv_float - pv_fixed
        else:
            net_pv = pv_fixed - pv_float

        self.value_ = [ self.currency.value.code(), net_pv ]


