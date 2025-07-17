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
        columns = set(dataCollection.columns.to_list())
        assert 'INDEX' in columns 
        assert 'AXIS1' in columns 
        assert 'AXIS2' in columns
        for p in self.PARAMETERS:
            assert p in columns, f"SABR data must include '{p}'"
        super().__init__(valueDate, self.MODEL_TYPE, dataCollection, buildMethodCollection)
        self._subModel = ycModel
        
    @classmethod
    def from_curve(
        cls,
        valueDate: str,
        dataCollection: pd.DataFrame,
        buildMethodCollection: List[Dict[str, Any]],
        ycModel: YieldCurve) -> "SabrModel":
        return cls(valueDate, dataCollection, buildMethodCollection, ycModel)

    @classmethod
    def from_data(
        cls,
        valueDate: str,
        dataCollection: pd.DataFrame,
        buildMethodCollection: List[Dict[str, Any]],
        ycData: pd.DataFrame,
        ycBuildMethods: List[Dict[str, Any]]) -> "SabrModel":
        yc = YieldCurve(valueDate, ycData, ycBuildMethods)
        return cls(valueDate, dataCollection, buildMethodCollection, yc)

    def newModelComponent(self, build_method: Dict[str, Any]) -> ModelComponent:
        return SabrModelComponent(self.valueDate, self.dataCollection, build_method)

    def get_sabr_parameters(
        self,
        index: str,
        expiry: float,
        tenor: float,
    ) -> Tuple[float, float, float, float, float, float]:

        params: List[float] = []
        for p in self.PARAMETERS:
            comp_key = f"{index}-{p}".upper()
            comp = self.components.get(comp_key)
            if comp is None:
                raise KeyError(f"No SABR component found for {index} / {p}")
            params.append(comp.interpolate(expiry, tenor))
    
        comp0 = self.components[f"{index}-NORMALVOL".upper()]
        shift = comp0.shift
        decay = comp0.vol_decay_speed

        return (*params, shift, decay)
    
    @property
    def subModel(self):
        return self._subModel

class SabrModelComponent(ModelComponent):

    def __init__(self, valueDate: Date, dataCollection: pd.DataFrame, buildMethod: Dict[str, Any]) -> None:
        super().__init__(valueDate, dataCollection, buildMethod)
        self.shift           = float(buildMethod.get("SHIFT", 0.0))
        self.vol_decay_speed = float(buildMethod.get("VOL_DECAY_SPEED", 0.0))
        self.calibrate()

    def calibrate(self) -> None:
        df = self.dataCollection_[self.dataCollection_["INDEX"] == self.target_]
        if df.empty:
            raise ValueError(f"No data for SABR target {self.target_}")

        x = df[self.buildMethod_["AXIS1"]].astype(float).values
        y = df[self.buildMethod_["AXIS2"]].astype(float).values
        ux = np.unique(x)
        uy = np.unique(y)

        mat = (df.pivot_table(index=self.buildMethod_["AXIS1"], columns=self.buildMethod_["AXIS2"], values=self.buildMethod_["VALUES"]).loc[ux, uy].values)

        self._interp2d = Interpolator2D(
            axis1=ux,
            axis2=uy,
            values=mat,
            method=self.buildMethod_.get("INTERPOLATION", "LINEAR")
        )

    def interpolate(self, expiry: float, tenor: float) -> float:

        return self._interp2d.interpolate(expiry, tenor)