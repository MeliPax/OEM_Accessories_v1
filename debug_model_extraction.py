#!/usr/bin/env python3
"""Debug model name extraction"""

import pandas as pd
from pathlib import Path

file_path = Path("accy_v2/data/landing_zone/honda/may_2026/CVIC5D.xlsx")

en_df = pd.read_excel(file_path, sheet_name="26MY_CIV5D_APP_EN", header=None)
fr_df = pd.read_excel(file_path, sheet_name="26MY_CIV5D_APP_FR", header=None)

print("="*100)
print("EN SHEET - Row 2 (Model Name row)")
print("="*100)
row2_en = en_df.iloc[2]
for col_idx, val in enumerate(row2_en):
    if pd.notna(val):
        print(f"  Column {col_idx}: '{val}'")

print("\n" + "="*100)
print("FR SHEET - Row 2 (Nom du modèle row)")
print("="*100)
row2_fr = fr_df.iloc[2]
for col_idx, val in enumerate(row2_fr):
    if pd.notna(val):
        print(f"  Column {col_idx}: '{val}'")

print("\n" + "="*100)
print("FINDING THE PATTERN")
print("="*100)

print("\nEN Row 2 analysis:")
row_str_en = " ".join(str(v) for v in en_df.iloc[2].values if pd.notna(v)).lower()
print(f"Row string: {row_str_en}")

# Find where "model name" appears
if "model name" in row_str_en:
    print("✓ 'model name' found in row 2")
    # But what column has it?
    for col_idx, val in enumerate(en_df.iloc[2]):
        if pd.notna(val) and "model name" in str(val).lower():
            print(f"  'model name' label found in column {col_idx}: '{val}'")
            # The value should be in the next columns
            for check_col in range(col_idx + 1, len(en_df.iloc[2])):
                check_val = en_df.iloc[2, check_col]
                if pd.notna(check_val) and str(check_val).strip() and "nan" not in str(check_val).lower():
                    print(f"  → Value in column {check_col}: '{check_val}'")
                    break

print("\nFR Row 2 analysis:")
row_str_fr = " ".join(str(v) for v in fr_df.iloc[2].values if pd.notna(v)).lower()
print(f"Row string: {row_str_fr}")

if "nom du modèle" in row_str_fr:
    print("✓ 'nom du modèle' found in row 2")
    for col_idx, val in enumerate(fr_df.iloc[2]):
        if pd.notna(val) and "nom du modèle" in str(val).lower():
            print(f"  'nom du modèle' label found in column {col_idx}: '{val}'")
            for check_col in range(col_idx + 1, len(fr_df.iloc[2])):
                check_val = fr_df.iloc[2, check_col]
                if pd.notna(check_val) and str(check_val).strip() and "nan" not in str(check_val).lower():
                    print(f"  → Value in column {check_col}: '{check_val}'")
                    break
