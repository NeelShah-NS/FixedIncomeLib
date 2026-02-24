import numpy as np
from typing import Dict, Union, Optional, Tuple, List
from fixedincomelib.builders import (anchor_date, build_anchor_pillars)
from fixedincomelib.date import Date, Period, TermOrTerminationDate, accrued
from fixedincomelib.model import Model, ModelComponent
from fixedincomelib.market import *
from fixedincomelib.utilities import Interpolator1D, simple_solver
from fixedincomelib.data import DataCollection
from fixedincomelib.builders import build_yc_calibration_basket_from_dc
from fixedincomelib.valuation import ValuationEngineRegistry
from fixedincomelib.yield_curve.pillar_node import PillarNode

DEFAULT_IFR_GUESS = 0.04

class YieldCurve(Model):
    MODEL_TYPE = 'YIELD_CURVE'

    def __init__(self, valueDate: str, dataCollection: DataCollection, buildMethodCollection: list) -> None:
        super().__init__(valueDate, 'YIELD_CURVE', dataCollection, buildMethodCollection)
        self.gradient_labels_: List[str] = []
        self.gradient_offsets_: np.ndarray = np.zeros(1, dtype=int)
        self.gradient_slices_: Dict[str, slice] = {}
        self.gradient_: np.ndarray = np.zeros(0, dtype=float)

        self._build_gradient_lists()
    
    def _components_in_order(self) -> List[ModelComponent]:
        seen = set()
        ordered: List[ModelComponent] = []
        for comp in self.components.values():
            key = str(comp.target).upper()
            if key not in seen:
                seen.add(key)
                ordered.append(comp)
        return ordered

    def _build_gradient_lists(self) -> None:
        components = self._components_in_order()
        labels: List[str] = []
        lengths: List[int] = []

        for component in components:
            label = str(component.target).upper()
            n = int(len(component.stateVars_))
            labels.append(label)
            lengths.append(n)

        offsets = np.zeros(len(lengths) + 1, dtype=int)
        if lengths:
            offsets[1:] = np.cumsum(lengths, dtype=int)

        slices: Dict[str, slice] = {}
        for i, lab in enumerate(labels):
            slices[lab] = slice(offsets[i], offsets[i + 1])

        total = int(offsets[-1])
        self.gradient_labels_ = labels
        self.gradient_offsets_ = offsets
        self.gradient_slices_ = slices
        self.gradient_ = np.zeros(total, dtype=float)

    def clearGradient(self) -> None:
        if self.gradient_.size:
            self.gradient_.fill(0.0)

    def getGradientArray(self) -> np.ndarray:
        return self.gradient_.copy()
    
    def _target_slice(self, index: str) -> slice:
        key = str(index).upper()
        if key not in self.gradient_slices_:
            raise KeyError(f"Unknown gradient block for index '{index}'. Known: {list(self.gradient_slices_.keys())}")
        return self.gradient_slices_[key]

    def newModelComponent(self, buildMethod: dict):
        return YieldCurveModelComponent(self.valueDate, self.dataCollection, buildMethod, parent_model=self)
    
    def discountFactor(self, index : str, to_date : Union[str, Date]):
        this_component = self.retrieveComponent(index)
        to_date_ = to_date
        if isinstance(to_date, str): 
            to_date_ = Date(to_date) 
        assert to_date_ >= self.valueDate_
        dc = this_component.targetIndex_.dayCounter()
        time = float(dc.yearFraction(self.valueDate_, to_date_))
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
            return self.forwardIborIndex(component.target, effectiveDate, termOrTerminationDate)
        
    def forwardIborIndex(self, index, effectiveDate, termOrTerminationDate):
        component = self.components[index]
        liborIndex = component.targetIndex_

        effectiveDate_ = Date(effectiveDate) if isinstance(effectiveDate, str) else effectiveDate

        if isinstance(termOrTerminationDate, Date):
            termDate = termOrTerminationDate
        else:
            to = termOrTerminationDate if isinstance(termOrTerminationDate, TermOrTerminationDate) \
                else TermOrTerminationDate(termOrTerminationDate)

            if to.isTerm():
                cal = liborIndex.fixingCalendar()
                bdc = liborIndex.businessDayConvention()
                termDate = Date(cal.advance(effectiveDate_, to.getTerm(), bdc))
            else:
                termDate = to.getDate()

        accrual = liborIndex.dayCounter().yearFraction(effectiveDate_, termDate)

        dfStart = self.discountFactor(index, effectiveDate_)
        dfEnd   = self.discountFactor(index, termDate)

        return (dfStart / dfEnd - 1.0) / accrual
    
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
    
    def discountFactorGradientWrtModelParameters(
            self,
            index: str,
            to_date: Union[str, Date],
            gradient: Optional[np.ndarray] = None,
            scaler: float =1.0,
            accumulate: bool = False) -> None:
        
        comp = self.retrieveComponent(index)
        if comp is None:
            raise KeyError(f"Unknown component '{index}'")
        if comp.interpolationMethod_.upper() != "PIECEWISE_CONSTANT":
            raise NotImplementedError("Only PIECEWISE_CONSTANT IFR gradient is implemented.")
        
        to_dt = Date(to_date)
        if not (to_dt >= self.valueDate_):
            raise AssertionError("time must be >= value date")
        
        dc = comp.targetIndex_.dayCounter()
        tau = float(dc.yearFraction(self.valueDate_, to_dt))
        # tau = accrued(start_dt=self.valueDate_, end_date=to_dt)
        df = float(self.discountFactor(index=index, to_date=to_dt))
        pillar_times = np.asarray(comp.pillarsTimeToDate, dtype=float)

        if pillar_times.size:
            starts   = np.concatenate(([0.0], pillar_times[:-1]))
            ends     = pillar_times
            overlap  = np.maximum(0.0, np.minimum(tau, ends) - starts)
            grad_vec = (-df) * overlap
        else:
            grad_vec = np.zeros(0, dtype=float)
        
        grad = self.gradient_ if gradient is None else gradient
        block = self._target_slice(comp.target)
        if accumulate:
            grad[block] += float(scaler) * grad_vec
        else:
            grad[block] = float(scaler) * grad_vec
    
    def forwardRateGradientWrtModelParameters(
        self,
        index: str,
        start_time: Union[str, Date],
        end_time: Union[str, Date],
        gradient: Optional[np.ndarray] = None,
        scaler: float = 1.0,
        accumulate: bool = False,
    ) -> None:
        
        comp = self.retrieveComponent(index)
        if comp is None:
            raise KeyError(f"Unknown component '{index}'")

        if comp.interpolationMethod_.upper() != "PIECEWISE_CONSTANT":
            raise NotImplementedError("Only PIECEWISE_CONSTANT IFR gradient is implemented.")
        
        start = Date(start_time)
        end = Date(end_time)
        if not (end >= start >= self.valueDate_):
            raise AssertionError("start_time/end_time out of order or before value date.") 
        
        start_dt = Date(start)
        end_dt   = Date(end)

        if comp.isOvernightIndex_:
            accrual = float(comp.targetIndex_.dayCounter().yearFraction(start_dt, end_dt))
        else:
            accrual = float(comp.targetIndex_.dayCounter().yearFraction(start_dt, end_dt))

        if accrual <= 0.0:
            raise ValueError(f"Non-positive accrual in forward gradient: {accrual}")
        pillar_times = np.asarray(comp.pillarsTimeToDate, dtype=float)

        grad = self.gradient_ if gradient is None else gradient
        block = self._target_slice(comp.target)
        
        if accrual <= 0.0 or pillar_times.size == 0:
            if accumulate:
                return
            else:
                grad[block] = 0.0
                return

        df_S = float(self.discountFactor(index, start))
        df_E = float(self.discountFactor(index, end))

        starts = np.concatenate(([0.0], pillar_times[:-1]))
        ends = pillar_times
        dc = comp.targetIndex_.dayCounter()
        tau_S = float(dc.yearFraction(self.valueDate_, start_dt))
        tau_E = float(dc.yearFraction(self.valueDate_, end_dt))
        overlap_S = np.maximum(0.0, np.minimum(tau_S, ends) - starts)
        overlap_E = np.maximum(0.0, np.minimum(tau_E, ends) - starts)
        g_S = (-df_S) * overlap_S
        g_E = (-df_E) * overlap_E

        dF = ((g_S / df_E) - (df_S * g_E) / (df_E * df_E)) / accrual

        if accumulate:
            grad[block] += float(scaler) * dF
        else:
            grad[block] = float(scaler) * dF

    def jacobian(self):
        registry = ValuationEngineRegistry()

        components: List[ModelComponent] = self._components_in_order()
        n = sum(len(getattr(comp, "nodes", [])) for comp in components)
        J = np.zeros((n, n), dtype=float)

        self._jacobian_row_labels = []
        r = 0

        for comp in components:
            vp = {"FUNDING INDEX": comp.target}
            for node in getattr(comp, "nodes", []):
                prod = node.instrument
                ve = registry.new_valuation_engine(self, vp, prod)

                # This fills model.gradient_ with ∂PV_i/∂θ_k for this instrument
                ve.calculateFirstOrderRisk(gradient=None, scaler=1.0, accumulate=False)
                J[r, :] = self.getGradientArray()

                node_id = getattr(node, "node_id", str(getattr(node, "pillar_date", "")))
                self._jacobian_row_labels.append(node_id)
                r += 1

        J[np.abs(J) < 1e-12] = 0.0
        return J
    
    def calibration_quote_sensitivity(self) -> np.ndarray:
        registry = ValuationEngineRegistry()
        components: List[ModelComponent] = self._components_in_order()
        n = sum(len(getattr(comp, "nodes", [])) for comp in components)
        S = np.ones(n, dtype=float)

        r = 0
        for comp in components:
            vp = {"FUNDING INDEX": comp.target}
            for node in getattr(comp, "nodes", []):
                prod = node.instrument
                prod_type = getattr(prod, "prodType", "")

                if prod_type == "ProductRfrFuture":
                    df = float(self.discountFactor(comp.target, prod.maturityDate))
                    N  = float(prod.notional)
                    S[r] = -N * df

                elif prod_type == "ProductOvernightSwap":
                    ve_cal = registry.new_valuation_engine(self, vp, prod)
                    ve_cal.calculateValue()
                    ann = float(ve_cal.annuity())
                    N   = float(prod.notional)
                    S[r] = N * ann

                else:
                    S[r] = 1.0

                r += 1
        return S


