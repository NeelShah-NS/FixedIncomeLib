import numpy as np
from pysabr.models.hagan_2002_lognormal_sabr import Hagan2002LognormalSABR

class TimeDecayLognormalSABR(Hagan2002LognormalSABR): 

    def __init__(self, f, shift, t, vAtmN, beta, rho, volVol, volDecaySpeed, decayStart):
        self._ts = float(decayStart)
        self._te = float(t)
        self.volDecaySpeed = float(volDecaySpeed)

        if self._te <= 0.0:
            raise ValueError(f"[TimeDecayLognormalSABR] te=t must be > 0, got {self._te}.")
        if self._ts < 0.0:
            raise ValueError(f"[TimeDecayLognormalSABR] ts=decayStart must be >= 0, got {self._ts}.")
        if self.volDecaySpeed < 0.0:
            raise ValueError(f"[TimeDecayLognormalSABR] volDecaySpeed must be >= 0, got {self.volDecaySpeed}.")
        if not (0.0 <= float(beta) <= 1.0):
            raise ValueError(f"[TimeDecayLognormalSABR] beta must be in [0,1], got {beta}.")
        if not (-1.0 < float(rho) < 1.0):
            raise ValueError(f"[TimeDecayLognormalSABR] rho must be in (-1,1), got {rho}.")
        if float(volVol) < 0.0:
            raise ValueError(f"[TimeDecayLognormalSABR] volVol(nu) must be >= 0, got {volVol}.")
        if float(vAtmN) < 0.0:
            raise ValueError(f"[TimeDecayLognormalSABR] vAtmN(normal vol) must be >= 0, got {vAtmN}.")

        super().__init__(
            f=float(f),
            shift=float(shift),
            t=self._te,
            v_atm_n=float(vAtmN),
            beta=float(beta),
            rho=float(rho),
            volvol=float(volVol),
        )

        self._computeEffectiveParams()

    def _computeEffectiveParams(self):
        ts = self._ts
        te = self._te
        k = self.volDecaySpeed

        # If decay start is at/after effective time, mapping degenerates to base params
        if ts >= te:
            a0 = float(super().alpha())
            if a0 <= 0.0:
                raise ValueError(f"[TimeDecayLognormalSABR] base alpha <= 0 at te={te}: {a0}")
            self._alphaEff = a0
            return

        # Base params at te
        alpha0 = float(super().alpha())
        rho0 = float(self.rho)
        nu0 = float(self.volvol)

        if alpha0 <= 0.0:
            raise ValueError(f"[TimeDecayLognormalSABR] base alpha <= 0 at te={te}: {alpha0}")
        if not (-1.0 < rho0 < 1.0):
            raise ValueError(f"[TimeDecayLognormalSABR] base rho not in (-1,1): {rho0}")
        if nu0 < 0.0:
            raise ValueError(f"[TimeDecayLognormalSABR] base nu < 0: {nu0}")

        tau = 2.0 * k * ts + te
        if tau <= 0.0:
            raise ValueError(f"[TimeDecayLognormalSABR] tau <= 0 (tau={tau}) for k={k}, ts={ts}, te={te}")

        den0 = (4.0 * k + 3.0) * (2.0 * k + 1.0)
        den2 = (4.0 * k + 3.0) * (3.0 * k + 2.0) ** 2
        if den0 == 0.0 or den2 == 0.0:
            raise ValueError(f"[TimeDecayLognormalSABR] invalid denominators den0={den0}, den2={den2}")

        gammaFirstTerm = tau * (2.0 * tau**3 + te**3 + (4.0 * k * k - 2.0 * k) * ts**3 + 6.0 * k * ts**2 * te)
        gammaSecondTerm = (3.0 * k * rho0 * rho0 * (te - ts) ** 2 * (3.0 * tau**2 - te**2 + 5.0 * k * ts**2 + 4.0 * ts * te))
        gamma = gammaFirstTerm / den0 + gammaSecondTerm / den2

        if not np.isfinite(gamma):
            raise ValueError(f"[TimeDecayLognormalSABR] gamma is not finite: {gamma}")
        if gamma <= 0.0:
            raise ValueError(
                f"[TimeDecayLognormalSABR] gamma must be > 0 for sqrt(gamma). "
                f"Got gamma={gamma} (k={k}, ts={ts}, te={te}, rho={rho0})."
            )

        nuHat2 = nu0 * nu0 * gamma * (2.0 * k + 1.0) / (tau**3 * te)
        if not np.isfinite(nuHat2):
            raise ValueError(f"[TimeDecayLognormalSABR] nuHat2 is not finite: {nuHat2}")
        if nuHat2 < 0.0:
            raise ValueError(f"[TimeDecayLognormalSABR] nuHat2 < 0: {nuHat2}")

        H = nu0 * nu0 * (tau**2 + 2.0 * k * ts**2 + te**2) / (2.0 * te * tau * (k + 1.0)) - nuHat2
        if not np.isfinite(H):
            raise ValueError(f"[TimeDecayLognormalSABR] H is not finite: {H}")

        alphaHat2 = (alpha0 * alpha0) / (2.0 * k + 1.0) * (tau / te) * np.exp(0.5 * H * te)
        if not np.isfinite(alphaHat2):
            raise ValueError(f"[TimeDecayLognormalSABR] alphaHat2 is not finite: {alphaHat2}")
        if alphaHat2 < 0.0:
            raise ValueError(f"[TimeDecayLognormalSABR] alphaHat2 < 0: {alphaHat2}")

        rhoHat = (rho0 * (3.0 * tau * tau + 2.0 * k * ts * ts + te * te) / (np.sqrt(gamma) * (6.0 * k + 4.0)))
        if not np.isfinite(rhoHat):
            raise ValueError(f"[TimeDecayLognormalSABR] rhoHat is not finite: {rhoHat}")
        if not (-1.0 < rhoHat < 1.0):
            raise ValueError(
                f"[TimeDecayLognormalSABR] rhoHat must be in (-1,1). Got rhoHat={rhoHat}. "
                f"(base rho={rho0}, gamma={gamma})"
            )

        # Write effective params into pricer
        self.volvol = float(np.sqrt(nuHat2))
        self.rho = float(rhoHat)
        self._alphaEff = float(np.sqrt(alphaHat2))

        if self._alphaEff <= 0.0:
            raise ValueError(f"[TimeDecayLognormalSABR] alphaEff <= 0: {self._alphaEff}")

    def alpha(self):
        return self._alphaEff
