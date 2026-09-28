#!/usr/bin/env python3
"""Debug FR sheet metadata extraction"""

import pandas as pd
from pathlib import Path

file_path = Path("accy_v2/data/landing_zone/honda/may_2026/CVIC5D.xlsx")

# Load both sheets
en_df = pd.read_excel(file_path, sheet_name="26MY_CIV5D_APP_EN", header=None)
fr_df = pd.read_excel(file_path, sheet_name="26MY_CIV5D_APP_FR", header=None)

print("="*100)
print("EN SHEET - First 10 rows (metadata area)")
print("="*100)
print(en_df.iloc[0:10, 0:5])

print("\n" + "="*100)
print("FR SHEET - First 10 rows (metadata area)")
print("="*100)
print(fr_df.iloc[0:10, 0:5])

print("\n" + "="*100)
print("EN SHEET - Row content as strings (first 6 rows)")
print("="*100)
for i in range(min(6, len(en_df))):
    row_str = " | ".join(str(v).strip() for v in en_df.iloc[i, 0:5].values if pd.notna(v))
    print(f"Row {i}: {row_str}")

print("\n" + "="*100)
print("FR SHEET - Row content as strings (first 6 rows)")
print("="*100)
for i in range(min(6, len(fr_df))):
    row_str = " | ".join(str(v).strip() for v in fr_df.iloc[i, 0:5].values if pd.notna(v))
    print(f"Row {i}: {row_str}")

print("\n" + "="*100)
print("ANALYSIS")
print("="*100)
print("\nLooking for metadata labels in FR sheet:")
for idx in range(min(10, len(fr_df))):
    row = fr_df.iloc[idx]
    row_str = " ".join(str(v) for v in row.values if pd.notna(v)).lower()

    if any(keyword in row_str for keyword in ["model", "nom", "année", "year", "model name"]):
        print(f"  Row {idx}: {row_str[:100]}")
