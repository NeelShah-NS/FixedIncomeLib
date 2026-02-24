from typing import Any, Dict
from fixedincomelib.sabr.sabr_model import SabrModel
from fixedincomelib.analytics.sabr_calculator import SABRCalculator
from fixedincomelib.valuation.valuation_engine import ValuationEngine
from fixedincomelib.valuation.valuation_engine_registry import ValuationEngineRegistry
from fixedincomelib.valuation.index_fixing_registry import IndexManager
from fixedincomelib.product.non_linear_products import (LongOrShort, ProductIborCapFloorlet, ProductOvernightCapFloorlet, ProductIborCapFloor, ProductOvernightCapFloor, ProductIborSwaption, ProductOvernightSwaption)
from fixedincomelib.date.utilities import accrued
from fixedincomelib.sabr.sabr_surface_risk import accumulate_surface_pillar_risk
import numpy as np
import warnings

class ValuationEngineIborCapFloorlet(ValuationEngine):

    def __init__(self, model: SabrModel, valuation_parameters: Dict[str, Any], product: ProductIborCapFloorlet) -> None:
        super().__init__(model, valuation_parameters, product)
        self.yieldCurve   = model.subModel
        raw = valuation_parameters.get("SABR_METHOD")
        method_input = raw.lower() if isinstance(raw, str) else ""
        if method_input in ("top-down", "bottom-up"):
            warnings.warn(
                f"SABR_METHOD='{raw}' is not allowed for Ibor products; "
                "forcing standard Hagan SABR.",
                UserWarning
            )
        self.sabrCalc = SABRCalculator(model, method=None)
        self.currencyCode = product.currency.value.code()
        self.accrualStart = product.accrualStart
        self.accrualEnd   = product.accrualEnd
        self.strikeRate   = product.strike
        self.optionType   = product.optionType
        self.notional     = product.notional
        self.buyOrSell    = 1.0 if product.longOrShort.value == LongOrShort.LONG else -1.
        self.fundingIndex = valuation_parameters.get("FUNDING INDEX", self.product.index)

    def calculateValue(self) -> None:

        dc = self.product.dayCounter
        expiry_t = float(dc.yearFraction(self.valueDate, self.accrualStart))
        tenor_t  = float(self.product.accrualFactor)

        forward_rate    = self.yieldCurve.forward(self.product.index,self.accrualStart,self.accrualEnd)
        discount_factor = self.yieldCurve.discountFactor(self.fundingIndex, self.accrualEnd)

        price = self.sabrCalc.option_price(
            index       = self.product.index,
            expiry      = expiry_t,
            tenor       = tenor_t,
            forward     = forward_rate,
            strike      = self.strikeRate,
            option_type = self.optionType,
        )

        accrual_factor = float(self.product.accrualFactor)
        pv = self.notional * discount_factor * accrual_factor * price *  self.buyOrSell

        self.value_ = [self.currencyCode, pv]

    def calculateFirstOrderRisk(self, gradient=None, scaler = 1, accumulate = False):
        if gradient is None:
                gradient = self.model.gradient_
                if not accumulate:
                    self.model.clearGradient()

        dc = self.product.dayCounter
        expiry_t = float(dc.yearFraction(self.valueDate, self.accrualStart))
        accrual_factor = float(self.product.accrualFactor)
        tenor_t  = float(accrual_factor)

        forward_rate    = self.yieldCurve.forward(self.product.index, self.accrualStart,self.accrualEnd)
        discount_factor = self.yieldCurve.discountFactor(self.fundingIndex, self.accrualEnd)

        price = self.sabrCalc.option_price(
            index       = self.product.index,
            expiry      = expiry_t,
            tenor       = tenor_t,
            forward     = forward_rate,
            strike      = self.strikeRate,
            option_type = self.optionType,
        )

        normalVol, beta, nu, rho, shift, decay = self.model.get_sabr_parameters(
            index=self.product.index,
            expiry=expiry_t,
            tenor=tenor_t,
            product_type=None
        )

        # Yield curve risk: DF + forward
        numCurveParams = int(np.asarray(self.yieldCurve.getGradientArray()).size)
        curveGradient  = gradient[:numCurveParams]

        # DF term
        dfScaler = float(scaler) * self.notional * self.buyOrSell * accrual_factor * price
        self.yieldCurve.discountFactorGradientWrtModelParameters(
            index=self.fundingIndex,
            to_date=self.accrualEnd,
            gradient=curveGradient,
            scaler=dfScaler,
            accumulate=True
        )

        # Forward term
        dPrice_dForward, dPrice_dVol, dVol_dForward = self.sabrCalc.option_price_greeks(
            index         = self.product.index,
            expiry        = expiry_t,
            tenor         = tenor_t,
            forward       = forward_rate,
            strike        = self.strikeRate,
            option_type   = self.optionType,
            normal_vol     = normalVol,
            beta          = beta,
            nu            = nu,
            rho           = rho,
            shift         = shift,
            decay         = decay
        )

        dPrice_dForward_total = dPrice_dForward + dPrice_dVol * dVol_dForward

        forwardScaler = float(scaler) * self.notional * self.buyOrSell * discount_factor * accrual_factor * dPrice_dForward_total
        self.yieldCurve.forwardRateGradientWrtModelParameters(
            index=self.product.index,
            start_time=self.accrualStart,
            end_time=self.accrualEnd,
            gradient=curveGradient,
            scaler=forwardScaler,
            accumulate=True
        )

        # SABR pillar risk (NORMALVOL, BETA, NU, RHO)
        pvScale = float(scaler) * float(self.notional) * float(self.buyOrSell) * float(discount_factor) * float(accrual_factor)

        # NORMALVOL 
        dVol_dNormalVol = self.sabrCalc.dVol_dNormalVol(
            index     = self.product.index,
            expiry    = expiry_t,
            tenor     = tenor_t,
            forward   = forward_rate,
            strike    = self.strikeRate,
            normalVol = normalVol,
            beta      = beta,
            nu        = nu,
            rho       = rho,
            shift     = shift,
            decay     = decay
        )
        
        accumulate_surface_pillar_risk(
            model=self.model,
            gradient=gradient,
            index=self.product.index,
            parameter="NORMALVOL",
            expiry_t=expiry_t,
            tenor_t=tenor_t,
            pvScale=pvScale,
            dPrice_dVol=dPrice_dVol,
            dSigma_dP=dVol_dNormalVol,
            product_type_for_scalar=None
        )

        #  BETA 
        dVol_dBeta = self.sabrCalc.dVol_dBeta(
            index     = self.product.index,
            expiry    = expiry_t,
            tenor     = tenor_t,
            forward   = forward_rate,
            strike    = self.strikeRate,
            normalVol = normalVol,
            beta      = beta,
            nu        = nu,
            rho       = rho,
            shift     = shift,
            decay     = decay
        )
        accumulate_surface_pillar_risk(
            model=self.model,
            gradient=gradient,
            index=self.product.index,
            parameter="BETA",
            expiry_t=expiry_t,
            tenor_t=tenor_t,
            pvScale=pvScale,
            dPrice_dVol=dPrice_dVol,
            dSigma_dP=dVol_dBeta,
            product_type_for_scalar=None
        )

        #  NU 
        dVol_dNu = self.sabrCalc.dVol_dNu(
            index     = self.product.index,
            expiry    = expiry_t,
            tenor     = tenor_t,
            forward   = forward_rate,
            strike    = self.strikeRate,
            normalVol = normalVol,
            beta      = beta,
            nu        = nu,
            rho       = rho,
            shift     = shift,
            decay     = decay
        )
        accumulate_surface_pillar_risk(
            model=self.model,
            gradient=gradient,
            index=self.product.index,
            parameter="NU",
            expiry_t=expiry_t,
            tenor_t=tenor_t,
            pvScale=pvScale,
            dPrice_dVol=dPrice_dVol,
            dSigma_dP=dVol_dNu,
            product_type_for_scalar=None
        )

        #  RHO 
        dVol_dRho = self.sabrCalc.dVol_dRho(
            index     = self.product.index,
            expiry    = expiry_t,
            tenor     = tenor_t,
            forward   = forward_rate,
            strike    = self.strikeRate,
            normalVol = normalVol,
            beta      = beta,
            nu        = nu,
            rho       = rho,
            shift     = shift,
            decay     = decay
        )
        accumulate_surface_pillar_risk(
            model=self.model,
            gradient=gradient,
            index=self.product.index,
            parameter="RHO",
            expiry_t=expiry_t,
            tenor_t=tenor_t,
            pvScale=pvScale,
            dPrice_dVol=dPrice_dVol,
            dSigma_dP=dVol_dRho,
            product_type_for_scalar=None
        )
     
        self.firstOrderRisk_ = gradient

