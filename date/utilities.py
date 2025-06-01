import pandas as pd
from .classes import *
from ..market import *

def addPeriod(start_date : str, term : str, biz_conv : Optional[str]='NONE', hol_conv : Optional[str]='NONE', endOfMonth : Optional[bool]=False):
    this_cal = HolidayConvention(hol_conv).value
    return Date(this_cal.advance(Date(start_date), Period(term), BusinessDayConvention(biz_conv).value, endOfMonth))

def accrued(start_dt : str, end_date : str, accrual_basis : Optional[str]='NONE', biz_conv : Optional[str]='NONE', hol_conv : Optional[str]='NONE'):
    # in case end date falls on non-business day
    adjusted_end_dt = moveToBusinessDay(end_date, biz_conv, hol_conv) 
    return AccrualBasis(accrual_basis).value.yearFraction(Date(start_dt), adjusted_end_dt)

def moveToBusinessDay(input_date : str, biz_conv : str, hol_conv : str):
    return Date(HolidayConvention(hol_conv).value.adjust(Date(input_date), BusinessDayConvention(biz_conv).value))

def isBusinessDay(input_date : str, hol_conv : str):
    return HolidayConvention(hol_conv).value.isBusinessDay(Date(input_date))

def isHoliday(input_date : str, hol_conv : str):
    return HolidayConvention(hol_conv).value.isHoliday(Date(input_date))

def isWeekend(input_date : str, hol_conv : str):
    return HolidayConvention(hol_conv).value.isWeekend(Date(input_date))

def isEndOfMonth(input_date : str, hol_conv : str):
    return HolidayConvention(hol_conv).value.isEndOfMonth(Date(input_date))

def endOfMonth(input_date : str, hol_conv : str):
    return HolidayConvention(hol_conv).value.endOfMonth(Date(input_date))

def makeScheudle(
        start_dt : str, 
        end_dt : str, 
        frequency : str,
        hol_conv : str,
        biz_conv : str, 
        acc_basis : str,
        rule : Optional[str]='BACKWARD', 
        endOfMonth : Optional[bool]=False,
        fix_in_arrear : Optional[bool]=False, 
        fixing_offset : Optional[str]='',
        fixing_offset_biz_conv : Optional[str]='',
        fixing_offset_hol_conv : Optional[str]='',
        paymnent_offset : Optional[str]='',
        payment_offset_biz_conv : Optional[str]='',
        payment_offset_hol_conv: Optional[str]='') -> pd.DataFrame:

    this_rule = ql.DateGeneration.Backward if rule.upper() == 'BACKWARD' else ql.DateGeneration.Forward
    # set up start date and end date of each period
    this_schedule = ql.Schedule(Date(start_dt), Date(end_dt), Period(frequency), 
                                HolidayConvention(hol_conv).value, 
                                BusinessDayConvention(biz_conv).value, 
                                BusinessDayConvention(biz_conv).value,  
                                this_rule, 
                                endOfMonth)
    
    # add fixing date and payment date
    start_dates = this_schedule.dates()[:-1]
    end_dates = this_schedule.dates()[1:]
    fixing_dates, payment_dates, accs = [], [], []
    for s, e in zip(start_dates, end_dates):
        f = s
        if fixing_offset != '':
            f = addPeriod(e if fix_in_arrear else s, fixing_offset, fixing_offset_biz_conv, fixing_offset_hol_conv)
        fixing_dates.append(f)
        p = e
        if paymnent_offset != '':
            p = addPeriod(e, paymnent_offset, payment_offset_biz_conv, payment_offset_hol_conv)
        payment_dates.append(p)
        accs.append(accrued(s, e, acc_basis, biz_conv, hol_conv))

    # set up container
    df = pd.DataFrame(columns=['StartDate', 'EndDate', 'FixingDate', 'PaymentDate', 'Accrued'])
    df['StartDate'] = start_dates
    df['EndDate'] = end_dates
    df['FixingDate'] = fixing_dates
    df['PaymentDate'] = payment_dates
    df['Accrued'] = accs
    
    return df