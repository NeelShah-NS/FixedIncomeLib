import math
from typing import Any, Dict, List, Tuple
import numpy as np
import pandas as pd
from model.model import Model, ModelComponent
from date import Date
from utilities.numerics import Interpolator2D
from yield_curve import YieldCurve

class SabrModel(Model):
    MODEL_TYPE = "IR_SABR"
    PARAMETERS = ["NORMALVOL", "BETA", "NU", "RHO"]

    def __init__(
        self,
        valueDate: str,
        dataCollection: pd.DataFrame,
        buildMethodCollection: List[Dict[str, Any]],
        ycModel: YieldCurve,
    ):
        cols = set(dataCollection.columns)
        for req in ("INDEX", "AXIS1", "AXIS2", *self.PARAMETERS):
            assert req in cols, f"SABR data must include '{req}'"

        for bm in buildMethodCollection:
            tgt  = bm["TARGET"]
            vals = bm["VALUES"]
            prod = bm.get("PRODUCT")
            bm["NAME"] = f"{tgt}-{vals}" + (f"-{prod}" if prod else "")

        super().__init__(valueDate, self.MODEL_TYPE, dataCollection, buildMethodCollection)
        self._subModel = ycModel

    @classmethod
    def from_curve(
        cls,
        valueDate: str,
        dataCollection: pd.DataFrame,
        buildMethodCollection: List[Dict[str, Any]],
        ycModel: YieldCurve
    ) -> "SabrModel":
        return cls(valueDate, dataCollection, buildMethodCollection, ycModel)

    @classmethod
    def from_data(
        cls,
        valueDate: str,
        dataCollection: pd.DataFrame,
        buildMethodCollection: List[Dict[str, Any]],
        ycData: pd.DataFrame,
        ycBuildMethods: List[Dict[str, Any]]
    ) -> "SabrModel":
        yc = YieldCurve(valueDate, ycData, ycBuildMethods)
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

    @property
    def subModel(self):
        return self._subModel


class SabrModelComponent(ModelComponent):

    def __init__(
        self,
        valueDate: Date,
        dataCollection: pd.DataFrame,
        buildMethod: Dict[str, Any]
    ) -> None:
        super().__init__(valueDate, dataCollection, buildMethod)
        self.shift           = float(buildMethod.get("SHIFT", 0.0))
        self.vol_decay_speed = float(buildMethod.get("VOL_DECAY_SPEED", 0.0))
        self.product_type    = buildMethod.get("PRODUCT")
        self.calibrate()

    def calibrate(self) -> None:
        df = self.dataCollection_[
            self.dataCollection_["INDEX"] == self.target_
        ]
        prod = self.buildMethod_.get("PRODUCT")
        if prod:
            df = df[df["PRODUCT"].str.upper() == prod.upper()]

        if df.empty:
            raise ValueError(f"No data for SABR {self.target_} / {prod or 'ANY'}")

        x = df[self.buildMethod_["AXIS1"]].astype(float).values
        y = df[self.buildMethod_["AXIS2"]].astype(float).values
        ux, uy = np.unique(x), np.unique(y)

        mat = (
            df
            .pivot_table(
                index=self.buildMethod_["AXIS1"],
                columns=self.buildMethod_["AXIS2"],
                values=self.buildMethod_["VALUES"]
            )
            .loc[ux, uy]
            .values
        )

        self.axis1 = ux
        self.axis2 = uy
        self.grid  = mat
        self._interp2d = Interpolator2D(
            axis1=ux,
            axis2=uy,
            values=mat,
            method=self.buildMethod_.get("INTERPOLATION", "LINEAR")
        )

    def interpolate(self, expiry: float, tenor: float) -> float:
        return self._interp2d.interpolate(expiry, tenor)