class ValuationEngineOvernightCapFloorlet(ValuationEngine):

    def __init__(self, model: SabrModel, valuation_parameters: Dict[str, Any], product: ProductOvernightCapFloorlet) -> None:
        super().__init__(model, valuation_parameters, product)
        self.yieldCurve = model.subModel
        raw = valuation_parameters.get("SABR_METHOD")
        sabr_method   = raw.lower() if isinstance(raw, str) else "" 
        prod_flag     = "CAPLET"   if sabr_method=="top-down" else None
        self.prod_flag = prod_flag
        self.sabrCalc = SABRCalculator(
            model,
            method  = valuation_parameters.get("SABR_METHOD", None),
            product = product,
            product_type = prod_flag 
        )
        self.currencyCode = product.currency.value.code()
        self.accrualStart = product.effectiveDate
        self.accrualEnd   = product.maturityDate
        self.strikeRate   = product.strike
        self.optionType   = product.optionType
        self.notional     = product.notional
        self.buyOrSell    = 1.0 if product.longOrShort.value == LongOrShort.LONG else -1.
        self.fundingIndex = valuation_parameters.get("FUNDING INDEX", self.product.index)

    def calculateValue(self) -> None:
        
        dc = self.product.dayCounter
        expiry_t = float(dc.yearFraction(self.valueDate, self.accrualStart))
        tenor_t  = float(self.product.accrualFactor)


        forward_rate    = self.yieldCurve.forward(
            self.product.index,
            self.accrualStart,
            self.accrualEnd,
        )
        discount_factor = self.yieldCurve.discountFactor(self.fundingIndex, self.accrualEnd)

        price = self.sabrCalc.option_price(
            index       = self.product.index,
            expiry      = expiry_t,
            tenor       = tenor_t,
            forward     = forward_rate,
            strike      = self.strikeRate,
            option_type = self.optionType,
        )

        accrual_factor = self.product.accrualFactor
        pv = self.notional * discount_factor * accrual_factor * price *  self.buyOrSell

        self.value_ = [self.currencyCode, pv]
    
    def calculateFirstOrderRisk(self, gradient=None, scaler=1, accumulate=False):
        if gradient is None:
            gradient = self.model.gradient_
            if not accumulate:
                self.model.clearGradient()

        dc = self.product.dayCounter
        expiry_t = float(dc.yearFraction(self.valueDate, self.accrualStart))
        accrual_factor = self.product.accrualFactor
        tenor_t  = float(self.product.accrualFactor)

        forward_rate = self.yieldCurve.forward(
            self.product.index,
            self.accrualStart,
            self.accrualEnd,
        )
        discount_factor = self.yieldCurve.discountFactor(self.fundingIndex, self.accrualEnd)

        price = self.sabrCalc.option_price(
            index       = self.product.index,
            expiry      = expiry_t,
            tenor       = tenor_t,
            forward     = forward_rate,
            strike      = self.strikeRate,
            option_type = self.optionType,
        )

        normalVol, beta, nu, rho, shift, decay = self.model.get_sabr_parameters(
            index=self.product.index,
            expiry=expiry_t,
            tenor=tenor_t,
            product_type=self.prod_flag
        )

        #  Yield curve risk: DF + forward 
        numCurveParams = int(np.asarray(self.yieldCurve.getGradientArray()).size)
        curveGradient  = gradient[:numCurveParams]

        # DF term
        dfScaler = float(scaler) * self.notional * self.buyOrSell * accrual_factor * price
        self.yieldCurve.discountFactorGradientWrtModelParameters(
            index=self.fundingIndex,
            to_date=self.accrualEnd,
            gradient=curveGradient,
            scaler=dfScaler,
            accumulate=True
        )

        # Forward term
        dPrice_dForward, dPrice_dVol, dVol_dForward = self.sabrCalc.option_price_greeks(
            index          = self.product.index,
            expiry         = expiry_t,
            tenor          = tenor_t,
            forward        = forward_rate,
            strike         = self.strikeRate,
            option_type    = self.optionType,
            normal_vol     = normalVol,
            beta           = beta,
            nu             = nu,
            rho            = rho,
            shift          = shift,
            decay          = decay
        )

        dPrice_dForward_total = dPrice_dForward + dPrice_dVol * dVol_dForward

        forwardScaler = (
            float(scaler)
            * self.notional
            * self.buyOrSell
            * discount_factor
            * accrual_factor
            * dPrice_dForward_total
        )
        self.yieldCurve.forwardRateGradientWrtModelParameters(
            index=self.product.index,
            start_time=self.accrualStart,
            end_time=self.accrualEnd,
            gradient=curveGradient,
            scaler=forwardScaler,
            accumulate=True
        )

        #  SABR pillar risk (NORMALVOL, BETA, NU, RHO) 
        pvScale = (
            float(scaler)
            * float(self.notional)
            * float(self.buyOrSell)
            * float(discount_factor)
            * float(accrual_factor)
        )

        #  NORMALVOL 
        dVol_dNormalVol = self.sabrCalc.dVol_dNormalVol(
            index     = self.product.index,
            expiry    = expiry_t,
            tenor     = tenor_t,
            forward   = forward_rate,
            strike    = self.strikeRate,
            normalVol = normalVol,
            beta      = beta,
            nu        = nu,
            rho       = rho,
            shift     = shift,
            decay     = decay
        )
        accumulate_surface_pillar_risk(
            model=self.model,
            gradient=gradient,
            index=self.product.index,
            parameter="NORMALVOL",
            expiry_t=expiry_t,
            tenor_t=tenor_t,
            pvScale=pvScale,
            dPrice_dVol=dPrice_dVol,
            dSigma_dP=dVol_dNormalVol,
            product_type_for_scalar=self.prod_flag
        )

        #  BETA 
        dVol_dBeta = self.sabrCalc.dVol_dBeta(
            index     = self.product.index,
            expiry    = expiry_t,
            tenor     = tenor_t,
            forward   = forward_rate,
            strike    = self.strikeRate,
            normalVol = normalVol,
            beta      = beta,
            nu        = nu,
            rho       = rho,
            shift     = shift,
            decay     = decay
        )
        accumulate_surface_pillar_risk(
            model=self.model,
            gradient=gradient,
            index=self.product.index,
            parameter="BETA",
            expiry_t=expiry_t,
            tenor_t=tenor_t,
            pvScale=pvScale,
            dPrice_dVol=dPrice_dVol,
            dSigma_dP=dVol_dBeta,
            product_type_for_scalar=self.prod_flag
        )

        #  NU 
        dVol_dNu = self.sabrCalc.dVol_dNu(
            index     = self.product.index,
            expiry    = expiry_t,
            tenor     = tenor_t,
            forward   = forward_rate,
            strike    = self.strikeRate,
            normalVol = normalVol,
            beta      = beta,
            nu        = nu,
            rho       = rho,
            shift     = shift,
            decay     = decay
        )
        accumulate_surface_pillar_risk(
            model=self.model,
            gradient=gradient,
            index=self.product.index,
            parameter="NU",
            expiry_t=expiry_t,
            tenor_t=tenor_t,
            pvScale=pvScale,
            dPrice_dVol=dPrice_dVol,
            dSigma_dP=dVol_dNu,
            product_type_for_scalar=self.prod_flag
        )

        #  RHO 
        dVol_dRho = self.sabrCalc.dVol_dRho(
            index     = self.product.index,
            expiry    = expiry_t,
            tenor     = tenor_t,
            forward   = forward_rate,
            strike    = self.strikeRate,
            normalVol = normalVol,
            beta      = beta,
            nu        = nu,
            rho       = rho,
            shift     = shift,
            decay     = decay
        )
        accumulate_surface_pillar_risk(
            model=self.model,
            gradient=gradient,
            index=self.product.index,
            parameter="RHO",
            expiry_t=expiry_t,
            tenor_t=tenor_t,
            pvScale=pvScale,
            dPrice_dVol=dPrice_dVol,
            dSigma_dP=dVol_dRho,
            product_type_for_scalar=self.prod_flag
        )

        self.firstOrderRisk_ = gradient

