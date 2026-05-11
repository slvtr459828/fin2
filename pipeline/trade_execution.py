#!/usr/bin/env python3
"""
Trade Execution Report — Restructuring Window Daily Tracking
=============================================================
Phân tích từng ngày 20/04 → 11/05/2026:
- Giá old portfolio vs new portfolio daily
- Khối lượng giao dịch thực tế
- Điểm entry/exit tối ưu trong cửa sổ tái cơ cấu
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from vnstock_data import Market

from pipeline.config import EXPORT_DIR, ensure_dirs

ensure_dirs()
REPORT_DIR = EXPORT_DIR / "execution_report"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

START = "2026-04-20"
END   = "2026-05-11"
TOTAL_CAPITAL = 911_000_000

OLD_STOCKS = ["FPT", "SZC", "DGC", "FTS", "VPB"]
OLD_SHARES = {"FPT": 4000, "SZC": 6000, "DGC": 3000, "FTS": 5000, "VPB": 5000}

NEW_WEIGHTS = {"FPT": 0.3511, "SIP": 0.1781, "VTP": 0.1750, "CTR": 0.1723, "VHC": 0.1235}
NEW_STOCKS  = list(NEW_WEIGHTS.keys())


def fetch_daily_prices(symbols: list[str], start: str, end: str) -> pd.DataFrame:
    mkt = Market()
    frames = {}
    for sym in symbols:
        df = mkt.equity(sym).ohlcv(start=start, end=end)
        if df is not None and not df.empty:
            df["time"] = pd.to_datetime(df["time"])
            df = df.set_index("time").sort_index()
            frames[sym] = df["close"].rename(sym)
    return pd.concat(frames.values(), axis=1).dropna()


def compute_daily_values(prices: pd.DataFrame) -> pd.DataFrame:
    """Prices from API are in thousands VND — multiply by 1000 for actual VND."""
    result = pd.DataFrame(index=prices.index)
    K = 1000  # convert thousands → actual VND

    old_value = pd.Series(0.0, index=prices.index)
    for sym, shares in OLD_SHARES.items():
        if sym in prices.columns:
            old_value += shares * prices[sym] * K
    result["old_value"] = old_value
    result["old_return"] = old_value / old_value.iloc[0] - 1

    new_value = pd.Series(0.0, index=prices.index)
    for sym, weight in NEW_WEIGHTS.items():
        if sym in prices.columns:
            shares = (TOTAL_CAPITAL * weight) / (prices[sym].iloc[0] * K)
            new_value += shares * prices[sym] * K
    result["new_value"] = new_value
    result["new_return"] = new_value / new_value.iloc[0] - 1

    result["benefit"] = result["new_value"] - result["old_value"]
    return result


def analyze_timing(ohlcv_dict: dict) -> dict:
    """Analyze open vs close patterns → recommend ATO or ATC for each symbol."""
    timing = {}
    for sym, df in ohlcv_dict.items():
        bears = (df['open'] > df['close']).sum()
        bulls = (df['close'] > df['open']).sum()
        avg_oc = (df['close'] / df['open'] - 1).mean() * 100
        timing[sym] = {
            'bear_days': bears, 'bull_days': bulls, 'avg_oc': avg_oc,
        }
    return timing


def get_session(action: str, sym: str, timing: dict) -> str:
    """Determine optimal session + time for execution (English, no special chars)."""
    if sym not in timing:
        return "10:00-11:00 (mid-session)"
    t = timing[sym]
    if action in ("SELL",):
        if t['bear_days'] >= t['bull_days']:
            return "ATO 09:00-09:15 (open higher than close)"
        return "10:00-11:00 (mid-session)"
    else:
        if t['bear_days'] >= t['bull_days']:
            return "ATC 14:30-14:45 (close lower than open)"
        return "ATO 09:00-09:15 (open lower than close)"


def find_optimal_execution(prices: pd.DataFrame) -> pd.DataFrame:
    K = 1000
    # Build ohlcv dict for timing analysis
    mkt = Market()
    ohlcv_dict = {}
    for sym in list(set(OLD_STOCKS + NEW_STOCKS)):
        df = mkt.equity(sym).ohlcv(start=START, end=END)
        if df is not None and not df.empty:
            df["time"] = pd.to_datetime(df["time"])
            ohlcv_dict[sym] = df.set_index("time").sort_index()
    timing = analyze_timing(ohlcv_dict)

    records = []
    for sym in OLD_STOCKS:
        if sym not in prices.columns:
            continue
        best = prices[sym].idxmax()
        first = prices[sym].iloc[0]
        best_p = prices[sym].max()
        session = get_session("SELL", sym, timing)
        records.append({
            "Action": "SELL",
            "Symbol": sym,
            "Shares": OLD_SHARES[sym],
            "Best Date": best.strftime("%d/%m/%Y"),
            "Session": session,
            "Price (VND)": int(best_p * K),
            "Value (VND)": int(OLD_SHARES[sym] * best_p * K),
            "Open-to-Close %": f"{timing.get(sym, {}).get('avg_oc', 0):+.2f}%",
            "Note": f"Peak in window, {best_p/first-1:+.1%} vs 20/04.",
        })

    for sym in NEW_STOCKS:
        if sym not in prices.columns or sym in OLD_STOCKS:
            continue
        best = prices[sym].idxmin()
        first = prices[sym].iloc[0]
        best_p = prices[sym].min()
        target_shares = int(TOTAL_CAPITAL * NEW_WEIGHTS[sym] / (best_p * K) / 100) * 100
        session = get_session("BUY", sym, timing)
        records.append({
            "Action": "BUY",
            "Symbol": sym,
            "Shares": target_shares,
            "Best Date": best.strftime("%d/%m/%Y"),
            "Session": session,
            "Price (VND)": int(best_p * K),
            "Value (VND)": int(target_shares * best_p * K),
            "Open-to-Close %": f"{timing.get(sym, {}).get('avg_oc', 0):+.2f}%",
            "Note": f"Lowest in window ({best_p/first-1:+.1%} vs 20/04).",
        })

    # FPT adjustment
    if "FPT" in prices.columns:
        current = OLD_SHARES["FPT"]
        best_p = prices["FPT"].min()
        target = int(TOTAL_CAPITAL * NEW_WEIGHTS["FPT"] / (best_p * K) / 100) * 100
        delta = target - current
        session = get_session("BUY", "FPT", timing)
        records.append({
            "Action": "BUY MORE",
            "Symbol": "FPT",
            "Shares": abs(delta),
            "Best Date": prices["FPT"].idxmin().strftime("%d/%m/%Y"),
            "Session": session,
            "Price (VND)": int(best_p * K),
            "Value (VND)": int(abs(delta) * best_p * K),
            "Open-to-Close %": f"{timing.get('FPT', {}).get('avg_oc', 0):+.2f}%",
            "Note": f"Holding {current:,} → {target:,} shares ({NEW_WEIGHTS['FPT']:.1%}). Delta: {delta:+,}.",
        })
    return pd.DataFrame(records)


def plot_daily_tracking(values: pd.DataFrame):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [2, 1]})

    ax1.plot(values.index, values["old_value"]/1e6, 'r-', lw=1.5, label='Cũ (FPT+SZC+DGC+FTS+VPB)')
    ax1.plot(values.index, values["new_value"]/1e6, 'g-', lw=1.5, label='Mới (FPT+SIP+VTP+CTR+VHC)')
    ax1.axhline(y=TOTAL_CAPITAL/1e6, color='gray', ls='--', lw=0.8, label=f'Vốn {TOTAL_CAPITAL/1e6:.0f}M')
    ax1.set_ylabel('Giá trị (triệu VND)')
    ax1.set_title('Daily Portfolio Value — Restructuring Window 20/04→11/05/2026', fontsize=13, fontweight='bold')
    ax1.legend(fontsize=9); ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    ax1.xaxis.set_major_locator(mdates.DayLocator(interval=2))

    delta = values["benefit"] / 1e6
    colors = ['green' if d > 0 else 'red' for d in delta]
    ax2.bar(values.index, delta, color=colors, alpha=0.7, width=0.8)
    ax2.axhline(y=0, color='black', lw=0.5)
    ax2.set_ylabel('Chênh lệch (triệu)\nMới − Cũ')
    ax2.set_xlabel('Ngày')
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    ax2.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    fig.tight_layout()
    fig.savefig(REPORT_DIR / "daily_tracking.png", dpi=150)
    plt.close(fig)


def main():
    print("=" * 60)
    print(f"  M6: TRADE EXECUTION REPORT  ({START} → {END})")
    print("=" * 60)

    all_symbols = list(set(OLD_STOCKS + NEW_STOCKS))
    prices = fetch_daily_prices(all_symbols, START, END)
    values = compute_daily_values(prices)

    old_end = values["old_value"].iloc[-1]
    new_end = values["new_value"].iloc[-1]
    benefit = values["new_value"].iloc[-1] - values["old_value"].iloc[-1]

    print(f"\n📈 Tổng kết ({len(values)} phiên):")
    print(f"   Old final: {old_end:,.0f} VND ({values['old_return'].iloc[-1]*100:+.2f}%)")
    print(f"   New final: {new_end:,.0f} VND ({values['new_return'].iloc[-1]*100:+.2f}%)")
    print(f"   Lợi thế tái cơ cấu: {benefit:+,.0f} VND")

    exec_plan = find_optimal_execution(prices)
    print(f"\n📋 KẾ HOẠCH GIAO DỊCH:")
    for _, row in exec_plan.iterrows():
        print(f"   [{row['Action']:<10}] {row['Symbol']:<6} "
              f"{row['Shares']:>10,} shares — {row['Best Date']} {row['Session']}")
        print(f"            @ {row['Price (VND)']:>,} VND | Value: {row['Value (VND)']:>,} VND")
        print(f"            {row['Note']}")

    values.to_csv(REPORT_DIR / "daily_values.csv", float_format="%.2f")
    exec_plan.to_csv(REPORT_DIR / "execution_plan.csv", index=False)
    exec_plan.to_excel(REPORT_DIR / "execution_plan.xlsx", index=False)
    (prices.round(0).astype(int) * 1000).to_csv(REPORT_DIR / "daily_prices.csv")
    plot_daily_tracking(values)
    print(f"\n✅ Reports: {REPORT_DIR}/")
    for f in sorted(REPORT_DIR.glob("*")):
        print(f"   {f.name}")


if __name__ == "__main__":
    main()
