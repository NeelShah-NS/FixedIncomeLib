import pandas as pd
from .product import ProductVisitor
from .product import Product
from date import (Date, Period, TermOrTerminationDate)
from market import (IndexRegistry, Currency)
from typing import Union

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
    
class ProductOvernightCashflow(Product):

    def __init__(self,
                 effectiveDate: str,
                 termOrEnd: Union[str, TermOrTerminationDate],
                 index: str,
                 spread: float,
                 notional: float,
                 longOrShort: str) -> None:

        
        self.effDate_ = Date(effectiveDate)
        if isinstance(termOrEnd, str):
            self.termOrEnd_ = TermOrTerminationDate(termOrEnd)
        else:
            self.termOrEnd_ = termOrEnd

        self.oisIndex_ = IndexRegistry().get(index)
        cal         = self.oisIndex_.fixingCalendar()
        if self.termOrEnd_.isTerm():
            # advance by the tenor:
            tenor = self.termOrEnd_.getTerm()
            self.endDate_ = Date(cal.advance(self.effDate_, tenor, self.oisIndex_.businessDayConvention()))
        else:
            # it was given as a literal date:
            self.endDate_ = self.termOrEnd_.getDate()
        
        self.spread_  = spread
        ccy_code = self.oisIndex_.currency().code()
        super().__init__(self.effDate_, self.endDate_, notional, longOrShort, Currency(ccy_code))

    @property
    def prodType(self):
        return ProductOvernightCashflow.__name__

    @property
    def index(self):
        return self.oisIndex_.name()

    @property
    def effectiveDate(self):
        return self.effDate_

    @property
    def terminationDate(self):
        return self.endDate_

    @property
    def spread(self):
        return self.spread_

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
        self.indexKey_ = index
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
    def index(self) -> str:
        # Return the original registry key string, not the QL internal name.
        return self.indexKey_

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)
    
class ProductRfrFuture(Product):

    def __init__(self,
                 effectiveDate: str,
                 index: str,
                 strike: float,
                 notional: float,
                 longOrShort: str) -> None:

        self.effDate_    = Date(effectiveDate)
        self.indexKey_   = index
        tokenized       = index.split('-')
        self.tenor_     = tokenized[-1]
        self.oisIndex_  = IndexRegistry().get(index)
        self.expirationDate_ = Date(self.oisIndex_.fixingDate(self.effDate_))
        self.maturityDate_   = Date(self.oisIndex_.maturityDate(self.effDate_))
        self.strike_   = strike
        self.notional_ = notional
        ccy_code      = self.oisIndex_.currency().code()

        super().__init__(
            self.expirationDate_,
            self.maturityDate_,
            self.notional_,
            longOrShort,
            Currency(ccy_code)
        )

    @property
    def prodType(self):
        return ProductRfrFuture.__name__

    @property
    def expirationDate(self):
        return self.expirationDate_

    @property
    def maturityDate(self):
        return self.maturityDate_

    @property
    def tenor(self) -> str:
        return self.tenor_

    @property
    def index(self) -> str:
        return self.indexKey_

    @property
    def strike(self):
        return self.strike_

    @property
    def effectiveDate(self):
        return self.effDate_

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)

class ProductIborSwap(Product):
    def __init__(
        self,
        effectiveDate: str,
        maturity: TermOrTerminationDate | str,
        payFixed: bool,
        fixedRate: float,
        floatingIndex: str,
        notional: float,
        longOrShort: str
    ) -> None:
        
        self.indexKey_ = floatingIndex
        idxName, tenor = floatingIndex.rsplit('-', 1)
        self.iborIndex_ = IndexRegistry().get(idxName, tenor)
        self.effDate_ = Date(effectiveDate)

        if isinstance(maturity, str) and '-' not in maturity:
            self.maturity_ = TermOrTerminationDate(maturity)
        elif isinstance(maturity, TermOrTerminationDate):
            self.maturity_ = maturity
        else:
            self.maturity_ = TermOrTerminationDate(maturity)

        cal = self.iborIndex_.fixingCalendar()
        if self.maturity_.isTerm():
            term = self.maturity_.getTerm()
            self.maturityDate_ = Date(
                cal.advance(self.effDate_, term, self.iborIndex_.businessDayConvention())
            )
        else:
            self.maturityDate_ = self.maturity_.getDate()

        self.payFixed_      = payFixed
        self.fixedRate_     = fixedRate
        self.notional_      = notional
        ccy_code = self.iborIndex_.currency().code()
        super().__init__(self.effDate_, self.maturityDate_, self.notional_, longOrShort, Currency(ccy_code))

    @property
    def index(self) -> str:
        return self.indexKey_
    
    @property
    def effectiveDate(self) -> Date:
        return self.effDate_
    
    @property
    def terminationDate(self) -> Date:
        return self.maturityDate_

    @property
    def effectiveDate(self) -> Date:
        return self.effDate_

    @property
    def terminationDate(self) -> Date:
        return self.maturityDate_

    @property
    def payFixed(self) -> bool:
        return self.payFixed_

    @property
    def fixedRate(self) -> float:
        return self.fixedRate_

    @property
    def floatingIndex(self) -> str:
        return self.iborIndex_.name()

    @property
    def notional(self) -> float:
        return self.notional_

    @property
    def prodType(self) -> str:
        return ProductIborSwap.__name__

    def accept(self, visitor):
        return visitor.visit(self)
    
class ProductOvernightSwap(Product):
    def __init__(
        self,
        effectiveDate: str,
        maturity: TermOrTerminationDate | str,
        payFixed: bool,
        fixedRate: float,
        overnightIndex: str,
        notional: float,
        longOrShort: str
    ) -> None:
        
        self.indexKey_ = overnightIndex
        self.oisIndex_ = IndexRegistry().get(overnightIndex)
        self.effDate_ = Date(effectiveDate)
        if isinstance(maturity, str) and '-' not in maturity:
            self.maturity_ = TermOrTerminationDate(maturity)
        elif isinstance(maturity, TermOrTerminationDate):
            self.maturity_ = maturity
        else:
            self.maturity_ = TermOrTerminationDate(maturity)

        cal = self.oisIndex_.fixingCalendar()
        if self.maturity_.isTerm():
            term = self.maturity_.getTerm()
            self.maturityDate_ = Date(
                cal.advance(self.effDate_, term, self.oisIndex_.businessDayConvention())
            )
        else:
            self.maturityDate_ = self.maturity_.getDate()
        self.payFixed_       = payFixed
        self.fixedRate_      = fixedRate
        self.notional_       = notional
        ccy_code = self.oisIndex_.currency().code()
        super().__init__(self.effDate_, self.maturityDate_, self.notional_, longOrShort, Currency(ccy_code))

    @property
    def index(self) -> str:
        return self.indexKey_

    @property
    def effectiveDate(self) -> Date:
        return self.effDate_

    @property
    def terminationDate(self) -> Date:
        return self.maturityDate_

    @property
    def payFixed(self) -> bool:
        return self.payFixed_

    @property
    def fixedRate(self) -> float:
        return self.fixedRate_

    @property
    def overnightIndex(self) -> str:
        return self.oisIndex_.name()

    @property
    def notional(self) -> float:
        return self.notional_

    @property
    def prodType(self) -> str:
        return ProductOvernightSwap.__name__

    def accept(self, visitor):
        return visitor.visit(self)