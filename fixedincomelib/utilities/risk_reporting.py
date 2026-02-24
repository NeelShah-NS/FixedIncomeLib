import numpy as np
import pandas as pd
from fixedincomelib.valuation import ValuationEngineRegistry

def createValueReport(valuation_parameters, model, product, request="all", space="pv"):
    ve = ValuationEngineRegistry().new_valuation_engine(model, valuation_parameters, product)

    # 1) PV
    if request in ("value", "all"):
        ve.calculateValue()
        _, pv = ve.value_
        if request == "value":
            return float(pv)

    # 2) Risk
    if request in ("firstOrderRisk", "all"):
        J_pv = np.asarray(model.jacobian(), dtype=float) 
        ve.calculateFirstOrderRisk()
        g = np.asarray(ve.firstOrderRisk_, dtype=float).copy()
        param_risk = np.linalg.solve(J_pv.T, g)

        out = {"pv": pv, "g_theta": g, "param_risk": param_risk}

        if space.lower() == "pv":
            return param_risk if request == "firstOrderRisk" else out

        if space.lower() == "quote":
            S = np.asarray(model.calibration_quote_sensitivity(), dtype=float)
            quote_risk = S * param_risk
            out["quote_risk"] = quote_risk
            return quote_risk if request == "firstOrderRisk" else out

        raise ValueError("space must be 'pv' or 'quote'")

    raise ValueError("request must be one of: 'value', 'firstOrderRisk', 'all'")

pd.set_option("display.max_rows", 500)
pd.set_option("display.max_columns", 50)
pd.set_option("display.float_format", lambda x: f"{x:,.6f}")

SABR_PARAMS = {"NORMALVOL","BETA","NU","RHO"}

def risk_vectors_to_df(model, report, yc_index="SOFR-1B"):
    pv = report.get("pv", None)
    g  = np.asarray(report["g_theta"], float)         
    w  = np.asarray(report["param_risk"], float)       
    qr = report.get("quote_risk", None)
    qr = (np.asarray(qr, float) if qr is not None else None)

    n_yc = int(model._n_yc_params)

    rows = []

    # YC block 
    yc = model.subModel_
    yc_comp = yc.retrieveComponent(yc_index)
    for k, node in enumerate(yc_comp.nodes):
        pos = k
        rows.append(dict(
            block="YC",
            index=yc_index,
            param="IFR",
            expiry=np.nan,
            tenor=np.nan,
            node=getattr(node, "node_id", f"YC[{k}]"),
            pos=pos,
            dPV_dModelParam=g[pos],
            hedgeWeightPV=w[pos],
            dPV_dQuote=(qr[pos] if qr is not None else np.nan),
        ))

    #  SABR blocks 
    for key, sl in model._sabr_slice_by_key.items():
        keyu = str(key).upper()
        parts = keyu.split("-")
        sabr_param = parts[-1] if parts[-1] in SABR_PARAMS else "UNKNOWN"
        idx_name = "-".join(parts[:-1]) if sabr_param != "UNKNOWN" else parts[0]

        comp = model.components[key]
        axis1 = list(comp.axis1)
        axis2 = list(comp.axis2)
        n1, n2 = len(axis1), len(axis2)
        expected = n1 * n2
        if (sl.stop - sl.start) != expected:
            raise ValueError(f"{key}: slice len != grid len ({expected})")

        base = n_yc + sl.start

        for local in range(expected):
            i = local // n2
            j = local % n2
            pos = base + local
            rows.append(dict(
                block="SABR",
                index=idx_name,
                param=sabr_param,
                expiry=float(axis1[i]),
                tenor=float(axis2[j]),
                node=f"{sabr_param} @ ({axis1[i]:g}y x {axis2[j]:g}y)",
                pos=pos,
                dPV_dModelParam=g[pos],
                hedgeWeightPV=w[pos],
                dPV_dQuote=(qr[pos] if qr is not None else np.nan),
            ))

    df = pd.DataFrame(rows)

    df["abs_model"] = df["dPV_dModelParam"].abs()
    df["abs_weight"] = df["hedgeWeightPV"].abs()
    df["abs_quote"] = df["dPV_dQuote"].abs() if "dPV_dQuote" in df else np.nan

    df = df.reset_index(drop=True)
    df.attrs["pv"] = pv
    df.attrs["n_yc"] = n_yc
    return df