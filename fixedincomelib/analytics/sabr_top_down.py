import numpy as np
from pysabr.models.hagan_2002_lognormal_sabr import Hagan2002LognormalSABR

class TimeDecayLognormalSABR(Hagan2002LognormalSABR):

    def __init__(self, f, shift, t, vAtmN, beta, rho, volVol, volDecaySpeed, decayStart):
        self._ts = decayStart
        self._te = t
        self.volDecaySpeed = volDecaySpeed
        super().__init__(f=f, shift=shift, t=t, v_atm_n=vAtmN, beta=beta, rho=rho, volvol=volVol)
        self._computeEffectiveParams()

    def _computeEffectiveParams(self):
        ts = self._ts
        te = self._te

        if ts >= te:
            self._alphaEff = super().alpha()
            return

        volDecaySpeed = self.volDecaySpeed
        alpha = super().alpha()
        rho   = self.rho
        nu    = self.volvol

        # build tau
        tau = 2 * volDecaySpeed * ts + te

        # gamma
        gammaFirstTerm = tau * (2 * tau**3+ te**3+ (4 * volDecaySpeed * volDecaySpeed - 2 * volDecaySpeed) * ts**3+ 6 * volDecaySpeed * ts**2 * te)
        gammaSecondTerm = (3 * volDecaySpeed * rho * rho * (te - ts)**2* (3 * tau**2 - te**2 + 5 * volDecaySpeed * ts**2 + 4 * ts * te))
        gamma = (gammaFirstTerm / ((4 * volDecaySpeed + 3) * (2 * volDecaySpeed + 1))+ gammaSecondTerm / ((4 * volDecaySpeed + 3) * (3 * volDecaySpeed + 2)**2))

        # nu-hat squared
        nuHat2 = nu * nu * gamma * (2 * volDecaySpeed + 1) / (tau**3 * te)

        # H
        H = (nu * nu * (tau**2 + 2 * volDecaySpeed * ts**2 + te**2)/ (2 * te * tau * (volDecaySpeed + 1))- nuHat2)

        # alpha-hat squared
        alphaHat2 = ((alpha * alpha) / (2 * volDecaySpeed + 1)* (tau / te)* np.exp(0.5 * H * te))

        # rho-hat
        rhoHat = (rho* (3 * tau * tau + 2 * volDecaySpeed * ts * ts + te * te)/ (np.sqrt(gamma) * (6 * volDecaySpeed + 4)))

        self.volvol    = np.sqrt(nuHat2)
        self.rho       = rhoHat
        self._alphaEff = np.sqrt(alphaHat2)

    def alpha(self):
        return self._alphaEff
