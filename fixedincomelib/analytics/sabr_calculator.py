import pandas as pd
import numpy as np
from pysabr import Hagan2002LognormalSABR
from fixedincomelib.sabr import SabrModel
from fixedincomelib.analytics.sabr_top_down      import TimeDecayLognormalSABR
from fixedincomelib.analytics.sabr_bottom_up     import BottomUpLognormalSABR
from fixedincomelib.analytics.correlation_surface import CorrSurface
from typing import Optional
from fixedincomelib.data import DataCollection, Data2D

class SABRCalculator:

    def __init__(self, sabr_model: SabrModel, method: str = "bottom-up", corr_surf: Optional[CorrSurface] = None, product_type: Optional[str] | None = None, product=None):
        self.model = sabr_model
        self.method = method.lower() if method is not None else None
        self.product_type = product_type
        self.product = product

        if self.method == "bottom-up" and corr_surf is None:
            # we expect a Data2D registered under ("corr", index)
            md = self.model.dataCollection.get("corr", self.product.index)
            assert isinstance(md, Data2D)
            corr_surf = CorrSurface.from_data2d(md)

        self.corr_surf = corr_surf

    def option_price(self, index: str, expiry: float, tenor: float, forward: float, strike: float, option_type: str) -> float:
        normal_vol, beta, nu, rho, shift, decay = self.model.get_sabr_parameters(index, expiry, tenor, product_type=self.product_type)

        if self.method == "top-down":
            sabr_pricer = TimeDecayLognormalSABR(
                f            = forward + shift,
                shift        = shift,
                t            = expiry + tenor,
                vAtmN        = normal_vol,
                beta         = beta,
                rho          = rho,
                volVol       = nu,
                volDecaySpeed= decay,
                decayStart   = expiry
            )
        elif self.method == "bottom-up":
            if self.corr_surf is None:
                raise ValueError("corr_df must be provided for bottom-up method")
            sabr_pricer = BottomUpLognormalSABR(
                f        = forward + shift,
                shift    = shift,
                expiry   = expiry,
                tenor    = tenor,
                model    = self.model,
                corr_surf= self.corr_surf,
                product  = self.product
            )
        else:
            # default to plain Hagan log-normal SABR
            sabr_pricer = Hagan2002LognormalSABR(
                f       = forward + shift,
                shift   = shift,
                t       = expiry,
                v_atm_n = normal_vol,
                beta    = beta,
                rho     = rho,
                volvol  = nu,
            )

        k_shifted = strike + shift
        
        if option_type.upper() == "CAP":
            if hasattr(sabr_pricer, "callPrice"):
                raw_price = sabr_pricer.callPrice(k_shifted)
            elif hasattr(sabr_pricer, "call"):
                raw_price = sabr_pricer.call(k_shifted, cp='call')
            else:
                raise AttributeError(f"No compatible call‐price method on pricer {type(sabr_pricer)}")
        else:
            if hasattr(sabr_pricer, "putPrice"):
                raw_price = sabr_pricer.putPrice(k_shifted)
            elif hasattr(sabr_pricer, "call"):
                raw_price = sabr_pricer.call(k_shifted, cp='put')
            else:
                raise AttributeError(f"No compatible put‐price method on pricer {type(sabr_pricer)}")
        
        return raw_price
