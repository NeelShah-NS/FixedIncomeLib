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
from utilities import (Interpolator1D, gauss_newton)
from product.linear_products import ProductIborCashflow, ProductOvernightIndexCashflow
from data import DataCollection, Data1D
from builders import build_yc_calibration_basket_from_dc, make_default_pillars
from valuation import ValuationEngineRegistry

DEFAULT_IFR_GUESS = 0.04


class YieldCurve(Model):
    MODEL_TYPE = 'YIELD_CURVE'

    def __init__(self, valueDate: str, dataCollection: DataCollection, buildMethodCollection: list) -> None:
        super().__init__(valueDate, 'YIELD_CURVE', dataCollection, buildMethodCollection)

    def newModelComponent(self, buildMethod: dict):
        return YieldCurveModelComponent(self.valueDate, self.dataCollection, buildMethod, parent_model = self)
    
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
        accrual = liborIndex.dayCounter().yearFraction(effectiveDate_, termDate)
        # forward rate
        dfStart = self.discountFactor(index, effectiveDate_)
        dfEnd = self.discountFactor(index, termDate)
        return (dfStart / dfEnd - 1.) / accrual
    
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
        return ((dfStart / dfEnd) - 1.0) / accrual

class YieldCurveModelComponent(ModelComponent):

    def __init__(self, valueDate: Date, dataCollection: DataCollection, buildMethod: dict, parent_model=None) -> None:
        super().__init__(valueDate, dataCollection, buildMethod)
        self._model = parent_model
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

        if self._model is not None:
            key = str(self.buildMethod_.get("TARGET", self.target_))
            self._model.components[key] = self
            self._model.components[key.upper()] = self

        self.calibrate()
    
    def calibrate(self):
    #Build PRODUCTS + QUOTES basket from DataCollection using INSTRUMENTS
        self._calibration_basket = build_yc_calibration_basket_from_dc(
            value_date=self.valueDate_,
            data_collection=self.dataCollection,
            build_method=self.buildMethod_,
        )

        unique_pillars, times = make_default_pillars(self.valueDate_, self.targetIndex_)
        if not times:
            cal = self.targetIndex_.fixingCalendar()
            bdc = self.targetIndex_.businessDayConvention()
            one_day = Date(cal.advance(self.valueDate_, Period("1D"), bdc))
            unique_pillars = [one_day]
            times = [accrued(self.valueDate_, one_day)]
        
        theta0 = DEFAULT_IFR_GUESS
        self.axis1 = unique_pillars
        self.timeToDate = times
        self.stateVars = [theta0] * len(times)
        self.ifrInterpolator = Interpolator1D(self.timeToDate, self.stateVars, self.interpolationMethod_)

        #Calibration residuals via ValuationEngineRegistry
        vp = {"FUNDING INDEX": self.target_, "valuation_date": self.valueDate_}
        reg = ValuationEngineRegistry()

        future_engines = []
        swap_engines = []
        for it in self._calibration_basket:
            prod = it.product
            typ = str(getattr(prod, "prodType", "")).upper()
            eng = reg.new_valuation_engine(self._model, vp, prod)
            if "FUTURE" in typ:
                future_engines.append(eng)
            elif "SWAP" in typ:
                swap_engines.append(eng)

        def _install_theta(theta_vec):
            self.stateVars = list(theta_vec)
            self.ifrInterpolator = Interpolator1D(self.timeToDate, self.stateVars, self.interpolationMethod_)

        def residuals_fn(theta_vec):
            _install_theta(theta_vec)
            r = []
            # Futures: model_price - market_price
            for eng in future_engines:
                eng.calculateValue()
                r.append(float(eng.value_[1]))
            # Swaps: par - fixedRate
            for eng in swap_engines:
                eng.calculateValue()
                par = float(eng.parRateOrSpread())
                r.append(par - float(eng.product.fixedRate))
            return np.asarray(r, dtype=float)

        #Solve for IFRs
        theta0_vec = np.array(self.stateVars, dtype=float)
        theta_sol, final_residuals = gauss_newton(
            residuals_fn=residuals_fn,
            initial_params=theta0_vec,
            max_iterations=int(self.buildMethod_.get("MAX_ITERS", 25)),
            lower_bound=float(self.buildMethod_.get("IFR_LB", -0.05)),
            upper_bound=float(self.buildMethod_.get("IFR_UB", 0.15)),
            tolerance=float(self.buildMethod_.get("TOL", 1e-10)),
            fd_step=float(self.buildMethod_.get("FD_EPS", 1e-6)),
        )
        _install_theta(theta_sol)
        if bool(self.buildMethod_.get("DEBUG", False)):
            self._debug("\n[YC DEBUG] Calibrated IFRs at pillars")
            header = f"{'idx':>3}  {'pillar':<12}  {'t (yrs)':>10}  {'theta*':>10}  {'∫θ du':>12}  {'DF(t)':>12}"
            self._debug(header)
            self._debug("-" * len(header))
            for i, (d, t, th) in enumerate(zip(self.axis1, self.timeToDate, self.stateVars)):
                integral = self.ifrInterpolator.integral(0.0, float(t))
                df = np.exp(-integral)
                self._debug(f"{i:3d}  {self._dstr(d):<12}  {t:10.10f}  {th:10.8f}  {integral:12.10f}  {df:12.10f}")


        self._calibration_summary = {
    "rmse": float(np.sqrt(np.mean(final_residuals**2))),
    "max_abs": float(np.max(np.abs(final_residuals))),
    "n_residuals": int(final_residuals.size),
    "n_parameters": len(theta_sol),
}
    
    def _dstr(self, d):
        """Best-effort date -> string."""
        # Try common names first, then fall back
        for attr in ("toString", "ISO", "isoformat", "__str__"):
            f = getattr(d, attr, None)
            if callable(f):
                try:
                    return f()
                except:
                    pass
        return str(d)

    def _debug(self, *args):
        """Opt-in debug print if build method contains DEBUG=True."""
        if bool(self.buildMethod_.get("DEBUG", False)):
            print(*args)

    def getStateVarInterpolator(self):
            return self.ifrInterpolator

    @property
    def isOvernightIndex(self):
        return self.isOvernightIndex_

    @property
    def targetIndex(self):
        return self.targetIndex_
    
    @property
    def target(self):
        return getattr(self, "target_", None)
    
    