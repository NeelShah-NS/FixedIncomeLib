from typing import Any, Dict, List, Tuple, Union
from fixedincomelib.valuation import ValuationEngineRegistry

def check_calibration(
    component: Any,
    verbose: bool = True,
    return_rows: bool = False) -> Union[float, Tuple[float, List[Dict[str, Any]]]]:
    engine_registry = ValuationEngineRegistry()
    valuation_params = {"FUNDING INDEX": component.target}

    diagnostic_rows: List[Dict[str, Any]] = []
    max_abs_pv: float = 0.0

    for node in component.nodes:
        instrument = node.instrument
        product_type = instrument.prodType.upper()
        
        engine = engine_registry.new_valuation_engine(
            component._model, valuation_params, instrument
        )
        engine.calculateValue()
        currency, pv_raw = engine.value_
        present_value = float(pv_raw)

        if abs(present_value) > max_abs_pv:
            max_abs_pv = abs(present_value)

        record: Dict[str, Any] = {
            "node": node.node_id,
            "present_value": present_value,
            "product_type": product_type,
        }

        base_msg = f"{node.node_id:40s}  PV={present_value:+.6e}"

        if "FUTURE" in product_type:
            model_forward_rate = float(
                component._model.forward(
                    instrument.index,
                    instrument.effectiveDate,
                    instrument.maturityDate,
                )
            )
            model_futures_price = 100.0 * (1.0 - model_forward_rate)
            market_futures_price = float(instrument.strike)
            price_error = model_futures_price - market_futures_price

            record.update(
                {
                    "model_forward_rate": model_forward_rate,
                    "model_futures_price": model_futures_price,
                    "market_futures_price": market_futures_price,
                    "futures_price_error": price_error,
                }
            )

            if verbose:
                print(
                    f"{base_msg}  Fut model={model_futures_price:.4f}  "
                    f"mkt={market_futures_price:.4f}  price_error={price_error:+.4e}"
                )

        elif "SWAP" in product_type:
            par_rate = float(engine.parRateOrSpread())
            market_fixed_rate = float(instrument.fixedRate)
            par_minus_market = par_rate - market_fixed_rate

            record.update(
                {
                    "par_rate": par_rate,
                    "market_fixed_rate": market_fixed_rate,
                    "par_minus_market": par_minus_market,
                }
            )

            if verbose:
                print(
                    f"{base_msg}  Par={par_rate:.6f}  K={market_fixed_rate:.6f}  "
                    f"price_error={par_minus_market:+.2e}"
                )
        else:
            if verbose:
                print(base_msg)

        diagnostic_rows.append(record)

    if verbose:
        print("max |PV| =", max_abs_pv)

    return (max_abs_pv, diagnostic_rows) if return_rows else max_abs_pv


def assert_calibrated(component: Any, tolerance: float = 1e-10) -> None:
    max_abs_pv = check_calibration(component, verbose=False, return_rows=False)
    if max_abs_pv > tolerance:
        raise AssertionError(f"Calibration residual too large: {max_abs_pv} > {tolerance}")
