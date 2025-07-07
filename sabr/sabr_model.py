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
        shift: float = 0.0
    ):
        columns = set(dataCollection.columns.to_list())
        assert 'INDEX' in columns 
        assert 'AXIS1' in columns 
        assert 'AXIS2' in columns
        for p in self.PARAMETERS:
            assert p in columns, f"SABR data must include '{p}'"
        super().__init__(valueDate, self.MODEL_TYPE, dataCollection, buildMethodCollection)
        self.subModel = ycModel
        self.shift = shift
    
    @classmethod
    def from_curve(
        cls,
        valueDate: str,
        dataCollection: pd.DataFrame,
        buildMethodCollection: List[Dict[str, Any]],
        ycModel: YieldCurve,
        shift: float = 0.0 ) -> "SabrModel":
        return cls(valueDate, dataCollection, buildMethodCollection, ycModel, shift)

    @classmethod
    def from_data(
        cls,
        valueDate: str,
        dataCollection: pd.DataFrame,
        buildMethodCollection: List[Dict[str, Any]],
        ycData: pd.DataFrame,
        ycBuildMethods: List[Dict[str, Any]],
        shift: float = 0.0 ) -> "SabrModel":
        yc = YieldCurve(valueDate, ycData, ycBuildMethods)
        return cls(valueDate, dataCollection, buildMethodCollection, yc, shift)

    def newModelComponent(self, build_method: Dict[str, Any]) -> ModelComponent:
        return SabrModelComponent(self.valueDate, self.dataCollection, build_method)

    def get_sabr_parameters(
        self,
        index: str,
        expiry: float,
        tenor: float,
    ) -> Tuple[float, float, float, float]:
        
        params: List[float] = []
        for p in self.PARAMETERS:
            key = f"{index}-{p}"
            this_component = self.retrieveComponent(key)
            if this_component is None:
                raise KeyError(f"Missing SABR component: {key}")
            params.append(this_component.interpolate(expiry, tenor))
        return tuple(params)  # type: ignore

class SabrModelComponent(ModelComponent):
    
    def __init__(self, valueDate: Date, dataCollection: pd.DataFrame, buildMethod: Dict[str, Any]) -> None:
        super().__init__(valueDate, dataCollection, buildMethod)
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