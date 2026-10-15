#!/usr/bin/env python3
"""
Test: Examine what's actually in the defect rows
"""

import sys
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path.cwd() / 'accy_v2'))

file_path = Path('accy_v2/data/landing_zone/honda/may_2026/CVIC5D.xlsx')

print("=" * 120)
print("EXAMINING DEFECT ROWS - What data do they actually contain?")
print("=" * 120)
print()

# Load EN sheet
df_en = pd.read_excel(file_path, sheet_name='26MY_CIV5D_APP_EN', header=None, engine='openpyxl')

# Sample defect rows from "Packages and Kits" section
defect_rows_en = [17, 21, 25, 34, 38, 42, 47, 52, 56]

print("[EN SHEET] Sample defect rows from Packages and Kits:")
print()

for row_idx in defect_rows_en[:3]:  # Just show first 3
    row_data = df_en.iloc[row_idx]
    print(f"Row {row_idx}:")
    print(f"  All values: {list(row_data)}")
    print(f"  Non-null count: {row_data.notna().sum()}")
    print(f"  Non-empty values:")
    for col_idx, val in enumerate(row_data):
        if pd.notna(val):
            val_str = str(val).strip()
            if val_str and val_str.lower() not in ["nan", "none"]:
                print(f"    Col {col_idx}: {repr(val_str)}")
    print()

print()
print("[FR SHEET] Sample defect rows from Groupes et ensembles:")
print()

df_fr = pd.read_excel(file_path, sheet_name='26MY_CIV5D_APP_FR', header=None, engine='openpyxl')
defect_rows_fr = [17, 21, 25, 34, 38, 42, 46, 51, 56, 60]

for row_idx in defect_rows_fr[:3]:  # Just show first 3
    row_data = df_fr.iloc[row_idx]
    print(f"Row {row_idx}:")
    print(f"  All values: {list(row_data)}")
    print(f"  Non-null count: {row_data.notna().sum()}")
    print(f"  Non-empty values:")
    for col_idx, val in enumerate(row_data):
        if pd.notna(val):
            val_str = str(val).strip()
            if val_str and val_str.lower() not in ["nan", "none"]:
                print(f"    Col {col_idx}: {repr(val_str)}")
    print()
