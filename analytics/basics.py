import numpy as np
from pysabr.black import (
    normal_call,
    shifted_lognormal_call,
    normal_to_shifted_lognormal,
    shifted_lognormal_to_normal,
)

def one_third_rule(v_atm_n: float,
                   accrualStart: float,
                   accrualEnd: float) -> float:
    
    length = accrualEnd - accrualStart

    return v_atm_n * np.sqrt((accrualEnd - length + (length)/3)/accrualEnd)