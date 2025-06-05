import pandas as pd
from .product import ProductVisitor
from .product import Product
from date import (Date, Period, TermOrTerminationDate)
from market import (IndexRegistry, Currency)

class ProductBulletCashflow(Product):

    def __init__(self, 
                 terminationDate : str, 
                 currency : str,
                 notional : float,
                 longOrShort : str) -> None:
        super().__init__(Date(terminationDate), Date(terminationDate), notional, longOrShort, Currency(currency))
    
    @property
    def terminationDate(self):
        return self.lastDate

    @property
    def prodType(self):
        return ProductBulletCashflow.__name__

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)
    
### TODO: implement LIBOR cashflow/overnightindex cashflow classes, respectively
class ProductIborCashflow(Product):

    def __init__(self,
                 startDate: str,
                 endDate: str,
                 index: str,
                 spread: float,
                 notional: float,
                 longOrShort: str) -> None:
        
        self.accrualStart_ = Date(startDate)
        self.accrualEnd_   = Date(endDate)
        tokenized = index.split('-')
        tenor     = tokenized[-1]  # e.g. "3M"
        indexName = '-'.join(tokenized[:-1])
        self.iborIndex_ = IndexRegistry().get(indexName, tenor)
        self.spread_ = spread
        ccy_code = self.iborIndex_.currency().code()
        super().__init__(self.accrualStart_,self.accrualEnd_,notional,longOrShort,Currency(ccy_code))

    @property
    def prodType(self):
        return ProductIborCashflow.__name__

    @property
    def index(self):
        return self.iborIndex_.name()

    @property
    def spread(self):
        return self.spread_

    @property
    def accrualStart(self):
        return self.accrualStart_

    @property
    def accrualEnd(self):
        return self.accrualEnd_

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)

class ProductFuture(Product):

    def __init__(self, 
                 effectiveDate : str,
                 index : str,
                 strike : float,
                 notional : float,
                 longOrShort : str) -> None:
        
        self.strike_ = strike
        self.effectiveDate_ = Date(effectiveDate)
        tokenized_index = index.split('-')
        self.tenor_ = tokenized_index[-1] # if this errors
        self.index_ = IndexRegistry()._instance.get('-'.join(tokenized_index[:-1]), self.tenor_)
        self.expirationDate_ = Date(self.index_.fixingDate(self.effectiveDate_))
        self.maturityDate_ = Date(self.index_.maturityDate(self.effectiveDate_))
        
        super().__init__(self.effectiveDate_, self.maturityDate_, notional, longOrShort, 
                         Currency(self.index_.currency().code()))
    
    @property
    def expirationDate(self):
        return self.expirationDate_

    @property
    def effectiveDate(self):
        return self.effectiveDate_

    @property
    def terminationDate(self):
        return self.maturityDate_

    @property
    def prodType(self):
        return ProductFuture.__name__

    @property
    def strike(self):
        return self.strike_
    
    @property
    def index(self):
        return self.index_.name()

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)
    

### TODO: implement RFR Future

### TODO: implement LIBOR based Swap and RFR based Swap