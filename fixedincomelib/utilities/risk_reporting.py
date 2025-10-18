from __future__ import annotations
import numpy as np
from fixedincomelib.valuation import ValuationEngineRegistry
np.set_printoptions(suppress=True)
np.set_printoptions(precision=8)  

def createValueReport(valuation_parameters, model, product, request="all"):
    """
    request:
      - "value"            -> returns PV (float)
      - "firstOrderRisk"   -> returns product risk
      - "all"              -> returns dict with {"pv", "param_risk", "quote_risk"(optional)}
    """
    ve = ValuationEngineRegistry().new_valuation_engine(model, valuation_parameters, product)
    if request in ("value", "all"):
        ve.calculateValue()
        _,pv = ve.value_
        if request == "value":
            return float(pv)

    if request in ("firstOrderRisk", "all"):
        """
        Here the risk is per PV unit - not per quote unit
        """
        ve.calculateFirstOrderRisk()
        firstOrderrisk = np.asarray(ve.firstOrderRisk_, dtype=float)
        jacobian = np.asarray(model.jacobian(), dtype=float)
        risk = np.linalg.solve(jacobian.T, firstOrderrisk)
        if request == "firstOrderRisk":
            return risk
        return {"pv": pv, "risk": risk}
    
    raise ValueError("request must be one of: 'value', 'firstOrderRisk', 'all'")
