"""
Module 2 — Alpha Generation (Fama-French 3-Factor)
===================================================
2.1 Construct SMB & HML factor series from Market Cap / P/B sorts
2.2 Run OLS regression FF3 per stock
2.3 Compute forward-looking E(R) with fixed E(Rm), E(SMB), E(HML)
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm

from pipeline.config import E_Rm, E_SMB, E_HML


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  2.1 — Fama-French Factor Construction (SMB, HML)                  ║
# ╚══════════════════════════════════════════════════════════════════════╝

def construct_factors(
    R_stocks: np.ndarray,
    symbols: list[str],
    dates: pd.DatetimeIndex,
    fundamentals: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Build daily SMB and HML factor series.

    - Sort by Market Cap → median split → Small (S) / Big (B)
    - Sort by P/B → 30/40/30 → High (H) / Medium (M) / Low (L)
    - Intersection → 6 portfolios, equal-weighted daily return
    - SMB = avg(S/H, S/M, S/L) - avg(B/H, B/M, B/L)
    - HML = avg(S/H, B/H) - avg(S/L, B/L)
    """
    T, N = R_stocks.shape
    R_df = pd.DataFrame(R_stocks, index=dates, columns=symbols)

    common = [s for s in symbols if s in fundamentals.index]
    if len(common) < 20:
        raise RuntimeError(f"Chỉ có {len(common)} mã có fundamental data, cần ≥20.")

    fund = fundamentals.loc[common].copy()
    R_sub = R_df[common]

    # Size sort — coerce to numeric (API may return strings)
    mcap = pd.to_numeric(fund["market_cap"], errors="coerce")
    has_mcap = mcap.notna() & (mcap > 0)
    if has_mcap.sum() < 10:
        raise RuntimeError("Không đủ Market Cap data.")

    mcap_median = mcap[has_mcap].median()
    small_mask = (mcap <= mcap_median) & has_mcap
    big_mask   = (mcap > mcap_median)  & has_mcap

    # Value sort (30/40/30) — coerce to numeric
    pb = pd.to_numeric(fund["pb"], errors="coerce")
    has_pb = pb.notna() & (pb > 0)
    if has_pb.sum() < 10:
        raise RuntimeError("Không đủ P/B data.")

    pb_sorted = pb[has_pb].sort_values()
    n_pb = len(pb_sorted)
    lo_cut = int(n_pb * 0.30)
    hi_cut = int(n_pb * 0.70)

    low_pb_mask  = pd.Series(False, index=fund.index)
    high_pb_mask = pd.Series(False, index=fund.index)
    low_pb_mask[pb_sorted.index[:lo_cut]] = True
    high_pb_mask[pb_sorted.index[hi_cut:]] = True

    # Assign 6 portfolios
    portfolios = {"SH": [], "SM": [], "SL": [], "BH": [], "BM": [], "BL": []}
    for sym in common:
        s = "S" if sym in small_mask[small_mask].index else "B"
        if high_pb_mask[sym]:
            v = "H"
        elif low_pb_mask[sym]:
            v = "L"
        else:
            v = "M"
        portfolios[f"{s}{v}"].append(sym)

    print(f"[M2] 6 portfolios: " + ", ".join(f"{k}={len(v)}" for k, v in portfolios.items()))

    # Daily equal-weighted returns
    port_returns = {}
    for name, mems in portfolios.items():
        port_returns[name] = R_sub[mems].mean(axis=1) if mems else pd.Series(0.0, index=dates)

    SMB = (
        (port_returns["SH"] + port_returns["SM"] + port_returns["SL"]) / 3
        - (port_returns["BH"] + port_returns["BM"] + port_returns["BL"]) / 3
    )
    HML = (
        (port_returns["SH"] + port_returns["BH"]) / 2
        - (port_returns["SL"] + port_returns["BL"]) / 2
    )

    print(f"[M2] ✅ SMB ann={SMB.mean()*252:.4f}, HML ann={HML.mean()*252:.4f}")
    SMB = SMB.fillna(0.0).values.astype(np.float64)
    HML = HML.fillna(0.0).values.astype(np.float64)
    return SMB, HML


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  2.2 — OLS Regression (FF3 per stock)                              ║
# ╚══════════════════════════════════════════════════════════════════════╝

def run_ff3_regression(
    excess_returns: np.ndarray,
    mkt_excess: np.ndarray,
    smb: np.ndarray,
    hml: np.ndarray,
) -> dict:
    """R_i - R_f = α + β1·(R_m - R_f) + β2·SMB + β3·HML + ε"""
    T = min(len(excess_returns), len(mkt_excess), len(smb), len(hml))
    y = excess_returns[-T:].copy()
    X = np.column_stack([mkt_excess[-T:], smb[-T:], hml[-T:]])

    # Drop rows with NaN/Inf in y or X
    valid = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
    y, X = y[valid], X[valid]

    if len(y) < 10:
        raise ValueError("Not enough valid data points after NaN removal")

    X = sm.add_constant(X)
    model = sm.OLS(y, X).fit()
    return {
        "alpha":    model.params[0],
        "beta_mkt": model.params[1],
        "beta_smb": model.params[2],
        "beta_hml": model.params[3],
        "r_squared": model.rsquared,
        "t_mkt":    model.tvalues[1],
        "resid_std": np.std(model.resid, ddof=4),
    }


def run_ff3_all_stocks(
    R_excess: np.ndarray,
    symbols: list[str],
    mkt_excess: np.ndarray,
    smb: np.ndarray,
    hml: np.ndarray,
) -> pd.DataFrame:
    """Run FF3 regression for all N stocks. Returns DataFrame index=symbol."""
    T, N = R_excess.shape
    records = []
    for i, sym in enumerate(symbols):
        try:
            r = run_ff3_regression(R_excess[:, i], mkt_excess, smb, hml)
            records.append({"symbol": sym, **r})
        except Exception as e:
            print(f"  ⚠️ FF3 failed: {sym}: {e}")

    df = pd.DataFrame(records).set_index("symbol")
    print(f"[M2] ✅ FF3: {len(df)}/{N} stocks, mean R²={df['r_squared'].mean():.3f}")
    return df


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  2.3 — Forward-Looking E(R)                                        ║
# ╚══════════════════════════════════════════════════════════════════════╝

def compute_expected_returns(
    ff3_results: pd.DataFrame,
    rf: float,
    E_Rm: float = E_Rm,
    E_SMB: float = E_SMB,
    E_HML: float = E_HML,
) -> pd.Series:
    """
    E(R_i) = rf + β_mkt·(E_Rm - rf) + β_smb·E_SMB + β_hml·E_HML
    Returns Series index=symbol, sorted descending.
    """
    df = ff3_results
    expected = (
        rf
        + df["beta_mkt"] * (E_Rm - rf)
        + df["beta_smb"] * E_SMB
        + df["beta_hml"] * E_HML
    )
    expected.name = "E_R"
    print(f"[M2] ✅ E(R): {len(expected)} stocks, "
          f"range [{expected.min():.2%}, {expected.max():.2%}]")
    return expected.sort_values(ascending=False)