class YieldCurveModelComponent(ModelComponent):

    def __init__(self, valueDate: Date, dataCollection: DataCollection, buildMethod: dict, parent_model=None) -> None:
        super().__init__(valueDate, dataCollection, buildMethod)
        self._model = parent_model
        self.interpolationMethod_ = self.buildMethod_.get('INTERPOLATION METHOD', 'PIECEWISE_CONSTANT')
        self.pillarDates: List[Date] = []
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
        calibration_instruments = build_yc_calibration_basket_from_dc(
            value_date=self.valueDate_,
            data_collection=self.dataCollection,
            build_method=self.buildMethod_,
        )

        dc = self.targetIndex_.dayCounter()
        anchors, times, pillar_instruments = build_anchor_pillars(list(calibration_instruments),self.valueDate_, dc)
        self.pillarDates = anchors
        self.pillarsTimeToDate = times

        # Initial IFR guess
        theta = np.full(len(times), DEFAULT_IFR_GUESS, dtype=float)
        self.stateVars_ = list(theta)
        self.ifrInterpolator = Interpolator1D(self.pillarsTimeToDate, self.stateVars_, self.interpolationMethod_)

        # Build pillar nodes (ID + index + dates + product)
        self.nodes : List[PillarNode] = []
        for k, item in enumerate(pillar_instruments):
            product = item.product
            product_type = product.prodType
            pillar_date = anchors[k]
            pillar_time = float(times[k])
            data_type = item.data_type
            data_convention = item.data_convention


            if "FUTURE" in product_type.upper():
                start_date, end_date = product.effectiveDate, product.maturityDate
                axis = f"{start_date} x {end_date}"
            else:
                start_date, end_date = None , pillar_date
                axis = end_date
            node_id = data_type + f" " + data_convention + f" " + str(axis) 
            self.nodes.append(PillarNode(node_id = node_id, 
                                         pillar_index= k, 
                                         pillar_time= pillar_time, 
                                         pillar_date= pillar_date, 
                                         start_date = start_date, 
                                         end_date= end_date, 
                                         instrument = product,
                                         state_value=float(theta[k])))
                        
        def _install_theta(theta_vec):
            self.stateVars_ = list(map(float, theta_vec))
            self.ifrInterpolator = Interpolator1D(self.pillarsTimeToDate, self.stateVars_, self.interpolationMethod_)

        valuation_params = {"FUNDING INDEX" : self.target_}
        registry = ValuationEngineRegistry()
        root_tolerance = float(self.buildMethod_.get("LOCAL_TOL", 1e-12))

        _install_theta(theta)

        for node in self.nodes:
            product = node.instrument
            engine = registry.new_valuation_engine(self._model, valuation_params, product)
            pillar_idx = node.pillar_index

            def residual_for_bucket(theta_k: float) -> float:
                theta_trial = theta.copy()
                theta_trial[pillar_idx] = float(theta_k)
                _install_theta(theta_trial)
                engine.calculateValue()
                currency, value = engine.value_
                return float(value)
            
            theta_guess0 = float(theta[pillar_idx])
            theta_guess1 = theta_guess0 * 1.0001 + (0.0001 if theta_guess0 == 0.0 else 0.0)
            theta_star = simple_solver(
                    residual_fn=residual_for_bucket,
                    x_prev=theta_guess0,
                    x_curr=theta_guess1,
                    tolerance=root_tolerance)
            
            theta[pillar_idx] = theta_star
            _install_theta(theta)
            node.state_value = float(theta[pillar_idx])
            
        self.stateVars_ = list(theta)
        self.ifrInterpolator = Interpolator1D(self.pillarsTimeToDate, self.stateVars_, self.interpolationMethod_)

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
    
    @property
    def state_variables(self) -> List[float]:
        return [float(x) for x in self.stateVars_]

    @property
    def pillar_times_to_date(self) -> List[float]:
        return [float(t) for t in self.pillarsTimeToDate]

    @property
    def pillar_dates(self) -> List[Date]:
        """Anchor associated with the pillars."""
        return list(self.pillarDates)

    @property
    def pillar_nodes(self) -> List[PillarNode]:
        return list(self.nodes)
    
    def perturbModelParameter(self, state_var_index: int, perturb_size: float) -> None:
        super().perturbModelParameter(state_var_index, perturb_size)
        self.ifrInterpolator = Interpolator1D(self.pillarsTimeToDate, self.stateVars_, self.interpolationMethod_)
        self.nodes[state_var_index].state_value = float(self.stateVars_[state_var_index])