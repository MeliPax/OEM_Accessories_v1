#!/usr/bin/env python3
"""Debug trim column detection"""

import pandas as pd
from pathlib import Path

file_path = Path("accy_v2/data/landing_zone/honda/may_2026/CVIC5D.xlsx")

en_df = pd.read_excel(file_path, sheet_name="26MY_CIV5D_APP_EN", header=None)
fr_df = pd.read_excel(file_path, sheet_name="26MY_CIV5D_APP_FR", header=None)

# Packages and Kits section (first section) starts at marker row 9
packages_marker_row_en = 9
packages_data_start_en = packages_marker_row_en + 1  # 10
packages_header_row_en = packages_data_start_en  # 10

print("="*100)
print("EN SHEET - Packages and Kits section header")
print("="*100)
print("Header row index:", packages_header_row_en)
header_row_en = en_df.iloc[packages_header_row_en]

print("\nAll header values:")
for col_idx, val in enumerate(header_row_en):
    if pd.notna(val):
        val_str = str(val).strip()
        print(f"  Column {col_idx:2d}: '{val_str}'")

print("\n" + "="*100)
print("FR SHEET - Groupes et ensembles section header")
print("="*100)
print("Header row index:", packages_header_row_en)
header_row_fr = fr_df.iloc[packages_header_row_en]

print("\nAll header values:")
for col_idx, val in enumerate(header_row_fr):
    if pd.notna(val):
        val_str = str(val).strip()
        print(f"  Column {col_idx:2d}: '{val_str}'")

print("\n" + "="*100)
print("TRIM COLUMN DETECTION")
print("="*100)

product_col_keywords = [
    "part", "number", "description", "item", "name", "frt", "residual",
    "price", "net", "dealer", "list", "comments", "application", "installed", "cost",
]

print("\nEN Sheet - Classifying columns:")
for col_idx, val in enumerate(header_row_en):
    if pd.notna(val):
        header = str(val).strip()
        header_lower = header.lower()
        is_product = any(keyword in header_lower for keyword in product_col_keywords)
        col_type = "PRODUCT" if is_product else "TRIM"
        print(f"  Column {col_idx:2d}: {col_type:7s} - '{header}'")

print("\nFR Sheet - Classifying columns:")
for col_idx, val in enumerate(header_row_fr):
    if pd.notna(val):
        header = str(val).strip()
        header_lower = header.lower()
        is_product = any(keyword in header_lower for keyword in product_col_keywords)
        col_type = "PRODUCT" if is_product else "TRIM"
        print(f"  Column {col_idx:2d}: {col_type:7s} - '{header}'")
