"""
Pipeline config — paths, dates, constants.
"""

from pathlib import Path

# ── Dates ────────────────────────────────────────────────────────────────
START_DATE = "2021-01-01"
END_DATE   = "2026-05-11"

# ── Directories ──────────────────────────────────────────────────────────
ROOT_DIR     = Path(__file__).resolve().parent.parent   # fin2/
DATA_DIR     = ROOT_DIR / "vn100_data"
EXPORT_DIR   = ROOT_DIR / "export"

PKG1_MACRO       = EXPORT_DIR / "package1_macro"
PKG2_FUNDAMENTAL = EXPORT_DIR / "package2_fundamental"
PKG3_PM          = EXPORT_DIR / "package3_pm"

# ── Cache files ──────────────────────────────────────────────────────────
CACHE_OHLCV       = DATA_DIR / "vn100_ohlcv.pqt"
CACHE_VNINDEX     = DATA_DIR / "vnindex_ohlcv.pqt"
CACHE_CLOSE       = DATA_DIR / "vn100_close.pqt"
CACHE_RETURNS     = DATA_DIR / "vn100_log_returns.pqt"
CACHE_VNINDEX_RET = DATA_DIR / "vnindex_log_returns.pqt"
CHECKPOINT_FILE   = DATA_DIR / "_checkpoint.json"

# ── Bond yield CSV (user-provided) ───────────────────────────────────────
BOND_YIELD_CSV = ROOT_DIR / "Dữ liệu Lịch sử Suất Thu lợi Trái phiếu 10 Năm Việt Nam.csv"

# ── Final portfolio (locked after committee decision) ────────────────────
FINAL_PORTFOLIO = {
    "FPT": 0.3511,
    "SIP": 0.1781,
    "VTP": 0.1750,
    "CTR": 0.1723,
    "VHC": 0.1235,
}

# ── Forward-looking assumptions ──────────────────────────────────────────
E_Rm   = 0.12    # Kỳ vọng VN-Index 2026: +12%
E_SMB  = 0.02    # Size premium: Small - Big
E_HML  = 0.03    # Value premium: High P/B - Low P/B

# ── Constraints ──────────────────────────────────────────────────────────
MAX_WEIGHT_PER_STOCK = 0.30
FPT_MIN_WEIGHT       = 0.20
MIN_DAILY_VOLUME     = 50_000_000_000   # 50 tỷ VND/phiên
TOP_N_FILTER         = 20
FINAL_TOP_K          = 5

# ── Monte Carlo ──────────────────────────────────────────────────────────
MC_N_SIMULATIONS = 10_000
MC_FORECAST_DAYS = 30
CVAR_ALPHA       = 0.05

# ── Trading days ─────────────────────────────────────────────────────────
TRADING_DAYS = 252


def ensure_dirs():
    """Create all output directories."""
    DATA_DIR.mkdir(exist_ok=True)
    for d in [PKG1_MACRO, PKG2_FUNDAMENTAL, PKG3_PM]:
        d.mkdir(parents=True, exist_ok=True)
