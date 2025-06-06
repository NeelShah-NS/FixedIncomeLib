from .yield_curve_model import YieldCurve
from product import (LongOrShort, ProductBulletCashflow, ProductFuture, ProductRfrFuture)
from valuation import (ValuationEngine)
from date import TermOrTerminationDate, Date

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
        termOrDate   = TermOrTerminationDate(self.maturityDate.ISO())
        forwardOis   = self.model.forward(self.indexKey, self.expirationDate, termOrDate)
        futuresPrice = 1.0 - forwardOis
        pnl          = (futuresPrice - self.strike) * self.notional * self.buyOrSell
        self.value_  = [ self.currency.value.code(), pnl ]


### TODO: Implement val engine for swap (libor/rfr) etc


