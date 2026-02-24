import numpy as np
from pysabr.models.hagan_2002_lognormal_sabr import Hagan2002LognormalSABR
import QuantLib as ql

class BottomUpLognormalSABR(Hagan2002LognormalSABR):
    def __init__(
        self,
        f: float,
        shift: float,
        expiry: float,
        tenor: float,
        model,
        corr_surf,
        product,
    ):
        self._expiry = float(expiry)
        self._tenor = float(tenor)
        self._model = model
        self._corr = corr_surf
        self._product = product

        if self._expiry <= 0.0:
            raise ValueError(f"[BottomUpLognormalSABR] expiry must be > 0, got {self._expiry}")
        if self._tenor <= 0.0:
            raise ValueError(f"[BottomUpLognormalSABR] tenor must be > 0, got {self._tenor}")

        super().__init__(
            f=float(f),
            shift=float(shift),
            t=self._expiry,
            v_atm_n=0.0,
            beta=0.0,
            rho=0.0,
            volvol=0.0,
        )

        self._computeEffectiveParams()

    def _computeEffectiveParams(self):
        dates = self._product.get_fixing_schedule()
        if dates is None or len(dates) < 2:
            raise ValueError("[BottomUpLognormalSABR] product fixing schedule must have at least 2 dates.")
        
        dc = self._product.dayCounter
        Tis = [float(dc.yearFraction(d0, d1)) for d0, d1 in zip(dates, dates[1:])]
        if any((not np.isfinite(Ti)) for Ti in Tis):
            raise ValueError(f"[BottomUpLognormalSABR] Non-finite accruals in Tis: {Tis}")
        if any(Ti <= 0.0 for Ti in Tis):
            raise ValueError(f"[BottomUpLognormalSABR] All segment accruals Ti must be > 0, got {Tis}")

        total = float(sum(Tis))
        if total <= 0.0:
            raise ValueError(f"[BottomUpLognormalSABR] Sum of segment accruals must be > 0, got {total}")

        weights = [float(Ti / total) for Ti in Tis]

        offsets_start = np.cumsum([0.0] + Tis[:-1])
        Tstarts = [self._expiry + float(x) for x in offsets_start]
        Tends   = [Ts + Ti for Ts, Ti in zip(Tstarts, Tis)]


        if any((not np.isfinite(T)) for T in Tends):
            raise ValueError(f"[BottomUpLognormalSABR] Non-finite segment end times Tends: {Tends}")
        if any(T <= 0.0 for T in Tends):
            raise ValueError(f"[BottomUpLognormalSABR] All segment end times Tend must be > 0, got {Tends}")
        
        if any((not np.isfinite(T)) for T in Tstarts):
            raise ValueError(f"[BottomUpLognormalSABR] Non-finite segment start times Tstarts: {Tstarts}")
        if any(T < 0.0 for T in Tstarts):
            raise ValueError(f"[BottomUpLognormalSABR] All segment start times Tstart must be >= 0, got {Tstarts}")

        use_end_time = (self._product.oisIndex_ is not None)

        Texp = Tends if use_end_time else Tstarts

        if len(Texp) == 1:
            self.t = max(float(Texp[0]), 1e-12)
        else:
            self.t = max(float(self._expiry), 1e-12)

        Tbar = float(sum(w * T for w, T in zip(weights, Texp)))
        if not np.isfinite(Tbar) or Tbar <= 0.0:
            raise ValueError(f"[BottomUpLognormalSABR] Tbar must be finite and > 0, got Tbar={Tbar}")

        time_scales = [float(np.sqrt(T / Tbar)) for T in Texp]
        if any((not np.isfinite(s)) for s in time_scales):
            raise ValueError(f"[BottomUpLognormalSABR] Non-finite time_scales: {time_scales}")

        alphas: list[float] = []
        betas: list[float] = []
        nus: list[float] = []
        rhos: list[float] = []

        for Ti, Tstart, Te in zip(Tis, Tstarts, Texp):
            v_n_i, b_i, nu_i, rho_i, _, _ = self._model.get_sabr_parameters(
                index=self._product.index,
                expiry=float(Te),
                tenor=float(Ti),          
                product_type=None,
            )

            v_n_i = float(v_n_i)
            b_i = float(b_i)
            nu_i = float(nu_i)
            rho_i = float(rho_i)

            if v_n_i < 0.0:
                raise ValueError(f"[BottomUpLognormalSABR] Segment normal vol < 0: {v_n_i} at Tstart={Tstart}, Ti={Ti}")
            if not (0.0 <= b_i <= 1.0):
                raise ValueError(f"[BottomUpLognormalSABR] Segment beta not in [0,1]: {b_i} at Tstart={Tstart}, Ti={Ti}")
            if nu_i < 0.0:
                raise ValueError(f"[BottomUpLognormalSABR] Segment nu < 0: {nu_i} at Tstart={Tstart}, Ti={Ti}")
            if not (-1.0 < rho_i < 1.0):
                raise ValueError(f"[BottomUpLognormalSABR] Segment rho not in (-1,1): {rho_i} at Tstart={Tstart}, Ti={Ti}")

            p = Hagan2002LognormalSABR(
                f=float(self.f),
                shift=float(self.shift),
                t=float(Te),
                v_atm_n=v_n_i,
                beta=b_i,
                rho=rho_i,
                volvol=nu_i,
            )
            a_i = float(p.alpha())
            if not np.isfinite(a_i) or a_i <= 0.0:
                raise ValueError(f"[BottomUpLognormalSABR] Segment alpha <= 0 or non-finite: {a_i} at Tstart={Tstart}, Ti={Ti}")

            alphas.append(a_i)
            betas.append(b_i)
            nus.append(nu_i)
            rhos.append(rho_i)

        # Correlation aggregation
        t_first = float(Texp[0])
        t_last  = float(Texp[-1])
        gamma_1N = float(self._corr.corr(t_first, t_last))

        if not np.isfinite(gamma_1N):
            raise ValueError(f"[BottomUpLognormalSABR] gamma_1N is not finite: {gamma_1N}")
        if not (0.0 <= gamma_1N <= 1.0):
            raise ValueError(f"[BottomUpLognormalSABR] corr(expiry, T_total) must be in [0,1], got {gamma_1N}")

        N = len(Tis)
        if N <= 1:
            gamma_bar = 1.0
        else:
            mu = (1.0 - gamma_1N) / (N - 1)
            if not np.isfinite(mu) or mu < 0.0:
                raise ValueError(f"[BottomUpLognormalSABR] Invalid mu={mu} from gamma_1N={gamma_1N}, N={N}")

            Gamma = np.zeros((N, N))
            for i in range(N):
                for j in range(N):
                    dt = abs(i - j)
                    val = 1.0 - mu * dt
                    if val < 0.0:
                        val = 0.0
                    Gamma[i, j] = val

            gamma_bar = float(Gamma.mean())

        if not np.isfinite(gamma_bar):
            raise ValueError(f"[BottomUpLognormalSABR] gamma_bar is not finite: {gamma_bar}")
        if gamma_bar <= 0.0 or gamma_bar > 1.0:
            raise ValueError(f"[BottomUpLognormalSABR] gamma_bar must be in (0,1], got {gamma_bar}")

        sqrt_g = float(np.sqrt(gamma_bar))

        # Effective params
        alpha_star = sqrt_g * sum(w * a * s for w, a, s in zip(weights, alphas, time_scales))
        beta_star = sum(w * b for w, b in zip(weights, betas))
        nu_star = sum(w * nu * s for w, nu, s in zip(weights, nus, time_scales))
        rho_star = (1.0 / sqrt_g) * sum(w * r for w, r in zip(weights, rhos))

        if not np.isfinite(alpha_star) or alpha_star <= 0.0:
            raise ValueError(f"[BottomUpLognormalSABR] alpha_star invalid: {alpha_star}")
        if not np.isfinite(nu_star) or nu_star < 0.0:
            raise ValueError(f"[BottomUpLognormalSABR] nu_star invalid: {nu_star}")
        if not (0.0 <= beta_star <= 1.0):
            raise ValueError(f"[BottomUpLognormalSABR] beta_star must be in [0,1], got {beta_star}")
        if not (-1.0 < rho_star < 1.0):
            raise ValueError(f"[BottomUpLognormalSABR] rho_star must be in (-1,1), got {rho_star}")

        self.volvol = float(nu_star)
        self.rho = float(rho_star)
        self.beta = float(beta_star)
        self._alphaEff = float(alpha_star)

    def alpha(self):
        return self._alphaEff