class ValuationEngineIborCapFloor(ValuationEngine):

    def __init__(
        self,
        model: SabrModel,
        valuation_parameters: Dict[str, Any],
        product: ProductIborCapFloor,
    ) -> None:
        super().__init__(model, valuation_parameters, product)
        self.currencyCode = product.currency.value.code()
        self.caplets      = product.capStream
        self.engines = [ValuationEngineIborCapFloorlet(model, valuation_parameters, caplet) for caplet in self.caplets.products]

    def calculateValue(self) -> None:
        total_pv = 0.0
        for engine in self.engines:
            engine.calculateValue()
            _, pv = engine.value_
            total_pv += pv
        self.value_ = [self.currencyCode, total_pv]

    def calculateFirstOrderRisk(self, gradient=None, scaler: float = 1.0, accumulate: bool = False) -> None:
        if gradient is None:
            gradient = self.model.gradient_
            if not accumulate:
                self.model.clearGradient()

        for eng in self.engines:
            eng.calculateFirstOrderRisk(gradient=gradient, scaler=scaler, accumulate=True)

        self.firstOrderRisk_ = gradient

class ValuationEngineOvernightCapFloor(ValuationEngine):

    def __init__(
        self,
        model: SabrModel,
        valuation_parameters: Dict[str, Any],
        product: ProductOvernightCapFloor,
    ) -> None:
        super().__init__(model, valuation_parameters, product)
        self.currencyCode = product.currency.value.code()
        self.caplets      = product.capStream
        self.engines = [ ValuationEngineOvernightCapFloorlet(model, valuation_parameters, caplet) for caplet in self.caplets.products]

    def calculateValue(self) -> None:
        total_pv = 0.0
        for engine in self.engines:
            engine.calculateValue()
            _, pv = engine.value_
            total_pv += pv
        self.value_ = [self.currencyCode, total_pv]

    def calculateFirstOrderRisk(self, gradient=None, scaler: float = 1.0, accumulate: bool = False) -> None:
        if gradient is None:
            gradient = self.model.gradient_
            if not accumulate:
                self.model.clearGradient()

        for eng in self.engines:
            eng.calculateFirstOrderRisk(gradient=gradient, scaler=scaler, accumulate=True)

        self.firstOrderRisk_ = gradient

