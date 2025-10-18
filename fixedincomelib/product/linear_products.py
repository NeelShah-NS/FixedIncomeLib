import pandas as pd
from fixedincomelib.market.basics import AccrualBasis, BusinessDayConvention, HolidayConvention
from fixedincomelib.product.product import LongOrShort, ProductVisitor, Product
from fixedincomelib.date import (Date, Period, TermOrTerminationDate)
from fixedincomelib.market import (IndexRegistry, Currency)
from typing import List, Optional, Union
from fixedincomelib.date.utilities import makeSchedule,accrued
from fixedincomelib.product.portfolio import ProductPortfolio

# -------------------------
# Atomic Cash-Flow Classes
# -------------------------

class ProductBulletCashflow(Product):
    prodType = "ProductBulletCashflow"

    def __init__(self, 
                 terminationDate : str, 
                 currency : str,
                 notional : float,
                 longOrShort : str,
                 paymentDate: Optional[Union[str, Date]] = None) -> None:
        super().__init__(Date(terminationDate), Date(terminationDate), notional, longOrShort, Currency(currency))
    
        self.paymentDate_ = Date(terminationDate) if paymentDate is None else (paymentDate if isinstance(paymentDate, Date) else Date(paymentDate))

    @property
    def terminationDate(self):
        return self.lastDate
    
    @property
    def paymentDate(self) -> Date:
        return self.paymentDate_

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)
    
class ProductIborCashflow(Product):
    prodType = "ProductIborCashflow"

    def __init__(self,
                 startDate: str,
                 endDate: str,
                 index: str,
                 spread: float,
                 notional: float,
                 longOrShort: str,
                 paymentDate: Optional[Union[str, Date]] = None) -> None:
        
        self.accrualStart_ = Date(startDate)
        self.accrualEnd_   = Date(endDate)
        self.indexKey_ = index 
        tokenized = index.split('-')
        assert len(tokenized) >= 1, f"invalid index format: '{index}'"
        tenor     = tokenized[-1]  # e.g. "3M"
        indexName = '-'.join(tokenized[:-1])
        self.iborIndex_ = IndexRegistry().get(indexName, tenor)
        self.spread_ = spread
        ccy_code = self.iborIndex_.currency().code()
        super().__init__(self.accrualStart_, self.accrualEnd_, notional, longOrShort, Currency(ccy_code))
        self.paymentDate_ = (self.accrualEnd_ if paymentDate is None else (paymentDate if isinstance(paymentDate, Date) else Date(paymentDate)))

    @property
    def index(self):
        return self.indexKey_

    @property
    def spread(self):
        return self.spread_

    @property
    def accrualStart(self):
        return self.accrualStart_

    @property
    def accrualEnd(self):
        return self.accrualEnd_
    
    @property
    def accrualFactor(self) -> float:
        return accrued(self.accrualStart_, self.accrualEnd_)
    
    @property
    def paymentDate(self) -> Date:
        return self.paymentDate_

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)
    
