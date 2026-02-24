from typing import Any, Dict, List, Tuple
import numpy as np
from fixedincomelib.model.model import Model, ModelComponent
from fixedincomelib.date import Date
from fixedincomelib.utilities.numerics import Interpolator2D
from fixedincomelib.yield_curve import YieldCurve
from fixedincomelib.data import DataCollection, Data2D
from fixedincomelib.data import build_yc_data_collection

class SabrModel(Model):
    MODEL_TYPE = "IR_SABR"
    PARAMETERS = ["NORMALVOL", "BETA", "NU", "RHO"]
    
    def __init__(
        self,
        valueDate: str,
        dataCollection: DataCollection,
        buildMethodCollection: List[Dict[str, Any]],
        ycModel: YieldCurve,
    ):
        for bm in buildMethodCollection:
            tgt  = bm["TARGET"]
            vals = bm["VALUES"]
            prod = bm.get("PRODUCT")
            bm["NAME"] = f"{tgt}-{vals}" + (f"-{prod}" if prod else "")

        super().__init__(valueDate, self.MODEL_TYPE, dataCollection, buildMethodCollection)
        self.subModel_ = ycModel

        # Cache YC param count (avoid computing YC jacobian inside weights mapping)
        self._n_yc_params = int(np.asarray(self.subModel_.getGradientArray()).size)
        self._build_sabr_layout()

        n_total = int(self._n_yc_params + self._num_sabr_pillars)
        self.gradient_ = np.zeros(n_total, dtype=float)

        self._build_gradient_labels()

    @classmethod
    def from_curve(
        cls,
        valueDate: str,
        dataCollection: DataCollection,
        buildMethodCollection: List[Dict[str, Any]],
        ycModel: YieldCurve
    ) -> "SabrModel":
        return cls(valueDate, dataCollection, buildMethodCollection, ycModel)

    @classmethod
    def from_data(
        cls,
        valueDate: str,
        dataCollection: DataCollection,                 # SABR surfaces (Data2D)
        buildMethodCollection: List[Dict[str, Any]],     # SABR build methods
        yc_market_df,                                   # calibration instrument quotes
        ycBuildMethods: List[Dict[str, Any]]
    ) -> "SabrModel":
        
        _, yc_dc = build_yc_data_collection(yc_market_df)
        yc = YieldCurve(valueDate, yc_dc, ycBuildMethods)
        return cls(valueDate, dataCollection, buildMethodCollection, yc)

    def newModelComponent(self, build_method: Dict[str, Any]) -> ModelComponent:
        return SabrModelComponent(self.valueDate, self.dataCollection, build_method)

    def get_sabr_parameters(
        self,
        index: str,
        expiry: float,
        tenor: float,
        product_type: str | None = None
    ) -> Tuple[float, float, float, float, float, float]:
        suffix = f"-{product_type}".upper() if product_type else ""
        params = []
        for p in self.PARAMETERS:
            key = f"{index}-{p}{suffix}".upper()
            comp = self.components.get(key)
            if comp is None:
                raise KeyError(f"No SABR component found for {key}")
            params.append(comp.interpolate(expiry, tenor))
        nv_key = f"{index}-NORMALVOL{suffix}".upper()
        nv_comp = self.components[nv_key]
        return (*params, nv_comp.shift, nv_comp.vol_decay_speed)
    
    # Layout for SABR pillars
    def _build_sabr_layout(self) -> None:
        """
        Defines the ordering of SABR pillar parameters within the SABR block.
        """
        self._sabr_slice_by_key: Dict[str, slice] = {}
        offset = 0
        for key, comp in self.components.items():  # insertion-ordered dict
            n = int(len(getattr(comp, "stateVars_", [])))
            if n == 0:
                # fallback if stateVars_ isn't set (should not happen if component is implemented properly)
                n = int(np.asarray(getattr(comp, "grid")).size)
            self._sabr_slice_by_key[key] = slice(offset, offset + n)
            offset += n
        self._num_sabr_pillars = int(offset)

    def num_sabr_pillars(self) -> int:
        return int(self._num_sabr_pillars)

    def sabr_component_key(self, index: str, parameter: str, product_type: str | None = None) -> str:
        suffix = f"-{product_type}".upper() if product_type else ""
        return f"{index}-{parameter}{suffix}".upper()

    def sabr_global_node_indices_and_weights(
        self,
        index: str,
        parameter: str,
        expiry: float,
        tenor: float,
        product_type: str | None = None,
    ) -> List[Tuple[int, float]]:
        """
        For a given SABR surface (index + parameter + optional product_type),
        return the *global model parameter indices* and interpolation weights
        for the 4 pillars used at (expiry, tenor).

        Global model parameter ordering:
            [YC params] + [SABR params]
        """
        key = self.sabr_component_key(index, parameter, product_type)
        comp = self.components.get(key)
        if comp is None:
            raise KeyError(f"No SABR component found for {key}")

        # local weights inside the component: (flat_idx, w)
        local = comp.weights(expiry, tenor)

        # global offset = YC param count + SABR component slice start
        n_yc = int(self._n_yc_params)

        sl = self._sabr_slice_by_key[key]
        base = int(sl.start)

        return [(n_yc + base + int(flat_idx), float(w)) for flat_idx, w in local]
    
    def jacobian(self) -> np.ndarray:
        """
            J = [[ J_yc, 0 ],
                 [  0 ,  I ]]

        - J_yc: yield curve calibration Jacobian
        - I: identity for SABR pillars (no SABR calibration in-code)
        """
        J_yc = np.asarray(self.subModel_.jacobian(), dtype=float)
        if J_yc.ndim != 2 or J_yc.shape[0] != J_yc.shape[1]:
            raise ValueError(f"YieldCurve jacobian must be square, got shape {J_yc.shape}")

        n = int(J_yc.shape[0])
        m = int(self.num_sabr_pillars())

        J = np.zeros((n + m, n + m), dtype=float)
        J[:n, :n] = J_yc
        if m > 0:
            J[n:, n:] = np.eye(m, dtype=float)
        return J

    def calibration_quote_sensitivity(self) -> np.ndarray:
        """
        Quote sensitivity scaling used by risk_reporting.py:
            quote_risk = S * param_risk

        - YC part uses YieldCurve.calibration_quote_sensitivity()
        - SABR pillars: quote == parameter => sensitivity = 1 for each pillar
        """
        S_yc = np.asarray(self.subModel_.calibration_quote_sensitivity(), dtype=float)
        m = int(self.num_sabr_pillars())
        if m == 0:
            return S_yc
        return np.concatenate([S_yc, np.ones(m, dtype=float)])
    
    #Gradient
    def clearGradient(self) -> None:
        self.gradient_[:] = 0.0

    def getGradientArray(self) -> np.ndarray:
        return np.asarray(self.gradient_, dtype=float).copy()

    def _build_gradient_labels(self) -> None:
        labels: List[str] = []

        # YC labels (YieldCurve uses block labels; expand them into per-parameter labels)
        yc_labels  = getattr(self.subModel_, "gradient_labels_", None)
        yc_offsets = getattr(self.subModel_, "gradient_offsets_", None)

        if yc_labels is not None and yc_offsets is not None and len(yc_offsets) == len(yc_labels) + 1:
            for i, lab in enumerate(list(yc_labels)):
                n = int(yc_offsets[i + 1] - yc_offsets[i])
                labels.extend([f"{lab}[{k}]" for k in range(n)])
        else:
            # fallback: generic per-parameter labels
            labels.extend([f"YC[{i}]" for i in range(int(self._n_yc_params))])

        # SABR pillar labels
        for key, sl in self._sabr_slice_by_key.items():
            n = int(sl.stop - sl.start)
            labels.extend([f"{key}[{k}]" for k in range(n)])

        self.gradient_labels_ = labels
    
    @property
    def subModel(self):
        return self.subModel_
    
