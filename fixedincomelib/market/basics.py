from typing import Optional
import QuantLib as ql

### below are some wrappers to allow str -> quantlib object conversion
### businessdayconvention, holidayconvention, accrualbasis

class BusinessDayConvention:
    
    def __init__(self, input : Optional[str]='NONE') -> None:
        self.value_ = None
        if input.upper() == 'MF':
            self.value_ = ql.ModifiedFollowing
        elif input.upper() == 'F':
            self.value_ = ql.Following
        elif input.upper() == 'P' or input.upper() == 'NONE':
            self.value_ = ql.Preceding
        else:
            raise Exception(input + ' is not current supported business day convention.')

    @property
    def value(self):
        return self.value_
    
class HolidayConvention:
    
    def __init__(self, input : Optional[str]='NONE') -> None:
        self.value_ = ql.NullCalendar()
        if input.upper() == 'NYC':
            self.value_ = ql.UnitedStates(ql.UnitedStates.LiborImpact)
        elif input.upper() == 'USGS':
            self.value_ = ql.UnitedStates(ql.UnitedStates.FederalReserve) # not sure
        elif input.upper() == 'LON':
            self.value_ = ql.UnitedKingdom(ql.UnitedKingdom.Exchange)
        elif input.upper() == 'TOK':
            self.value_ = ql.Japan()
        elif input.upper() == 'TARGET':
            self.value_ = ql.JointCalendar(ql.TARGET(), ql.France(), ql.Germany(), ql.Italy()) # good enough ?
        elif input.upper() == 'SYD':
            self.value_ = ql.Australia() 
        if self.value_ == None:
            raise Exception(input + ' is not current supported Hoiday Center.')

    @property
    def value(self):
        return self.value_
    
class AccrualBasis(ql.DayCounter):

    def __init__(self, input : Optional[str]='NONE') -> None:
        self.value_ = None
        if input.upper() == 'NONE':
            self.value_ = ql.SimpleDayCounter()
        elif input.upper() == 'ACT/ACT':
            self.value_ = ql.ActualActual(ql.ActualActual.ISDA)
        elif input.upper() == 'ACT/365 FIXED':
            self.value_ = ql.Actual365Fixed()
        elif input.upper() == 'ACT/360':
            self.value_ = ql.Actual360()
        elif input.upper() == '30/360':
            self.value_ = ql.Thirty360(ql.Thirty360.ISDA)
        elif input.upper() == 'BUSINESS252':
            self.value_ = ql.Business252()
        else:
            raise Exception(input + ' is not current supported accrual basis.')

    @property
    def value(self):
        return self.value_