class ProductOvernightIndexCashflow(Product):
    prodType = "ProductOvernightIndexCashflow"

    def __init__(
        self,
        effectiveDate: str,
        termOrEnd: Union[str, TermOrTerminationDate, Date],
        index: str,
        compounding: str,
        spread: float,
        notional: float,
        longOrShort: str,
        paymentDate: Optional[Union[str, Date]] = None) -> None:
        
        self.effDate_ = Date(effectiveDate)
        self.indexKey_   = index
        self.oisIndex_  = IndexRegistry().get(index)

        if isinstance(termOrEnd, Date):
            self.endDate_ = termOrEnd
        else:
            to = (TermOrTerminationDate(termOrEnd) if isinstance(termOrEnd, TermOrTerminationDate) else TermOrTerminationDate(termOrEnd))
            self.termOrEnd_ = to

            cal = self.oisIndex_.fixingCalendar()
            if to.isTerm():
                tenor = to.getTerm()
                self.endDate_ = Date(
                    cal.advance(self.effDate_, tenor, self.oisIndex_.businessDayConvention())
                )
            else:
                self.endDate_ = to.getDate()

        self.compounding_ = compounding.upper()
        self.spread_      = spread
        ccy_code         = self.oisIndex_.currency().code()

        super().__init__(
            self.effDate_,
            self.endDate_,
            notional,
            longOrShort,
            Currency(ccy_code)
        )

        self.paymentDate_ = (self.endDate_ if paymentDate is None else (paymentDate if isinstance(paymentDate, Date) else Date(paymentDate)))

    @property
    def index(self) -> str:
        return self.indexKey_

    @property
    def compounding(self) -> str:
        return self.compounding_

    @property
    def effectiveDate(self) -> Date:
        return self.effDate_

    @property
    def terminationDate(self) -> Date:
        return self.endDate_

    @property
    def spread(self) -> float:
        return self.spread_
    
    @property
    def paymentDate(self) -> Date:
        return self.paymentDate_

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)

class ProductFuture(Product):
    prodType = "ProductFuture"

    def __init__(self, 
                 effectiveDate : str,
                 index : str,
                 strike : float,
                 notional : float,
                 longOrShort : str,
                 contractualSize: Optional[float] = None) -> None:
        
        self.strike_ = strike
        self.indexKey_ = index
        self.effectiveDate_ = Date(effectiveDate)
        tokenized_index = index.split('-')
        self.tenor_ = tokenized_index[-1] # if this errors
        self.index_ = IndexRegistry()._instance.get('-'.join(tokenized_index[:-1]), self.tenor_)
        self.expirationDate_ = Date(self.index_.fixingDate(self.effectiveDate_))
        self.maturityDate_ = Date(self.index_.maturityDate(self.effectiveDate_))

         # contractual size override vs. actual accrual
        self.contractualSize_ = contractualSize
        if contractualSize is not None:
            self.accrualFactor_ = contractualSize
        else:
            self.accrualFactor_ = accrued(self.effectiveDate_, self.maturityDate_)
        
        super().__init__(self.effectiveDate_, self.maturityDate_, notional, longOrShort, Currency(self.index_.currency().code()))
     
    @property
    def expirationDate(self):
        return self.expirationDate_

    @property
    def effectiveDate(self):
        return self.effectiveDate_

    @property
    def maturityDate(self):
        return self.maturityDate_
    
    @property
    def accrualFactor(self) -> float:
        return self.accrualFactor_
    
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
    prodType = "ProductRfrFuture"

    def __init__(self,
                 effectiveDate: str,
                 termOrEnd: Union[str, TermOrTerminationDate],
                 index: str,
                 compounding: str,
                 strike: float,
                 notional: float,
                 longOrShort: str,
                 contractualSize: Optional[float] = None) -> None:
        
        self.effDate_    = Date(effectiveDate)
        self.indexKey_   = index
        self.strike_     = strike
        self.notional_   = notional
        self.oisIndex_   = IndexRegistry().get(index)
        self.compounding_ = compounding.upper()

        if isinstance(termOrEnd, str):
            self.termOrEnd_ = TermOrTerminationDate(termOrEnd)
        else:
            self.termOrEnd_ = termOrEnd

        cal = self.oisIndex_.fixingCalendar()
        if self.termOrEnd_.isTerm():
            tenor = self.termOrEnd_.getTerm()
            self.maturityDate_ = Date(
                cal.advance(self.effDate_, tenor, self.oisIndex_.businessDayConvention())
            )
        else:
            self.maturityDate_ = self.termOrEnd_.getDate()
        
        self.contractualSize_ = contractualSize
        if contractualSize is not None:
            self.accrualFactor_ = contractualSize
        else:
            # uses your accrued() util to compute year‐fraction
            self.accrualFactor_ = accrued(self.effDate_, self.maturityDate_)

        super().__init__(self.effDate_, self.maturityDate_, self.notional_, longOrShort, Currency(self.oisIndex_.currency().code()))

    @property
    def effectiveDate(self) -> Date:
        return self.effDate_

    @property
    def maturityDate(self) -> Date:
        return self.maturityDate_
    
    @property
    def accrualFactor(self) -> float:
        return self.accrualFactor_

    @property
    def strike(self) -> float:
        return self.strike_

    @property
    def index(self) -> str:
        return self.indexKey_
    
    @property
    def compounding(self) -> str:
        return self.compounding_
    
    @property
    def terminationDate(self):
        return self.lastDate

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)
    
