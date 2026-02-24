import pandas as pd
from fixedincomelib.market.basics import AccrualBasis, BusinessDayConvention, HolidayConvention
from fixedincomelib.product.product import LongOrShort, ProductVisitor, Product
from fixedincomelib.date import Date, TermOrTerminationDate
from fixedincomelib.market import IndexRegistry, Currency
from fixedincomelib.date.utilities import makeSchedule, business_day_schedule
from fixedincomelib.product.portfolio import ProductPortfolio
from typing import List, Optional, Union
from fixedincomelib.product.linear_products import ProductIborSwap,ProductOvernightSwap
from fixedincomelib.valuation.index_fixing_registry import IndexManager

class ProductIborCapFloorlet(Product):
    prodType = "ProductIborCapFloorlet"

    def __init__(
        self,
        startDate: str,
        endDate: str,
        index: str,
        optionType: str,
        strike: float,
        notional: float,
        longOrShort: str,
    ) -> None:
        self.optionType_ = optionType.upper()
        assert self.optionType_ in ("CAP", "FLOOR"), f"Invalid option type: {optionType}"
        self.indexKey_ = index
        tokenized = index.split('-')
        tenor = tokenized[-1]
        indexName = '-'.join(tokenized[:-1])
        self.iborIndex_ = IndexRegistry().get(indexName, tenor)
        cal = self.iborIndex_.fixingCalendar()
        bdc = self.iborIndex_.businessDayConvention()
        self.accrualStart_ = Date(cal.adjust(Date(startDate), bdc))
        self.accrualEnd_   = Date(cal.adjust(Date(endDate),   bdc))
        self.strike_ = strike

        dc = self.iborIndex_.dayCounter()
        self.accrualFactor_ = float(dc.yearFraction(self.accrualStart_, self.accrualEnd_))
        if self.accrualFactor_ <= 0.0:
            raise ValueError(
                f"Non-positive accrualFactor for IBOR caplet: "
                f"{self.accrualStart_} -> {self.accrualEnd_}, tau={self.accrualFactor_}"
            )

        ccy_code = self.iborIndex_.currency().code()
        super().__init__(
            self.accrualStart_, self.accrualEnd_, notional, longOrShort, Currency(ccy_code)
        )

    @property
    def optionType(self) -> str:
        return self.optionType_

    @property
    def strike(self) -> float:
        return self.strike_

    @property
    def accrualStart(self) -> Date:
        return self.accrualStart_

    @property
    def accrualEnd(self) -> Date:
        return self.accrualEnd_

    @property
    def index(self) -> str:
        return self.indexKey_
    
    @property
    def accrualFactor(self) -> float:
        return float(self.accrualFactor_)
    
    @property
    def dayCounter(self):
        return self.iborIndex_.dayCounter()

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)

class ProductOvernightCapFloorlet(Product):
    prodType = "ProductOvernightCapFloorlet"

    def __init__(
        self,
        effectiveDate: str,
        termOrEnd: Union[str, TermOrTerminationDate],
        index: str,
        compounding: str,
        optionType: str,
        strike: float,
        notional: float,
        longOrShort: str,
    ) -> None:
        self.indexKey_ = index
        self.oisIndex_ = IndexRegistry().get(index)
        self.optionType_ = optionType.upper()
        assert self.optionType_ in ("CAP", "FLOOR"), f"Invalid option type: {optionType}"
        self.compounding_ = compounding.upper()
        self.strike_ = strike
        cal = self.oisIndex_.fixingCalendar()
        bdc = self.oisIndex_.businessDayConvention()
        self.effDate_ = Date(cal.adjust(Date(effectiveDate), bdc))
        if isinstance(termOrEnd, Date):
            end_raw = termOrEnd
        elif isinstance(termOrEnd, TermOrTerminationDate):
            to = termOrEnd
            if to.isTerm():
                tenor = to.getTerm()
                end_raw = Date(cal.advance(self.effDate_, tenor, bdc))
            else:
                end_raw = to.getDate()
        else:
            to = TermOrTerminationDate(termOrEnd)
            if to.isTerm():
                tenor = to.getTerm()
                end_raw = Date(cal.advance(self.effDate_, tenor, bdc))
            else:
                end_raw = to.getDate()

        self.endDate_ = Date(cal.adjust(end_raw, bdc))
        dc = self.oisIndex_.dayCounter()
        self.accrualFactor_ = float(dc.yearFraction(self.effDate_, self.endDate_))
        if self.accrualFactor_ <= 0.0:
            raise ValueError(
                f"Non-positive accrualFactor for OIS caplet: "
                f"{self.effDate_} -> {self.endDate_}, tau={self.accrualFactor_}"
            )

        ccy_code = self.oisIndex_.currency().code()
        super().__init__(
            self.effDate_, self.endDate_, notional, longOrShort, Currency(ccy_code)
        )

    def get_fixing_schedule(self) -> list[Date]:
        cal = self.oisIndex_.fixingCalendar()
        return business_day_schedule(self.effDate_, self.endDate_, cal)

    @property
    def optionType(self) -> str:
        return self.optionType_

    @property
    def strike(self) -> float:
        return self.strike_

    @property
    def compounding(self) -> str:
        return self.compounding_

    @property
    def effectiveDate(self) -> Date:
        return self.effDate_

    @property
    def maturityDate(self) -> Date:
        return self.lastDate

    @property
    def index(self) -> str:
        return self.indexKey_
    
    @property
    def fixing_schedule(self) -> list[Date]:
        return self.get_fixing_schedule()
    
    @property
    def dayCounter(self):
        return self.oisIndex_.dayCounter()

    @property
    def accrualFactor(self) -> float:
        return float(self.accrualFactor_)

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)

