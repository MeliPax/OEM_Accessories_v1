#!/usr/bin/env python3
"""Debug why FR sheet shows 8 trim columns vs EN's 4"""

import pandas as pd
from pathlib import Path

file_path = Path("accy_v2/data/landing_zone/honda/may_2026/CVIC5D.xlsx")

en_df = pd.read_excel(file_path, sheet_name="26MY_CIV5D_APP_EN", header=None)
fr_df = pd.read_excel(file_path, sheet_name="26MY_CIV5D_APP_FR", header=None)

# First section: marker at row 10, header at row 11, trim sub-header at row 12

print("="*100)
print("EN SHEET - Row 11 (Header) + Row 12 (Trim Sub-header)")
print("="*100)

print("\nRow 11 (Header):")
for col_idx, val in enumerate(en_df.iloc[11]):
    if pd.notna(val):
        val_str = str(val).strip()
        print(f"  Col {col_idx:2d}: '{val_str}'")

print("\nRow 12 (Trim Sub-header):")
for col_idx, val in enumerate(en_df.iloc[12]):
    if pd.notna(val):
        val_str = str(val).strip()
        print(f"  Col {col_idx:2d}: '{val_str}'")

print("\n" + "="*100)
print("FR SHEET - Row 11 (Header) + Row 12 (Trim Sub-header)")
print("="*100)

print("\nRow 11 (Header):")
for col_idx, val in enumerate(fr_df.iloc[11]):
    if pd.notna(val):
        val_str = str(val).strip()
        print(f"  Col {col_idx:2d}: '{val_str}'")

print("\nRow 12 (Trim Sub-header):")
for col_idx, val in enumerate(fr_df.iloc[12]):
    if pd.notna(val):
        val_str = str(val).strip()
        print(f"  Col {col_idx:2d}: '{val_str}'")

print("\n" + "="*100)
print("COMPARISON - Which columns are classified as trim?")
print("="*100)

product_col_keywords = [
    "part", "number", "description", "item", "name", "frt", "residual",
    "price", "net", "dealer", "list", "comments", "application", "installed", "cost",
]

print("\nEN Sheet:")
header_row = en_df.iloc[11]
trim_sub_header = en_df.iloc[12]

for col_idx, val in enumerate(header_row):
    header_str = str(val).strip() if pd.notna(val) else f"_col_{col_idx}"
    is_product = any(keyword in header_str.lower() for keyword in product_col_keywords)
    
    if header_str.startswith("_col_"):
        trim_val = trim_sub_header.iloc[col_idx]
        trim_str = str(trim_val).strip() if pd.notna(trim_val) else ""
        has_trim = trim_str and trim_str.lower() not in ("nan", "0", "0.0")
        status = f"TRIM (has value: '{trim_str}')" if has_trim else f"NOT TRIM (value: '{trim_str}')"
        print(f"  Col {col_idx:2d}: {status}")
    elif not is_product:
        print(f"  Col {col_idx:2d}: TRIM (named '{header_str}')")

print("\nFR Sheet:")
header_row = fr_df.iloc[11]
trim_sub_header = fr_df.iloc[12]

for col_idx, val in enumerate(header_row):
    header_str = str(val).strip() if pd.notna(val) else f"_col_{col_idx}"
    is_product = any(keyword in header_str.lower() for keyword in product_col_keywords)
    
    if header_str.startswith("_col_"):
        trim_val = trim_sub_header.iloc[col_idx]
        trim_str = str(trim_val).strip() if pd.notna(trim_val) else ""
        has_trim = trim_str and trim_str.lower() not in ("nan", "0", "0.0")
        status = f"TRIM (has value: '{trim_str}')" if has_trim else f"NOT TRIM (value: '{trim_str}')"
        print(f"  Col {col_idx:2d}: {status}")
    elif not is_product:
        print(f"  Col {col_idx:2d}: TRIM (named '{header_str}')")
