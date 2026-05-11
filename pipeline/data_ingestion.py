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

from vnstock_data import Market, Reference

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
        combined = pd.concat([existing, df_out], ignore_index=True)
    else:
        combined = df_out
    combined.to_parquet(CACHE_OHLCV, index=False)


def fetch_single_stock(symbol: str, sleep: float = 0.3) -> Optional[pd.DataFrame]:
    try:
        mkt = Market()
        df = mkt.equity(symbol).ohlcv(start=START_DATE, end=END_DATE)
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
    """Kéo toàn bộ OHLCV với checkpoint resume."""
    cache: dict[str, pd.DataFrame] = {}
    ck = _load_checkpoint()
    already_done = set(ck["done"])

    if CACHE_OHLCV.exists() and len(already_done) >= len(symbols):
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
        return cache

    pending = [s for s in symbols if s not in already_done]
    if CACHE_OHLCV.exists():
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

    if not pending:
        print(f"[M1] ✅ Tất cả {len(symbols)} mã đã được fetch.")
        return cache

    print(f"[M1] 📡 Kéo OHLCV {len(pending)} mã ({START_DATE} → {END_DATE})...")
    success = len(already_done)
    fail = 0
    done = list(already_done)

    for i, sym in enumerate(pending):
        df = fetch_single_stock(sym)
        if df is not None and not df.empty:
            cache[sym] = df
            _append_to_parquet(sym, df)
            done.append(sym)
            _save_checkpoint(done)
            success += 1
            print(f"  [{i+1}/{len(pending)}] {sym} ✓ ({len(df)} dòng)")
        else:
            fail += 1
            print(f"  [{i+1}/{len(pending)}] {sym} ✗")

    _save_checkpoint(done)
    print(f"[M1] ✅ Done: {success} OK, {fail} fail.")
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
    Fetch Market Cap + P/B + P/E via Market().equity(sym).summary() [KBS].
    Returns market_cap, pb, pe, beta, eps, roe.
    Falls back to volume×close mcap proxy if summary fails.
    Returns DataFrame index=symbol.
    """
    print(f"[M1] 📡 Fetch fundamentals for {len(symbols)} symbols (summary API)...")
    mkt = Market()
    records = {}
    for i, sym in enumerate(symbols):
        try:
            df = mkt.equity(sym).summary()
            if df is not None and not df.empty:
                row = df.iloc[0]
                records[sym] = {
                    "market_cap": row.get("market_cap", np.nan),
                    "pb":         row.get("pb", np.nan),
                    "pe":         row.get("pe", np.nan),
                    "eps":        row.get("eps", np.nan),
                    "roe":        row.get("roe", np.nan),
                }
        except Exception:
            pass
        if (i + 1) % 20 == 0:
            print(f"   ... {i+1}/{len(symbols)}")

    if not records:
        raise RuntimeError("Không thể fetch fundamental data.")

    df = pd.DataFrame.from_dict(records, orient="index")
    print(f"[M1] ✅ Fundamentals: {len(df)} symbols, "
          f"MCap={df['market_cap'].notna().sum()}/{len(df)}, "
          f"P/B={df['pb'].notna().sum()}/{len(df)}")
    return df
