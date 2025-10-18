from typing import Callable

def simple_solver(
    residual_fn: Callable[[float], float],
    x_prev: float,
    x_curr: float,
    tolerance: float = 1e-12,
    max_iter: int = 50,
) -> float:

    f_prev = float(residual_fn(x_prev))
    f_curr = float(residual_fn(x_curr))

    for iteration in range(max_iter):
        slope_est = (f_curr - f_prev)
        if slope_est == 0.0:
            slope_est = 1e-18  
        x_next = x_curr - f_curr * (x_curr - x_prev) / slope_est

        if abs(x_next - x_curr) <= tolerance * (1.0 + abs(x_curr)):
            return float(x_next)

        x_prev, f_prev = x_curr, f_curr
        x_curr, f_curr = x_next, float(residual_fn(x_next))

    return float(x_curr)