class CapFloorStream(ProductPortfolio):
    prodType = "CapFloorStream"

    def __init__(
        self,
        startDate: str,
        endDate: str,
        frequency: str,
        iborIndex: Optional[str] = None,
        overnightIndex: Optional[str] = None,
        compounding: str = "COMPOUND",
        optionType: str = "CAP",
        strike: float = 0.0,
        notional: float = 1.0,
        longOrShort: str = "LONG",
        holConv: str = 'TARGET',
        bizConv: str = 'MF',
        accrualBasis: str = 'ACT/365 FIXED',
        rule: str = 'BACKWARD',
        endOfMonth: bool = False,
    ) -> None:
        schedule = makeSchedule(startDate, endDate, frequency,holConv, bizConv, accrualBasis, rule, endOfMonth)
        products = []
        weights = []
        for row in schedule.itertuples(index=False):
            if iborIndex:
                cf = ProductIborCapFloorlet(Date(row.StartDate), Date(row.EndDate), iborIndex, optionType, strike, notional, longOrShort)
            elif overnightIndex:
                cf = ProductOvernightCapFloorlet(Date(row.StartDate), Date(row.EndDate), overnightIndex, compounding, optionType, strike, notional, longOrShort)
            else:
                raise ValueError("CapFloorStream requires either iborIndex or overnightIndex")
            products.append(cf)
            weights.append(1.0)
        super().__init__(products, weights)
        self.products = products

    def cashflow(self, i: int) -> Product:
        return self.element(i)


class ProductIborCapFloor(Product):
    prodType = "ProductIborCapFloor"

    def __init__(
        self,
        effectiveDate: str,
        maturityDate: str,
        frequency: str,
        index: str,
        optionType: str,
        strike: float,
        notional: float,
        longOrShort: str,
        holConv: str = 'TARGET',
        bizConv: str = 'MF',
        accrualBasis: str = 'ACT/365 FIXED',
        rule: str = 'BACKWARD',
        endOfMonth: bool = False,
    ) -> None:
        self.indexKey_ = index
        self.optionType_ = optionType.upper()
        self.capStream = CapFloorStream(
            effectiveDate, maturityDate, frequency,
            iborIndex=index,
            optionType=optionType,
            strike=strike,
            notional=notional,
            longOrShort=longOrShort,
            holConv=holConv,
            bizConv=bizConv,
            accrualBasis=accrualBasis,
            rule=rule,
            endOfMonth=endOfMonth
        )
        self.notional_ = notional
        self.position_ = LongOrShort(longOrShort)
        super().__init__(
            Date(effectiveDate), Date(maturityDate),
            notional, longOrShort,
            self.capStream.element(0).currency
        )

    @property
    def effectiveDate(self) -> Date:
        return self.firstDate

    @property
    def maturityDate(self) -> Date:
        return self.lastDate

    @property
    def index(self) -> str:
        return self.indexKey_

    @property
    def optionType(self) -> str:
        return self.optionType_

    def caplet(self, i: int) -> Product:
        return self.capStream.element(i)

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)


class ProductOvernightCapFloor(Product):
    prodType = "ProductOvernightCapFloor"

    def __init__(
        self,
        effectiveDate: str,
        maturityDate: str,
        frequency: str,
        index: str,
        compounding: str,
        optionType: str,
        strike: float,
        notional: float,
        longOrShort: str,
        holConv: str = 'TARGET',
        bizConv: str = 'MF',
        accrualBasis: str = 'ACT/365 FIXED',
        rule: str = 'BACKWARD',
        endOfMonth: bool = False,
    ) -> None:
        self.indexKey_ = index
        self.capStream = CapFloorStream(
            effectiveDate, maturityDate, frequency,
            overnightIndex=index,
            compounding=compounding,
            optionType=optionType,
            strike=strike,
            notional=notional,
            longOrShort=longOrShort,
            holConv=holConv,
            bizConv=bizConv,
            accrualBasis=accrualBasis,
            rule=rule,
            endOfMonth=endOfMonth
        )
        self.notional_ = notional
        self.position_ = LongOrShort(longOrShort)
        super().__init__(
            Date(effectiveDate), Date(maturityDate),
            notional, longOrShort,
            self.capStream.element(0).currency
        )

    def get_fixing_schedule(self) -> list[Date]:
        cal = self.capStream.element(0).oisIndex_.fixingCalendar()
        return business_day_schedule(self.effectiveDate, self.maturityDate, cal)

    @property
    def effectiveDate(self) -> Date:
        return self.firstDate

    @property
    def maturityDate(self) -> Date:
        return self.lastDate

    @property
    def index(self) -> str:
        return self.indexKey_

    @property
    def optionType(self) -> str:
        return self.capStream.element(0).optionType

    @property
    def compounding(self) -> str:
        # delegate to first caplet
        return self.capStream.element(0).compounding

    def caplet(self, i: int) -> Product:
        return self.capStream.element(i)

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)