class SabrModelComponent(ModelComponent):

    def __init__(
        self,
        valueDate: Date,
        dataCollection: DataCollection,
        buildMethod: Dict[str, Any]
    ) -> None:
        
        super().__init__(valueDate, dataCollection, buildMethod)
        self.shift           = float(buildMethod.get("SHIFT", 0.0))
        self.vol_decay_speed = float(buildMethod.get("VOL_DECAY_SPEED", 0.0))
        self.product_type    = buildMethod.get("PRODUCT")

        self.axis1: np.ndarray
        self.axis2: np.ndarray
        self.grid: np.ndarray
        self._shape: Tuple[int, int]

        self._interp2d: Interpolator2D

        self.calibrate()

    def calibrate(self) -> None:

        param = self.buildMethod_["VALUES"]  

        md = self.dataCollection.get(param.lower(), self.target_)
        assert isinstance(md, Data2D)

        self.axis1 = np.array(md.axis1, dtype=float)  
        self.axis2 = np.array(md.axis2, dtype=float)   
        self.grid = np.array(md.values, dtype=float)

        if len(self.axis1) >= 2 and np.any(np.diff(self.axis1) < 0.0):
            raise ValueError(f"{self.target_}: axis1 must be sorted ascending for interpolation/risk. "f"Got axis1={self.axis1}")

        if len(self.axis2) >= 2 and np.any(np.diff(self.axis2) < 0.0):
            raise ValueError(f"{self.target_}: axis2 must be sorted ascending for interpolation/risk. "f"Got axis2={self.axis2}")

        if self.grid.shape != (len(self.axis1), len(self.axis2)):
            raise ValueError(f"{self.target_}: grid shape {self.grid.shape} "f"!= ({len(self.axis1)}, {len(self.axis2)})")

        self._shape = self.grid.shape  

        # Make grid nodes the internal parameter vector (row-major flatten)
        self.stateVars_ = self.grid.reshape(-1).astype(float).tolist()                      

        method = str(self.buildMethod_.get("INTERPOLATION", "LINEAR")).upper()
        if method != "LINEAR":
            raise ValueError(f"{self.target_}: only LINEAR interpolation supported for risk, got {method}")
        self._interp2d = Interpolator2D(
            axis1=self.axis1,
            axis2=self.axis2,
            values=self.grid,
            method=method
        )

    def interpolate(self, expiry: float, tenor: float) -> float:
        return self._interp2d.interpolate(expiry, tenor)
    
    def _flat_index(self, i: int, j: int) -> int:
        return int(i) * int(len(self.axis2)) + int(j)

    def weights(self, expiry: float, tenor: float):
        corners = self._interp2d.weights(float(expiry), float(tenor))
        n2 = len(self.axis2)
        return [(int(i) * int(n2) + int(j), float(w)) for (i, j), w in corners]
    
    def _sync_from_statevars(self) -> None:
        self.grid = np.asarray(self.stateVars_, dtype=float).reshape(self._shape)
        self._interp2d = Interpolator2D(
            axis1=self.axis1,
            axis2=self.axis2,
            values=self.grid,
            method="LINEAR"
        )

    def perturbModelParameter(self, state_var_index: int, perturb_size: float) -> None:
        super().perturbModelParameter(state_var_index, perturb_size)
        self._sync_from_statevars()
