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