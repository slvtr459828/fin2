"""
Module 5 — Automated Export (Data Packages)
============================================
Package 1 (TV2 - Vĩ mô):  macro_yield.csv
Package 2 (TV3 - Cơ bản): fundamental_top5.csv
Package 3 (TV4 - PM):     weights_final.csv, efficient_frontier.png, CVaR_Report.txt
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pipeline.config import PKG1_MACRO, PKG2_FUNDAMENTAL, PKG3_PM, TRADING_DAYS


def export_package1_macro(rf_daily: pd.Series):
    """Daily risk-free rate series."""
    PKG1_MACRO.mkdir(parents=True, exist_ok=True)
    path = PKG1_MACRO / "macro_yield.csv"
    df = rf_daily.to_frame("rf_daily")
    df["rf_annual_pct"] = rf_daily * 100 * TRADING_DAYS
    df.index.name = "date"
    df.to_csv(path, float_format="%.8f")
    print(f"[M5] 📦 Package 1: {path} ({len(df)} rows)")


def export_package2_fundamental(
    top5_weights: pd.DataFrame,
    E_R: pd.Series,
    fundamentals: pd.DataFrame,
):
    """Top-5 symbols + E(R) + P/E + P/B."""
    PKG2_FUNDAMENTAL.mkdir(parents=True, exist_ok=True)
    path = PKG2_FUNDAMENTAL / "fundamental_top5.csv"
    rows = []
    for sym in top5_weights.index:
        row = {"symbol": sym, "E_R_annual": E_R.get(sym, np.nan)}
        if sym in fundamentals.index:
            fd = fundamentals.loc[sym]
            row["pb"] = fd.get("pb", np.nan)
            row["pe"] = fd.get("pe", np.nan)
            row["market_cap"] = fd.get("market_cap", np.nan)
        rows.append(row)
    pd.DataFrame(rows).to_csv(path, index=False, float_format="%.6f")
    print(f"[M5] 📦 Package 2: {path}")


def export_package3_pm(
    top5_weights: pd.DataFrame,
    optimizer,
    risk_result: dict,
):
    """Weights CSV + EF chart + CVaR report."""
    PKG3_PM.mkdir(parents=True, exist_ok=True)

    # Weights
    wp = PKG3_PM / "weights_final.csv"
    top5_weights.to_csv(wp, float_format="%.4f")
    print(f"[M5] 📦 Package 3 — weights: {wp}")

    # EF chart
    efp = PKG3_PM / "efficient_frontier.png"
    _plot_ef(optimizer, efp)
    print(f"[M5] 📦 Package 3 — EF: {efp}")

    # CVaR report
    cp = PKG3_PM / "CVaR_Report.txt"
    c = risk_result
    report = (
        f"=== CVaR RISK REPORT ===\n"
        f"Date: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"Portfolio: {', '.join(top5_weights.index.tolist())}\n\n"
        f"Expected 30d return: {c['expected_return_30d']*100:+.2f}%\n"
        f"VaR 95% (30d):       {c['var_95']*100:.2f}%\n"
        f"CVaR 95% (30d):      {c['cvar_95']*100:.2f}%\n"
        f"P(loss):             {c['prob_loss']*100:.1f}%\n\n"
        f"--- KHUYẾN NGHỊ ---\n"
        f"Trong trường hợp tồi tệ nhất (5% đuôi phân phối),\n"
        f"danh mục dự kiến sụt giảm {abs(c['cvar_95'])*100:.2f}% trong 30 phiên.\n"
        f"Stop-loss khuyến nghị: -{abs(c['cvar_95'])*2*100:.2f}% (2× CVaR).\n"
    )
    cp.write_text(report)
    print(f"[M5] 📦 Package 3 — CVaR: {cp}")


def _plot_ef(optimizer, path: str):
    """Efficient frontier plot."""
    mu = optimizer.mu
    Sigma = optimizer.Sigma

    targets = np.linspace(mu.min(), mu.max(), 50)
    frontier_ret, frontier_risk = [], []
    for t in targets:
        try:
            w = optimizer.solve(mode="target_return", target_return=t, rf=0.04)
            frontier_ret.append(w @ mu)
            frontier_risk.append(np.sqrt(w @ Sigma @ w))
        except Exception:
            pass

    # Re-solve max Sharpe for the gold star dot
    try:
        w_opt = optimizer.solve(mode="max_sharpe", rf=0.04)
    except Exception:
        w_opt = None

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(np.sqrt(np.diag(Sigma)), mu, c="steelblue", alpha=0.5, s=30)
    if frontier_risk:
        ax.plot(frontier_risk, frontier_ret, "r-", lw=2, label="Efficient Frontier")

    if w_opt is not None:
        rp_opt = w_opt @ mu
        sp_opt = np.sqrt(w_opt @ Sigma @ w_opt)
        ax.scatter([sp_opt], [rp_opt], c="gold", s=150,
                   edgecolors="black", zorder=5, label="Max Sharpe")
        ax.scatter([np.sqrt(w @ Sigma @ w)], [w @ mu], c="gold", s=150,
                   edgecolors="black", zorder=5, label="Optimal")

    ax.set_xlabel("Annualized Volatility")
    ax.set_ylabel("Annualized Expected Return")
    ax.set_title("Efficient Frontier — VN100 Portfolio")
    ax.legend(); ax.grid(True, alpha=0.3)
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)
