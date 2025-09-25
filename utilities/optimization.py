import numpy as np

def _finite_difference_jacobian(residuals_fn, param_vector, fd_step):
    base_residuals = residuals_fn(param_vector)  # r(theta)
    m, n = base_residuals.size, param_vector.size
    J = np.empty((m, n), dtype=float)

    for col_idx in range(n):
        perturbed = param_vector.copy()
        perturbed[col_idx] += fd_step
        J[:, col_idx] = (residuals_fn(perturbed) - base_residuals) / fd_step

    return J


def gauss_newton(
    residuals_fn,
    initial_params,
    max_iterations=25,
    lower_bound=-0.05,
    upper_bound=0.15,
    tolerance=1e-10,
    fd_step=1e-6,
    backtrack_trials=8,
):
    theta = np.clip(np.asarray(initial_params, dtype=float), lower_bound, upper_bound)
    residuals = residuals_fn(theta)

    for iteration_idx in range(max_iterations):
        if np.linalg.norm(residuals) < tolerance:
            break

        J = _finite_difference_jacobian(residuals_fn, theta, fd_step)

        # Solve J * step = -residuals (least squares)
        step_direction, ls_residuals, ls_rank, ls_singular_values = np.linalg.lstsq(
            J, -residuals, rcond=None
        )

        current_norm = float(np.linalg.norm(residuals))
        step_size = 1.0
        improved = False

        for trial_idx in range(backtrack_trials):
            candidate = np.clip(theta + step_size * step_direction, lower_bound, upper_bound)
            candidate_residuals = residuals_fn(candidate)
            candidate_norm = float(np.linalg.norm(candidate_residuals))

            if candidate_norm < current_norm:
                theta = candidate
                residuals = candidate_residuals
                improved = True
                break

            step_size *= 0.5

        if not improved:
            break

    return theta, residuals
