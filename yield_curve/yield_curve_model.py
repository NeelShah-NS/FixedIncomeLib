import datetime as dt
import pandas as pd
import numpy as np
from typing import Union, Optional
from date import Date
import pandas as pd
from date import (Date, Period, accrued)
from model import (Model, ModelComponent, ModelType)
from market import *
from utilities import (Interpolator1D)


class YiedCurve(Model):

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
        
    def forward(self, index : str, effectiveDate : str, termOrTerminationDate : Union[Date, str]):
        ### TODO: needs to be implemented
        pass

class YieldCurveModelComponent(ModelComponent):

    def __init__(self, valueDate: Date, dataCollection: pd.DataFrame, buildMethod: dict) -> None:
        super().__init__(valueDate, dataCollection, buildMethod)
        self.interpolationMethod_ = 'PIECEWISE_CONSTANT'
        if 'INTERPOLATION METHOD' in self.buildMethod_:
            self.interpolationMethod_ = self.buildMethod_['INTERPOLATION METHOD']
        self.axis1 = []
        self.timeToDate = []
        self.ifrInterpolator = None
        # i don't like this implementation
        if '1B' in self.target_: 
            self.targetIndex = IndexRegistry()._instance.get(self.target_)
        else:
            tokenized_index = self.target_.split('-')
            tenor = tokenized_index[-1]
            self.targetIndex = IndexRegistry()._instance.get('-'.join(tokenized_index[:-1]), tenor)
        self.calibrate()

    def calibrate(self):
        ### TODO: calibration to market instruments instead of directly feeding ifr
        this_df = self.dataCollection_[self.dataCollection_['INDEX'] == self.target_]
        ### TODO: axis1 can be a combination of dates and tenors
        ###       for now, i assume they're all tenor based

        cal = self.targetIndex.fixingCalendar()
        for each in this_df['AXIS1'].values.tolist():
            this_dt = Date(cal.advance(self.valueDate_, Period(each), self.targetIndex.businessDayConvention()))
            self.axis1.append(this_dt)
            self.timeToDate.append(accrued(self.valueDate_, this_dt))
        self.state_vars_ = this_df['VALUES'].values.tolist()
        self.ifrInterpolator = Interpolator1D(self.timeToDate, self.state_vars_, self.interpolationMethod_)
    
    def getStateVarInterpolator(self):
        return self.ifrInterpolator
