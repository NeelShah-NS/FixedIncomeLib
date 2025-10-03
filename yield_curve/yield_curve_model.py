import numpy as np
from typing import Union, Optional, Tuple, List
from builders.pillar_builders import (anchor_date, fixed_leg_dates_alphas, build_anchor_pillars)
from date import Date, Period, TermOrTerminationDate, accrued
from model import Model, ModelComponent
from market import *
from utilities import Interpolator1D, newton_1d
from data import DataCollection
from builders import build_yc_calibration_basket_from_dc
from valuation import ValuationEngineRegistry

DEFAULT_IFR_GUESS = 0.04

class YieldCurve(Model):
    MODEL_TYPE = 'YIELD_CURVE'

    def __init__(self, valueDate: str, dataCollection: DataCollection, buildMethodCollection: list) -> None:
        super().__init__(valueDate, 'YIELD_CURVE', dataCollection, buildMethodCollection)

    def newModelComponent(self, buildMethod: dict):
        return YieldCurveModelComponent(self.valueDate, self.dataCollection, buildMethod, parent_model=self)
    
    def discountFactor(self, index : str, to_date : Union[str, Date]):
        this_component = self.retrieveComponent(index)
        to_date_ = to_date
        if isinstance(to_date, str): 
            to_date_ = Date(to_date) 
        assert to_date_ >= self.valueDate_
        time = accrued(self.valueDate_, to_date_)
        exponent = this_component.getStateVarInterpolator().integral(0, time)
        return np.exp(-exponent)
    
    def gradientDiscountFactor(self, index: str, to_date: Union[str, Date]) -> np.ndarray:
        this_component = self.retrieveComponent(index)
        to_date_ = to_date if not isinstance(to_date, str) else Date(to_date)
        assert to_date_ >= self.valueDate_
        time_to_date = accrued(self.valueDate_, to_date_)
        df = float(self.discountFactor(index, to_date_))

        pillar_times = np.asarray(this_component.pillarsTimeToDate, dtype=float)
        if pillar_times.size == 0:
            return np.zeros(0, dtype=float)

        if str(getattr(this_component, "interpolationMethod_", "PIECEWISE_CONSTANT")).upper() == "PIECEWISE_CONSTANT":
            interval_starts = np.concatenate((np.array([0.0]), pillar_times[:-1]))
            interval_ends = pillar_times
            overlap = np.maximum(0.0, np.minimum(time_to_date, interval_ends) - interval_starts)
            return (-df) * overlap

        return np.zeros_like(pillar_times, dtype=float)

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

    def __init__(self, valueDate: Date, dataCollection: DataCollection, buildMethod: dict, parent_model=None) -> None:
        super().__init__(valueDate, dataCollection, buildMethod)
        self._model = parent_model
        self.interpolationMethod_ = self.buildMethod_.get('INTERPOLATION METHOD', 'PIECEWISE_CONSTANT')
        self.axis1: List[Date] = []
        self.pillarsTimeToDate: List[float] = []
        self.ifrInterpolator = None
        self.targetIndex_ = None
        self.isOvernightIndex_ = False

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
        raw_basket = build_yc_calibration_basket_from_dc(
            value_date=self.valueDate_,
            data_collection=self.dataCollection,
            build_method=self.buildMethod_,
        )

        axis1, times, kept_items = build_anchor_pillars(list(raw_basket),self.valueDate_)
        self.axis1 = axis1
        self.pillarsTimeToDate = times

        # Initial IFR guess
        theta0 = DEFAULT_IFR_GUESS
        self.stateVars = [theta0] * len(times)
        self.ifrInterpolator = Interpolator1D(self.pillarsTimeToDate, self.stateVars, self.interpolationMethod_)

        vp = {"FUNDING INDEX": self.target_, "valuation_date": self.valueDate_}
        reg = ValuationEngineRegistry()
        engines = [reg.new_valuation_engine(self._model, vp, it.product) for it in kept_items]

        def _install_theta(theta_vec: np.ndarray) -> None:
            self.stateVars = list(np.asarray(theta_vec, float))
            self.ifrInterpolator = Interpolator1D(self.pillarsTimeToDate, self.stateVars, self.interpolationMethod_)

        def _df_and_grad(d: Date) -> Tuple[float, np.ndarray]:
            df = self._model.discountFactor(self.target_, d)
            g = self._model.gradientDiscountFactor(self.target_, d)
            return float(df), np.asarray(g, float)

        def _instrument_k(it) -> int:
            """Map instrument to pillar index via its anchor date."""
            anc = anchor_date(it.product)
            t = float(accrued(self.valueDate_, anc))
            for j, tj in enumerate(self.pillarsTimeToDate):
                if t <= tj + 1e-14:
                    return j
            return len(self.pillarsTimeToDate) - 1

        # ---------- residuals ----------

        def _residual(eng) -> float:
            prod = eng.product
            typ = str(getattr(prod, "prodType", "")).upper()

            if "SWAP" in typ:
                eng.calculateValue()
                par = float(eng.parRateOrSpread())
                K = float(getattr(prod, "fixedRate"))
                return par - K

            elif "FUTURE" in typ:
                S = getattr(prod, "effectiveDate")
                E = getattr(prod, "maturityDate")
                idx = getattr(prod, "index", self.target_)
                f_model = float(self._model.forward(idx, S, E))
                strike = float(getattr(prod, "strike"))
                f_mkt = (100.0 - strike) / 100.0
                return f_model - f_mkt

            else:
                raise RuntimeError(f"Unsupported product type: {typ}")

        # derivatives : Change once CalculateRisk() is implemented in valuation engines
        def _derivative_row(eng) -> np.ndarray:
            prod = eng.product
            typ = str(getattr(prod, "prodType", "")).upper()

            if "FUTURE" in typ:
                S = getattr(prod, "effectiveDate", None)
                E = getattr(prod, "maturityDate", None)
                if S is None or E is None:
                    raise RuntimeError(f"Future missing effective/maturity dates: {type(prod).__name__}")

                accrualFactor = getattr(prod, "accrualFactor", None)
                if accrualFactor is None:
                    try:
                        accrualFactor = float(self.targetIndex_.dayCounter().yearFraction(S, E))
                    except Exception:
                        accrualFactor = float(accrued(S, E))
                else:
                    accrualFactor = float(accrualFactor)

                DF_S, gS = _df_and_grad(S)
                DF_E, gE = _df_and_grad(E)
                dF = (gS / DF_E) - (DF_S * gE) / (DF_E * DF_E)
                dF /= accrualFactor
                return dF.astype(float)

            elif "SWAP" in typ:
                dates, alphas = fixed_leg_dates_alphas(prod, self.valueDate_)

                DFs, Gs = [], []
                for di in dates:
                    df_i, g_i = _df_and_grad(di)
                    DFs.append(float(df_i))
                    Gs.append(np.asarray(g_i, float))
                alphas = np.asarray(alphas, float)
                DFs = np.asarray(DFs, float)
                Gs = np.asarray(Gs, float)

                A = float((alphas * DFs).sum())   
                B = 1.0 - float(DFs[-1])          
                dA = (Gs * alphas[:, None]).sum(axis=0)
                dB = -Gs[-1]
                dR = (dB * A - B * dA) / (A * A)
                return dR.astype(float)

            else:
                raise RuntimeError(f"Unsupported product type for derivative: {typ}")

        def _check_single_new_bucket(eng, k: int, solved_mask: np.ndarray) -> bool:
            drow = _derivative_row(eng)  # (N,)
            touched = np.where(np.abs(drow) > 1e-14)[0]
            new_touch = [i for i in touched if not solved_mask[i]]
            return (len(new_touch) == 1 and new_touch[0] == k)

        theta = np.array(self.stateVars, float)
        solved = np.zeros(len(self.pillarsTimeToDate), dtype=bool)

        tol_r = float(self.buildMethod_.get("LOCAL_TOL", 1e-12))
        maxit = int(self.buildMethod_.get("MAX_LOCAL_ITERS", 100))
        touch_tol = float(self.buildMethod_.get("TOUCH_TOL", 1e-12))

        for idx, eng in enumerate(engines):
            it = kept_items[idx]
            k = _instrument_k(it)

            if k > 0 and not solved[k - 1]:
                raise RuntimeError(f"Instrument for pillar k={k} arrives before pillar k={k-1} solved.")

            if not _check_single_new_bucket(eng, k, solved):
                policy = str(self.buildMethod_.get("ON_MULTI_BUCKET", "ERROR")).upper()  # ERROR | DROP
                if policy == "DROP":
                    continue
                else:
                    typ = str(getattr(eng.product, "prodType", ""))
                    raise RuntimeError(f"Instrument {typ} at pillar k={k} touches more than one new bucket.")

            def residual_theta(x: float) -> float:
                theta_tmp = theta.copy()
                theta_tmp[k] = float(x)
                _install_theta(theta_tmp)
                return _residual(eng)

            def derivative_theta(x: float) -> float:
                theta_tmp = theta.copy()
                theta_tmp[k] = float(x)
                _install_theta(theta_tmp)
                drow = _derivative_row(eng)
                return float(drow[k])
            
            x_opt, max_iter, residual = newton_1d(
                residual=residual_theta,
                derivative=derivative_theta,
                initial_guess=float(theta[k]),
                tol=tol_r,
                max_iter=maxit,
                min_slope=touch_tol,
            )

            theta[k] = x_opt
            solved[k] = True
            _install_theta(theta)

        self.stateVars = list(theta)
        self.ifrInterpolator = Interpolator1D(self.pillarsTimeToDate, self.stateVars, self.interpolationMethod_)

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
