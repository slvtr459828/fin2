"""
Module 3 — Markowitz Core Optimizer
====================================
3.1 Filter: top-20 by E(R) + force-in FPT
3.2 Covariance matrix Σ from full returns, annualized
3.3 Maximize Sharpe with per-symbol constraints
3.4 Post-process: drop w<1%, keep top-5
"""

from typing import Optional

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from pipeline.config import (
    MAX_WEIGHT_PER_STOCK, FPT_MIN_WEIGHT,
    TOP_N_FILTER, FINAL_TOP_K, TRADING_DAYS,
)


def _compute_covariance(R: np.ndarray) -> np.ndarray:
    T = R.shape[0]
    R_centered = R - R.mean(axis=0)
    return (R_centered.T @ R_centered) / (T - 1)


def filter_top_stocks(
    E_R: pd.Series,
    R_daily: np.ndarray,
    symbols: list[str],
    force_include: list[str] = None,
) -> tuple[list[str], np.ndarray]:
    """Select top-N by E(R), ensure force_include present. Returns (symbols, R_selected)."""
    force_include = force_include or []

    # Start with force-included
    selected = [s for s in force_include if s in E_R.index]

    # Fill remaining slots from top E(R)
    for sym in E_R.index:
        if sym in selected:
            continue
        if len(selected) >= TOP_N_FILTER:
            break
        selected.append(sym)

    # Map to return matrix columns
    idx_map = {s: i for i, s in enumerate(symbols)}
    idxs = [idx_map[s] for s in selected if s in idx_map]
    R_filtered = R_daily[:, idxs]
    actual = [symbols[i] for i in idxs]

    print(f"[M3] ✅ Filtered {len(actual)} stocks (force-in: {[s for s in force_include if s in actual]})")
    return actual, R_filtered


class ConstrainedOptimizer:
    """Markowitz optimizer with per-symbol minimum weight constraints."""

    def __init__(self, mu: np.ndarray, Sigma: np.ndarray, symbols: list[str]):
        self.mu = mu
        self.Sigma = Sigma
        self.symbols = symbols
        self.N = len(symbols)
        self._last_weights: Optional[np.ndarray] = None

    def _make_bounds(self, min_weights: dict[str, float]) -> list[tuple]:
        bounds = []
        for i, sym in enumerate(self.symbols):
            lo = max(0.0, min_weights.get(sym, 0.0))
            bounds.append((lo, MAX_WEIGHT_PER_STOCK))
        return bounds

    def _make_constraints(self, min_weights: dict[str, float]) -> list[dict]:
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        for sym, mw in min_weights.items():
            if sym in self.symbols:
                idx = self.symbols.index(sym)
                constraints.append({
                    "type": "ineq",
                    "fun": lambda w, i=idx, mw=mw: w[i] - mw,
                })
        return constraints

    def _negative_sharpe(self, w: np.ndarray, rf: float) -> float:
        rp = w @ self.mu
        vp = w @ self.Sigma @ w
        return -(rp - rf) / max(np.sqrt(vp), 1e-12)

    def solve(self, rf: float, min_weights: dict[str, float] = None) -> np.ndarray:
        min_weights = min_weights or {}
        bounds = self._make_bounds(min_weights)
        constraints = self._make_constraints(min_weights)

        total_min = sum(min_weights.get(s, 0.0) for s in self.symbols)
        if total_min > 1.0:
            raise ValueError(f"Tổng min_weights ({total_min}) > 1.0.")

        x0 = np.ones(self.N) / self.N
        for sym, mw in min_weights.items():
            if sym in self.symbols:
                x0[self.symbols.index(sym)] = max(x0[self.symbols.index(sym)], mw)
        x0 = x0 / x0.sum()

        result = minimize(
            lambda w: self._negative_sharpe(w, rf),
            x0, method="SLSQP",
            bounds=bounds, constraints=constraints,
            options={"maxiter": 5000, "ftol": 1e-12},
        )
        if not result.success:
            raise RuntimeError(f"Optimizer failed: {result.message}")

        self._last_weights = result.x
        return result.x

    def top_k_weights(self, w: np.ndarray, k: int = FINAL_TOP_K) -> pd.DataFrame:
        """Drop w < 0.01, keep top-k, re-normalize."""
        df = pd.DataFrame({"symbol": self.symbols, "weight": w})
        df = df[df["weight"] >= 0.01].nlargest(k, "weight").copy()
        df["weight"] = df["weight"] / df["weight"].sum()
        return df.set_index("symbol")


def run_markowitz_pipeline(
    E_R: pd.Series,
    R_daily: np.ndarray,
    symbols: list[str],
    rf: float,
    force_include: list[str] = None,
    min_weights: dict[str, float] = None,
) -> tuple[pd.DataFrame, np.ndarray, ConstrainedOptimizer]:
    """Full Module 3: filter → covariance → optimize → top-k."""
    sel_symbols, R_sel = filter_top_stocks(E_R, R_daily, symbols, force_include)

    Sigma_annual = _compute_covariance(R_sel) * TRADING_DAYS
    mu_sel = np.array([E_R.get(s, E_R.median()) for s in sel_symbols])

    opt = ConstrainedOptimizer(mu_sel, Sigma_annual, sel_symbols)
    w = opt.solve(rf=rf, min_weights=min_weights)
    top_k = opt.top_k_weights(w)

    rp = w @ mu_sel
    sp = np.sqrt(w @ Sigma_annual @ w)
    sharpe = (rp - rf) / max(sp, 1e-12)

    print(f"\n[M3] ═══ PORTFOLIO ═══")
    print(f"   Return: {rp*100:.2f}%  Risk: {sp*100:.2f}%  Sharpe: {sharpe:.3f}")
    for sym, row in top_k.iterrows():
        print(f"     {sym:<6} {row['weight']:8.2%}")

    return top_k, R_sel, opt
