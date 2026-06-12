# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VN100 quantitative portfolio restructuring pipeline — restructures a ~911M VND portfolio of 5 Vietnamese stocks using Fama-French 3-Factor → Markowitz optimization → Monte Carlo CVaR. Data source is the `vnstock_data` library (Vietnam stock market API wrapper).

## Commands

```bash
# Full pipeline (M1→M5): data ingestion → FF3 → Markowitz → risk → export
~/.venv/bin/python3 -m pipeline.main

# Trade execution report (M6): daily tracking, execution plan, post-restructuring evaluation
~/.venv/bin/python3 -m pipeline.trade_execution

# Convert all Parquet cache files to CSV
~/.venv/bin/python3 export_pqt_to_csv.py
```

All commands run from the repo root. The Python interpreter is `~/.venv/bin/python3`.

## Architecture

The pipeline is a linear 6-module flow defined in `pipeline/`. Each module reads from the previous module's output; there's no circular dependency.

```
pipeline/config.py         → Paths, dates, constants, portfolio constraints, locked weights
pipeline/data_ingestion.py → M1: Fetch VN100 OHLCV, VN-Index, bond yield, fundamentals
pipeline/fama_french.py    → M2: Construct SMB/HML factors, OLS regression per stock, E(R)
pipeline/markowitz.py      → M3: Filter top-20 by E(R), covariance matrix, Sharpe maximization
pipeline/risk_engine.py    → M4: Monte Carlo GBM (10k paths × 30 days), CVaR 95%
pipeline/export_packages.py → M5: Write 3 data packages (macro, fundamental, PM) to export/
pipeline/trade_execution.py → M6: Daily price tracking, execution plan, post-restructuring eval
pipeline/main.py           → Orchestrator: wires M1→M5 via `main()`
```

**Data flow:** `vn100_data/` holds Parquet caches (OHLCV, close prices, log returns). `export/` holds output packages, execution reports, and post-restructuring analysis. The orchestrator in `main.py` calls each module in sequence, passing numpy arrays and DataFrames between them — no intermediate serialization between M1→M4.

### M6 details (trade_execution.py)

Beyond the execution plan and daily tracking chart, `trade_execution.py` includes `evaluate_at_may20()` — a post-restructuring evaluation that compares actual portfolio performance at 2026-05-20 against the Monte Carlo expected 30-day return. It outputs `performance_20May.csv` and prints alpha vs. holding the old portfolio.

## Key Dependencies

- **vnstock_data** — VN stock market data API (`Market`, `Reference`, `Fundamental` classes)
- **statsmodels** — OLS regression for Fama-French factor loadings
- **scipy.optimize** — SLSQP solver for Markowitz Sharpe maximization
- **numpy** — Cholesky decomposition for Monte Carlo, matrix operations
- **pandas / pyarrow** — DataFrame ops and Parquet cache I/O
- **matplotlib** — Efficient frontier and tracking charts (Agg backend)
- **openpyxl** — Excel export for execution plan (optional, trade_execution.py only)

## Important Conventions

- **Vietnamese naming throughout**: comments, print output, and CSV headers are in Vietnamese. Data files may have Vietnamese filenames (e.g., bond yield CSV). This is intentional — the target audience is Vietnamese.
- **Cache-first ingestion**: `data_ingestion.py` checks Parquet caches before calling the API. To force re-fetch, delete the relevant `.pqt` files in `vn100_data/`. Incremental fetch is supported: only missing data or data newer than cache is fetched.
- **Deterministic runs**: Random seeds are fixed (42) in `main.py` and `risk_engine.py`.
- **Config is centralized**: All tunable parameters live in `pipeline/config.py` — dates (currently 2021-01-01 → 2026-06-05), constraints, factor premiums, Monte Carlo settings, and the locked final portfolio weights (`FINAL_PORTFOLIO` dict).

## Output Structure

| Directory | Contents | Produced By |
|---|---|---|
| `export/package1_macro/` | `macro_yield.csv` (daily rf series) | M5 |
| `export/package2_fundamental/` | `fundamental_top5.csv` (E(R), P/E, P/B) | M5 |
| `export/package3_pm/` | `weights_final.csv`, `efficient_frontier.png`, `CVaR_Report.txt` | M5 |
| `export/execution_report/` | `execution_plan.xlsx`, `daily_tracking.png`, `daily_values.csv`, `daily_prices.csv`, `performance_20May.csv` | M6 |
| `export/optimal_report/` | Manual post-restructuring analysis artifacts (comparison, execution log, charts, report sections) | Manual |

## Locked Final Portfolio (as of 2026-06-05)

Weights are locked in `pipeline/config.py` → `FINAL_PORTFOLIO`:

| Symbol | Weight |
|---|---|
| FPT | 35.11% |
| SIP | 17.81% |
| VTP | 17.50% |
| CTR | 17.23% |
| VHC | 12.35% |

## Entry Point

`pipeline.main.main()` is the single entry point for the full pipeline. It imports and calls each module function directly — there is no parameterized wrapper. To change parameters, edit `pipeline/config.py` directly. The function prints progress and a summary to stdout; it returns `None`.