# --------------------------------
# Composition: Streams & Swaps
# --------------------------------

class InterestRateStream(ProductPortfolio):

    def __init__(
        self,
        startDate: str,
        endDate: str,
        frequency: str,
        iborIndex: Optional[str]       = None,
        overnightIndex: Optional[str]  = None,
        fixedRate: Optional[float]     = None,
        ois_compounding: str           = "COMPOUND",
        ois_spread: float              = 0.0,
        notional: float                = 1.0,
        position: str                  = 'LONG',
        currency: str                  = 'USD',
        holConv: str                   = 'TARGET',
        bizConv: str                   = 'MF',
        accrualBasis: str              = 'ACT/365 FIXED',
        rule: str                      = 'BACKWARD',
        endOfMonth: bool               = False
    ):

        # calendar    = HolidayConvention(holConv).value
        # bdc         = BusinessDayConvention(bizConv).value
        # dayCounter  = AccrualBasis(accrualBasis).value

        schedule = makeSchedule(startDate, endDate, frequency, holConv, bizConv, accrualBasis, rule, endOfMonth)
        prods, weights = [], []
        for row in schedule.itertuples(index=False):
            if iborIndex:
                cf = ProductIborCashflow(Date(row.StartDate), Date(row.EndDate), iborIndex, 0.0, notional, position, Date(row.PaymentDate))
            elif overnightIndex:
                cf = ProductOvernightIndexCashflow(Date(row.StartDate), Date(row.EndDate), overnightIndex, ois_compounding, ois_spread, notional, position, Date(row.PaymentDate))
            else:
                alpha_i = accrued(Date(row.StartDate), Date(row.EndDate))
                coupon_amt = notional * (fixedRate or 0.0) * alpha_i
                cf = ProductBulletCashflow(Date(row.EndDate), currency, coupon_amt, position, Date(row.PaymentDate))
            prods.append(cf)
            weights.append(1.0)

        super().__init__(prods, weights)

    def cashflow(self, i: int) -> Product:
        return self.element(i)