class ValuationEngineIborSwaption(ValuationEngine):

    def __init__(
        self,
        model: SabrModel,
        valuation_parameters: Dict[str, Any],
        product: ProductIborSwaption,
    ) -> None:
        super().__init__(model, valuation_parameters, product)
        self.yieldCurve   = model.subModel
        raw = valuation_parameters.get("SABR_METHOD")
        method_input = raw.lower() if isinstance(raw, str) else ""
        if method_input in ("top-down", "bottom-up"):
            warnings.warn(
                f"SABR_METHOD='{raw}' is not allowed for Ibor products; "
                "forcing standard Hagan SABR.",
                UserWarning
            )
        self.sabrCalc = SABRCalculator(model, method=None)
        self.swap          = product.swap
        self.expiry        = product.expiryDate
        self.notional      = product.notional
        self.buyOrSell     = 1.0 if product.longOrShort.value == LongOrShort.LONG else -1.
        self.currencyCode  = self.swap.currency.value.code()
        self.strikeRate    = self.swap.fixedRate
        self.optionType    = product.optionType
        self.optionFlag    = 'CAP'   if self.optionType == 'PAYER' else 'FLOOR'

    def calculateValue(self) -> None:
        dc = self.product.dayCounter 
        t_exp = float(dc.yearFraction(self.valueDate, self.expiry))
        t_ten = float(dc.yearFraction(self.swap.firstDate, self.swap.lastDate))

        ir_vp = {"FUNDING INDEX": self.swap.index}
        ir_engine = ValuationEngineRegistry().new_valuation_engine(self.yieldCurve, ir_vp, self.swap)
        ir_engine.calculateValue()
        forward_swap_rate   = ir_engine.parRateOrSpread()
        swap_annuity_signed = ir_engine.annuity()
        swap_annuity        = abs(swap_annuity_signed)

        price = self.sabrCalc.option_price(
            index       = self.swap.index,
            expiry      = t_exp,
            tenor       = t_ten,
            forward     = forward_swap_rate,
            strike      = self.strikeRate,
            option_type = self.optionFlag,
        )

        pv = self.notional * swap_annuity * price *  self.buyOrSell
        self.value_ = [self.currencyCode, pv]

    def calculateFirstOrderRisk(self, gradient=None, scaler: float = 1.0, accumulate: bool = False) -> None:
        if gradient is None:
            gradient = self.model.gradient_
            if not accumulate:
                self.model.clearGradient()

        #times
        dc = self.product.dayCounter
        t_exp = float(dc.yearFraction(self.valueDate, self.expiry))
        t_ten = float(dc.yearFraction(self.swap.firstDate, self.swap.lastDate))

        #  build swap engine on YC to get forward + annuity
        ir_vp = {"FUNDING INDEX": self.swap.index}
        ir_engine = ValuationEngineRegistry().new_valuation_engine(self.yieldCurve, ir_vp, self.swap)
        ir_engine.calculateValue()
        forward_swap_rate = float(ir_engine.parRateOrSpread())

        swap_annuity_signed = float(ir_engine.annuity())

        # need pv_float for dF/dCurve formula
        pv_float = float(getattr(ir_engine, "_pv_float", 0.0))
        pv_fixed = float(getattr(ir_engine, "_pv_fixed", 0.0))

        swap_notional = float(getattr(self.swap, "notional", self.notional))
        if swap_notional == 0.0:
            raise RuntimeError("Swap notional is zero; cannot compute swaption risk.")
        if float(self.strikeRate) == 0.0:
            raise RuntimeError("Swap fixedRate (strikeRate) is zero; annuity is undefined.")

        if swap_annuity_signed == 0.0:
            raise RuntimeError("Swap annuity is zero; cannot compute par rate sensitivity.")
        
        swap_annuity = abs(swap_annuity_signed)
        sign_annuity = 1.0 if swap_annuity_signed > 0.0 else -1.0

        #  SABR price + greeks 
        price = float(self.sabrCalc.option_price(
            index       = self.swap.index,
            expiry      = t_exp,
            tenor       = t_ten,
            forward     = forward_swap_rate,
            strike      = self.strikeRate,
            option_type = self.optionFlag,
        ))

        normalVol, beta, nu, rho, shift, decay = self.model.get_sabr_parameters(
            index=self.swap.index,
            expiry=t_exp,
            tenor=t_ten,
            product_type=None
        )

        dPrice_dForward, dPrice_dVol, dVol_dForward = self.sabrCalc.option_price_greeks(
            index       = self.swap.index,
            expiry      = t_exp,
            tenor       = t_ten,
            forward     = forward_swap_rate,
            strike      = self.strikeRate,
            option_type = self.optionFlag,
            normal_vol  = normalVol,
            beta        = beta,
            nu          = nu,
            rho         = rho,
            shift       = shift,
            decay       = decay
        )

        dPrice_dForward_total = float(dPrice_dForward) + float(dPrice_dVol) * float(dVol_dForward)

        #  curve slice 
        numCurveParams = int(np.asarray(self.yieldCurve.getGradientArray()).size)
        curveGradient  = gradient[:numCurveParams]

        #  build fixed-leg and float-leg engines 
        fixed_leg_engine = ValuationEngineRegistry().new_valuation_engine(self.yieldCurve, ir_vp, self.swap.fixedLeg)
        float_leg_engine = ValuationEngineRegistry().new_valuation_engine(self.yieldCurve, ir_vp, self.swap.floatingLeg)

        fixed_leg_engine.calculateValue()
        _, pv_fixed_check = fixed_leg_engine.value_
        pv_fixed_check = float(pv_fixed_check)

        float_leg_engine.calculateValue()
        _, pv_float_check = float_leg_engine.value_
        pv_float_check = float(pv_float_check)

        if pv_fixed == 0.0 and pv_fixed_check != 0.0:
            pv_fixed = pv_fixed_check
        if pv_float == 0.0 and pv_float_check != 0.0:
            pv_float = pv_float_check

        #  gradients for PV_fixed and PV_float wrt curve params 
        g_pv_fixed = np.zeros(numCurveParams, dtype=float)
        g_pv_float = np.zeros(numCurveParams, dtype=float)

        # accumulate PV_fixed risk
        stack = [fixed_leg_engine]
        while stack:
            eng = stack.pop()

            # handle common aggregators
            if hasattr(eng, "_engines"):
                for child in eng._engines:
                    stack.append(child)
                continue

            # handle stream-like engines if they ever appear
            if hasattr(eng, "_fixed_engine") and hasattr(eng, "_float_engine"):
                stack.append(eng._fixed_engine)
                stack.append(eng._float_engine)
                continue

            eng.calculateFirstOrderRisk(gradient=g_pv_fixed, scaler=1.0, accumulate=True)

        # accumulate PV_float risk
        stack = [float_leg_engine]
        while stack:
            eng = stack.pop()

            if hasattr(eng, "_engines"):
                for child in eng._engines:
                    stack.append(child)
                continue

            if hasattr(eng, "_fixed_engine") and hasattr(eng, "_float_engine"):
                stack.append(eng._fixed_engine)
                stack.append(eng._float_engine)
                continue

            eng.calculateFirstOrderRisk(gradient=g_pv_float, scaler=1.0, accumulate=True)

        #  convert leg PV risks -> annuity/par-rate risks 
        dA_dCurve_signed = g_pv_fixed / (float(self.strikeRate) * swap_notional)
        dA_dCurve = sign_annuity * dA_dCurve_signed

        dF_dCurve = -(1.0 / (swap_notional * swap_annuity_signed)) * g_pv_float + (pv_float / (swap_notional * swap_annuity_signed * swap_annuity_signed)) * dA_dCurve_signed

        #  push curve risk into global gradient 
        curve_scale = float(scaler) * float(self.notional) * float(self.buyOrSell)
        curveGradient += curve_scale * (price * dA_dCurve + swap_annuity * dPrice_dForward_total * dF_dCurve)

        #  SABR pillar risks 
        pvScale = float(scaler) * float(self.notional) * float(self.buyOrSell) * float(swap_annuity)

        # NORMALVOL
        dVol_dNormalVol = self.sabrCalc.dVol_dNormalVol(
            index     = self.swap.index,
            expiry    = t_exp,
            tenor     = t_ten,
            forward   = forward_swap_rate,
            strike    = self.strikeRate,
            normalVol = normalVol,
            beta      = beta,
            nu        = nu,
            rho       = rho,
            shift     = shift,
            decay     = decay
        )
        accumulate_surface_pillar_risk(
            model=self.model,
            gradient=gradient,
            index=self.swap.index,
            parameter="NORMALVOL",
            expiry_t=t_exp,
            tenor_t=t_ten,
            pvScale=pvScale,
            dPrice_dVol=float(dPrice_dVol),
            dSigma_dP=dVol_dNormalVol,
            product_type_for_scalar=None
        )

        # BETA
        dVol_dBeta = self.sabrCalc.dVol_dBeta(
            index     = self.swap.index,
            expiry    = t_exp,
            tenor     = t_ten,
            forward   = forward_swap_rate,
            strike    = self.strikeRate,
            normalVol = normalVol,
            beta      = beta,
            nu        = nu,
            rho       = rho,
            shift     = shift,
            decay     = decay
        )
        accumulate_surface_pillar_risk(
            model=self.model,
            gradient=gradient,
            index=self.swap.index,
            parameter="BETA",
            expiry_t=t_exp,
            tenor_t=t_ten,
            pvScale=pvScale,
            dPrice_dVol=float(dPrice_dVol),
            dSigma_dP=dVol_dBeta,
            product_type_for_scalar=None
        )

        # NU
        dVol_dNu = self.sabrCalc.dVol_dNu(
            index     = self.swap.index,
            expiry    = t_exp,
            tenor     = t_ten,
            forward   = forward_swap_rate,
            strike    = self.strikeRate,
            normalVol = normalVol,
            beta      = beta,
            nu        = nu,
            rho       = rho,
            shift     = shift,
            decay     = decay
        )
        accumulate_surface_pillar_risk(
            model=self.model,
            gradient=gradient,
            index=self.swap.index,
            parameter="NU",
            expiry_t=t_exp,
            tenor_t=t_ten,
            pvScale=pvScale,
            dPrice_dVol=float(dPrice_dVol),
            dSigma_dP=dVol_dNu,
            product_type_for_scalar=None
        )

        # RHO
        dVol_dRho = self.sabrCalc.dVol_dRho(
            index     = self.swap.index,
            expiry    = t_exp,
            tenor     = t_ten,
            forward   = forward_swap_rate,
            strike    = self.strikeRate,
            normalVol = normalVol,
            beta      = beta,
            nu        = nu,
            rho       = rho,
            shift     = shift,
            decay     = decay
        )
        accumulate_surface_pillar_risk(
            model=self.model,
            gradient=gradient,
            index=self.swap.index,
            parameter="RHO",
            expiry_t=t_exp,
            tenor_t=t_ten,
            pvScale=pvScale,
            dPrice_dVol=float(dPrice_dVol),
            dSigma_dP=dVol_dRho,
            product_type_for_scalar=None
        )

        self.firstOrderRisk_ = gradient 

