#!/usr/bin/env python3
"""Debug section rows"""

import pandas as pd
from pathlib import Path

file_path = Path("accy_v2/data/landing_zone/honda/may_2026/CVIC5D.xlsx")

en_df = pd.read_excel(file_path, sheet_name="26MY_CIV5D_APP_EN", header=None)

print("="*100)
print("EN SHEET - Rows 9-14 (around first section marker)")
print("="*100)

for row_idx in range(9, min(15, len(en_df))):
    row = en_df.iloc[row_idx]
    row_values = []
    for col_idx in range(17):
        val = row.iloc[col_idx]
        if pd.notna(val):
            val_str = str(val).strip()
            if len(val_str) > 50:
                val_str = val_str[:47] + "..."
            row_values.append(f"{col_idx}:'{val_str}'")

    row_str = " | ".join(row_values) if row_values else "[EMPTY ROW]"
    print(f"Row {row_idx:2d}: {row_str}")

print("\n" + "="*100)
print("ANALYSIS")
print("="*100)
print("\nBased on playground_2:")
print("  Row 9:  Section marker '1.0 Packages and Kits'")
print("  Row 10: Header row with column names")
print("  Row 11: Trim sub-header row")
print("  Row 12+: Data rows")

print("\nActual content:")
print(f"  Row 9:  {en_df.iloc[9, 2] if pd.notna(en_df.iloc[9, 2]) else 'empty'}")
print(f"  Row 10: {en_df.iloc[10, 0:5].tolist()}")
print(f"  Row 11: {en_df.iloc[11, 0:5].tolist()}")
print(f"  Row 12: {en_df.iloc[12, 0:5].tolist()}")
