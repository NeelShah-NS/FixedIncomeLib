import numpy as np
from pysabr.models.hagan_2002_lognormal_sabr import Hagan2002LognormalSABR
from fixedincomelib.date.utilities import accrued

class BottomUpLognormalSABR(Hagan2002LognormalSABR):
    def __init__(
        self,
        f: float,
        shift: float,
        expiry: float,
        tenor: float,
        model,
        corr_surf,
        product
    ):
        self._expiry   = expiry
        self._tenor    = tenor
        self._model    = model
        self._corr     = corr_surf
        self._product  = product

        super().__init__(
            f       = f,
            shift   = shift,
            t       = expiry + tenor,
            v_atm_n = 0.0,              
            beta    = 0.0,              
            rho     = 0.0,              
            volvol  = 0.0               
        )

        self._computeEffectiveParams()

    def _computeEffectiveParams(self):
        dates = self._product.get_fixing_schedule()
        Tis   = [accrued(d0, d1) for d0,d1 in zip(dates, dates[1:])]
        total = sum(Tis)
        weights = [Ti/total for Ti in Tis]

        alphas = []
        betas  = []
        nus    = []
        rhos   = []
        for Ti in Tis:
            v_n_i, b_i, nu_i, rho_i, _, _ = self._model.get_sabr_parameters(
                index        = self._product.index,
                expiry       = self._expiry,
                tenor        = Ti,
                product_type = None
            )
            p = Hagan2002LognormalSABR(
                f       = self.f,
                shift   = self.shift,
                t       = self._expiry,
                v_atm_n = v_n_i,
                beta    = b_i,
                rho     = rho_i,
                volvol  = nu_i
            )
            alphas.append(p.alpha())
            betas .append(b_i)
            nus   .append(nu_i)
            rhos  .append(rho_i)

        T_total = sum(Tis)
        gamma_1N = self._corr.corr(self._expiry, T_total)
        mu = (1.0 - gamma_1N) / (len(Tis) - 1)

        N = len(Tis)
        taus = np.cumsum([0.0] + Tis)
        Gamma = np.zeros((N, N))
        for i in range(N):
            for j in range(N):
                dt = abs(taus[i+1] - taus[j+1])
                Gamma[i, j] = max(0.0, 1.0 - mu * dt)
        gamma_bar = Gamma.mean()

        alpha_star = np.sqrt(gamma_bar) * sum(w*alpha*np.sqrt(Ti/total)  for w,alpha,Ti in zip(weights,alphas, Tis))
        beta_star = sum(w*b for w,b in zip(weights, betas))
        nu_star = sum(w*nu*np.sqrt(Ti/total) for w,nu,Ti in zip(weights, nus,   Tis))
        rho_star = (1/np.sqrt(gamma_bar)) * sum(w*rho for w,rho in zip(weights, rhos))

        self.volvol = nu_star
        self.rho    = rho_star
        self.beta   = beta_star
        self._alphaEff = alpha_star

    def alpha(self):
        return self._alphaEff