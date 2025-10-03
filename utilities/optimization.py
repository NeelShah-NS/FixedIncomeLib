from typing import Callable, Tuple
import numpy as np

def newton_1d(
        residual: Callable[[float], float],
        derivative: Callable[[float], float],
        initial_guess: float,
        tol: float = 1e-12,
        max_iter: int = 100,
        min_slope: float = 1e-12,   # << added
    ) -> Tuple[float, int, float]:
    x = float(initial_guess)
    for it in range(1, max_iter + 1):
        r = residual(x)
        if not np.isfinite(r):
            raise RuntimeError("Non-finite residual in Newton step.")
        if abs(r) <= tol:
            return x, it, r
        d = derivative(x)
        if not np.isfinite(d) or abs(d) <= min_slope:
            raise RuntimeError("Near-zero or non-finite slope in Newton step.")
        x = x - r / d
    # return last state if not converged
    r = residual(x)
    return x, max_iter, r
