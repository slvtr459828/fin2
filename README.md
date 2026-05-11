# VN100 Quantitative Portfolio Restructuring

Pipeline đầu tư định lượng tái cơ cấu danh mục 911M VND từ 5 năm dữ liệu VN100 qua
Fama-French 3-Factor → Markowitz → Monte Carlo CVaR.

## Mục tiêu

Tái cơ cấu danh mục 5 mã (FPT, SZC, DGC, FTS, VPB) đang lỗ -28.3% (20/04/2026)
thành danh mục tối ưu dựa trên dữ liệu định lượng.

## Kiến trúc

```
fin2/
├── pipeline/                    ← Core (6 modules + orchestrator)
│   ├── config.py               ← Paths, constants, constraints
│   ├── data_ingestion.py       ← M1: OHLCV, VN-Index, Bond Yield, Fundamentals
│   ├── fama_french.py          ← M2: FF3 factors, OLS, E(R)
│   ├── markowitz.py            ← M3: Filter, optimize, constraints, top-5
│   ├── risk_engine.py          ← M4: Monte Carlo GBM, CVaR 95%
│   ├── export_packages.py      ← M5: 3 export packages
│   ├── trade_execution.py      ← M6: Daily tracking, execution plan
│   └── main.py                 ← Orchestrator M1→M6
├── export/                      ← Output
│   ├── package1_macro/          ← TV2: macro_yield.csv + yield_curve.png
│   ├── package2_fundamental/    ← TV3: fundamental_top5.csv
│   ├── package3_pm/             ← TV4: weights, EF chart, CVaR report
│   └── execution_report/        ← Trade plan (.xlsx), daily tracking chart
├── vn100_data/                  ← OHLCV cache (Parquet)
└── vnstock_data_api_reference.md ← API reference
```

## Flow tổng thể

```
┌─────────────────────────────────────────────────────────────────────┐
│ M1: DATA INGESTION                                                 │
│ 100 VN100 stocks × 5yr OHLCV → Log Returns (T×N matrix)           │
│ VN-Index log returns → R_m                                        │
│ VN 10Y Bond Yield → daily R_f → Excess Returns = R_i − R_f       │
│ Fundamentals: Market Cap, P/B, P/E via KBS summary API            │
├─────────────────────────────────────────────────────────────────────┤
│ M2: ALPHA GENERATION (Fama-French 3-Factor)                       │
│ Sort by MCap (S/B) + P/B (H/M/L) → 6 portfolios                  │
│ SMB = Small − Big, HML = High PB − Low PB                         │
│ OLS per stock: R_i−R_f = α + β1(R_m−R_f) + β2·SMB + β3·HML + ε  │
│ Forward E(R) = rf + β_mkt·(E_Rm−rf) + β_smb·E_SMB + β_hml·E_HML  │
├─────────────────────────────────────────────────────────────────────┤
│ M3: MARKOWITZ OPTIMIZATION                                        │
│ Top-20 by E(R) + volume >50B + force-in FPT                       │
│ Σ from 1300-day returns × 252 annualized                          │
│ Maximize Sharpe: max (w·E(R)−rf) / √(w·Σ·w)                       │
│ Constraints: Σw=1, 0≤w≤0.3, w_FPT≥0.2, drop w<0.01 → top-5      │
├─────────────────────────────────────────────────────────────────────┤
│ M4: RISK ENGINE                                                   │
│ Monte Carlo 10,000 paths × 30 days (Cholesky GBM)                 │
│ CVaR 95% = mean of worst 5% scenarios                             │
├─────────────────────────────────────────────────────────────────────┤
│ M5: EXPORT                                                        │
│ Package 1 (TV2 Macro): bond yield time series + chart             │
│ Package 2 (TV3 Fundamental): top-5 + E(R) + P/E + P/B             │
│ Package 3 (TV4 PM): final weights, EF chart, CVaR report          │
├─────────────────────────────────────────────────────────────────────┤
│ M6: TRADE EXECUTION                                               │
│ Daily price tracking 20/04→11/05/2026                             │
│ Optimal entry/exit dates + ATO/ATC session timing                  │
│ Execution plan .xlsx for trader                                    │
└─────────────────────────────────────────────────────────────────────┘
```

## Thuật toán

