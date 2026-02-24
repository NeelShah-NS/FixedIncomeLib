from typing import Iterable, List, Tuple, Optional, Union
import numpy as np

BottomUp = Iterable[Tuple[float, float, float]]  # (seg_expiry, seg_tenor, dSigma_i)

def accumulate_surface_pillar_risk(
    *,
    model,
    gradient: np.ndarray,
    index: str,
    parameter: str,
    expiry_t: float,
    tenor_t: float,
    pvScale: float,
    dPrice_dVol: float,
    dSigma_dP: Union[float, BottomUp],
    product_type_for_scalar: Optional[str] = None,
) -> None:
    if isinstance(dSigma_dP, (list, tuple)):
        for seg_expiry, seg_tenor, dSigma_i in dSigma_dP:
            dPV_i = float(pvScale) * float(dPrice_dVol) * float(dSigma_i)
            nodes = model.sabr_global_node_indices_and_weights(
                index=index,
                parameter=parameter,
                expiry=float(seg_expiry),
                tenor=float(seg_tenor),
                product_type=None,
            )
            for gi, w in nodes:
                gradient[int(gi)] += dPV_i * float(w)
    else:
        dPV = float(pvScale) * float(dPrice_dVol) * float(dSigma_dP)
        nodes = model.sabr_global_node_indices_and_weights(
            index=index,
            parameter=parameter,
            expiry=float(expiry_t),
            tenor=float(tenor_t),
            product_type=product_type_for_scalar,
        )
        for gi, w in nodes:
            gradient[int(gi)] += dPV * float(w)
