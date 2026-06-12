"""
Module 1 — Data Ingestion & Preprocessing
=========================================
1.1 Asset Price Matrix — OHLCV → close matrix → log returns
1.2 VN-Index — OHLCV → log returns
1.3 Risk-Free Rate — bond yield CSV → daily rf → excess returns
1.4 Fundamental Array — Market Cap, P/B, P/E
"""

import json
import time
from typing import Optional

import numpy as np
import pandas as pd

from vnstock import Market, Reference

from pipeline.config import (
    START_DATE, END_DATE, TRADING_DAYS,
    BOND_YIELD_CSV,
    CACHE_OHLCV, CACHE_VNINDEX, CACHE_CLOSE,
    CACHE_RETURNS, CACHE_VNINDEX_RET, CHECKPOINT_FILE,
    ensure_dirs,
)

ensure_dirs()


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  1.1 — Asset Price Matrix                                          ║
# ╚══════════════════════════════════════════════════════════════════════╝

def get_vn100_symbols() -> list[str]:
    """Lấy danh sách mã VN100 từ Reference API."""
    ref = Reference()
    result = ref.equity.list_by_group("VN100")
    if isinstance(result, pd.Series):
        symbols = result.tolist()
    elif isinstance(result, pd.DataFrame):
        symbols = result["symbol"].tolist() if "symbol" in result.columns else result.iloc[:, 0].tolist()
    else:
        symbols = list(result)
    print(f"[M1] ✅ {len(symbols)} mã VN100 từ API.")
    return symbols


# ── Checkpoint helpers ─────────────────────────────────────────────────

def _load_checkpoint() -> dict:
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {"done": [], "end_date": END_DATE}


def _save_checkpoint(done_symbols: list[str]):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump({"done": done_symbols, "end_date": END_DATE}, f, indent=2)


def _append_to_parquet(symbol: str, df: pd.DataFrame):
    df_out = df.copy()
    df_out["symbol"] = symbol
    df_out = df_out.reset_index()
    if CACHE_OHLCV.exists():
        existing = pd.read_parquet(CACHE_OHLCV)
        # Remove old rows for this symbol (for incremental updates)
        existing = existing[existing["symbol"] != symbol]
        combined = pd.concat([existing, df_out], ignore_index=True)
    else:
        combined = df_out
    combined.to_parquet(CACHE_OHLCV, index=False)


def fetch_single_stock(symbol: str, sleep: float = 0.3,
                       start: str = None, end: str = None) -> Optional[pd.DataFrame]:
    try:
        mkt = Market()
        sd = start or START_DATE
        ed = end or END_DATE
        df = mkt.equity(symbol).ohlcv(start=sd, end=ed)
        if df is None or df.empty:
            return None
        time.sleep(sleep)
        df["time"] = pd.to_datetime(df["time"])
        df = df.set_index("time").sort_index()
        return df
    except Exception as e:
        print(f"  ⚠️ {symbol}: {e}")
        return None


def fetch_vn100_ohlcv(symbols: list[str]) -> dict[str, pd.DataFrame]:
    """Kéo OHLCV với incremental fetch: chỉ fetch dữ liệu mới nếu cache cũ hơn END_DATE."""
    cache: dict[str, pd.DataFrame] = {}
    ck = _load_checkpoint()

    # Load existing cache
    if CACHE_OHLCV.exists():
        print(f"[M1] 📂 Load cache OHLCV từ {CACHE_OHLCV}")
        all_df = pd.read_parquet(CACHE_OHLCV)
        for sym in all_df["symbol"].unique():
            sub = all_df[all_df["symbol"] == sym].drop(columns="symbol").copy()
            if "time" in sub.columns:
                sub["time"] = pd.to_datetime(sub["time"])
                sub = sub.set_index("time")
            else:
                sub.index = pd.to_datetime(sub.index)
            sub = sub.sort_index()
            cache[sym] = sub
        print(f"   Đã load {len(cache)} mã.")

    # Check if we need to fetch new data
    need_fetch = []
    need_update = []
    for sym in symbols:
        if sym in cache and not cache[sym].empty:
            last_date = cache[sym].index.max()
            end_dt = pd.Timestamp(END_DATE)
            if last_date < end_dt - pd.Timedelta(days=1):
                need_update.append(sym)
        elif sym not in cache:
            need_fetch.append(sym)

    if not need_fetch and not need_update:
        print(f"[M1] ✅ Cache up-to-date ({len(cache)} mã).")
        return cache

    if need_update:
        print(f"[M1] 📡 Incremental fetch {len(need_update)} mã "
              f"(dữ liệu mới từ ~{cache[need_update[0]].index.max().date()} → {END_DATE})...")

    all_pending = need_fetch + need_update
    success = 0
    fail = 0

    for i, sym in enumerate(all_pending):
        df = fetch_single_stock(sym, sleep=0.5)
        if df is not None and not df.empty:
            if sym in cache and sym in need_update:
                # Merge: keep old + new, deduplicate by date
                old_df = cache[sym]
                combined = pd.concat([old_df, df]).sort_index()
                combined = combined[~combined.index.duplicated(keep='last')]
                cache[sym] = combined
                # Rebuild full cache parquet
                _append_to_parquet(sym, combined)
            else:
                cache[sym] = df
                _append_to_parquet(sym, df)
            success += 1
            print(f"  [{i+1}/{len(all_pending)}] {sym} ✓ "
                  f"({'new' if sym in need_fetch else f'+{len(df)}d'})")
        else:
            fail += 1
            print(f"  [{i+1}/{len(all_pending)}] {sym} ✗")

    print(f"[M1] ✅ Done: {success} OK, {fail} fail. Total cache: {len(cache)} mã.")
    return cache


