#!/usr/bin/env python3
"""
Pipeline Orchestrator — VN100 Fama-French + Markowitz + Monte Carlo
====================================================================
M1: Data Ingestion  →  OHLCV, VN-Index, Bond Yield, Fundamentals
M2: Fama-French     →  SMB/HML factors, FF3 regression, E(R)
M3: Markowitz       →  Filter top-20, optimize with constraints, top-5
M4: Risk Engine     →  Monte Carlo 10k×30d, CVaR 95%
M5: Export          →  3 data packages (macro, fundamental, PM)

Usage: ~/.venv/bin/python3 -m pipeline.main
"""

import time
import numpy as np
import pandas as pd

from pipeline.data_ingestion import (
    get_vn100_symbols, fetch_vn100_ohlcv, fetch_vnindex_ohlcv,
    build_close_matrix, compute_log_returns, compute_vnindex_log_returns,
    load_bond_yield, compute_daily_rf, compute_excess_returns, fetch_fundamentals,
)
from pipeline.fama_french import (
    construct_factors, run_ff3_all_stocks, compute_expected_returns,
)
from pipeline.markowitz import run_markowitz_pipeline
from pipeline.risk_engine import run_risk_assessment
from pipeline.export_packages import (
    export_package1_macro, export_package2_fundamental, export_package3_pm,
)
from pipeline.config import (
    START_DATE, END_DATE, E_Rm, E_SMB, E_HML,
    FPT_MIN_WEIGHT, TRADING_DAYS, ensure_dirs,
)


def main():
    ensure_dirs()
    t0 = time.time()

    print("╔══════════════════════════════════════════════════════════╗")
    print("║  VN100 PIPELINE — FF3 + MARKOWITZ + MC                 ║")
    print("╚══════════════════════════════════════════════════════════╝")

    # ═══ M1: DATA INGESTION ═══════════════════════════════════════
    print("\n" + "=" * 60)
    print("  MODULE 1 — DATA INGESTION")
    print("=" * 60)

    symbols = get_vn100_symbols()
    ohlcv_dict = fetch_vn100_ohlcv(symbols)
    vnindex_df = fetch_vnindex_ohlcv()

    close = build_close_matrix(ohlcv_dict)
    R_daily, active_symbols, dates = compute_log_returns(close)
    r_m_daily = compute_vnindex_log_returns(vnindex_df)

    T = min(R_daily.shape[0], len(r_m_daily))
    R_daily = R_daily[-T:]
    r_m_daily = r_m_daily[-T:]

    bond_yield = load_bond_yield()
    rf_daily = compute_daily_rf(bond_yield)
    rf_latest = bond_yield.iloc[-1] / 100.0

    R_excess = compute_excess_returns(R_daily, rf_daily, dates[-T:])
    stock_dates = pd.DatetimeIndex(dates[-T:]).normalize()
    rf_aligned = rf_daily.copy()
    rf_aligned.index = rf_aligned.index.normalize()
    rf_vals = rf_aligned.reindex(stock_dates).ffill().bfill().values
    mkt_excess = r_m_daily - rf_vals

    fundamentals = fetch_fundamentals(active_symbols)

    # ═══ M2: FAMA-FRENCH ═══════════════════════════════════════════
    print("\n" + "=" * 60)
    print("  MODULE 2 — FAMA-FRENCH ALPHA GENERATION")
    print("=" * 60)

    smb, hml = construct_factors(R_daily, active_symbols, dates[-T:], fundamentals)
    ff3_results = run_ff3_all_stocks(R_excess, active_symbols, mkt_excess, smb, hml)
    E_R = compute_expected_returns(ff3_results, rf=rf_latest)

    print(f"\n   Forward assumptions: E(Rm)={E_Rm:.0%}, E(SMB)={E_SMB:.0%}, "
          f"E(HML)={E_HML:.0%}, rf={rf_latest:.2%}")
    print(f"   Top 10 E(R):")
    for sym, er in E_R.head(10).items():
        print(f"     {sym:<6} {er:.2%}")

    # ═══ M3: MARKOWITZ ═════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("  MODULE 3 — MARKOWITZ OPTIMIZATION")
    print("=" * 60)

    top5, R_sel, optimizer = run_markowitz_pipeline(
        E_R=E_R, R_daily=R_daily, symbols=active_symbols,
        rf=rf_latest,
        force_include=["FPT"],
        min_weights={"FPT": FPT_MIN_WEIGHT},
    )

    # ═══ M4: RISK ENGINE ═══════════════════════════════════════════
    print("\n" + "=" * 60)
    print("  MODULE 4 — RISK ENGINE")
    print("=" * 60)

    sel_symbols = top5.index.tolist()
    idx_map = {s: i for i, s in enumerate(active_symbols)}
    idxs = [idx_map[s] for s in sel_symbols]
    R_top5 = R_daily[:, idxs]
    mu_top5 = np.array([E_R.get(s, E_R.median()) for s in sel_symbols])
    Sigma_top5 = np.cov(R_top5, rowvar=False) * TRADING_DAYS

    risk = run_risk_assessment(top5, mu_top5, Sigma_top5)

    # ═══ M5: EXPORT ═════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("  MODULE 5 — EXPORT PACKAGES")
    print("=" * 60)

    export_package1_macro(rf_daily)
    export_package2_fundamental(top5, E_R, fundamentals)
    export_package3_pm(top5, optimizer, risk)

    # ═══ SUMMARY ═════════════════════════════════════════════════════
    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"  ✅ PIPELINE COMPLETE — {elapsed:.0f}s")
    print(f"  {START_DATE} → {END_DATE} | {len(active_symbols)} stocks | {T} days")
    print(f"  Top-5: {', '.join(sel_symbols)}")
    print(f"  FPT ≥{FPT_MIN_WEIGHT:.0%} ✓")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
