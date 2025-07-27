import math
from typing import Any, Dict, List, Tuple
import numpy as np
import pandas as pd
from model.model import Model, ModelComponent
from date import Date
from utilities.numerics import Interpolator2D
from yield_curve import YieldCurve
from data import DataCollection, Data2D

class SabrModel(Model):
    MODEL_TYPE = "IR_SABR"
    PARAMETERS = ["NORMALVOL", "BETA", "NU", "RHO"]

    def __init__(
        self,
        valueDate: str,
        dataRepository: DataCollection,
        buildMethodCollection: List[Dict[str, Any]],
        ycModel: YieldCurve,
    ):
        for bm in buildMethodCollection:
            bm["DATA_TYPE"]       = bm["DATA_TYPE"].upper()
            bm["DATA_CONVENTION"] = bm.get("DATA_CONVENTION", bm["TARGET"]).upper()
            name = f"{bm['TARGET']}-{bm['DATA_TYPE']}"
            if bm.get("PRODUCT"):
                name += f"-{bm['PRODUCT']}"
            bm["NAME"] = name.upper()

        super().__init__(valueDate, self.MODEL_TYPE, dataRepository, buildMethodCollection)
        self._subModel = ycModel

    @classmethod
    def from_curve(
        cls,
        valueDate: str,
        dataRepository: DataCollection,
        buildMethodCollection: List[Dict[str, Any]],
        ycModel: YieldCurve
    ) -> "SabrModel":
        return cls(valueDate, dataRepository, buildMethodCollection, ycModel)

    @classmethod
    def from_data(
        cls,
        valueDate: str,
        dataRepository: DataCollection,
        buildMethodCollection: List[Dict[str, Any]],
        ycData: DataCollection,
        ycBuildMethods: List[Dict[str, Any]]
    ) -> "SabrModel":
        for ym in ycBuildMethods:
            target = ym["TARGET"]
            method = ym.get("INTERPOLATION_METHOD", "PIECEWISE_CONSTANT")
            dataRepository.register_zero_rate_for_target(
                df         = ycData,
                value_date = valueDate,
                target     = target,
                method     = method
            )

        yc = YieldCurve(valueDate, dataRepository, ycBuildMethods)
        return cls(valueDate, dataRepository, buildMethodCollection, yc)

    def newModelComponent(self, build_method: Dict[str, Any]) -> ModelComponent:
        surface2d: Data2D = self.dataRepo.get(
            build_method["DATA_TYPE"],
            build_method["DATA_CONVENTION"]
        )
        return SabrModelComponent(self.valueDate, surface2d, build_method)
    
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

    @property
    def subModel(self):
        return self._subModel


class SabrModelComponent(ModelComponent):

    def __init__(
        self,
        valueDate: Date,
        surface2d: Data2D,
        buildMethod: Dict[str, Any]
    ) -> None:
        super().__init__(valueDate, None, {"TARGET": buildMethod["TARGET"]})
        self.shift           = float(buildMethod.get("SHIFT", 0.0))
        self.vol_decay_speed = float(buildMethod.get("VOL_DECAY_SPEED", 0.0))
        self.surface2d       = surface2d
        self._interp2d       = surface2d._interp2d

    def calibrate(self) -> None:
        # no‐op: Data2D has already built the grid and interpolator
        pass

    def interpolate(self, expiry: float, tenor: float) -> float:
        return self._interp2d.interpolate(expiry, tenor)