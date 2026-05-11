"""
Module 4 — Risk Engine & Stress Test
=====================================
4.1 Monte Carlo Simulation — 10,000 paths × 30 days GBM
4.2 CVaR 95% — expected loss in worst 5% scenarios
"""

import numpy as np
import pandas as pd

from pipeline.config import MC_N_SIMULATIONS, MC_FORECAST_DAYS, CVAR_ALPHA, TRADING_DAYS


def monte_carlo_sim(
    weights: np.ndarray,
    mu_annual: np.ndarray,
    Sigma_annual: np.ndarray,
    n_sim: int = MC_N_SIMULATIONS,
    days: int = MC_FORECAST_DAYS,
    seed: int = 42,
) -> np.ndarray:
    """
    Geometric Brownian Motion.
    P_t = P_0 · exp((μ - σ²/2)·Δt + L·Z·√Δt)
    Returns (n_sim,) cumulative portfolio returns over forecast period.
    """
    rng = np.random.default_rng(seed)
    N = len(weights)
    dt = 1 / TRADING_DAYS
    mu_daily = mu_annual / TRADING_DAYS
    Sigma_daily = Sigma_annual / TRADING_DAYS

    try:
        L = np.linalg.cholesky(Sigma_daily)
    except np.linalg.LinAlgError:
        Sigma_daily += np.eye(N) * 1e-8
        L = np.linalg.cholesky(Sigma_daily)

    portfolio_returns = np.zeros(n_sim)
    drift = mu_daily - 0.5 * np.diag(Sigma_daily)

    for i in range(n_sim):
        Z = rng.standard_normal((days, N))
        daily_returns = drift + Z @ L.T
        cumulative = np.exp(np.sum(daily_returns, axis=0))
        portfolio_returns[i] = np.dot(weights, cumulative) - 1.0

    return portfolio_returns


def compute_cvar(returns: np.ndarray, alpha: float = CVAR_ALPHA) -> float:
    """CVaR_α = mean of returns below α-percentile."""
    cutoff = int(len(returns) * alpha)
    return np.mean(np.sort(returns)[:cutoff])


def run_risk_assessment(
    weights_df: pd.DataFrame,
    mu_annual: np.ndarray,
    Sigma_annual: np.ndarray,
) -> dict:
    """Full risk assessment: MC simulation → VaR, CVaR, expected return."""
    symbols = weights_df.index.tolist()
    weights = weights_df["weight"].values
    N = len(weights)

    if len(mu_annual) != N:
        raise ValueError(f"mu_annual size {len(mu_annual)} != weights count {N}")

    print(f"[M4] MC: {MC_N_SIMULATIONS:,} paths × {MC_FORECAST_DAYS} days, {N} assets...")

    sim_returns = monte_carlo_sim(weights, mu_annual, Sigma_annual)

    cvar_95 = compute_cvar(sim_returns)
    var_95 = np.percentile(sim_returns, CVAR_ALPHA * 100)
    worst = sim_returns.min()
    expected = sim_returns.mean()
    prob_loss = (sim_returns < 0).mean()

    result = {
        "cvar_95": cvar_95, "var_95": var_95,
        "worst_case": worst, "expected_return_30d": expected,
        "prob_loss": prob_loss, "sim_returns": sim_returns,
    }

    print(f"[M4] ═══ RISK ═══")
    print(f"   Expected 30d: {expected*100:+.2f}%  VaR95: {var_95*100:.2f}%  CVaR95: {cvar_95*100:.2f}%")
    print(f"   Worst case:   {worst*100:.2f}%  P(loss): {prob_loss*100:.1f}%")
    return result