class ValuationEngineOvernightSwaption(ValuationEngine):

    def __init__(self, model: SabrModel, valuation_parameters: Dict[str, Any], product: ProductOvernightSwaption) -> None:
        super().__init__(model, valuation_parameters, product)
        self.yieldCurve   = model.subModel
        raw = valuation_parameters.get("SABR_METHOD")
        method_input = raw.lower() if isinstance(raw, str) else ""
        if method_input in ("top-down", "bottom-up"):
            warnings.warn(
                f"SABR_METHOD='{raw}' is not allowed for Overnight Swaptions; "
                "forcing standard Hagan SABR.",
                UserWarning
            )
        self.sabrCalc = SABRCalculator(model, method=None)
        self.swap          = product.swap
        self.expiry        = product.expiryDate
        self.notional      = product.notional
        self.buyOrSell     = 1.0 if product.longOrShort.value == LongOrShort.LONG else -1.
        self.currencyCode  = self.swap.currency.value.code()
        self.strikeRate    = self.swap.fixedRate
        self.optionType = product.optionType
        self.optionFlag = 'CAP'   if self.optionType == 'PAYER' else 'FLOOR'

    def calculateValue(self) -> None:
        dc = self.product.dayCounter
        t_exp = float(dc.yearFraction(self.valueDate, self.expiry))
        t_ten = float(dc.yearFraction(self.swap.firstDate, self.swap.lastDate))

        ir_vp = {"FUNDING INDEX": self.swap.index}
        ir_engine = ValuationEngineRegistry().new_valuation_engine(self.yieldCurve, ir_vp, self.swap)
        ir_engine.calculateValue()
        forward_swap_rate = ir_engine.parRateOrSpread()
        swap_annuity_signed = ir_engine.annuity()
        swap_annuity        = abs(swap_annuity_signed)

        price = self.sabrCalc.option_price(
            index       = self.swap.index,
            expiry      = t_exp,
            tenor       = t_ten,
            forward     = forward_swap_rate,
            strike      = self.strikeRate,
            option_type = self.optionFlag,
        )

        pv = self.notional * swap_annuity * price * self.buyOrSell
        self.value_ = [self.currencyCode, pv]
    
    def calculateFirstOrderRisk(self, gradient=None, scaler: float = 1.0, accumulate: bool = False) -> None:
        if gradient is None:
            gradient = self.model.gradient_
            if not accumulate:
                self.model.clearGradient()

        #  times 
        dc = self.product.dayCounter
        t_exp = float(dc.yearFraction(self.valueDate, self.expiry))
        t_ten = float(dc.yearFraction(self.swap.firstDate, self.swap.lastDate))

        #  swap engine (YC) for forward + annuity 
        ir_vp = {"FUNDING INDEX": self.swap.index}
        ir_engine = ValuationEngineRegistry().new_valuation_engine(self.yieldCurve, ir_vp, self.swap)
        ir_engine.calculateValue()
        forward_swap_rate = float(ir_engine.parRateOrSpread())

        swap_annuity_signed = float(ir_engine.annuity())

        # prefer cached leg PVs if present (from InterestRateStream)
        pv_float = float(getattr(ir_engine, "_pv_float", 0.0))
        pv_fixed = float(getattr(ir_engine, "_pv_fixed", 0.0))

        swap_notional = float(getattr(self.swap, "notional", self.notional))
        if swap_notional == 0.0:
            raise RuntimeError("Swap notional is zero; cannot compute swaption risk.")
        if float(self.strikeRate) == 0.0:
            raise RuntimeError("Swap fixedRate (strikeRate) is zero; annuity is undefined.")
        if swap_annuity_signed == 0.0:
            raise RuntimeError("Swap annuity is zero; cannot compute par rate sensitivity.")
        
        swap_annuity = abs(swap_annuity_signed)
        sign_annuity = 1.0 if swap_annuity_signed > 0.0 else -1.0

        #  SABR price + greeks 
        price = float(self.sabrCalc.option_price(
            index       = self.swap.index,
            expiry      = t_exp,
            tenor       = t_ten,
            forward     = forward_swap_rate,
            strike      = self.strikeRate,
            option_type = self.optionFlag,
        ))

        normalVol, beta, nu, rho, shift, decay = self.model.get_sabr_parameters(
            index=self.swap.index,
            expiry=t_exp,
            tenor=t_ten,
            product_type=None
        )

        dPrice_dForward, dPrice_dVol, dVol_dForward = self.sabrCalc.option_price_greeks(
            index       = self.swap.index,
            expiry      = t_exp,
            tenor       = t_ten,
            forward     = forward_swap_rate,
            strike      = self.strikeRate,
            option_type = self.optionFlag,
            normal_vol  = normalVol,
            beta        = beta,
            nu          = nu,
            rho         = rho,
            shift       = shift,
            decay       = decay
        )

        dPrice_dForward_total = float(dPrice_dForward) + float(dPrice_dVol) * float(dVol_dForward)

        #  curve slice 
        numCurveParams = int(np.asarray(self.yieldCurve.getGradientArray()).size)
        curveGradient  = gradient[:numCurveParams]

        #  fixed + floating leg engines 
        fixed_leg_engine = ValuationEngineRegistry().new_valuation_engine(self.yieldCurve, ir_vp, self.swap.fixedLeg)
        float_leg_engine = ValuationEngineRegistry().new_valuation_engine(self.yieldCurve, ir_vp, self.swap.floatingLeg)

        fixed_leg_engine.calculateValue()
        _, pv_fixed_check = fixed_leg_engine.value_
        pv_fixed_check = float(pv_fixed_check)

        float_leg_engine.calculateValue()
        _, pv_float_check = float_leg_engine.value_
        pv_float_check = float(pv_float_check)

        if pv_fixed == 0.0 and pv_fixed_check != 0.0:
            pv_fixed = pv_fixed_check
        if pv_float == 0.0 and pv_float_check != 0.0:
            pv_float = pv_float_check

        #  gradients for PV_fixed and PV_float wrt curve params 
        g_pv_fixed = np.zeros(numCurveParams, dtype=float)
        g_pv_float = np.zeros(numCurveParams, dtype=float)

        # accumulate PV_fixed risk (inline walk)
        stack = [fixed_leg_engine]
        while stack:
            eng = stack.pop()

            if hasattr(eng, "_engines"):
                for child in eng._engines:
                    stack.append(child)
                continue

            if hasattr(eng, "_fixed_engine") and hasattr(eng, "_float_engine"):
                stack.append(eng._fixed_engine)
                stack.append(eng._float_engine)
                continue

            eng.calculateFirstOrderRisk(gradient=g_pv_fixed, scaler=1.0, accumulate=True)

        # accumulate PV_float risk (inline walk)
        stack = [float_leg_engine]
        while stack:
            eng = stack.pop()

            if hasattr(eng, "_engines"):
                for child in eng._engines:
                    stack.append(child)
                continue

            if hasattr(eng, "_fixed_engine") and hasattr(eng, "_float_engine"):
                stack.append(eng._fixed_engine)
                stack.append(eng._float_engine)
                continue

            eng.calculateFirstOrderRisk(gradient=g_pv_float, scaler=1.0, accumulate=True)

        #  convert leg PV risks -> annuity/par-rate risks
        dA_dCurve_signed = g_pv_fixed / (float(self.strikeRate) * swap_notional)
        dA_dCurve = sign_annuity * dA_dCurve_signed

        dF_dCurve = (
            -(1.0 / (swap_notional * swap_annuity_signed)) * g_pv_float
            + (pv_float / (swap_notional * swap_annuity_signed * swap_annuity_signed)) * dA_dCurve_signed
        )

        #  push curve risk into global gradient 
        curve_scale = float(scaler) * float(self.notional) * float(self.buyOrSell)
        curveGradient += curve_scale * (price * dA_dCurve + swap_annuity * dPrice_dForward_total * dF_dCurve)

        #  SABR pillar risks 
        pvScale = float(scaler) * float(self.notional) * float(self.buyOrSell) * float(swap_annuity)

        # NORMALVOL
        dVol_dNormalVol = self.sabrCalc.dVol_dNormalVol(
            index     = self.swap.index,
            expiry    = t_exp,
            tenor     = t_ten,
            forward   = forward_swap_rate,
            strike    = self.strikeRate,
            normalVol = normalVol,
            beta      = beta,
            nu        = nu,
            rho       = rho,
            shift     = shift,
            decay     = decay
        )
        accumulate_surface_pillar_risk(
            model=self.model,
            gradient=gradient,
            index=self.swap.index,
            parameter="NORMALVOL",
            expiry_t=t_exp,
            tenor_t=t_ten,
            pvScale=pvScale,
            dPrice_dVol=float(dPrice_dVol),
            dSigma_dP=dVol_dNormalVol,
            product_type_for_scalar=None
        )

        # BETA
        dVol_dBeta = self.sabrCalc.dVol_dBeta(
            index     = self.swap.index,
            expiry    = t_exp,
            tenor     = t_ten,
            forward   = forward_swap_rate,
            strike    = self.strikeRate,
            normalVol = normalVol,
            beta      = beta,
            nu        = nu,
            rho       = rho,
            shift     = shift,
            decay     = decay
        )
        accumulate_surface_pillar_risk(
            model=self.model,
            gradient=gradient,
            index=self.swap.index,
            parameter="BETA",
            expiry_t=t_exp,
            tenor_t=t_ten,
            pvScale=pvScale,
            dPrice_dVol=float(dPrice_dVol),
            dSigma_dP=dVol_dBeta,
            product_type_for_scalar=None
        )

        # NU
        dVol_dNu = self.sabrCalc.dVol_dNu(
            index     = self.swap.index,
            expiry    = t_exp,
            tenor     = t_ten,
            forward   = forward_swap_rate,
            strike    = self.strikeRate,
            normalVol = normalVol,
            beta      = beta,
            nu        = nu,
            rho       = rho,
            shift     = shift,
            decay     = decay
        )
        accumulate_surface_pillar_risk(
            model=self.model,
            gradient=gradient,
            index=self.swap.index,
            parameter="NU",
            expiry_t=t_exp,
            tenor_t=t_ten,
            pvScale=pvScale,
            dPrice_dVol=float(dPrice_dVol),
            dSigma_dP=dVol_dNu,
            product_type_for_scalar=None
        )

        # RHO
        dVol_dRho = self.sabrCalc.dVol_dRho(
            index     = self.swap.index,
            expiry    = t_exp,
            tenor     = t_ten,
            forward   = forward_swap_rate,
            strike    = self.strikeRate,
            normalVol = normalVol,
            beta      = beta,
            nu        = nu,
            rho       = rho,
            shift     = shift,
            decay     = decay
        )
        accumulate_surface_pillar_risk(
            model=self.model,
            gradient=gradient,
            index=self.swap.index,
            parameter="RHO",
            expiry_t=t_exp,
            tenor_t=t_ten,
            pvScale=pvScale,
            dPrice_dVol=float(dPrice_dVol),
            dSigma_dP=dVol_dRho,
            product_type_for_scalar=None
        )

        self.firstOrderRisk_ = gradient


_SABR_ENGINE_MAP = {
    ProductIborCapFloorlet.prodType:       ValuationEngineIborCapFloorlet,
    ProductOvernightCapFloorlet.prodType:  ValuationEngineOvernightCapFloorlet,
    ProductIborCapFloor.prodType:          ValuationEngineIborCapFloor,
    ProductOvernightCapFloor.prodType:     ValuationEngineOvernightCapFloor,
    ProductIborSwaption.prodType:          ValuationEngineIborSwaption,
    ProductOvernightSwaption.prodType:     ValuationEngineOvernightSwaption,
}

for prod_type, eng_cls in _SABR_ENGINE_MAP.items():
    ValuationEngineRegistry().insert(
        SabrModel.MODEL_TYPE,
        prod_type,
        eng_cls
    )