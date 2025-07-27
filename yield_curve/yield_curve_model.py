import pandas as pd
import numpy as np
from typing import Any, Dict, Union, Optional
from date import Date
import pandas as pd
from date import (Date, Period, TermOrTerminationDate, accrued)
from model import (Model, ModelComponent)
from market import *
from utilities import (Interpolator1D)
from data import DataCollection, Data1D

class YieldCurve(Model):
    MODEL_TYPE = 'YIELD_CURVE'

    def __init__(self, valueDate: str, dataRepository: DataCollection, buildMethodCollection: list) -> None:
        for bm in buildMethodCollection:
            bm["DATA_TYPE"]       = bm.get("DATA_TYPE", "ZERO_RATE").upper()
            bm["DATA_CONVENTION"] = bm.get("DATA_CONVENTION", bm["TARGET"])
            bm["NAME"]            = bm["TARGET"].upper()

        super().__init__(valueDate, self.MODEL_TYPE, dataRepository, buildMethodCollection)

    def newModelComponent(self, buildMethod: Dict[str, Any]) -> ModelComponent:
        data_type       = buildMethod["DATA_TYPE"].upper()
        data_convention = buildMethod["DATA_CONVENTION"]
        interp_method = buildMethod.get("INTERPOLATION_METHOD", "PIECEWISE_CONSTANT")
        zero_curve: Data1D = self.dataRepo.get(data_type, data_convention)
        return YieldCurveModelComponent(self.valueDate, zero_curve, interp_method)
    
    def discountFactor(self, index : str, to_date : Union[str, Date]):
        to_date_ = (Date(to_date) if isinstance(to_date, str) else to_date)
        assert to_date_ >= self.valueDate_, "to_date must be ≥ valuation date"
        t = accrued(self.valueDate_, to_date_)
        component = self.retrieveComponent(index)
        integral_value = component.integral(0.0, t)
        return float(np.exp(-integral_value))
    
    def forward(self, index : str, effectiveDate : Union[Date, str], termOrTerminationDate : Optional[Union[str, TermOrTerminationDate]]=''):
        component = self.retrieveComponent(index)
        isOIS = component.isOvernightIndex
        if isOIS:
            if isinstance(termOrTerminationDate, str) and termOrTerminationDate == '':
                raise Exception('For OIS, one needs to specify term or termination date.')
            return self.forwardOvernightIndex(index, effectiveDate, termOrTerminationDate)
        else:
            return self.forwardIborIndex(index, effectiveDate)
        
    def forwardIborIndex(self, index : str, effectiveDate : Union[Date, str]):
        component = self.retrieveComponent(index)
        liborIndex = component.targetIndex
        tenor = liborIndex.tenor()
        # end date
        calendar = liborIndex.fixingCalendar()
        effectiveDate_ = effectiveDate
        if isinstance(effectiveDate, str): effectiveDate_ = Date(effectiveDate)
        termDate = Date(calendar.advance(effectiveDate_, tenor, liborIndex.businessDayConvention()))
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
            calendar = oisIndex.fixingCalendar()
            if to.isTerm():
                termDate = Date(
                    calendar.advance(effectiveDate_, to.getTerm(), oisIndex.businessDayConvention())
                )
            else:
                termDate = to.getDate()

        accrual = oisIndex.dayCounter().yearFraction(effectiveDate_, termDate)
        dfStart = self.discountFactor(index, effectiveDate_)
        dfEnd   = self.discountFactor(index, termDate)
        return (dfStart / dfEnd - 1.0) / accrual

class YieldCurveModelComponent(ModelComponent):

    def __init__(self, valueDate: Date, zeroCurve: Data1D, interpolationMethod: str) -> None:
        dummy_bm = {"TARGET": zeroCurve.data_convention}
        super().__init__(valueDate, None, dummy_bm)
        # self.axis1 = []
        # self.timeToDate = []
        # i don't like this implementation
        # if '1B' in self.target_: 
        #     self.targetIndex_ = IndexRegistry()._instance.get(self.target_)
        #     self.isOvernightIndex_ = True
        # else:
        #     tokenizedIndex = self.target_.split('-')
        #     tenor = tokenizedIndex[-1]
        #     self.targetIndex_ = IndexRegistry()._instance.get('-'.join(tokenizedIndex[:-1]), tenor)
        self._curve    = zeroCurve
        self._interp   = zeroCurve._interp
        self.method    = interpolationMethod

        # figure out QuantLib index for forwards
        idx_key = zeroCurve.data_convention
        if idx_key.endswith("1B"):
            # Overnight index
            self._ql_index  = IndexRegistry().get(idx_key)
            self._is_ois    = True
        else:
            # IBOR index: split base key and tenor
            base, tenor     = idx_key.rsplit("-", 1)
            self._ql_index  = IndexRegistry().get(base, tenor)
            self._is_ois    = False

    def calibrate(self) -> None:
        # no‐op: the Data1D already built the interpolator
        pass

    @property
    def isOvernightIndex(self) -> bool:
        return self._is_ois

    @property
    def targetIndex(self):
        return self._ql_index

    def integral(self, start: float, end: float) -> float:
        return self._interp.integral(start, end)

    def getStateVarInterpolator(self):
        return self._interp

    # def calibrate(self):
    #     ### TODO: calibration to market instruments instead of directly feeding ifr
    #     # this_df = self.dataCollection_[self.dataCollection_['INDEX'] == self.target_]
    #     ### TODO: axis1 can be a combination of dates and tenors
    #     ###       for now, i assume they're all tenor based
    #     # calendar = self.targetIndex_.fixingCalendar()
    #     # for each in this_df['AXIS1'].values.tolist():
    #     #     this_dt = Date(calendar.advance(self.valueDate_, Period(each), self.targetIndex_.businessDayConvention()))
    #     #     self.axis1.append(this_dt)
    #     #     self.timeToDate.append(accrued(self.valueDate_, this_dt))
    #     # self.stateVars = this_df['VALUES'].values.tolist()