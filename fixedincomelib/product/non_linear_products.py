import pandas as pd
from fixedincomelib.market.basics import AccrualBasis, BusinessDayConvention, HolidayConvention
from fixedincomelib.product.product import LongOrShort, ProductVisitor, Product
from fixedincomelib.date import Date, TermOrTerminationDate
from fixedincomelib.market import IndexRegistry, Currency
from fixedincomelib.date.utilities import makeSchedule, business_day_schedule
from fixedincomelib.product.portfolio import ProductPortfolio
from typing import List, Optional, Union
from fixedincomelib.product.linear_products import ProductIborSwap,ProductOvernightSwap
from fixedincomelib.valuation import IndexManager

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
        self.accrualStart_ = Date(startDate)
        self.accrualEnd_ = Date(endDate)
        self.optionType_ = optionType.upper()
        assert self.optionType_ in ("CAP", "FLOOR"), f"Invalid option type: {optionType}"
        self.indexKey_ = index
        tokenized = index.split('-')
        tenor = tokenized[-1]
        indexName = '-'.join(tokenized[:-1])
        self.iborIndex_ = IndexRegistry().get(indexName, tenor)
        self.strike_ = strike
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
        self.effDate_ = Date(effectiveDate)
        self.indexKey_ = index
        self.oisIndex_ = IndexRegistry().get(index)
        self.optionType_ = optionType.upper()
        assert self.optionType_ in ("CAP", "FLOOR"), f"Invalid option type: {optionType}"
        self.compounding_ = compounding.upper()
        self.strike_ = strike
        if isinstance(termOrEnd, Date):
            self.endDate_ = termOrEnd
        else:
            to = TermOrTerminationDate(termOrEnd)
            cal = self.oisIndex_.fixingCalendar()
            if to.isTerm():
                tenor = to.getTerm()
                self.endDate_ = Date(
                    cal.advance(self.effDate_, tenor, self.oisIndex_.businessDayConvention())
                )
            else:
                self.endDate_ = to.getDate()
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
        mgr     = IndexManager.instance()
        raw     = mgr.get_fixings(self.indexKey_, self.effDate_, self.endDate_)
        fixing_qldates = sorted(raw.keys())
        print(f"[ProductOvernightCapFloorlet] index={self.indexKey_}  eff={self.effDate_}  end={self.endDate_}")
        print(f"    → raw fixings keys: {fixing_qldates!r}")
        dates = [self.effDate_] + [Date(d) for d in fixing_qldates] + [self.endDate_]
        print(f"    → final fixing‐schedule: {dates!r}")
        return dates

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


# ------------------------
# Swaption Classes
# ------------------------

class ProductIborSwaption(Product):
    prodType = "ProductIborSwaption"

    def __init__(
        self,
        optionExpiry: str,
        swapStart: str,
        swapEnd: str,
        frequency: str,
        iborIndex: str,
        optionType: str,
        strikeRate: float,
        notional: float,
        longOrShort: str,
        holConv: str      = 'TARGET',
        bizConv: str      = 'MF',
        accrualBasis: str = 'ACT/365 FIXED',
        rule: str         = 'BACKWARD',
        endOfMonth: bool  = False,
    ) -> None:
        self.underlyingSwap = ProductIborSwap(
            effectiveDate=swapStart,
            maturityDate=swapEnd,
            frequency=frequency,
            iborIndex=iborIndex,
            spread=0.0,
            fixedRate=strikeRate,
            notional=notional,
            position=longOrShort,
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

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)


class ProductOvernightSwaption(Product):
    prodType = "ProductOvernightSwaption"

    def __init__(
        self,
        optionExpiry: str,
        swapStart: str,
        swapEnd: str,
        frequency: str,
        overnightIndex: str,
        optionType: str,
        strikeRate: float,
        notional: float,
        longOrShort: str,
        holConv: str      = 'TARGET',
        bizConv: str      = 'MF',
        accrualBasis: str = 'ACT/365 FIXED',
        rule: str         = 'BACKWARD',
        endOfMonth: bool  = False,
    ) -> None:

        self.underlyingSwap = ProductOvernightSwap(
            effectiveDate=swapStart,
            maturityDate=swapEnd,
            frequency=frequency,
            overnightIndex=overnightIndex,
            spread=0.0,
            fixedRate=strikeRate,
            notional=notional,
            position=longOrShort,
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

    def accept(self, visitor: ProductVisitor):
        return visitor.visit(self)