def build_close_matrix(ohlcv_dict: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Ma trận giá đóng cửa: rows = ngày, cols = mã. Forward-fill."""
    if CACHE_CLOSE.exists():
        print(f"[M1] 📂 Load close matrix từ {CACHE_CLOSE}")
        df = pd.read_parquet(CACHE_CLOSE)
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        return df

    frames = {}
    for sym, df in ohlcv_dict.items():
        s = df["close"].rename(sym)
        s = s[~s.index.duplicated(keep="first")]  # deduplicate dates
        frames[sym] = s
    close = pd.concat(frames.values(), axis=1)
    close.columns = list(frames.keys())
    close = close.sort_index()

    min_days = max(len(close) * 0.5, 1)
    close = close.dropna(axis=1, thresh=min_days)
    close = close.ffill().dropna()

    close.to_parquet(CACHE_CLOSE)
    print(f"[M1] 💾 Close matrix: {close.shape[1]} mã × {close.shape[0]} ngày")
    return close


def compute_log_returns(close: pd.DataFrame) -> tuple[np.ndarray, list[str], pd.DatetimeIndex]:
    """r_t = ln(P_t / P_{t-1})"""
    if CACHE_RETURNS.exists():
        print(f"[M1] 📂 Load log returns từ {CACHE_RETURNS}")
        df = pd.read_parquet(CACHE_RETURNS)
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        return df.values, df.columns.tolist(), df.index

    R_df = np.log(close / close.shift(1)).dropna()
    R_df.to_parquet(CACHE_RETURNS)
    print(f"[M1] 💾 Log returns: {R_df.shape[0]} ngày × {R_df.shape[1]} mã")
    return R_df.values, R_df.columns.tolist(), R_df.index


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  1.2 — VN-Index Market Benchmark                                   ║
# ╚══════════════════════════════════════════════════════════════════════╝

def fetch_vnindex_ohlcv() -> pd.DataFrame:
    if CACHE_VNINDEX.exists():
        print(f"[M1] 📂 Load cache VN-Index từ {CACHE_VNINDEX}")
        df = pd.read_parquet(CACHE_VNINDEX)
        if "time" in df.columns:
            df["time"] = pd.to_datetime(df["time"])
            df = df.set_index("time").sort_index()
        else:
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
        return df

    print(f"[M1] 📡 Kéo VN-Index OHLCV ({START_DATE} → {END_DATE})...")
    mkt = Market()
    df = mkt.index("VNINDEX").ohlcv(start=START_DATE, end=END_DATE)
    if df is None or df.empty:
        raise RuntimeError("Không lấy được dữ liệu VN-Index.")
    df["time"] = pd.to_datetime(df["time"])
    df = df.set_index("time").sort_index()
    df.to_parquet(CACHE_VNINDEX)
    print(f"[M1] 💾 VN-Index cache: {len(df)} rows")
    return df


def compute_vnindex_log_returns(vnindex: pd.DataFrame) -> np.ndarray:
    if CACHE_VNINDEX_RET.exists():
        print(f"[M1] 📂 Load VN-Index returns từ {CACHE_VNINDEX_RET}")
        df = pd.read_parquet(CACHE_VNINDEX_RET)
        if isinstance(df, pd.DataFrame):
            return df.iloc[:, 0].values.flatten()
        return df.values.flatten()

    r_m = np.log(vnindex["close"] / vnindex["close"].shift(1)).dropna()
    r_m.to_frame("vnindex_log_return").to_parquet(CACHE_VNINDEX_RET)
    print(f"[M1] 💾 VN-Index returns: {len(r_m)} ngày")
    return r_m.values


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  1.3 — Risk-Free Rate Vector (VN 10Y Bond Yield)                   ║
# ╚══════════════════════════════════════════════════════════════════════╝

def load_bond_yield(path: Optional[str] = None) -> pd.Series:
    """
    Load Vietnam 10Y Government Bond Yield CSV.
    Columns: Ngày (DD/MM/YYYY), Lần cuối (close yield %), Mở, Cao, Thấp, % Thay đổi.
    Returns Series with DatetimeIndex, values in % (e.g. 4.37 = 4.37%).
    """
    p = path or str(BOND_YIELD_CSV)
    df = pd.read_csv(p)
    df["date"] = pd.to_datetime(df["Ngày"], format="%d/%m/%Y")
    series = pd.to_numeric(df["Lần cuối"], errors="coerce")
    series.index = df["date"]
    series = series.sort_index().dropna()
    print(f"[M1] 📂 Bond yield: {len(series)} ngày "
          f"({series.index[0].date()} → {series.index[-1].date()})")
    print(f"   Latest 10Y yield: {series.iloc[-1]:.3f}%")
    return series


def compute_daily_rf(bond_yield_pct: pd.Series) -> pd.Series:
    """R_f,t = Yield_10Y / (100 × 252)"""
    return bond_yield_pct / (100 * TRADING_DAYS)


def compute_excess_returns(
    R_stocks: np.ndarray,
    rf_daily: pd.Series,
    stock_dates: pd.DatetimeIndex,
) -> np.ndarray:
    """Align rf to stock dates via reindex, then R_excess = R_i,t - R_f,t."""
    stock_dates = pd.DatetimeIndex(stock_dates).normalize()
    rf_daily = rf_daily.copy()
    rf_daily.index = rf_daily.index.normalize()
    rf_aligned = rf_daily.reindex(stock_dates).ffill().bfill().values
    return R_stocks - rf_aligned.reshape(-1, 1)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  1.4 — Fundamental Array (Market Cap, P/B, P/E)                    ║
# ╚══════════════════════════════════════════════════════════════════════╝

def fetch_fundamentals(symbols: list[str]) -> pd.DataFrame:
    """
    vnstock 4.x API:
    - P/B, P/E, ROE from Fundamental().equity(sym).ratio()
    - Market Cap proxy: batch quote close_price × volume_accumulated (size ranking)
      Exact market cap not needed for FF3 median-split size sort.
    Returns DataFrame index=symbol.
    """
    import time as _time
    from vnstock import Fundamental, Market

    print(f"[M1] 📡 Fetch fundamentals for {len(symbols)} symbols...")
    fun = Fundamental()
    mkt = Market()

    # 1) Batch quote: close_price + volume for size proxy (1 API call)
    print(f"   Fetching batch quote...")
    quotes = mkt.quote(symbols)
    quotes["mcap_proxy"] = quotes["close_price"].astype(float) * quotes["volume_accumulated"].astype(float)
    close_map = dict(zip(quotes["symbol"], quotes["close_price"]))
    mcap_map = dict(zip(quotes["symbol"], quotes["mcap_proxy"]))
    print(f"   Got {len(quotes)} quotes.")

    # 2) Per-symbol: ratio API for P/B, P/E, ROE (1 call/symbol = 98 calls total)
    # Need 0.5s delay to stay under 180 req/min
    records = {}
    for i, sym in enumerate(symbols):
        try:
            df_ratio = fun.equity(sym).ratio()
            if df_ratio is not None and not df_ratio.empty:
                ratio_map = {}
                for _, row in df_ratio.iterrows():
                    ratio_map[row["item_id"]] = row.get("2026-Q1", np.nan)
                records[sym] = {
                    "market_cap": mcap_map.get(sym, np.nan),
                    "pb":         ratio_map.get("pb_ratio", np.nan),
                    "pe":         ratio_map.get("pe_ratio", np.nan),
                    "eps":        ratio_map.get("trailing_eps", np.nan),
                    "roe":        ratio_map.get("roe_trailling", np.nan),
                }
        except Exception:
            pass

        # Delay between calls to stay under 180 req/min bronze limit
        _time.sleep(0.5)

        if (i + 1) % 20 == 0:
            print(f"   ... {i+1}/{len(symbols)} (collected {len(records)})")

    if len(records) < 20:
        raise RuntimeError(f"Không thể fetch fundamental data — chỉ có {len(records)} mã.")

    df = pd.DataFrame.from_dict(records, orient="index")
    df = df.dropna(subset=["pb"])
    print(f"[M1] ✅ Fundamentals: {len(df)} symbols, "
          f"MCap={df['market_cap'].notna().sum()}/{len(df)}, "
          f"P/B={df['pb'].notna().sum()}/{len(df)}")
    return df