# Swaption Classes

class ProductIborSwaption(Product):
    prodType = "ProductIborSwaption"

    def __init__(
        self,
        optionExpiry: str,
        swapStart: str,
        swapEnd: str,
        iborIndex: str,
        fixedFrequency: str,
        optionType: str,
        strikeRate: float,
        notional: float,
        longOrShort: str,
        floatFrequency: Optional[str] = None,
        holConv: str      = 'TARGET',
        bizConv: str      = 'MF',
        accrualBasis: str = 'ACT/365 FIXED',
        rule: str         = 'BACKWARD',
        endOfMonth: bool  = False,
    ) -> None:
        optionType = optionType.upper()
        assert optionType in ("PAYER", "RECEIVER")

        # Underlying swap direction must come from optionType (payer/receiver)
        swap_position = "SHORT" if optionType == "PAYER" else "LONG"
    
        self.underlyingSwap = ProductIborSwap(
            effectiveDate=swapStart,
            maturityDate=swapEnd,
            fixedFrequency=fixedFrequency,
            floatFrequency=floatFrequency,
            iborIndex=iborIndex,
            spread=0.0,
            fixedRate=strikeRate,
            notional=notional,
            position=swap_position,
            holConv=holConv,
            bizConv=bizConv,
            accrualBasis=accrualBasis,
            rule=rule,
            endOfMonth=endOfMonth,
        )
        self.expiryDate_ = Date(optionExpiry)
        self.notional_   = notional
        self.position_   = LongOrShort(longOrShort)
        self.optionType_ = optionType.upper()
        self.indexKey_ = iborIndex
        toks = iborIndex.split('-')
        assert len(toks) >= 2, f"invalid ibor index format: '{iborIndex}'"
        tenor = toks[-1]                 
        base  = '-'.join(toks[:-1])  
        self.iborIndex_ = IndexRegistry().get(base, tenor)
        assert self.optionType_ in ("PAYER","RECEIVER")        
        super().__init__(
            self.expiryDate_,
            self.underlyingSwap.lastDate,
            notional,
            longOrShort,
            self.underlyingSwap.currency,
        )

    @property
    def expiryDate(self) -> Date:
        return self.expiryDate_

    @property
    def maturityDate(self) -> Date:
        return self.lastDate

    @property
    def swap(self) -> ProductIborSwap:
        return self.underlyingSwap

    @property
    def optionType(self) -> str:
        return self.optionType_
    
    @property
    def dayCounter(self):
        return self.iborIndex_.dayCounter()


    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)

class ProductOvernightSwaption(Product):
    prodType = "ProductOvernightSwaption"

    def __init__(
        self,
        optionExpiry: str,
        swapStart: str,
        swapEnd: str,
        fixedFrequency: str,
        overnightIndex: str,
        optionType: str,
        strikeRate: float,
        notional: float,
        longOrShort: str,
        floatFrequency: Optional[str] = None,
        holConv: str      = 'TARGET',
        bizConv: str      = 'MF',
        accrualBasis: str = 'ACT/365 FIXED',
        rule: str         = 'BACKWARD',
        endOfMonth: bool  = False,
    ) -> None:
        optionType = optionType.upper()
        assert optionType in ("PAYER", "RECEIVER")

        # Underlying swap direction must come from optionType (payer/receiver)
        swap_position = "SHORT" if optionType == "PAYER" else "LONG"

        self.underlyingSwap = ProductOvernightSwap(
            effectiveDate=swapStart,
            maturityDate=swapEnd,
            fixedFrequency=fixedFrequency,
            floatFrequency=floatFrequency,
            overnightIndex=overnightIndex,
            spread=0.0,
            fixedRate=strikeRate,
            notional=notional,
            position=swap_position,
            holConv=holConv,
            bizConv=bizConv,
            accrualBasis=accrualBasis,
            rule=rule,
            endOfMonth=endOfMonth,
        )
        self.expiryDate_ = Date(optionExpiry)
        self.notional_  = notional
        self.position_  = LongOrShort(longOrShort)
        self.optionType_ = optionType.upper()
        self.oisIndex_ = IndexRegistry().get(overnightIndex)
        assert self.optionType_ in ("PAYER","RECEIVER")
        super().__init__(
            self.expiryDate_,
            self.underlyingSwap.lastDate,
            notional,
            longOrShort,
            self.underlyingSwap.currency,
        )

    @property
    def expiryDate(self) -> Date:
        return self.expiryDate_

    @property
    def maturityDate(self) -> Date:
        return self.lastDate

    @property
    def swap(self) -> ProductOvernightSwap:
        return self.underlyingSwap
    
    @property
    def optionType(self) -> str:
        return self.optionType_
    
    @property
    def dayCounter(self):
        return self.oisIndex_.dayCounter()

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)
