#!/usr/bin/env python3
"""Debug actual headers and trim columns"""

import pandas as pd
from pathlib import Path

file_path = Path("accy_v2/data/landing_zone/honda/may_2026/CVIC5D.xlsx")

en_df = pd.read_excel(file_path, sheet_name="26MY_CIV5D_APP_EN", header=None)

# Correct section structure:
# marker_row: 10
# data_start (header row): 11
# trim_sub_header: 12
# data_rows: 13+

print("="*100)
print("EN SHEET - First Section Header and Trim")
print("="*100)

print("\nRow 11 (Product Column Headers):")
for col_idx, val in enumerate(en_df.iloc[11]):
    if pd.notna(val):
        val_str = str(val).strip()
        print(f"  Col {col_idx:2d}: '{val_str}'")

print("\nRow 12 (Trim Sub-Header):")
for col_idx, val in enumerate(en_df.iloc[12]):
    if pd.notna(val):
        val_str = str(val).strip()
        print(f"  Col {col_idx:2d}: '{val_str}'")

print("\n" + "="*100)
print("TRIM COLUMN IDENTIFICATION")
print("="*100)

# The trim columns are those that have values in row 12 (trim sub-header)
# but are not in the product column list

product_col_keywords = [
    "part", "number", "description", "item", "name", "frt", "residual",
    "price", "net", "dealer", "list", "comments", "application", "installed", "cost",
]

product_cols = []
trim_cols = []

header_row = en_df.iloc[11]
for col_idx, val in enumerate(header_row):
    if pd.notna(val):
        header = str(val).strip()
        header_lower = header.lower()
        is_product = any(keyword in header_lower for keyword in product_col_keywords)
        if is_product:
            product_cols.append(col_idx)
        else:
            trim_cols.append(col_idx)

print(f"\nProduct columns: {product_cols}")
print(f"  Content: {[str(en_df.iloc[11, c]).strip() for c in product_cols if pd.notna(en_df.iloc[11, c])]}")

print(f"\nTrim columns (should have trim level names): {trim_cols}")
print(f"  Content: {[str(en_df.iloc[12, c]).strip() for c in trim_cols if pd.notna(en_df.iloc[12, c])]}")

# But the real trim columns are those that appear in the trim sub-header (row 12)
print("\nAlternative: Columns with values in row 12 (trim sub-header):")
trim_sub_header_cols = []
for col_idx, val in enumerate(en_df.iloc[12]):
    if pd.notna(val):
        val_str = str(val).strip()
        if val_str and val_str.lower() != "nan":
            trim_sub_header_cols.append(col_idx)
            print(f"  Col {col_idx}: '{val_str}'")

print(f"\nTotal trim columns with values: {len(trim_sub_header_cols)}")
