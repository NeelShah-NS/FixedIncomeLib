import numpy as np
import pandas as pd
from utilities.numerics import Interpolator2D

class CorrSurface:
    def __init__(self, df: pd.DataFrame, method="LINEAR"):
        self.raw_df = df
        ux, uy = np.sort(df["EXPIRY"].unique()), np.sort(df["TENOR"].unique())
        mat = (
          df.pivot_table(index="EXPIRY", columns="TENOR", values="CORR")
            .loc[ux, uy]
            .values
        )
        self._interp = Interpolator2D(axis1=ux, axis2=uy, values=mat, method=method)

    def get_corr(self, expiry: float, tenor: float) -> float:
        return self._interp.interpolate(expiry, tenor)