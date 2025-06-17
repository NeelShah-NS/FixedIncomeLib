import numpy as np
from pysabr.black import (
    normal_call,
    shifted_lognormal_call,
    normal_to_shifted_lognormal,
    shifted_lognormal_to_normal,
)

def one_third_rule(v_atm_n: float,
                   tau0: float,
                   tau1: float) -> float:

    return v_atm_n * np.sqrt((tau1 + tau0/3) / tau1)