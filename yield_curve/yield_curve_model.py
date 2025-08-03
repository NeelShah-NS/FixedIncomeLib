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
from data import DataCollection, Data1D

class YieldCurve(Model):
    MODEL_TYPE = 'YIELD_CURVE'

    def __init__(self, valueDate: str, dataCollection: DataCollection, buildMethodCollection: list) -> None:
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

    def __init__(self, valueDate: Date, dataCollection: DataCollection, buildMethod: dict) -> None:
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
        md = self.dataCollection.get('zero_rate', self.target)
        assert isinstance(md, Data1D)
        ### TODO: axis1 can be a combination of dates and tenors
        ###       for now, i assume they're all tenor based

        rates: list[float] = []

        cal = self.targetIndex.fixingCalendar()
        bdc = self.targetIndex.businessDayConvention()

        for tenor_str, r in zip(md.axis, md.values):
            p   = Period(tenor_str)
            dt  = Date(cal.advance(self.valueDate_, p, bdc))
            self.axis1.append(dt) 
            tau = accrued(self.valueDate_, dt)
            self.timeToDate.append(tau)
            rates.append(r)

        self.stateVars       = rates
        self.ifrInterpolator = Interpolator1D(self.timeToDate, self.stateVars, self.interpolationMethod_)

    def getStateVarInterpolator(self):
        return self.ifrInterpolator

    @property
    def isOvernightIndex(self):
        return self.isOvernightIndex_
    
    @property
    def targetIndex(self):
        return self.targetIndex_