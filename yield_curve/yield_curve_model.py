import datetime as dt
import pandas as pd
import numpy as np
from typing import Union, Optional
from date import Date,makeSchedule
import pandas as pd
from QuantLib import InterestRateIndex
from date import (Date, Period, TermOrTerminationDate, accrued)
from model import (Model, ModelComponent, ModelType)
from market import *
from utilities import (Interpolator1D)
from product.linear_products import ProductIborCashflow, ProductOvernightIndexCashflow


class YieldCurve(Model):
    MODEL_TYPE = 'YIELD_CURVE'

    def __init__(self, valueDate: str, dataCollection: pd.DataFrame, buildMethodCollection: list) -> None:
        columns = set(dataCollection.columns.to_list())
        assert 'INDEX' in columns; assert 'AXIS1' in columns; assert 'VALUES' in columns
        super().__init__(valueDate, 'YIELD_CURVE', dataCollection, buildMethodCollection)
    
    def newModelComponent(self, buildMethod: dict):
        return YieldCurveModelComponent(self.valueDate, self.dataCollection, buildMethod)
    
    def discountFactor(self, index : str, to_date : Union[str, Date]):
        this_component = self.retrieveComponent(index)
        to_date_ = to_date
        if isinstance(to_date, str): 
            to_date_ = Date(to_date) 
        assert to_date_ >= self.valueDate_
        time = accrued(self.valueDate_, to_date_)
        exponent = this_component.getStateVarInterpolator().integral(0, time)
        return np.exp(-exponent)
    
    def forward(self, index : str, effectiveDate : Union[Date, str], termOrTerminationDate : Optional[Union[str, TermOrTerminationDate]]=''):
        component = self.retrieveComponent(index)
        isOIS = component.isOvernightIndex
        if isOIS:
            if isinstance(termOrTerminationDate, str) and termOrTerminationDate == '':
                raise Exception('For OIS, one needs to specify term or termination date.')
            return self.forwardOvernightIndex(component.target, effectiveDate, termOrTerminationDate)
        else:
            return self.forwardIborIndex(component.target, effectiveDate)
        
    def forwardIborIndex(self, index : str, effectiveDate : Union[Date, str]):
        component = self.retrieveComponent(index)
        liborIndex = component.targetIndex
        tenor = liborIndex.tenor()
        # end date
        cal = liborIndex.fixingCalendar()
        effectiveDate_ = effectiveDate
        if isinstance(effectiveDate, str): effectiveDate_ = Date(effectiveDate)
        termDate = Date(cal.advance(effectiveDate_, tenor, liborIndex.businessDayConvention()))
        # accrued
        accrued = liborIndex.dayCounter().yearFraction(effectiveDate_, termDate)
        # forward rate
        dfStart = self.discountFactor(index, effectiveDate_)
        dfEnd = self.discountFactor(index, termDate)
        return (dfStart / dfEnd - 1.) / accrued
    
    def forwardOvernightIndex(self, index : str, effectiveDate : Union[Date, str], termOrTerminationDate : Union[str, TermOrTerminationDate, Date]):
        component = self.retrieveComponent(index)
        oisIndex = component.targetIndex

        effectiveDate_ = effectiveDate if isinstance(effectiveDate, Date) else Date(effectiveDate)

        if isinstance(termOrTerminationDate, Date):
            termDate = termOrTerminationDate
        else:
            to = (termOrTerminationDate 
                  if isinstance(termOrTerminationDate, TermOrTerminationDate)
                  else TermOrTerminationDate(termOrTerminationDate))
            cal = oisIndex.fixingCalendar()
            if to.isTerm():
                termDate = Date(
                    cal.advance(effectiveDate_, to.getTerm(), oisIndex.businessDayConvention())
                )
            else:
                termDate = to.getDate()

        accrual = oisIndex.dayCounter().yearFraction(effectiveDate_, termDate)
        dfStart = self.discountFactor(index, effectiveDate_)
        dfEnd   = self.discountFactor(index, termDate)
        return (dfStart / dfEnd - 1.0) / accrual

class YieldCurveModelComponent(ModelComponent):

    def __init__(self, valueDate: Date, dataCollection: pd.DataFrame, buildMethod: dict) -> None:
        super().__init__(valueDate, dataCollection, buildMethod)
        self.interpolationMethod_ = 'PIECEWISE_CONSTANT'
        if 'INTERPOLATION METHOD' in self.buildMethod_:
            self.interpolationMethod_ = self.buildMethod_['INTERPOLATION METHOD']
        self.axis1 = []
        self.timeToDate = []
        self.ifrInterpolator = None
        self.targetIndex_ = None
        self.isOvernightIndex_ = False
        # i don't like this implementation
        if '1B' in self.target_: 
            self.targetIndex_ = IndexRegistry()._instance.get(self.target_)
            self.isOvernightIndex_ = True
        else:
            tokenizedIndex = self.target_.split('-')
            tenor = tokenizedIndex[-1]
            self.targetIndex_ = IndexRegistry()._instance.get('-'.join(tokenizedIndex[:-1]), tenor)
        self.calibrate()

    def calibrate(self):
        ### TODO: calibration to market instruments instead of directly feeding ifr
        this_df = self.dataCollection_[self.dataCollection_['INDEX'] == self.target_]
        ### TODO: axis1 can be a combination of dates and tenors
        ###       for now, i assume they're all tenor based

        cal = self.targetIndex_.fixingCalendar()
        for each in this_df['AXIS1'].values.tolist():
            this_dt = Date(cal.advance(self.valueDate_, Period(each), self.targetIndex_.businessDayConvention()))
            self.axis1.append(this_dt)
            self.timeToDate.append(accrued(self.valueDate_, this_dt))
        self.stateVars = this_df['VALUES'].values.tolist()
        self.ifrInterpolator = Interpolator1D(self.timeToDate, self.stateVars, self.interpolationMethod_)
    
    def getStateVarInterpolator(self):
        return self.ifrInterpolator

    @property
    def isOvernightIndex(self):
        return self.isOvernightIndex_
    
    @property
    def targetIndex(self):
        return self.targetIndex_