class ProductIborSwap(Product):
    prodType = "ProductIborSwap"

    def __init__(
        self,
        effectiveDate: str,
        maturityDate: str,
        frequency: str,
        iborIndex: str,
        spread: float,
        fixedRate: float,
        notional: float,
        position: str,
        holConv: str      = 'TARGET',
        bizConv: str      = 'MF',
        accrualBasis: str = 'ACT/365 FIXED',
        rule: str         = 'BACKWARD',
        endOfMonth: bool  = False
    ) -> None:
        
        self.iborIndexKey = iborIndex
        self.fixedRate_   = fixedRate
        self.payFixed_    = (position.upper() == 'SHORT')
        float_position = "LONG" if self.payFixed_ else "SHORT"

        self.floatingLeg = InterestRateStream(
            startDate      = effectiveDate,
            endDate        = maturityDate,
            frequency      = frequency,
            iborIndex      = iborIndex,
            overnightIndex = None,
            fixedRate      = None,
            notional       = notional,
            position       = float_position,
            holConv        = holConv,
            bizConv        = bizConv,
            accrualBasis   = accrualBasis,
            rule           = rule,
            endOfMonth     = endOfMonth
        )
        
        self.fixedLeg = InterestRateStream(
            startDate      = effectiveDate,
            endDate        = maturityDate,
            frequency      = frequency,
            iborIndex      = None,
            overnightIndex = None,
            fixedRate      = fixedRate,
            notional       = notional,
            position       = position,
            holConv        = holConv,
            bizConv        = bizConv,
            accrualBasis   = accrualBasis,
            rule           = rule,
            endOfMonth     = endOfMonth
        )

        self.notional_ = notional
        self.position_ = LongOrShort(position)
        super().__init__(
            Date(effectiveDate),
            Date(maturityDate),
            notional,
            position,
            self.floatingLeg.element(0).currency
        )

    def floatingLegCashflow(self, i: int) -> Product:
        assert 0 <= i < self.floatingLeg.count
        return self.floatingLeg.element(i)

    def fixedLegCashflow(self, i: int) -> Product:
        assert 0 <= i < self.fixedLeg.count
        return self.fixedLeg.element(i)
    
    @property
    def effectiveDate(self) -> Date:
        return self.firstDate

    @property
    def maturityDate(self) -> Date:
        return self.lastDate

    @property
    def fixedRate(self) -> float:
        return self.fixedRate_

    @property
    def index(self) -> str:
        return self.iborIndexKey

    @property
    def payFixed(self) -> bool:
        return self.payFixed_
    
    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)


class ProductOvernightSwap(Product):
    prodType = "ProductOvernightSwap"

    def __init__(
        self,
        effectiveDate: str,
        maturityDate: str,
        frequency: str,
        overnightIndex: str,
        spread: float,
        fixedRate: float,
        notional: float,
        position: str,
        holConv: str      = 'TARGET',
        bizConv: str      = 'MF',
        accrualBasis: str = 'ACT/365 FIXED',
        rule: str         = 'BACKWARD',
        endOfMonth: bool  = False
    ) -> None:
        
        self.overnightIndexKey = overnightIndex
        self.fixedRate_        = fixedRate
        self.payFixed_         = (position.upper() == 'SHORT')
        float_position = "LONG" if self.payFixed_ else "SHORT"

        self.floatingLeg = InterestRateStream(
            startDate      = effectiveDate,
            endDate        = maturityDate,
            frequency      = frequency,
            iborIndex      = None,
            overnightIndex = overnightIndex,
            fixedRate      = None,
            notional       = notional,
            position       = float_position,
            holConv        = holConv,
            bizConv        = bizConv,
            accrualBasis   = accrualBasis,
            rule           = rule,
            endOfMonth     = endOfMonth
        )
        
        self.fixedLeg = InterestRateStream(
            startDate      = effectiveDate,
            endDate        = maturityDate,
            frequency      = frequency,
            iborIndex      = None,
            overnightIndex = None,
            fixedRate      = fixedRate,
            notional       = notional,
            position       = position,
            holConv        = holConv,
            bizConv        = bizConv,
            accrualBasis   = accrualBasis,
            rule           = rule,
            endOfMonth     = endOfMonth
        )

        self.notional_ = notional
        self.position_ = LongOrShort(position)
        super().__init__(
            Date(effectiveDate),
            Date(maturityDate),
            notional,
            position,
            self.floatingLeg.element(0).currency
        )

    def floatingLegCashflow(self, i: int) -> Product:
        assert 0 <= i < self.floatingLeg.count
        return self.floatingLeg.element(i)

    def fixedLegCashflow(self, i: int) -> Product:
        assert 0 <= i < self.fixedLeg.count
        return self.fixedLeg.element(i)
    
    @property
    def effectiveDate(self) -> Date:
        return self.firstDate

    @property
    def maturityDate(self) -> Date:
        return self.lastDate

    @property
    def fixedRate(self) -> float:
        return self.fixedRate_

    @property
    def index(self) -> str:
        return self.overnightIndexKey

    @property
    def payFixed(self) -> bool:
        return self.payFixed_
    
    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)