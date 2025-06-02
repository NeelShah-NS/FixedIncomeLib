from .yield_curve_model import YiedCurve
from product import (LongOrShort, ProductBulletCashflow, ProductFuture)
from valuation import (ValuationEngine)

class ValuationEngineProductBulletCashflow(ValuationEngine):

    def __init__(self, model : YiedCurve, valuationParameters : dict, product : ProductBulletCashflow):
        super().__init__(model, valuationParameters, product)
        self.currency = product.currency
        self.maturity = product.terminationDate
        self.buyOrSell = 1. if product.longOrShort.value == LongOrShort.LONG else -1.
        self.notional = product.notional
        self.fundingIndex = valuationParameters['FUNDING INDEX']
        
    def calculateValue(self):
        discountFactor = self.model.discountFactor(self.fundingIndex, self.maturity)
        self.value_ = [self.currency.value.code(), self.notional * self.buyOrSell * discountFactor]

### TODO: Implement val engine for future/swap (libor/rfr) etc