| Module | Algorithm | Formula |
|---|---|---|
| M1 | Log Returns | r_t = ln(P_t / P_{t−1}) |
| M1 | Risk-Free Rate | R_f,t = Yield_10Y / (100 × 252) |
| M1 | Excess Returns | R_excess = R_i,t − R_f,t |
| M2 | Fama-French Factor | Size/Value 2×3 sort, equal-weighted SMB & HML |
| M2 | OLS Regression | R_i−R_f = α + β₁·(R_m−R_f) + β₂·SMB + β₃·HML + ε |
| M2 | Forward E(R) | E(R_i) = rf + β_mkt·(E_Rm−rf) + β_smb·E_SMB + β_hml·E_HML |
| M3 | Covariance | Σ = (R−μ)ᵀ(R−μ)/(T−1), annualized ×252 |
| M3 | Markowitz Sharpe | max −(wᵀE(R)−rf) / √(wᵀΣw), SLSQP solver |
| M4 | Monte Carlo GBM | S_t = S₀·exp((μ−σ²/2)·Δt + L·Z·√Δt), Cholesky L |
| M4 | CVaR 95% | E[returns ∣ returns ≤ VaR_5%] |

## Tham số

| Parameter | Value | Meaning |
|---|---|---|
| START_DATE | 2021-01-01 | Post-COVID cycle start |
| END_DATE | 2026-05-11 | Current date |
| E_Rm | 12% | Expected VN-Index 2026 return |
| E_SMB | 2% | Size premium |
| E_HML | 3% | Value premium |
| rf | 4.37% | VN 10Y bond yield (current) |
| Universe | 100 stocks | VN100 index |
| Trading days | ~1,300 | 5 years |

## Ràng buộc

| Constraint | Value |
|---|---|
| Sum of weights | Σw = 100% |
| Per-stock cap | w_i ≤ 30% |
| FPT floor | w_FPT ≥ 20% |
| Liquidity floor | 50B VND/session |
| Max holdings | 5 (top after filter) |

## Kết quả

### Danh mục sau tái cơ cấu

| Symbol | Weight | E(R) annual | P/E | P/B | Role |
|---|---|---|---|---|---|
| **FPT** | 35.1% | 14.2% | 11.96 | 3.05 | Core tech (force-in) |
| **SIP** | 17.8% | 16.5% | 9.93 | 2.30 | Industrial park — cheap |
| **VTP** | 17.5% | 18.8% | 21.30 | 4.58 | Telecom — highest E(R) |
| **CTR** | 17.2% | 18.1% | 15.20 | 4.31 | Tech-telecom |
| **VHC** | 12.3% | 15.2% | 9.56 | 1.31 | Seafood — lowest P/B (value) |

### Risk metrics (Monte Carlo 10k paths × 30 days)

| Metric | Value |
|---|---|
| Expected 30d return | +1.96% |
| VaR 95% (30d) | −12.99% |
| CVaR 95% (30d) | −16.12% |
| P(loss) | 43.4% |
| Stop-loss | −32.24% (2× CVaR) |

### Old portfolio → decision

| Stock | Value (20/04) | Loss | Decision | Reason |
|---|---|---|---|---|
| DGC | 162.9M | −43.6% | ❌ CUT | No FF3 alpha |
| FTS | 139.0M | −31.6% | ❌ CUT | Not in top E(R) |
| SZC | 173.4M | −20.8% | ❌ CUT | Not in top-20 E(R) |
| VPB | 136.5M | −6.3% | ❌ CUT | Lower E(R) than alternatives |
| FPT | 299.2M | −27.6% | ✅ KEEP + ADD | Core, E(R)=14.2% |

## Cách chạy

```bash
pip install vnstock_data pandas numpy scipy statsmodels matplotlib openpyxl pyarrow

~/.venv/bin/python3 -m pipeline.main          # M1→M5: full pipeline
~/.venv/bin/python3 -m pipeline.trade_execution  # M6: execution plan
python3 export_pqt_to_csv.py                  # Convert cache → CSV
```

## Data packages

| Package | Contents | Recipient |
|---|---|---|
| `export/package1_macro/` | `macro_yield.csv`, `yield_curve.png` | TV2 — Macro |
| `export/package2_fundamental/` | `fundamental_top5.csv` | TV3 — Fundamental |
| `export/package3_pm/` | `weights_final.csv`, `efficient_frontier.png`, `CVaR_Report.txt` | TV4 — PM |
| `export/execution_report/` | `execution_plan.xlsx`, `daily_tracking.png` | Trader |
