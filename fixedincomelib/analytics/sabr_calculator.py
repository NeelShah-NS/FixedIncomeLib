import pandas as pd
import numpy as np
import QuantLib as ql
from pysabr import Hagan2002LognormalSABR
from pysabr.models.hagan_2002_lognormal_sabr import lognormal_vol
from pysabr import black
from fixedincomelib.sabr import SabrModel
from fixedincomelib.analytics.sabr_top_down import TimeDecayLognormalSABR
from fixedincomelib.analytics.sabr_bottom_up import BottomUpLognormalSABR
from fixedincomelib.analytics.correlation_surface import CorrSurface
from typing import Optional, Tuple
from fixedincomelib.data import DataCollection, Data2D
from scipy.stats import norm

class SABRCalculator:
    def __init__(
        self,
        sabr_model: SabrModel,
        method: str = "bottom-up",
        corr_surf: Optional[CorrSurface] = None,
        product_type: Optional[str] = None,
        product=None,
    ):
        self.model = sabr_model
        self.method = method.lower() if method is not None else None
        self.product_type = product_type
        self.product = product

        if self.method == "bottom-up":
            if self.product is None:
                raise ValueError("[SABRCalculator] product must be provided for bottom-up method.")
            if corr_surf is None:
                md = self.model.dataCollection.get("corr", self.product.index)
                if not isinstance(md, Data2D):
                    raise TypeError("[SABRCalculator] correlation surface data must be Data2D.")
                corr_surf = CorrSurface.from_data2d(md)

        self.corr_surf = corr_surf

    def option_price(self, index: str, expiry: float, tenor: float, forward: float, strike: float, option_type: str) -> float:
        normal_vol, beta, nu, rho, shift, decay = self.model.get_sabr_parameters(
            index, expiry, tenor, product_type=self.product_type)

        if self.method == "top-down":
            sabr_pricer = TimeDecayLognormalSABR(
                f=forward,
                shift=shift,
                t=expiry + tenor,
                vAtmN=normal_vol,
                beta=beta,
                rho=rho,
                volVol=nu,
                volDecaySpeed=decay,
                decayStart=expiry,
            )
            strike_to_price = strike

        elif self.method == "bottom-up":
            if self.corr_surf is None:
                raise ValueError("corr_surf must be provided for bottom-up method")

            sabr_pricer = BottomUpLognormalSABR(
                f=forward,
                shift=shift,
                expiry=expiry,
                tenor=tenor,
                model=self.model,
                corr_surf=self.corr_surf,
                product=self.product,
            )
            strike_to_price = strike

        else:
            sabr_pricer = Hagan2002LognormalSABR(
                f=forward,
                shift=shift,
                t=expiry,
                v_atm_n=normal_vol,
                beta=beta,
                rho=rho,
                volvol=nu,
            )
            strike_to_price = strike
        
        ot = option_type.upper()
        if ot in ("CAP", "CAPLET"):
            cp = "call"
        elif ot in ("FLOOR", "FLOORLET"):
            cp = "put"
        else:
            raise ValueError(f"Unknown option_type={option_type}")
        if hasattr(sabr_pricer, "call"):
            return float(sabr_pricer.call(strike_to_price, cp=cp))
        raise AttributeError(f"No compatible call-price method on pricer {type(sabr_pricer)}")

    def option_price_greeks(
        self,
        index: str,
        expiry: float,
        tenor: float,
        forward: float,
        strike: float,
        option_type: str,
        normal_vol: float,
        beta: float,
        nu: float,
        rho: float,
        shift: float,
        decay: float = 0.0,
    ) -> Tuple[float, float, float]:

        beta_in = float(beta)
        rho_in  = float(rho)
        nu_in   = float(nu)

        forward_shifted = forward + shift
        strike_shifted  = strike + shift

        if forward_shifted <= 0.0 or strike_shifted <= 0.0:
            raise ValueError(f"[option_price_greeks] forward+shift and strike+shift must be > 0. Got Forward shift={forward_shifted}, Strike shift={strike_shifted}.")

        # Build pricer
        if self.method == "bottom-up":
            if self.corr_surf is None:
                raise ValueError("corr_surf must be provided for bottom-up method")

            sabr_pricer = BottomUpLognormalSABR(
                f=forward,
                shift=shift,
                expiry=expiry,
                tenor=tenor,
                model=self.model,
                corr_surf=self.corr_surf,
                product=self.product,
            )

        elif self.method == "top-down":
            sabr_pricer = TimeDecayLognormalSABR(
                f=forward,
                shift=shift,
                t=expiry + tenor,
                vAtmN=normal_vol,
                beta=beta_in,
                rho=rho_in,
                volVol=nu_in,
                volDecaySpeed=decay,
                decayStart=expiry,
            )

        else:
            sabr_pricer = Hagan2002LognormalSABR(
                f=forward,
                shift=shift,
                t=expiry,
                v_atm_n=normal_vol,
                beta=beta_in,
                rho=rho_in,
                volvol=nu_in,
            )

        # Effective params used by lognormal_vol() (for top-down/bottom-up these are the effective ones)
        alpha = float(sabr_pricer.alpha())
        beta  = float(sabr_pricer.beta)
        rho   = float(sabr_pricer.rho)
        nu    = float(sabr_pricer.volvol)

        time_to_expiry = float(sabr_pricer.t)
        if alpha <= 0.0 or time_to_expiry <= 0.0:
            raise ValueError(f"[option_price_greeks] invalid alpha={alpha} or T={time_to_expiry}")
        if not (0.0 <= beta <= 1.0):
            raise ValueError(f"[option_price_greeks] beta not in [0,1]: {beta}")
        if not (-1.0 < rho < 1.0):
            raise ValueError(f"[option_price_greeks] rho not in (-1,1): {rho}")
        if nu < 0.0:
            raise ValueError(f"[option_price_greeks] nu < 0: {nu}")

        shifted_lognormal_vol = float(sabr_pricer.lognormal_vol(strike))
        if shifted_lognormal_vol <= 0.0:
            raise ValueError(f"[option_price_greeks] lognormal_vol invalid: {shifted_lognormal_vol}")

        # Price greeks w.r.t F and sigma (Black on shifted forward)
        sqrt_time = np.sqrt(time_to_expiry)
        d1 = (np.log(forward_shifted / strike_shifted)+ 0.5 * shifted_lognormal_vol * shifted_lognormal_vol * time_to_expiry) / (shifted_lognormal_vol * sqrt_time)

        ot = option_type.upper()
        if ot in ("CAP", "CAPLET"):
            is_call = True
        elif ot in ("FLOOR", "FLOORLET"):
            is_call = False
        else:
            raise ValueError(f"Unknown option_type={option_type}")

        dPrice_dForward = float(norm.cdf(d1)) if is_call else float(norm.cdf(d1) - 1.0)
        dPrice_dVol     = float(forward_shifted * norm.pdf(d1) * sqrt_time)

        # Hagan: dsigma/dF partial (alpha const) AND dsigma/dalpha
        one_minus_beta = 1.0 - beta
        log_forward_over_strike = np.log(forward_shifted / strike_shifted)
        fkbeta = (forward_shifted * strike_shifted) ** (1.0 - beta)
        sqrt_fkbeta = np.sqrt(fkbeta)

        A = (one_minus_beta ** 2) * (alpha ** 2) / (24.0 * fkbeta)
        B = 0.25 * rho * beta * nu * alpha / sqrt_fkbeta
        C = (2.0 - 3.0 * rho * rho) * (nu ** 2) / 24.0

        V = (one_minus_beta ** 2) * (log_forward_over_strike ** 2) / 24.0
        W = (one_minus_beta ** 4) * (log_forward_over_strike ** 4) / 1920.0

        H = 1.0 + (A + B + C) * time_to_expiry
        Q = 1.0 + V + W

        dlog_forward_over_strike_dF = 1.0 / forward_shifted
        dsqrt_fkbeta_dF = 0.5 * sqrt_fkbeta * (1.0 - beta) / forward_shifted

        dA_dF = -A * (1.0 - beta) / forward_shifted
        dB_dF = -0.5 * B * (1.0 - beta) / forward_shifted
        dV_dF = (one_minus_beta ** 2) * log_forward_over_strike / (12.0 * forward_shifted)
        dW_dF = (one_minus_beta ** 4) * (log_forward_over_strike ** 3) / (480.0 * forward_shifted)

        dA_dalpha = (one_minus_beta ** 2) * alpha / (12.0 * fkbeta)
        dB_dalpha = B / alpha

        dH_dF     = (dA_dF + dB_dF) * time_to_expiry
        dH_dalpha = (dA_dalpha + dB_dalpha) * time_to_expiry
        dQ_dF     = dV_dF + dW_dF

        z   = nu * sqrt_fkbeta * log_forward_over_strike / alpha
        eps = 1e-7

        dz_dF     = (nu / alpha) * (dsqrt_fkbeta_dF * log_forward_over_strike + sqrt_fkbeta * dlog_forward_over_strike_dF)
        dz_dalpha = -z / alpha

        if abs(z) > eps:
            sqrt_term = float(np.sqrt(1.0 - 2.0 * rho * z + z * z))
            Ax = float(sqrt_term + z - rho)
            Bx = float(1.0 - rho)
            if sqrt_term <= 0.0 or Ax <= 0.0 or Bx <= 0.0:
                dsigma_dF_partial = 0.0
                dsigma_dalpha = 0.0
            else:
                x = float(np.log(Ax / Bx))
                dx_dz     = float(1.0 / sqrt_term)
                dx_dF     = float(dx_dz * dz_dF)
                dx_dalpha = float(dx_dz * dz_dalpha)

                Numer = alpha * z * H
                Denom = sqrt_fkbeta * Q * x

                dNumer_dF = alpha * dz_dF * H + alpha * z * dH_dF
                dDenom_dF = dsqrt_fkbeta_dF * Q * x + sqrt_fkbeta * dQ_dF * x + sqrt_fkbeta * Q * dx_dF
                dsigma_dF_partial = 0.0 if abs(Denom) <= 1e-18 else float((dNumer_dF * Denom - Numer * dDenom_dF) / (Denom * Denom))

                dNumer_dalpha = alpha * z * dH_dalpha
                dDenom_dalpha = sqrt_fkbeta * Q * dx_dalpha
                dsigma_dalpha = 0.0 if abs(Denom) <= 1e-18 else float((dNumer_dalpha * Denom - Numer * dDenom_dalpha) / (Denom * Denom))
        else:
            Numer = alpha * H
            Denom = sqrt_fkbeta * Q

            dNumer_dF = alpha * dH_dF
            dDenom_dF = dsqrt_fkbeta_dF * Q + sqrt_fkbeta * dQ_dF
            dsigma_dF_partial = 0.0 if abs(Denom) <= 1e-18 else float((dNumer_dF * Denom - Numer * dDenom_dF) / (Denom * Denom))

            dNumer_dalpha = H + alpha * dH_dalpha
            dsigma_dalpha = 0.0 if abs(Denom) <= 1e-18 else float(dNumer_dalpha / Denom)

        # dalpha/dF (YC-risk): alpha depends on F via ATM constraint
        dalpha_dF = 0.0

        if self.method == "top-down":
            # base alpha at t = time_to_expiry using BASE params (beta_in, rho_in, nu_in)
            base_pricer = Hagan2002LognormalSABR(
                f=forward,
                shift=shift,
                t=time_to_expiry,
                v_atm_n=normal_vol,
                beta=beta_in,
                rho=rho_in,
                volvol=nu_in,
            )
            alpha_base = float(base_pricer.alpha())
            c = (alpha / alpha_base) if alpha_base > 0.0 else 0.0

            atm_sigma_ln = float(black.normal_to_shifted_lognormal(forward, forward, shift, time_to_expiry, normal_vol))
            if atm_sigma_ln > 0.0 and c > 0.0:
                atm_x = 0.5 * atm_sigma_ln * sqrt_time
                atm_phi = norm.pdf(atm_x)
                atm_A = 2.0 * norm.cdf(atm_x) - 1.0
                datm_sigma_ln_dF = 0.0 if atm_phi <= 0.0 else float(-atm_A / (forward_shifted * atm_phi * sqrt_time))

                one_minus_beta_b = 1.0 - beta_in
                f_power = forward_shifted ** (beta_in - 1.0)

                a3 = time_to_expiry * (f_power ** 3) * (one_minus_beta_b ** 2) / 24.0
                a2 = time_to_expiry * (f_power ** 2) * (rho_in * beta_in * nu_in) / 4.0
                a1 = (1.0 + time_to_expiry * (nu_in ** 2) * (2.0 - 3.0 * rho_in * rho_in) / 24.0) * f_power
                a0 = -atm_sigma_ln

                da3_dF = a3 * (3.0 * (beta_in - 1.0) / forward_shifted)
                da2_dF = a2 * (2.0 * (beta_in - 1.0) / forward_shifted)
                da1_dF = a1 * ((beta_in - 1.0) / forward_shifted)
                da0_dF = -datm_sigma_ln_dF

                dP_dalpha = 3.0 * a3 * alpha_base * alpha_base + 2.0 * a2 * alpha_base + a1
                dP_dF     = da3_dF * (alpha_base ** 3) + da2_dF * (alpha_base ** 2) + da1_dF * alpha_base + da0_dF
                dalpha_base_dF = 0.0 if abs(dP_dalpha) <= 1e-18 else float(-dP_dF / dP_dalpha)

                dalpha_dF = float(c * dalpha_base_dF)

        elif self.method == "bottom-up":

            dates = self.product.get_fixing_schedule()
            if dates is None or len(dates) < 2:
                dalpha_dF = 0.0
            else:
                dc = self.product.dayCounter
                Tis = [float(dc.yearFraction(d0, d1)) for d0, d1 in zip(dates, dates[1:])]
                total = float(sum(Tis))
                if total <= 0.0:
                    dalpha_dF = 0.0
                else:
                    weights = [float(Ti / total) for Ti in Tis]

                    offsets = np.cumsum([0.0] + Tis[:-1])
                    Tstarts = [float(expiry) + float(x) for x in offsets]
                    Tends   = [Ts + Ti for Ts, Ti in zip(Tstarts, Tis)]

                    use_end_time = (getattr(self.product, "oisIndex_", None) is not None)
                    Texp = Tends if use_end_time else Tstarts

                    # validate segment times
                    if any((not np.isfinite(T) or T <= 0.0) for T in Texp):
                        dalpha_dF = 0.0
                    else:
                        Tbar = float(sum(w * T for w, T in zip(weights, Texp)))
                        if not np.isfinite(Tbar) or Tbar <= 0.0:
                            dalpha_dF = 0.0
                        else:
                            time_scales = [float(np.sqrt(T / Tbar)) for T in Texp]

                            # CONSISTENT corr convention: corr(Texp[0], Texp[-1])
                            gamma_1N = float(self.corr_surf.corr(float(Texp[0]), float(Texp[-1])))

                            N = len(Tis)
                            if N <= 1:
                                gamma_bar = 1.0
                            else:
                                mu = (1.0 - gamma_1N) / (N - 1)
                                ssum = 0.0
                                for d in range(N):
                                    val = 1.0 - mu * d
                                    if val < 0.0:
                                        val = 0.0
                                    cnt = N if d == 0 else 2.0 * (N - d)
                                    ssum += cnt * val
                                gamma_bar = float(ssum / (N * N))

                            sqrt_g = float(np.sqrt(gamma_bar))

                            dalpha_eff_dF = 0.0
                            for Ti, Te, w, s in zip(Tis, Texp, weights, time_scales):

                                v_n_i, b_i, nu_i, rho_i, _, _ = self.model.get_sabr_parameters(
                                    index=index,
                                    expiry=float(Te),
                                    tenor=float(Ti),
                                    product_type=None,
                                )

                                seg_pricer = Hagan2002LognormalSABR(
                                    f=float(forward),
                                    shift=float(shift),
                                    t=float(Te),
                                    v_atm_n=float(v_n_i),
                                    beta=float(b_i),
                                    rho=float(rho_i),
                                    volvol=float(nu_i),
                                )
                                alpha_i = float(seg_pricer.alpha())
                                if alpha_i <= 0.0:
                                    continue

                                atm_sigma_ln = float(
                                    black.normal_to_shifted_lognormal(forward, forward, shift, float(Te), float(v_n_i))
                                )
                                if atm_sigma_ln <= 0.0:
                                    continue

                                sqrt_t = float(np.sqrt(Te))
                                atm_x = 0.5 * atm_sigma_ln * sqrt_t
                                atm_phi = float(norm.pdf(atm_x))
                                atm_A = float(2.0 * norm.cdf(atm_x) - 1.0)
                                datm_sigma_ln_dF = 0.0 if atm_phi <= 0.0 else float(
                                    -atm_A / (forward_shifted * atm_phi * sqrt_t)
                                )

                                one_minus_beta_i = 1.0 - float(b_i)
                                f_power_i = float(forward_shifted ** (float(b_i) - 1.0))

                                a3 = float(Te * (f_power_i ** 3) * (one_minus_beta_i ** 2) / 24.0)
                                a2 = float(Te * (f_power_i ** 2) * (float(rho_i) * float(b_i) * float(nu_i)) / 4.0)
                                a1 = float(
                                    (1.0 + Te * (float(nu_i) ** 2) * (2.0 - 3.0 * float(rho_i) * float(rho_i)) / 24.0)
                                    * f_power_i
                                )
                                a0 = float(-atm_sigma_ln)

                                da3_dF = float(a3 * (3.0 * (float(b_i) - 1.0) / forward_shifted))
                                da2_dF = float(a2 * (2.0 * (float(b_i) - 1.0) / forward_shifted))
                                da1_dF = float(a1 * ((float(b_i) - 1.0) / forward_shifted))
                                da0_dF = float(-datm_sigma_ln_dF)

                                dP_dalpha = float(3.0 * a3 * alpha_i * alpha_i + 2.0 * a2 * alpha_i + a1)
                                if abs(dP_dalpha) <= 1e-18:
                                    continue

                                dP_dF = float(
                                    da3_dF * (alpha_i ** 3) + da2_dF * (alpha_i ** 2) + da1_dF * alpha_i + da0_dF
                                )
                                dalpha_i_dF = float(-dP_dF / dP_dalpha)

                                dalpha_eff_dF += float(w * s * dalpha_i_dF)

                            dalpha_dF = float(sqrt_g * dalpha_eff_dF)

        else:
            # Plain Hagan
            atm_sigma_ln = float(black.normal_to_shifted_lognormal(forward, forward, shift, time_to_expiry, normal_vol))
            if atm_sigma_ln > 0.0:
                atm_x = 0.5 * atm_sigma_ln * sqrt_time
                atm_phi = norm.pdf(atm_x)
                atm_A = 2.0 * norm.cdf(atm_x) - 1.0
                datm_sigma_ln_dF = 0.0 if atm_phi <= 0.0 else float(-atm_A / (forward_shifted * atm_phi * sqrt_time))

                one_minus_beta_b = 1.0 - beta_in
                f_power = forward_shifted ** (beta_in - 1.0)

                a3 = time_to_expiry * (f_power ** 3) * (one_minus_beta_b ** 2) / 24.0
                a2 = time_to_expiry * (f_power ** 2) * (rho_in * beta_in * nu_in) / 4.0
                a1 = (1.0 + time_to_expiry * (nu_in ** 2) * (2.0 - 3.0 * rho_in * rho_in) / 24.0) * f_power
                a0 = -atm_sigma_ln

                da3_dF = a3 * (3.0 * (beta_in - 1.0) / forward_shifted)
                da2_dF = a2 * (2.0 * (beta_in - 1.0) / forward_shifted)
                da1_dF = a1 * ((beta_in - 1.0) / forward_shifted)
                da0_dF = -datm_sigma_ln_dF

                dP_dalpha = 3.0 * a3 * alpha * alpha + 2.0 * a2 * alpha + a1
                dP_dF     = da3_dF * (alpha ** 3) + da2_dF * (alpha ** 2) + da1_dF * alpha + da0_dF
                dalpha_dF = 0.0 if abs(dP_dalpha) <= 1e-18 else float(-dP_dF / dP_dalpha)

        dVol_dForward = float(dsigma_dF_partial + dsigma_dalpha * dalpha_dF)

        return dPrice_dForward, dPrice_dVol, dVol_dForward

    def dalpha_dNormalVol_atm(
        self,
        *,
        index: str,
        expiry: float,
        tenor: float,
        forward: float,
        normalVol: float,
        beta: float,
        nu: float,
        rho: float,
        shift: float,
        decay: float = 0.0,
    ):

        Fp = float(forward + shift)
        if Fp <= 0.0:
            return 0.0 if self.method != "bottom-up" else []

        T = float(expiry + tenor) if self.method in ("top-down", "bottom-up") else float(expiry)
        if T <= 0.0:
            return 0.0 if self.method != "bottom-up" else []

        # TOP-DOWN
        if self.method == "top-down":
            pr_eff = TimeDecayLognormalSABR(
                f=forward,
                shift=shift,
                t=expiry + tenor,
                vAtmN=normalVol,
                beta=float(beta),
                rho=float(rho),
                volVol=float(nu),
                volDecaySpeed=float(decay),
                decayStart=float(expiry),
            )
            alpha_eff = float(pr_eff.alpha())

            pr_base = Hagan2002LognormalSABR(
                f=forward,
                shift=shift,
                t=expiry + tenor,
                v_atm_n=normalVol,
                beta=float(beta),
                rho=float(rho),
                volvol=float(nu),
            )
            alpha_base = float(pr_base.alpha())

            if alpha_eff <= 0.0 or alpha_base <= 0.0:
                return 0.0

            c = float(alpha_eff / alpha_base)

            sig_ln_atm = float(black.normal_to_shifted_lognormal(forward, forward, shift, T, normalVol))
            if sig_ln_atm <= 0.0:
                return 0.0

            x = 0.5 * sig_ln_atm * np.sqrt(T)
            dsigln_dvn = float(np.exp(0.5 * x * x) / Fp)

            one_minus_beta = 1.0 - float(beta)
            f_power = float(Fp ** (float(beta) - 1.0))

            a3 = float(T * (f_power ** 3) * (one_minus_beta ** 2) / 24.0)
            a2 = float(T * (f_power ** 2) * (float(rho) * float(beta) * float(nu)) / 4.0)
            a1 = float((1.0 + T * (float(nu) ** 2) * (2.0 - 3.0 * float(rho) * float(rho)) / 24.0) * f_power)

            dP_dalpha = float(3.0 * a3 * alpha_base * alpha_base + 2.0 * a2 * alpha_base + a1)
            if abs(dP_dalpha) <= 1e-18:
                return 0.0

            dalpha_base_dvn = float(dsigln_dvn / dP_dalpha)
            return float(c * dalpha_base_dvn)

        # BOTTOM-UP
        if self.method == "bottom-up":

            if self.corr_surf is None:
                raise ValueError("corr_surf must be provided for bottom-up method")
            if self.product is None:
                raise ValueError("product must be provided for bottom-up method")

            dates = self.product.get_fixing_schedule()
            if dates is None or len(dates) < 2:
                return []

            dc = self.product.dayCounter

            Tis = [float(dc.yearFraction(d0, d1)) for d0, d1 in zip(dates, dates[1:])]
            if any(Ti <= 0.0 for Ti in Tis):
                raise ValueError(f"[bottom-up] non-positive segment accruals: {Tis}")

            total = float(sum(Tis))
            weights = [float(Ti / total) for Ti in Tis]

            offsets_start = np.cumsum([0.0] + Tis[:-1])
            Tstarts = [float(expiry) + float(x) for x in offsets_start]
            Tends   = [Ts + Ti for Ts, Ti in zip(Tstarts, Tis)]

            use_end_time = (getattr(self.product, "oisIndex_", None) is not None)
            Texp = Tends if use_end_time else Tstarts

            Tbar = float(sum(w * T for w, T in zip(weights, Texp)))
            if Tbar <= 0.0 or not np.isfinite(Tbar):
                raise ValueError(f"[bottom-up] invalid Tbar={Tbar}")

            time_scales = [float(np.sqrt(T / Tbar)) for T in Texp]

            t_first = float(Texp[0])
            t_last  = float(Texp[-1])
            gamma_1N = float(self.corr_surf.corr(t_first, t_last))

            N = len(Tis)
            if N <= 1:
                gamma_bar = 1.0
            else:
                mu = (1.0 - gamma_1N) / (N - 1)
                s = 0.0
                for d in range(N):
                    val = 1.0 - mu * d
                    if val < 0.0:
                        val = 0.0
                    cnt = N if d == 0 else 2.0 * (N - d)
                    s += cnt * val
                gamma_bar = float(s / (N * N))

            sqrt_g = float(np.sqrt(gamma_bar))

            out = []
            h = 1e-6

            for Ti, Te, w_i, s_i in zip(Tis, Texp, weights, time_scales):
                v_n_i, b_i, nu_i, rho_i, _, _ = self.model.get_sabr_parameters(
                    index=index,
                    expiry=float(Te),
                    tenor=float(Ti),
                    product_type= None,
                )

                v_n_i = float(v_n_i)
                b_i   = float(b_i)
                nu_i  = float(nu_i)
                rho_i = float(rho_i)

                pr_plus = Hagan2002LognormalSABR(
                    f=float(forward), shift=float(shift), t=float(Te),
                    v_atm_n=v_n_i + h, beta=b_i, rho=rho_i, volvol=nu_i
                )
                pr_minus = Hagan2002LognormalSABR(
                    f=float(forward), shift=float(shift), t=float(Te),
                    v_atm_n=v_n_i - h, beta=b_i, rho=rho_i, volvol=nu_i
                )

                a_plus = float(pr_plus.alpha())
                a_minus = float(pr_minus.alpha())

                dalpha_i_dvn = float((a_plus - a_minus) / (2.0 * h))

                out.append((float(Te), float(Ti), float(sqrt_g * w_i * s_i * dalpha_i_dvn)))

            return out

        # PLAIN HAGAN
        pr = Hagan2002LognormalSABR(
            f=forward,
            shift=shift,
            t=expiry,
            v_atm_n=normalVol,
            beta=float(beta),
            rho=float(rho),
            volvol=float(nu),
        )
        alpha = float(pr.alpha())
        if alpha <= 0.0:
            return 0.0

        sig_ln_atm = float(black.normal_to_shifted_lognormal(forward, forward, shift, T, normalVol))
        if sig_ln_atm <= 0.0:
            return 0.0

        x = 0.5 * sig_ln_atm * np.sqrt(T)
        dsigln_dvn = float(np.exp(0.5 * x * x) / Fp)

        one_minus_beta = 1.0 - float(beta)
        f_power = float(Fp ** (float(beta) - 1.0))

        a3 = float(T * (f_power ** 3) * (one_minus_beta ** 2) / 24.0)
        a2 = float(T * (f_power ** 2) * (float(rho) * float(beta) * float(nu)) / 4.0)
        a1 = float((1.0 + T * (float(nu) ** 2) * (2.0 - 3.0 * float(rho) * float(rho)) / 24.0) * f_power)

        dP_dalpha = float(3.0 * a3 * alpha * alpha + 2.0 * a2 * alpha + a1)
        if abs(dP_dalpha) <= 1e-18:
            return 0.0

        return float(dsigln_dvn / dP_dalpha)
    
    def dVol_dNormalVol(
        self,
        *,
        index: str,
        expiry: float,
        tenor: float,
        forward: float,
        strike: float,
        normalVol: float,
        beta: float,
        nu: float,
        rho: float,
        shift: float,
        decay: float = 0.0,
    ):
        
        beta_in = float(beta)
        rho_in  = float(rho)
        nu_in   = float(nu)

        Fp = float(forward + shift)
        Kp = float(strike  + shift)
        if Fp <= 0.0 or Kp <= 0.0:
            return 0.0 if self.method != "bottom-up" else []

        if self.method == "bottom-up":
            if self.corr_surf is None:
                raise ValueError("corr_surf must be provided for bottom-up method")
            if self.product is None:
                raise ValueError("product must be provided for bottom-up method")

            sabr_pricer = BottomUpLognormalSABR(
                f=forward,
                shift=shift,
                expiry=expiry,
                tenor=tenor,
                model=self.model,
                corr_surf=self.corr_surf,
                product=self.product,
            )

        elif self.method == "top-down":
            sabr_pricer = TimeDecayLognormalSABR(
                f=forward,
                shift=shift,
                t=expiry + tenor,
                vAtmN=normalVol,
                beta=beta_in,
                rho=rho_in,
                volVol=nu_in,
                volDecaySpeed=decay,
                decayStart=expiry,
            )

        else:
            sabr_pricer = Hagan2002LognormalSABR(
                f=forward,
                shift=shift,
                t=expiry,
                v_atm_n=normalVol,
                beta=beta_in,
                rho=rho_in,
                volvol=nu_in,
            )

        alpha = float(sabr_pricer.alpha())
        beta_eff = float(sabr_pricer.beta)
        rho_eff  = float(sabr_pricer.rho)
        nu_eff   = float(sabr_pricer.volvol)
        T = float(sabr_pricer.t)

        if alpha <= 0.0 or T <= 0.0:
            return 0.0 if self.method != "bottom-up" else []

        sigmaK = float(sabr_pricer.lognormal_vol(strike))
        if sigmaK <= 0.0:
            return 0.0 if self.method != "bottom-up" else []

        # dsigma/dalpha
        one_minus_beta = 1.0 - beta_eff
        L = float(np.log(Fp / Kp))

        fkbeta = float((Fp * Kp) ** (1.0 - beta_eff))
        sqrt_fkbeta = float(np.sqrt(fkbeta))

        A = float((one_minus_beta ** 2) * (alpha ** 2) / (24.0 * fkbeta))
        B = float(0.25 * rho_eff * beta_eff * nu_eff * alpha / sqrt_fkbeta)
        C = float((2.0 - 3.0 * rho_eff * rho_eff) * (nu_eff ** 2) / 24.0)

        V = float((one_minus_beta ** 2) * (L ** 2) / 24.0)
        W = float((one_minus_beta ** 4) * (L ** 4) / 1920.0)

        H = float(1.0 + (A + B + C) * T)
        Q = float(1.0 + V + W)

        dA_dalpha = float((one_minus_beta ** 2) * alpha / (12.0 * fkbeta))
        dB_dalpha = float(B / alpha)
        dH_dalpha = float((dA_dalpha + dB_dalpha) * T)

        z = float(nu_eff * sqrt_fkbeta * L / alpha)
        eps = 1e-7

        if abs(z) > eps:
            sqrt_term = float(np.sqrt(1.0 - 2.0 * rho_eff * z + z * z))
            Ax = float(sqrt_term + z - rho_eff)
            Bx = float(1.0 - rho_eff)
            if sqrt_term <= 0.0 or Ax <= 0.0 or Bx <= 0.0:
                return 0.0 if self.method != "bottom-up" else []

            x = float(np.log(Ax / Bx))

            dz_dalpha = float(-z / alpha)
            dx_dz = float(1.0 / sqrt_term)
            dx_dalpha = float(dx_dz * dz_dalpha)

            Numer = float(alpha * z * H)
            Denom = float(sqrt_fkbeta * Q * x)

            dNumer_dalpha = float(alpha * z * dH_dalpha)            
            dDenom_dalpha = float(sqrt_fkbeta * Q * dx_dalpha)

            dsigma_dalpha = 0.0 if abs(Denom) <= 1e-18 else float(
                (dNumer_dalpha * Denom - Numer * dDenom_dalpha) / (Denom * Denom))
        else:
            Denom = float(sqrt_fkbeta * Q)
            dsigma_dalpha = 0.0 if abs(Denom) <= 1e-18 else float((H + alpha * dH_dalpha) / Denom)

        # Chain: d sigma / d normalVol = (d sigma / d alpha) * (d alpha / d normalVol_ATM)
        dalpha_dvn = self.dalpha_dNormalVol_atm(
            index=index,
            expiry=expiry,
            tenor=tenor,
            forward=forward,
            normalVol=normalVol,
            beta=beta,
            nu=nu,
            rho=rho,
            shift=shift,
            decay=decay,
        )

        if self.method != "bottom-up":
            return float(dsigma_dalpha) * float(dalpha_dvn)

        # bottom-up
        out = []
        for Te, Ti, dAlphaStar_dVn_i in dalpha_dvn:
            out.append((float(Te), float(Ti), float(dsigma_dalpha) * float(dAlphaStar_dVn_i)))
        return out


    def dVol_dBeta(
        self,
        *,
        index: str,
        expiry: float,
        tenor: float,
        forward: float,
        strike: float,
        normalVol: float,
        beta: float,
        nu: float,
        rho: float,
        shift: float,
        decay: float = 0.0,
    ):

        beta_in = float(beta)
        rho_in  = float(rho)
        nu_in   = float(nu)

        Fp = float(forward + shift)
        Kp = float(strike  + shift)
        if Fp <= 0.0 or Kp <= 0.0:
            return 0.0 if self.method != "bottom-up" else []

        if self.method == "bottom-up":
            if self.corr_surf is None:
                raise ValueError("corr_surf must be provided for bottom-up method")
            if self.product is None:
                raise ValueError("product must be provided for bottom-up method")

            sabr_pricer = BottomUpLognormalSABR(
                f=forward,
                shift=shift,
                expiry=expiry,
                tenor=tenor,
                model=self.model,
                corr_surf=self.corr_surf,
                product=self.product,
            )
        elif self.method == "top-down":
            sabr_pricer = TimeDecayLognormalSABR(
                f=forward,
                shift=shift,
                t=expiry + tenor,
                vAtmN=normalVol,
                beta=beta_in,
                rho=rho_in,
                volVol=nu_in,
                volDecaySpeed=decay,
                decayStart=expiry,
            )
        else:
            sabr_pricer = Hagan2002LognormalSABR(
                f=forward,
                shift=shift,
                t=expiry,
                v_atm_n=normalVol,
                beta=beta_in,
                rho=rho_in,
                volvol=nu_in,
            )

        alpha = float(sabr_pricer.alpha())
        beta_eff = float(sabr_pricer.beta)
        rho_eff  = float(sabr_pricer.rho)
        nu_eff   = float(sabr_pricer.volvol)

        T = float(sabr_pricer.t)
        if alpha <= 0.0 or T <= 0.0:
            return 0.0 if self.method != "bottom-up" else []

        sigmaK = float(sabr_pricer.lognormal_vol(strike))
        if sigmaK <= 0.0:
            return 0.0 if self.method != "bottom-up" else []

        # Compute dsigma/dalpha and dsigma/dbeta
        one_minus_beta = 1.0 - beta_eff
        L = float(np.log(Fp / Kp))
        lnFK = float(np.log(Fp * Kp))

        fkbeta = float((Fp * Kp) ** (1.0 - beta_eff))
        sqrt_fkbeta = float(np.sqrt(fkbeta))

        A = (one_minus_beta ** 2) * (alpha ** 2) / (24.0 * fkbeta)
        B = 0.25 * rho_eff * beta_eff * nu_eff * alpha / sqrt_fkbeta
        C = (2.0 - 3.0 * rho_eff * rho_eff) * (nu_eff ** 2) / 24.0

        V = (one_minus_beta ** 2) * (L ** 2) / 24.0
        W = (one_minus_beta ** 4) * (L ** 4) / 1920.0

        H = 1.0 + (A + B + C) * T
        Q = 1.0 + V + W

        dA_dalpha = (one_minus_beta ** 2) * alpha / (12.0 * fkbeta)
        dB_dalpha = B / alpha
        dH_dalpha = (dA_dalpha + dB_dalpha) * T

        z = nu_eff * sqrt_fkbeta * L / alpha
        eps = 1e-7

        dz_dalpha = -z / alpha
        sqrt_term = float(np.sqrt(1.0 - 2.0 * rho_eff * z + z * z))
        x = float(np.log((sqrt_term + z - rho_eff) / (1.0 - rho_eff)))
        dx_dz = 1.0 / sqrt_term
        dx_dalpha = dx_dz * dz_dalpha

        # (d/dbeta)|alpha
        delta = 1.0 - beta_eff
        lnG = lnFK

        dsqrt_fkbeta_dbeta = -0.5 * sqrt_fkbeta * lnG
        dz_dbeta = -0.5 * lnG * z
        dA_dbeta = (alpha * alpha / (24.0 * fkbeta)) * (-2.0 * delta + (delta * delta) * lnG)

        constB = 0.25 * rho_eff * nu_eff * alpha
        dB_dbeta = (constB / sqrt_fkbeta) * (1.0 + 0.5 * beta_eff * lnG)
        dC_dbeta = 0.0
        dV_dbeta = -(delta * (L * L)) / 12.0

        L4 = (L * L) * (L * L)
        dW_dbeta = -(delta * delta * delta) * L4 / 480.0

        dH_dbeta = (dA_dbeta + dB_dbeta + dC_dbeta) * T
        dQ_dbeta = dV_dbeta + dW_dbeta

        dx_dbeta = dx_dz * dz_dbeta

        if abs(z) > eps:
            Numer = alpha * z * H
            Denom = sqrt_fkbeta * Q * x

            dNumer_dalpha = alpha * z * dH_dalpha
            dDenom_dalpha = sqrt_fkbeta * Q * dx_dalpha
            dsigma_dalpha = 0.0 if abs(Denom) <= 1e-18 else float((dNumer_dalpha * Denom - Numer * dDenom_dalpha) / (Denom * Denom))

            dNumer_dbeta = alpha * dz_dbeta * H + alpha * z * dH_dbeta
            dDenom_dbeta = dsqrt_fkbeta_dbeta * Q * x + sqrt_fkbeta * dQ_dbeta * x + sqrt_fkbeta * Q * dx_dbeta
            dsigma_dbeta_partial = 0.0 if abs(Denom) <= 1e-18 else float((dNumer_dbeta * Denom - Numer * dDenom_dbeta) / (Denom * Denom))
        else:
            Numer = alpha * H
            Denom = sqrt_fkbeta * Q

            dNumer_dalpha = H + alpha * dH_dalpha
            dsigma_dalpha = 0.0 if abs(Denom) <= 1e-18 else float(dNumer_dalpha / Denom)

            dNumer_dbeta = alpha * dH_dbeta
            dDenom_dbeta = dsqrt_fkbeta_dbeta * Q + sqrt_fkbeta * dQ_dbeta
            dsigma_dbeta_partial = 0.0 if abs(Denom) <= 1e-18 else float((dNumer_dbeta * Denom - Numer * dDenom_dbeta) / (Denom * Denom))

        # dalpha/dbeta from ATM constraint (holding normalVol pillar fixed)
        # Plain/top-down: scalar. Bottom-up: segment list.
        def _dalpha_dbeta_from_atm(alpha0: float, T0: float, vn0: float, b0: float, r0: float, nu0: float) -> float:
            # Holds sigma_ln_atm fixed (normalVol pillar separate)
            if T0 <= 0.0:
                return 0.0

            lnF = float(np.log(Fp))
            f_power = float(Fp ** (b0 - 1.0))  # = exp((b0-1)*lnF)
            delta = 1.0 - b0

            g = float(1.0 + T0 * (nu0 ** 2) * (2.0 - 3.0 * r0 * r0) / 24.0)

            a3 = float(T0 * (f_power ** 3) * (delta ** 2) / 24.0)
            a2 = float(T0 * (f_power ** 2) * (r0 * b0 * nu0) / 4.0)
            a1 = float(g * f_power)

            dP_dalpha = float(3.0 * a3 * alpha0 * alpha0 + 2.0 * a2 * alpha0 + a1)
            if abs(dP_dalpha) <= 1e-18:
                return 0.0

            da3_db = float((T0 / 24.0) * (f_power ** 3) * (-2.0 * delta + 3.0 * (delta ** 2) * lnF))
            da2_db = float((T0 * r0 * nu0 / 4.0) * (f_power ** 2) * (1.0 + 2.0 * b0 * lnF))
            da1_db = float(a1 * lnF)
            dP_dbeta = float(da3_db * (alpha0 ** 3) + da2_db * (alpha0 ** 2) + da1_db * alpha0)

            return float(-dP_dbeta / dP_dalpha)


        #TOP-DOWN 
        if self.method == "top-down":
            pr_base = Hagan2002LognormalSABR(
                f=forward,
                shift=shift,
                t=float(expiry + tenor),
                v_atm_n=normalVol,
                beta=beta_in,
                rho=rho_in,
                volvol=nu_in,
            )
            alpha_base = float(pr_base.alpha())
            c = float(alpha / alpha_base) if alpha_base > 0.0 else 0.0

            dalpha_base_dbeta = _dalpha_dbeta_from_atm(alpha_base, float(expiry + tenor), float(normalVol), beta_in, rho_in, nu_in)
            dalpha_eff_dbeta = float(c * dalpha_base_dbeta)

            return float(dsigma_dbeta_partial + dsigma_dalpha * dalpha_eff_dbeta)

        # BOTTOM-UP
        if self.method == "bottom-up":

            dates = self.product.get_fixing_schedule()
            if dates is None or len(dates) < 2:
                return []

            dc = self.product.dayCounter

            Tis = [float(dc.yearFraction(d0, d1)) for d0, d1 in zip(dates, dates[1:])]
            total = float(sum(Tis))
            if total <= 0.0:
                return []

            weights = [float(Ti / total) for Ti in Tis]
            offsets = np.cumsum([0.0] + Tis[:-1])
            Tstarts = [float(expiry) + float(x) for x in offsets]
            Tends   = [Ts + Ti for Ts, Ti in zip(Tstarts, Tis)]

            use_end_time = (getattr(self.product, "oisIndex_", None) is not None)
            Texp = Tends if use_end_time else Tstarts

            Tbar = float(sum(w * T for w, T in zip(weights, Texp)))
            time_scales = [float(np.sqrt(T / Tbar)) for T in Texp]

            t_first = float(Texp[0])
            t_last  = float(Texp[-1])
            gamma_1N = float(self.corr_surf.corr(t_first, t_last))

            N = len(Tis)
            if N <= 1:
                gamma_bar = 1.0
            else:
                mu = (1.0 - gamma_1N) / (N - 1)
                s = 0.0
                for d in range(N):
                    val = 1.0 - mu * d
                    if val < 0.0:
                        val = 0.0
                    cnt = N if d == 0 else 2.0 * (N - d)
                    s += cnt * val
                gamma_bar = float(s / (N * N))

            sqrt_g = float(np.sqrt(gamma_bar))

            # Build base segment params + segment alphas
            vns, bs, nus, rhos, alphas = [], [], [], [], []
            for Ti, Te in zip(Tis, Texp):
                vn_i, b_i, nu_i, rho_i, _, _ = self.model.get_sabr_parameters(
                    index=index, expiry=float(Te), tenor=float(Ti), product_type=None
                )
                vn_i = float(vn_i); b_i = float(b_i); nu_i = float(nu_i); rho_i = float(rho_i)

                pr = Hagan2002LognormalSABR(
                    f=float(forward), shift=float(shift), t=float(Te),
                    v_atm_n=vn_i, beta=b_i, rho=rho_i, volvol=nu_i
                )

                vns.append(vn_i); bs.append(b_i); nus.append(nu_i); rhos.append(rho_i)
                alphas.append(float(pr.alpha()))

            alpha_star = float(sqrt_g * sum(w * a * s for w, a, s in zip(weights, alphas, time_scales)))
            beta_star  = float(sum(w * b for w, b in zip(weights, bs)))
            nu_star    = float(sum(w * nu * s for w, nu, s in zip(weights, nus, time_scales)))
            rho_star   = float((1.0 / sqrt_g) * sum(w * r for w, r in zip(weights, rhos)))

            # Use same Teff as pricer does (sabr_pricer.t)
            Teff = float(sabr_pricer.t)
            Fp = float(forward + shift)
            Kp = float(strike + shift)

            h = 1e-4
            out = []
            for i, (Ti, Te, w_i, s_i) in enumerate(zip(Tis, Texp, weights, time_scales)):
                b0 = bs[i]

                b_plus = min(1.0, b0 + h)
                b_minus = max(0.0, b0 - h)

                pr_plus = Hagan2002LognormalSABR(
                    f=float(forward), shift=float(shift), t=float(Te),
                    v_atm_n=vns[i], beta=b_plus, rho=rhos[i], volvol=nus[i]
                )
                pr_minus = Hagan2002LognormalSABR(
                    f=float(forward), shift=float(shift), t=float(Te),
                    v_atm_n=vns[i], beta=b_minus, rho=rhos[i], volvol=nus[i]
                )

                a_plus = float(pr_plus.alpha())
                a_minus = float(pr_minus.alpha())

                alpha_plus = alpha_star + sqrt_g * w_i * s_i * (a_plus - alphas[i])
                alpha_minus = alpha_star + sqrt_g * w_i * s_i * (a_minus - alphas[i])

                beta_plus = beta_star + w_i * (b_plus - b0)
                beta_minus = beta_star + w_i * (b_minus - b0)

                sig_plus = float(lognormal_vol(Kp, Fp, Teff, alpha_plus, beta_plus, rho_star, nu_star))
                sig_minus = float(lognormal_vol(Kp, Fp, Teff, alpha_minus, beta_minus, rho_star, nu_star))

                denom = (b_plus - b_minus)
                dSig = (sig_plus - sig_minus) / denom if abs(denom) > 0.0 else 0.0

                out.append((float(Te), float(Ti), float(dSig)))

            return out

        #PLAIN
        dalpha_dbeta = _dalpha_dbeta_from_atm(alpha, float(expiry), float(normalVol), beta_in, rho_in, nu_in)
        return float(dsigma_dbeta_partial + dsigma_dalpha * dalpha_dbeta)


    def dVol_dNu(
        self,
        *,
        index: str,
        expiry: float,
        tenor: float,
        forward: float,
        strike: float,
        normalVol: float,
        beta: float,
        nu: float,
        rho: float,
        shift: float,
        decay: float = 0.0,
    ):

        beta_in = float(beta)
        rho_in  = float(rho)
        nu_in   = float(nu)

        Fp = float(forward + shift)
        Kp = float(strike  + shift)
        if Fp <= 0.0 or Kp <= 0.0:
            return 0.0 if self.method != "bottom-up" else []

        if self.method == "bottom-up":
            if self.corr_surf is None:
                raise ValueError("corr_surf must be provided for bottom-up method")
            if self.product is None:
                raise ValueError("product must be provided for bottom-up method")

            sabr_pricer = BottomUpLognormalSABR(
                f=forward,
                shift=shift,
                expiry=expiry,
                tenor=tenor,
                model=self.model,
                corr_surf=self.corr_surf,
                product=self.product,
            )
        elif self.method == "top-down":
            sabr_pricer = TimeDecayLognormalSABR(
                f=forward,
                shift=shift,
                t=expiry + tenor,
                vAtmN=normalVol,
                beta=beta_in,
                rho=rho_in,
                volVol=nu_in,
                volDecaySpeed=decay,
                decayStart=expiry,
            )
        else:
            sabr_pricer = Hagan2002LognormalSABR(
                f=forward,
                shift=shift,
                t=expiry,
                v_atm_n=normalVol,
                beta=beta_in,
                rho=rho_in,
                volvol=nu_in,
            )

        alpha = float(sabr_pricer.alpha())
        beta_eff = float(sabr_pricer.beta)
        rho_eff  = float(sabr_pricer.rho)
        nu_eff   = float(sabr_pricer.volvol)

        T = float(sabr_pricer.t)
        if alpha <= 0.0 or T <= 0.0:
            return 0.0 if self.method != "bottom-up" else []

        sigmaK = float(sabr_pricer.lognormal_vol(strike))
        if sigmaK <= 0.0:
            return 0.0 if self.method != "bottom-up" else []

        # Compute dsigma/dalpha and dsigma/dnu
        one_minus_beta = 1.0 - beta_eff
        L = float(np.log(Fp / Kp))

        fkbeta = float((Fp * Kp) ** (1.0 - beta_eff))
        sqrt_fkbeta = float(np.sqrt(fkbeta))

        A = (one_minus_beta ** 2) * (alpha ** 2) / (24.0 * fkbeta)
        B = 0.25 * rho_eff * beta_eff * nu_eff * alpha / sqrt_fkbeta
        C = (2.0 - 3.0 * rho_eff * rho_eff) * (nu_eff ** 2) / 24.0

        V = (one_minus_beta ** 2) * (L ** 2) / 24.0
        W = (one_minus_beta ** 4) * (L ** 4) / 1920.0

        H = 1.0 + (A + B + C) * T
        Q = 1.0 + V + W

        # dsigma/dalpha
        dA_dalpha = (one_minus_beta ** 2) * alpha / (12.0 * fkbeta)
        dB_dalpha = B / alpha
        dH_dalpha = (dA_dalpha + dB_dalpha) * T

        z = nu_eff * sqrt_fkbeta * L / alpha
        eps = 1e-7

        dz_dalpha = -z / alpha

        sqrt_term = float(np.sqrt(1.0 - 2.0 * rho_eff * z + z * z))
        x = float(np.log((sqrt_term + z - rho_eff) / (1.0 - rho_eff)))
        dx_dz = 1.0 / sqrt_term
        dx_dalpha = dx_dz * dz_dalpha

        # (d/dnu_eff)|alpha
        dz_dnu = float(sqrt_fkbeta * L / alpha) 
        dB_dnu = float(0.25 * rho_eff * beta_eff * alpha / sqrt_fkbeta)  
        dC_dnu = float((2.0 - 3.0 * rho_eff * rho_eff) * nu_eff / 12.0)   
        dH_dnu = float((dB_dnu + dC_dnu) * T)                             
        dx_dnu = float(dx_dz * dz_dnu)

        if abs(z) > eps:
            Numer = alpha * z * H
            Denom = sqrt_fkbeta * Q * x

            dNumer_dalpha = alpha * z * dH_dalpha
            dDenom_dalpha = sqrt_fkbeta * Q * dx_dalpha
            dsigma_dalpha = 0.0 if abs(Denom) <= 1e-18 else float((dNumer_dalpha * Denom - Numer * dDenom_dalpha) / (Denom * Denom))

            dNumer_dnu = alpha * dz_dnu * H + alpha * z * dH_dnu
            dDenom_dnu = sqrt_fkbeta * Q * dx_dnu
            dsigma_dnu_partial = 0.0 if abs(Denom) <= 1e-18 else float((dNumer_dnu * Denom - Numer * dDenom_dnu) / (Denom * Denom))
        else:
            Numer = alpha * H
            Denom = sqrt_fkbeta * Q

            dNumer_dalpha = H + alpha * dH_dalpha
            dsigma_dalpha = 0.0 if abs(Denom) <= 1e-18 else float(dNumer_dalpha / Denom)

            dsigma_dnu_partial = 0.0 if abs(Denom) <= 1e-18 else float((alpha * dH_dnu) / Denom)

        # dalpha/dnu from ATM constraint (holding normalVol pillar fixed)
        # Plain: alpha implied at T=expiry.
        # Top-down: alpha_eff depends on base alpha + time-decay H(nu) AND nu_eff(nu).
        # Bottom-up: segment-level dalpha_i/dnu_i.

        lnF = float(np.log(Fp))
        f_power_plain = float(Fp ** (beta_in - 1.0))
        one_minus_beta_in = 1.0 - beta_in

        # TOP-DOWN
        if self.method == "top-down":
            te = float(expiry + tenor)   
            ts = float(expiry)
            k  = float(decay)

            pr_base = Hagan2002LognormalSABR(
                f=forward, shift=shift, t=te,
                v_atm_n=normalVol, beta=beta_in, rho=rho_in, volvol=nu_in
            )
            alpha_base = float(pr_base.alpha())
            if alpha_base <= 0.0 or te <= 0.0:
                return 0.0

            f_power = float(Fp ** (beta_in - 1.0))
            c_rho = float(2.0 - 3.0 * rho_in * rho_in)
            g = float(1.0 + te * (nu_in ** 2) * c_rho / 24.0)

            a3 = float(te * (f_power ** 3) * (one_minus_beta_in ** 2) / 24.0)
            a2 = float(te * (f_power ** 2) * (rho_in * beta_in * nu_in) / 4.0)
            a1 = float(g * f_power)

            dP_dalpha = float(3.0 * a3 * alpha_base * alpha_base + 2.0 * a2 * alpha_base + a1)
            dalpha_base_dnu = 0.0
            if abs(dP_dalpha) > 1e-18:
                da2_dnu = float(te * (f_power ** 2) * (rho_in * beta_in) / 4.0)
                da1_dnu = float(f_power * te * nu_in * c_rho / 12.0)
                dP_dnu  = float(da2_dnu * (alpha_base ** 2) + da1_dnu * alpha_base)
                dalpha_base_dnu = float(-dP_dnu / dP_dalpha)

            # TimeDecay mapping pieces
            tau = float(2.0 * k * ts + te)
            if tau <= 0.0 or te <= 0.0:
                return 0.0

            gammaFirstTerm = tau * (2.0 * tau**3 + te**3 + (4.0*k*k - 2.0*k)*ts**3 + 6.0*k*ts**2*te)
            gammaSecondTerm = (3.0 * k * rho_in * rho_in * (te - ts)**2 * (3.0 * tau**2 - te**2 + 5.0*k*ts**2 + 4.0*ts*te))
            gamma = float(gammaFirstTerm / ((4.0*k + 3.0) * (2.0*k + 1.0)) + gammaSecondTerm / ((4.0*k + 3.0) * (3.0*k + 2.0)**2))
            
            nu_hat2_coeff = float(gamma * (2.0*k + 1.0) / (tau**3 * te)) if gamma > 0.0 else 0.0
            dnu_eff_dnu = float(np.sqrt(nu_hat2_coeff))  # d(nu_eff)/d(nu_in)

            A0 = float((tau**2 + 2.0*k*ts**2 + te**2) / (2.0*te*tau*(k + 1.0))) if (k + 1.0) != 0.0 else 0.0
            H_td = float((nu_in ** 2) * (A0 - nu_hat2_coeff))
            dHtd_dnu = float(2.0 * nu_in * (A0 - nu_hat2_coeff))

            # alpha_eff derivative wrt nu_in:
            dalpha_eff_dnu = 0.0
            if alpha > 0.0 and alpha_base > 0.0:
                dalpha_eff_dnu = float(alpha * (dalpha_base_dnu / alpha_base + 0.25 * te * dHtd_dnu))

            # Total: sigma depends on nu_eff and alpha_eff
            return float(dsigma_dnu_partial * dnu_eff_dnu + dsigma_dalpha * dalpha_eff_dnu)

        # BOTTOM-UP
        if self.method == "bottom-up":

            dates = self.product.get_fixing_schedule()
            if dates is None or len(dates) < 2:
                return []

            dc = self.product.dayCounter

            Tis = [float(dc.yearFraction(d0, d1)) for d0, d1 in zip(dates, dates[1:])]
            total = float(sum(Tis))
            if total <= 0.0 or any(Ti <= 0.0 for Ti in Tis):
                return []

            weights = [float(Ti / total) for Ti in Tis]
            offsets = np.cumsum([0.0] + Tis[:-1])
            Tstarts = [float(expiry) + float(x) for x in offsets]
            Tends   = [Ts + Ti for Ts, Ti in zip(Tstarts, Tis)]

            use_end_time = (getattr(self.product, "oisIndex_", None) is not None)
            Texp = Tends if use_end_time else Tstarts

            Tbar = float(sum(w * T for w, T in zip(weights, Texp)))
            if not np.isfinite(Tbar) or Tbar <= 0.0:
                return []

            time_scales = [float(np.sqrt(T / Tbar)) for T in Texp]

            t_first = float(Texp[0])
            t_last  = float(Texp[-1])
            gamma_1N = float(self.corr_surf.corr(t_first, t_last))

            N = len(Tis)
            if N <= 1:
                gamma_bar = 1.0
            else:
                mu = (1.0 - gamma_1N) / (N - 1)
                s = 0.0
                for d in range(N):
                    val = 1.0 - mu * d
                    if val < 0.0:
                        val = 0.0
                    cnt = N if d == 0 else 2.0 * (N - d)
                    s += cnt * val
                gamma_bar = float(s / (N * N))

            sqrt_g = float(np.sqrt(gamma_bar))
            if not (0.0 < sqrt_g <= 1.0):
                return []

            # Base segment params + segment alphas
            vns, bs, nus, rhos, alphas = [], [], [], [], []
            for Ti, Te in zip(Tis, Texp):
                vn_i, b_i, nu_i, rho_i, _, _ = self.model.get_sabr_parameters(
                    index=index, expiry=float(Te), tenor=float(Ti), product_type=None
                )
                vn_i = float(vn_i); b_i = float(b_i); nu_i = float(nu_i); rho_i = float(rho_i)

                pr = Hagan2002LognormalSABR(
                    f=float(forward), shift=float(shift), t=float(Te),
                    v_atm_n=vn_i, beta=b_i, rho=rho_i, volvol=nu_i
                )

                vns.append(vn_i); bs.append(b_i); nus.append(nu_i); rhos.append(rho_i)
                alphas.append(float(pr.alpha()))

            alpha_star = float(sqrt_g * sum(w * a * s for w, a, s in zip(weights, alphas, time_scales)))
            beta_star  = float(sum(w * b for w, b in zip(weights, bs)))
            nu_star    = float(sum(w * nu * s for w, nu, s in zip(weights, nus, time_scales)))
            rho_star   = float((1.0 / sqrt_g) * sum(w * r for w, r in zip(weights, rhos)))

            Teff = float(sabr_pricer.t)
            Fps = float(forward + shift)
            Kps = float(strike + shift)

            h = 1e-4
            out = []

            for i, (Ti, Te, w_i, s_i) in enumerate(zip(Tis, Texp, weights, time_scales)):
                nu0 = float(nus[i])

                nu_plus = nu0 + h
                nu_minus = max(0.0, nu0 - h)

                # alpha_i changes when nu_i changes
                pr_plus = Hagan2002LognormalSABR(
                    f=float(forward), shift=float(shift), t=float(Te),
                    v_atm_n=vns[i], beta=bs[i], rho=rhos[i], volvol=nu_plus
                )
                pr_minus = Hagan2002LognormalSABR(
                    f=float(forward), shift=float(shift), t=float(Te),
                    v_atm_n=vns[i], beta=bs[i], rho=rhos[i], volvol=nu_minus
                )

                a_plus = float(pr_plus.alpha())
                a_minus = float(pr_minus.alpha())

                alpha_plus = alpha_star + sqrt_g * w_i * s_i * (a_plus - alphas[i])
                alpha_minus = alpha_star + sqrt_g * w_i * s_i * (a_minus - alphas[i])

                nu_plus_star = nu_star + w_i * s_i * (nu_plus - nu0)
                nu_minus_star = nu_star + w_i * s_i * (nu_minus - nu0)

                sig_plus = float(lognormal_vol(Kps, Fps, Teff, alpha_plus, beta_star, rho_star, nu_plus_star))
                sig_minus = float(lognormal_vol(Kps, Fps, Teff, alpha_minus, beta_star, rho_star, nu_minus_star))

                denom = (nu_plus - nu_minus)
                dSig = (sig_plus - sig_minus) / denom if abs(denom) > 0.0 else 0.0

                out.append((float(Te), float(Ti), float(dSig)))

            return out

        #PLAIN
        f_power = float(Fp ** (beta_in - 1.0))
        c_rho = float(2.0 - 3.0 * rho_in * rho_in)
        g = float(1.0 + float(expiry) * (nu_in ** 2) * c_rho / 24.0)

        a3 = float(float(expiry) * (f_power ** 3) * (one_minus_beta_in ** 2) / 24.0)
        a2 = float(float(expiry) * (f_power ** 2) * (rho_in * beta_in * nu_in) / 4.0)
        a1 = float(g * f_power)

        dP_dalpha = float(3.0 * a3 * alpha * alpha + 2.0 * a2 * alpha + a1)

        dalpha_dnu = 0.0
        if abs(dP_dalpha) > 1e-18:
            da2_dnu = float(float(expiry) * (f_power ** 2) * (rho_in * beta_in) / 4.0)
            da1_dnu = float(f_power * float(expiry) * nu_in * c_rho / 12.0)
            dP_dnu  = float(da2_dnu * (alpha ** 2) + da1_dnu * alpha)
            dalpha_dnu = float(-dP_dnu / dP_dalpha)

        return float(dsigma_dnu_partial + dsigma_dalpha * dalpha_dnu)
    
    def dVol_dRho(
        self,
        *,
        index: str,
        expiry: float,
        tenor: float,
        forward: float,
        strike: float,
        normalVol: float,
        beta: float,
        nu: float,
        rho: float,
        shift: float,
        decay: float = 0.0,
    ):

        beta_in = float(beta)
        rho_in  = float(rho)
        nu_in   = float(nu)

        Fp = float(forward + shift)
        Kp = float(strike  + shift)
        if Fp <= 0.0 or Kp <= 0.0:
            return 0.0 if self.method != "bottom-up" else []

        if self.method == "bottom-up":
            if self.corr_surf is None:
                raise ValueError("corr_surf must be provided for bottom-up method")
            if self.product is None:
                raise ValueError("product must be provided for bottom-up method")

            sabr_pricer = BottomUpLognormalSABR(
                f=forward,
                shift=shift,
                expiry=expiry,
                tenor=tenor,
                model=self.model,
                corr_surf=self.corr_surf,
                product=self.product,
            )
        elif self.method == "top-down":
            sabr_pricer = TimeDecayLognormalSABR(
                f=forward,
                shift=shift,
                t=expiry + tenor,
                vAtmN=normalVol,
                beta=beta_in,
                rho=rho_in,
                volVol=nu_in,
                volDecaySpeed=decay,
                decayStart=expiry,
            )
        else:
            sabr_pricer = Hagan2002LognormalSABR(
                f=forward,
                shift=shift,
                t=expiry,
                v_atm_n=normalVol,
                beta=beta_in,
                rho=rho_in,
                volvol=nu_in,
            )

        alpha = float(sabr_pricer.alpha())
        beta_eff = float(sabr_pricer.beta)
        rho_eff  = float(sabr_pricer.rho)
        nu_eff   = float(sabr_pricer.volvol)

        T = float(sabr_pricer.t)
        if alpha <= 0.0 or T <= 0.0:
            return 0.0 if self.method != "bottom-up" else []

        sigmaK = float(sabr_pricer.lognormal_vol(strike))
        if sigmaK <= 0.0:
            return 0.0 if self.method != "bottom-up" else []

        # Compute dsigma/dalpha, (dsigma/drho)|alpha,nu, and (dsigma/dnu)|alpha,rho
        one_minus_beta = 1.0 - beta_eff
        L = float(np.log(Fp / Kp))

        fkbeta = float((Fp * Kp) ** (1.0 - beta_eff))
        sqrt_fkbeta = float(np.sqrt(fkbeta))

        A = (one_minus_beta ** 2) * (alpha ** 2) / (24.0 * fkbeta)
        B = 0.25 * rho_eff * beta_eff * nu_eff * alpha / sqrt_fkbeta
        C = (2.0 - 3.0 * rho_eff * rho_eff) * (nu_eff ** 2) / 24.0

        V = (one_minus_beta ** 2) * (L ** 2) / 24.0
        W = (one_minus_beta ** 4) * (L ** 4) / 1920.0

        H = 1.0 + (A + B + C) * T
        Q = 1.0 + V + W

        z = nu_eff * sqrt_fkbeta * L / alpha
        eps = 1e-7

        sqrt_term = float(np.sqrt(1.0 - 2.0 * rho_eff * z + z * z))
        x = float(np.log((sqrt_term + z - rho_eff) / (1.0 - rho_eff)))
        dx_dz = 1.0 / sqrt_term

        # dsigma/dalpha
        dA_dalpha = (one_minus_beta ** 2) * alpha / (12.0 * fkbeta)
        dB_dalpha = B / alpha
        dH_dalpha = float((dA_dalpha + dB_dalpha) * T)

        dz_dalpha = -z / alpha
        dx_dalpha = float(dx_dz * dz_dalpha)

        # (dsigma/dnu_eff)|alpha,rho
        dz_dnu = float(sqrt_fkbeta * L / alpha)
        dB_dnu = float(0.25 * rho_eff * beta_eff * alpha / sqrt_fkbeta)
        dC_dnu = float((2.0 - 3.0 * rho_eff * rho_eff) * nu_eff / 12.0)
        dH_dnu = float((dB_dnu + dC_dnu) * T)
        dx_dnu = float(dx_dz * dz_dnu)

        # (dsigma/drho_eff)|alpha,nu
        dB_drho = float(0.25 * beta_eff * nu_eff * alpha / sqrt_fkbeta)
        dC_drho = float(-(rho_eff * (nu_eff ** 2)) / 4.0)
        dH_drho = float((dB_drho + dC_drho) * T)

        # x(rho): z fixed w.r.t rho
        if abs(z) > eps:
            A_x = float(sqrt_term + z - rho_eff)
            if abs(A_x) <= 1e-18 or abs(1.0 - rho_eff) <= 1e-18:
                return 0.0 if self.method != "bottom-up" else []

            dsqrt_drho = float(-z / sqrt_term)             
            dA_x_drho  = float(dsqrt_drho - 1.0)
            dx_drho = float(dA_x_drho / A_x + 1.0 / (1.0 - rho_eff))
            Numer = alpha * z * H
            Denom = sqrt_fkbeta * Q * x

            # dsigma/dalpha
            dNumer_dalpha = alpha * z * dH_dalpha
            dDenom_dalpha = sqrt_fkbeta * Q * dx_dalpha
            dsigma_dalpha = 0.0 if abs(Denom) <= 1e-18 else float((dNumer_dalpha * Denom - Numer * dDenom_dalpha) / (Denom * Denom))

            # (dsigma/dnu_eff)|alpha,rho
            dNumer_dnu = alpha * dz_dnu * H + alpha * z * dH_dnu
            dDenom_dnu = sqrt_fkbeta * Q * dx_dnu
            dsigma_dnu_partial = 0.0 if abs(Denom) <= 1e-18 else float((dNumer_dnu * Denom - Numer * dDenom_dnu) / (Denom * Denom))

            # (dsigma/drho_eff)|alpha,nu
            dNumer_drho = alpha * z * dH_drho
            dDenom_drho = sqrt_fkbeta * Q * dx_drho
            dsigma_drho_partial = 0.0 if abs(Denom) <= 1e-18 else float((dNumer_drho * Denom - Numer * dDenom_drho) / (Denom * Denom))
        else:
            Numer = alpha * H
            Denom = sqrt_fkbeta * Q

            dNumer_dalpha = H + alpha * dH_dalpha
            dsigma_dalpha = 0.0 if abs(Denom) <= 1e-18 else float(dNumer_dalpha / Denom)

            dsigma_dnu_partial  = 0.0 if abs(Denom) <= 1e-18 else float((alpha * dH_dnu) / Denom)
            dsigma_drho_partial = 0.0 if abs(Denom) <= 1e-18 else float((alpha * dH_drho) / Denom)

        # Plain / top-down: need dalpha/dRho (ATM constraint holding normalVol fixed)
        # Bottom-up: segment-level dalpha_i/dRho_i

        # TOP-DOWN
        if self.method == "top-down":
            te = float(expiry + tenor)
            ts = float(expiry)
            k  = float(decay)

            pr_base = Hagan2002LognormalSABR(
                f=forward, shift=shift, t=te,
                v_atm_n=normalVol, beta=beta_in, rho=rho_in, volvol=nu_in
            )
            alpha_base = float(pr_base.alpha())
            if alpha_base <= 0.0 or te <= 0.0:
                return 0.0

            f_power = float(Fp ** (beta_in - 1.0))
            c_rho = float(2.0 - 3.0 * rho_in * rho_in)
            g = float(1.0 + te * (nu_in ** 2) * c_rho / 24.0)

            a3 = float(te * (f_power ** 3) * ((1.0 - beta_in) ** 2) / 24.0)
            a2 = float(te * (f_power ** 2) * (rho_in * beta_in * nu_in) / 4.0)
            a1 = float(g * f_power)

            dP_dalpha = float(3.0 * a3 * alpha_base * alpha_base + 2.0 * a2 * alpha_base + a1)

            dalpha_base_drho = 0.0
            if abs(dP_dalpha) > 1e-18:
                da2_drho = float(te * (f_power ** 2) * (beta_in * nu_in) / 4.0)
                da1_drho = float(-f_power * te * (nu_in ** 2) * rho_in / 4.0)
                dP_drho  = float(da2_drho * (alpha_base ** 2) + da1_drho * alpha_base)
                dalpha_base_drho = float(-dP_drho / dP_dalpha)

            tau = float(2.0 * k * ts + te)
            if tau <= 0.0:
                return 0.0

            gammaFirstTerm = tau * (2.0 * tau**3 + te**3 + (4.0*k*k - 2.0*k)*ts**3 + 6.0*k*ts**2*te)
            denom0 = float((4.0*k + 3.0) * (2.0*k + 1.0))
            denom2 = float((4.0*k + 3.0) * (3.0*k + 2.0)**2)

            G0 = float(gammaFirstTerm / denom0)

            G2_num = float(3.0 * k * (te - ts)**2 * (3.0 * tau**2 - te**2 + 5.0*k*ts**2 + 4.0*ts*te))
            G2 = float(G2_num / denom2)

            gamma = float(G0 + G2 * (rho_in ** 2))

            dgamma_drho = float(2.0 * rho_in * G2)

            Cnu = float((2.0*k + 1.0) / (tau**3 * te))
            nuHat2 = float((nu_in ** 2) * gamma * Cnu)
            nuHat2 = max(nuHat2, 0.0)

            dnuHat2_drho = float((nu_in ** 2) * Cnu * dgamma_drho)

            nu_eff_td = float(np.sqrt(nuHat2))
            dnu_eff_drho = 0.0
            if nu_eff_td > 0.0:
                dnu_eff_drho = float(0.5 * dnuHat2_drho / nu_eff_td)

            dHtd_drho = float(-dnuHat2_drho)
            dalpha_eff_drho = float(alpha * (dalpha_base_drho / alpha_base + 0.25 * te * dHtd_drho))
            M = float((3.0 * tau * tau + 2.0 * k * ts * ts + te * te) / (6.0 * k + 4.0))
            sqrt_gamma = float(np.sqrt(gamma))
            rho_eff_td = float(rho_in * M / sqrt_gamma)

            drho_eff_drho = float(M / sqrt_gamma - (rho_in * M) * 0.5 * dgamma_drho / (gamma * sqrt_gamma))

            return float(
                dsigma_drho_partial * drho_eff_drho
                + dsigma_dnu_partial * dnu_eff_drho
                + dsigma_dalpha * dalpha_eff_drho
            )

        # BOTTOM-UP
        if self.method == "bottom-up":
            dates = self.product.get_fixing_schedule()
            if dates is None or len(dates) < 2:
                return []

            dc = self.product.dayCounter

            Tis = [float(dc.yearFraction(d0, d1)) for d0, d1 in zip(dates, dates[1:])]
            total = float(sum(Tis))
            if total <= 0.0 or any(Ti <= 0.0 for Ti in Tis):
                return []

            weights = [float(Ti / total) for Ti in Tis]
            offsets = np.cumsum([0.0] + Tis[:-1])
            Tstarts = [float(expiry) + float(x) for x in offsets]
            Tends   = [Ts + Ti for Ts, Ti in zip(Tstarts, Tis)]

            use_end_time = (getattr(self.product, "oisIndex_", None) is not None)
            Texp = Tends if use_end_time else Tstarts

            Tbar = float(sum(w * T for w, T in zip(weights, Texp)))
            if not np.isfinite(Tbar) or Tbar <= 0.0:
                return []

            time_scales = [float(np.sqrt(T / Tbar)) for T in Texp]

            t_first = float(Texp[0])
            t_last  = float(Texp[-1])
            gamma_1N = float(self.corr_surf.corr(t_first, t_last))

            N = len(Tis)
            if N <= 1:
                gamma_bar = 1.0
            else:
                mu = (1.0 - gamma_1N) / (N - 1)
                s = 0.0
                for d in range(N):
                    val = 1.0 - mu * d
                    if val < 0.0:
                        val = 0.0
                    cnt = N if d == 0 else 2.0 * (N - d)
                    s += cnt * val
                gamma_bar = float(s / (N * N))

            sqrt_g = float(np.sqrt(gamma_bar))
            if not (0.0 < sqrt_g <= 1.0):
                return []

            vns, bs, nus, rhos, alphas = [], [], [], [], []
            for Ti, Te in zip(Tis, Texp):
                vn_i, b_i, nu_i, rho_i, _, _ = self.model.get_sabr_parameters(
                    index=index, expiry=float(Te), tenor=float(Ti), product_type=None
                )
                vn_i = float(vn_i); b_i = float(b_i); nu_i = float(nu_i); rho_i = float(rho_i)

                pr = Hagan2002LognormalSABR(
                    f=float(forward), shift=float(shift), t=float(Te),
                    v_atm_n=vn_i, beta=b_i, rho=rho_i, volvol=nu_i
                )

                vns.append(vn_i); bs.append(b_i); nus.append(nu_i); rhos.append(rho_i)
                alphas.append(float(pr.alpha()))

            alpha_star = float(sqrt_g * sum(w * a * s for w, a, s in zip(weights, alphas, time_scales)))
            beta_star  = float(sum(w * b for w, b in zip(weights, bs)))
            nu_star    = float(sum(w * nu * s for w, nu, s in zip(weights, nus, time_scales)))
            rho_star   = float((1.0 / sqrt_g) * sum(w * r for w, r in zip(weights, rhos)))

            Teff = float(sabr_pricer.t)
            Fps = float(forward + shift)
            Kps = float(strike + shift)

            h = 1e-4
            out = []

            for i, (Ti, Te, w_i, s_i) in enumerate(zip(Tis, Texp, weights, time_scales)):
                r0 = float(rhos[i])

                r_plus = min(0.9999, r0 + h)
                r_minus = max(-0.9999, r0 - h)

                pr_plus = Hagan2002LognormalSABR(
                    f=float(forward), shift=float(shift), t=float(Te),
                    v_atm_n=vns[i], beta=bs[i], rho=r_plus, volvol=nus[i]
                )
                pr_minus = Hagan2002LognormalSABR(
                    f=float(forward), shift=float(shift), t=float(Te),
                    v_atm_n=vns[i], beta=bs[i], rho=r_minus, volvol=nus[i]
                )

                a_plus = float(pr_plus.alpha())
                a_minus = float(pr_minus.alpha())

                alpha_plus = alpha_star + sqrt_g * w_i * s_i * (a_plus - alphas[i])
                alpha_minus = alpha_star + sqrt_g * w_i * s_i * (a_minus - alphas[i])

                rho_plus_star = rho_star + (w_i / sqrt_g) * (r_plus - r0)
                rho_minus_star = rho_star + (w_i / sqrt_g) * (r_minus - r0)

                sig_plus = float(lognormal_vol(Kps, Fps, Teff, alpha_plus, beta_star, rho_plus_star, nu_star))
                sig_minus = float(lognormal_vol(Kps, Fps, Teff, alpha_minus, beta_star, rho_minus_star, nu_star))

                denom = (r_plus - r_minus)
                dSig = (sig_plus - sig_minus) / denom if abs(denom) > 0.0 else 0.0

                out.append((float(Te), float(Ti), float(dSig)))

            return out

        #PLAIN
        T0 = float(expiry)
        if T0 <= 0.0:
            return 0.0

        f_power = float(Fp ** (beta_in - 1.0))
        c_rho = float(2.0 - 3.0 * rho_in * rho_in)
        g = float(1.0 + T0 * (nu_in ** 2) * c_rho / 24.0)

        a3 = float(T0 * (f_power ** 3) * ((1.0 - beta_in) ** 2) / 24.0)
        a2 = float(T0 * (f_power ** 2) * (rho_in * beta_in * nu_in) / 4.0)
        a1 = float(g * f_power)

        dP_dalpha = float(3.0 * a3 * alpha * alpha + 2.0 * a2 * alpha + a1)

        dalpha_drho = 0.0
        if abs(dP_dalpha) > 1e-18:
            da2_drho = float(T0 * (f_power ** 2) * (beta_in * nu_in) / 4.0)
            da1_drho = float(-f_power * T0 * (nu_in ** 2) * rho_in / 4.0)
            dP_drho  = float(da2_drho * (alpha ** 2) + da1_drho * alpha)
            dalpha_drho = float(-dP_drho / dP_dalpha)

        return float(dsigma_drho_partial + dsigma_dalpha * dalpha_drho)

    def dVol_dDecay(
        self,
        *,
        expiry: float,
        tenor: float,
        forward: float,
        strike: float,
        normalVol: float,
        beta: float,
        nu: float,
        rho: float,
        shift: float,
        decay: float,
    ) -> float:
        if self.method != "top-down":
            return 0.0

        ts = float(expiry)                 
        te = float(expiry + tenor)         
        k  = float(decay)

        if te <= 0.0:
            return 0.0
        if ts >= te:
            return 0.0

        Fp = float(forward + shift)
        Kp = float(strike  + shift)
        if Fp <= 0.0 or Kp <= 0.0:
            return 0.0

        pr_eff = TimeDecayLognormalSABR(
            f=forward,
            shift=shift,
            t=te,
            vAtmN=float(normalVol),
            beta=float(beta),
            rho=float(rho),
            volVol=float(nu),
            volDecaySpeed=float(decay),
            decayStart=float(expiry),
        )
        alpha_eff = float(pr_eff.alpha())
        beta_eff  = float(pr_eff.beta)
        rho_eff   = float(pr_eff.rho)
        nu_eff    = float(pr_eff.volvol)

        if alpha_eff <= 0.0 or nu_eff <= 0.0:
            return 0.0

        pr_base = Hagan2002LognormalSABR(
            f=forward,
            shift=shift,
            t=te,
            v_atm_n=float(normalVol),
            beta=float(beta),
            rho=float(rho),
            volvol=float(nu),
        )
        alpha_base = float(pr_base.alpha())
        if alpha_base <= 0.0:
            return 0.0

        #partials of sigma wrt effective params (alpha, rho, nu)
        alpha = alpha_eff
        beta_ = beta_eff
        rho_  = rho_eff
        nu_   = nu_eff
        T     = te

        one_minus_beta = 1.0 - beta_
        log_fk = float(np.log(Fp / Kp))

        fkbeta = float((Fp * Kp) ** (1.0 - beta_))
        sqrt_fkbeta = float(np.sqrt(fkbeta))

        A = float((one_minus_beta ** 2) * (alpha ** 2) / (24.0 * fkbeta))
        B = float(0.25 * rho_ * beta_ * nu_ * alpha / sqrt_fkbeta)
        C = float((2.0 - 3.0 * rho_ * rho_) * (nu_ ** 2) / 24.0)

        V = float((one_minus_beta ** 2) * (log_fk ** 2) / 24.0)
        W = float((one_minus_beta ** 4) * (log_fk ** 4) / 1920.0)

        H = float(1.0 + (A + B + C) * T)
        Q = float(1.0 + V + W)

        z = float(nu_ * sqrt_fkbeta * log_fk / alpha)
        eps = 1e-7

        dsigma_dalpha = 0.0
        dsigma_drho   = 0.0
        dsigma_dnu    = 0.0

        dB_drho = float(0.25 * beta_ * nu_ * alpha / sqrt_fkbeta)
        dC_drho = float(-rho_ * (nu_ ** 2) / 4.0)
        dH_drho = float((dB_drho + dC_drho) * T)

        dB_dnu  = float(0.25 * rho_ * beta_ * alpha / sqrt_fkbeta)
        dC_dnu  = float((2.0 - 3.0 * rho_ * rho_) * nu_ / 12.0)
        dH_dnu  = float((dB_dnu + dC_dnu) * T)

        dz_dnu = float(z / nu_) if abs(nu_) > 0.0 else 0.0
        dz_drho = 0.0

        if abs(z) > eps:
            sqrt_term = float(np.sqrt(1.0 - 2.0 * rho_ * z + z * z))
            A_x = float(sqrt_term + z - rho_)
            B_x = float(1.0 - rho_)
            if A_x <= 0.0 or B_x <= 0.0 or sqrt_term <= 0.0:
                return 0.0

            x = float(np.log(A_x / B_x))
            dx_dz = float(1.0 / sqrt_term)
            dA_drho = float((-z / sqrt_term) - 1.0)
            dx_drho = float(dA_drho / A_x + 1.0 / (1.0 - rho_))
            dx_dnu = float(dx_dz * dz_dnu)

            Numer = float(alpha * z * H)
            Denom = float(sqrt_fkbeta * Q * x)
            if abs(Denom) <= 1e-18:
                return 0.0

            # dz/dalpha = -z/alpha
            dz_dalpha = float(-z / alpha)
            dA_dalpha = float((one_minus_beta ** 2) * alpha / (12.0 * fkbeta))
            dB_dalpha = float(B / alpha)
            dH_dalpha = float((dA_dalpha + dB_dalpha) * T)
            dx_dalpha = float(dx_dz * dz_dalpha)

            dNumer_dalpha = float(alpha * z * dH_dalpha)
            dDenom_dalpha = float(sqrt_fkbeta * Q * dx_dalpha)

            dsigma_dalpha = float((dNumer_dalpha * Denom - Numer * dDenom_dalpha) / (Denom * Denom))

            #dsigma/drho
            dNumer_drho = float(alpha * dz_drho * H + alpha * z * dH_drho)  # dz_drho=0
            dDenom_drho = float(sqrt_fkbeta * Q * dx_drho)
            dsigma_drho = float((dNumer_drho * Denom - Numer * dDenom_drho) / (Denom * Denom))

            #dsigma/dnu
            dNumer_dnu = float(alpha * dz_dnu * H + alpha * z * dH_dnu)
            dDenom_dnu = float(sqrt_fkbeta * Q * dx_dnu)
            dsigma_dnu = float((dNumer_dnu * Denom - Numer * dDenom_dnu) / (Denom * Denom))

        else:
            Denom = float(sqrt_fkbeta * Q)
            if abs(Denom) <= 1e-18:
                return 0.0

            dA_dalpha = float((one_minus_beta ** 2) * alpha / (12.0 * fkbeta))
            dB_dalpha = float(B / alpha) if alpha != 0.0 else 0.0
            dH_dalpha = float((dA_dalpha + dB_dalpha) * T)
            dsigma_dalpha = float((H + alpha * dH_dalpha) / Denom)

            dsigma_drho = float(alpha * dH_drho / Denom)
            dsigma_dnu  = float(alpha * dH_dnu  / Denom)

        # d(alpha_eff)/dk, d(rho_eff)/dk, d(nu_eff)/dk from TimeDecay formulas
        # Using base (alpha_base, rho, nu) as constants wrt k
        alpha0 = alpha_base
        rho0   = float(rho)
        nu0    = float(nu)

        if k < 0.0:
            return 0.0

        dtau = float(2.0 * ts)
        tau  = float(2.0 * k * ts + te)
        if tau <= 0.0:
            return 0.0

        # gamma part
        denA = float((4.0 * k + 3.0) * (2.0 * k + 1.0))
        denB = float((4.0 * k + 3.0) * (3.0 * k + 2.0) ** 2)
        if denA == 0.0 or denB == 0.0:
            return 0.0

        inside1 = float(2.0 * tau**3 + te**3 + (4.0 * k * k - 2.0 * k) * ts**3 + 6.0 * k * ts**2 * te)
        gFirst  = float(tau * inside1)

        inside2 = float(3.0 * tau**2 - te**2 + 5.0 * k * ts**2 + 4.0 * ts * te)
        gSecond = float(3.0 * k * (rho0 ** 2) * (te - ts) ** 2 * inside2)

        gamma = float(gFirst / denA + gSecond / denB)

        if (not np.isfinite(gamma)) or gamma <= 0.0:
            return 0.0

        # derivatives of gamma wrt k
        dDenA = float(16.0 * k + 10.0)
        dDenB = float(4.0 * (3.0 * k + 2.0) ** 2 + (4.0 * k + 3.0) * (18.0 * k + 12.0))

        dinside1 = float(6.0 * tau**2 * dtau + (8.0 * k - 2.0) * ts**3 + 6.0 * ts**2 * te)
        dgFirst  = float(dtau * inside1 + tau * dinside1)

        dinside2 = float(6.0 * tau * dtau + 5.0 * ts**2)
        dgSecond = float(3.0 * (rho0 ** 2) * (te - ts) ** 2 * inside2 + 3.0 * k * (rho0 ** 2) * (te - ts) ** 2 * dinside2)

        dgamma = float((dgFirst * denA - gFirst * dDenA) / (denA * denA) + (dgSecond * denB - gSecond * dDenB) / (denB * denB))

        nuHat2 = float((nu0 ** 2) * gamma * (2.0 * k + 1.0) / (tau**3 * te))
        nuHat2 = max(nuHat2, 0.0)
        if nuHat2 <= 0.0:
            return 0.0
        nuHat = float(np.sqrt(nuHat2))

        # safe because gamma>0 due to guard above
        dnuHat2 = float(nuHat2 * ((dgamma / gamma) + (2.0 / (2.0 * k + 1.0)) - 3.0 * (dtau / tau)))
        dnuHat = float(0.5 * dnuHat2 / nuHat) if nuHat > 0.0 else 0.0


        termA = float((nu0 ** 2) * (tau**2 + 2.0 * k * ts**2 + te**2))
        termB = float(2.0 * te * tau * (k + 1.0))
        if termB == 0.0:
            return 0.0

        dtermA = float((nu0 ** 2) * (2.0 * tau * dtau + 2.0 * ts**2))
        dtermB = float(2.0 * te * ((k + 1.0) * dtau + tau))

        H1 = float(termA / termB)
        dH1 = float((dtermA * termB - termA * dtermB) / (termB * termB))

        H_td  = float(H1 - nuHat2)
        dH_td = float(dH1 - dnuHat2)

        alphaHat2 = float((alpha0 ** 2) / (2.0 * k + 1.0) * (tau / te) * np.exp(0.5 * H_td * te))
        alphaHat2 = max(alphaHat2, 0.0)
        if alphaHat2 <= 0.0:
            return 0.0
        alphaHat = float(np.sqrt(alphaHat2))

        dalphaHat2 = float(alphaHat2 * (-2.0 / (2.0 * k + 1.0) + (dtau / tau) + 0.5 * te * dH_td))
        dalphaHat = float(0.5 * dalphaHat2 / alphaHat) if alphaHat > 0.0 else 0.0


        numR = float(3.0 * tau**2 + 2.0 * k * ts**2 + te**2)
        dnumR = float(6.0 * tau * dtau + 2.0 * ts**2)

        rhoHat = float(rho0 * numR / (np.sqrt(gamma) * (6.0 * k + 4.0)))
        drhoHat = float(rhoHat * ((dnumR / numR) - 0.5 * (dgamma / gamma) - (6.0 / (6.0 * k + 4.0))))

        # Combine
        dSigma_dk = float(dsigma_dalpha * dalphaHat + dsigma_drho * drhoHat + dsigma_dnu * dnuHat)
        return dSigma_dk

    def dVol_dCorr(
        self,
        *,
        index: str,
        expiry: float,
        tenor: float,
        forward: float,
        strike: float,
        shift: float,
    ) -> float:
        if self.method != "bottom-up":
            return 0.0
        if self.corr_surf is None:
            raise ValueError("corr_surf must be provided for bottom-up method")
        if self.product is None:
            raise ValueError("product must be provided for bottom-up method")

        Fp = float(forward + shift)
        Kp = float(strike  + shift)
        if Fp <= 0.0 or Kp <= 0.0:
            return 0.0

        pr = BottomUpLognormalSABR(
            f=forward,
            shift=shift,
            expiry=float(expiry),
            tenor=float(tenor),
            model=self.model,
            corr_surf=self.corr_surf,
            product=self.product,
        )
        alpha_eff = float(pr.alpha())
        beta_eff  = float(pr.beta)
        rho_eff   = float(pr.rho)
        nu_eff    = float(pr.volvol)
        T         = float(pr.t)

        if T <= 0.0 or alpha_eff <= 0.0:
            return 0.0

        dates = self.product.get_fixing_schedule()
        dc = self.product.dayCounter
        Tis = [float(dc.yearFraction(d0, d1)) for d0, d1 in zip(dates, dates[1:])]

        total = float(sum(Tis))
        if total <= 0.0:
            return 0.0

        weights = [float(Ti / total) for Ti in Tis]
        offsets = np.cumsum([0.0] + Tis[:-1])
        Tstarts = [float(expiry) + float(x) for x in offsets]
        Tends   = [Ts + Ti for Ts, Ti in zip(Tstarts, Tis)]

        use_end_time = (getattr(self.product, "oisIndex_", None) is not None)
        Texp = Tends if use_end_time else Tstarts

        # validate segment times (validate Texp, not just Tstarts)
        if any((not np.isfinite(T) or T <= 0.0) for T in Texp):
            bad = [T for T in Texp if (not np.isfinite(T) or T <= 0.0)]
            raise ValueError(f"[bottom-up] invalid segment times in Texp (<=0 or non-finite): {bad}")

        Te = float(sum(w * T for w, T in zip(weights, Texp)))
        if not np.isfinite(Te) or Te <= 0.0:
            raise ValueError(
                f"[bottom-up] invalid Te={Te}. Check expiry={expiry}, tenor={tenor}, "
                f"Texp(min,max)=({min(Texp)}, {max(Texp)}), total={total}."
            )

        time_scales = [float(np.sqrt(T / Te)) for T in Texp]
        gamma_1N = float(self.corr_surf.corr(float(Texp[0]), float(Texp[-1])))

        N = len(Tis)
        if N <= 1:
            # gamma_bar = 1, derivative 0
            return 0.0

        mu = float((1.0 - gamma_1N) / (N - 1))
        dmu_dgamma1N = float(-1.0 / (N - 1))

        Gamma = np.zeros((N, N))
        dGamma_dmu = np.zeros((N, N))
        for i in range(N):
            for j in range(N):
                dt = abs(i - j)
                val = 1.0 - mu * dt
                if val > 0.0:
                    Gamma[i, j] = val
                    dGamma_dmu[i, j] = -float(dt)
                else:
                    Gamma[i, j] = 0.0
                    dGamma_dmu[i, j] = 0.0

        gamma_bar = float(Gamma.mean())

        dgamma_bar_dmu = float(dGamma_dmu.mean())
        dgamma_bar_dgamma1N = float(dgamma_bar_dmu * dmu_dgamma1N)

        alpha_sum = 0.0
        rho_sum   = 0.0
        for w, s, Ti, Tst in zip(weights, time_scales, Tis, Texp):
            if Tst <= 0.0:
                continue
            v_n_i, b_i, nu_i, rho_i, _, _ = self.model.get_sabr_parameters(
                index=index, expiry=float(Tst), tenor=float(Ti), product_type=None
            )
            p_i = Hagan2002LognormalSABR(
                f=forward,
                shift=shift,
                t=float(Tst),
                v_atm_n=float(v_n_i),
                beta=float(b_i),
                rho=float(rho_i),
                volvol=float(nu_i),
            )
            alpha_i = float(p_i.alpha())
            alpha_sum += float(w) * float(s) * alpha_i
            rho_sum   += float(w) * float(rho_i)

        sqrt_g = float(np.sqrt(gamma_bar))
        dalphaStar_dgbar = float(alpha_sum / (2.0 * sqrt_g))
        drhoStar_dgbar   = float(-rho_sum / (2.0 * (gamma_bar ** 1.5)))

        dalphaStar_dgamma1N = float(dalphaStar_dgbar * dgamma_bar_dgamma1N)
        drhoStar_dgamma1N   = float(drhoStar_dgbar   * dgamma_bar_dgamma1N)

        # Partials: dsigma/dalpha and dsigma/drho at effective params
        alpha = alpha_eff
        beta_ = beta_eff
        rho_  = rho_eff
        nu_   = nu_eff

        one_minus_beta = 1.0 - beta_
        log_fk = float(np.log(Fp / Kp))
        fkbeta = float((Fp * Kp) ** (1.0 - beta_))
        sqrt_fkbeta = float(np.sqrt(fkbeta))

        A = float((one_minus_beta ** 2) * (alpha ** 2) / (24.0 * fkbeta))
        B = float(0.25 * rho_ * beta_ * nu_ * alpha / sqrt_fkbeta)
        C = float((2.0 - 3.0 * rho_ * rho_) * (nu_ ** 2) / 24.0)

        V = float((one_minus_beta ** 2) * (log_fk ** 2) / 24.0)
        W = float((one_minus_beta ** 4) * (log_fk ** 4) / 1920.0)

        H = float(1.0 + (A + B + C) * T)
        Q = float(1.0 + V + W)

        z   = float(nu_ * sqrt_fkbeta * log_fk / alpha)
        eps = 1e-7

        dsigma_dalpha = 0.0
        dsigma_drho   = 0.0

        dB_drho = float(0.25 * beta_ * nu_ * alpha / sqrt_fkbeta)
        dC_drho = float(-rho_ * (nu_ ** 2) / 4.0)
        dH_drho = float((dB_drho + dC_drho) * T)

        if abs(z) > eps:
            sqrt_term = float(np.sqrt(1.0 - 2.0 * rho_ * z + z * z))
            A_x = float(sqrt_term + z - rho_)
            B_x = float(1.0 - rho_)
            if A_x <= 0.0 or B_x <= 0.0 or sqrt_term <= 0.0:
                return 0.0
            x = float(np.log(A_x / B_x))

            dx_dz = float(1.0 / sqrt_term)

            # dx/drho holding z constant
            dA_drho = float((-z / sqrt_term) - 1.0)
            dx_drho = float(dA_drho / A_x + 1.0 / (1.0 - rho_))

            Numer = float(alpha * z * H)
            Denom = float(sqrt_fkbeta * Q * x)
            if abs(Denom) <= 1e-18:
                return 0.0

            # dsigma/dalpha
            dz_dalpha = float(-z / alpha)
            dA_dalpha = float((one_minus_beta ** 2) * alpha / (12.0 * fkbeta))
            dB_dalpha = float(B / alpha)
            dH_dalpha = float((dA_dalpha + dB_dalpha) * T)
            dx_dalpha = float(dx_dz * dz_dalpha)

            dNumer_dalpha = float(alpha * z * dH_dalpha)
            dDenom_dalpha = float(sqrt_fkbeta * Q * dx_dalpha)
            dsigma_dalpha = float((dNumer_dalpha * Denom - Numer * dDenom_dalpha) / (Denom * Denom))

            # dsigma/drho
            dNumer_drho = float(alpha * z * dH_drho)
            dDenom_drho = float(sqrt_fkbeta * Q * dx_drho)
            dsigma_drho = float((dNumer_drho * Denom - Numer * dDenom_drho) / (Denom * Denom))

        else:
            Denom = float(sqrt_fkbeta * Q)
            if abs(Denom) <= 1e-18:
                return 0.0

            dA_dalpha = float((one_minus_beta ** 2) * alpha / (12.0 * fkbeta))
            dB_dalpha = float(B / alpha) if alpha != 0.0 else 0.0
            dH_dalpha = float((dA_dalpha + dB_dalpha) * T)
            dsigma_dalpha = float((H + alpha * dH_dalpha) / Denom)

            dsigma_drho = float(alpha * dH_drho / Denom)

        # Combine corr sensitivity
        dSigma_dgamma1N = float(dsigma_dalpha * dalphaStar_dgamma1N + dsigma_drho * drhoStar_dgamma1N)
        return dSigma_dgamma1N

