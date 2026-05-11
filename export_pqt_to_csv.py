#!/usr/bin/env python3
"""Convert all .pqt cache files in vn100_data/ to .csv"""
import pandas as pd
from pathlib import Path

DATA = Path("vn100_data")
for pqt in sorted(DATA.glob("*.pqt")):
    csv = pqt.with_suffix(".csv")
    df = pd.read_parquet(pqt)
    df.to_csv(csv, index=True, float_format="%.6f")
    print(f"✅ {pqt.name} → {csv.name} ({df.shape[0]} rows × {df.shape[1]} cols)")
print("Done.")
