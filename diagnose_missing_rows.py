"""
Diagnostic script to check if we're losing data during file load.
Specifically looking for "Racing Package - Type R" row.
"""

import pandas as pd
from pathlib import Path

# Find civic 5d file (search recursively through subdirectories)
landing_zone = Path("landing_zone/2026/Honda")
civic_5d_files = list(landing_zone.rglob("*civic*5d*.xlsx"))

if not civic_5d_files:
    print("[ERROR] civic 5d.xlsx not found")
    exit(1)

civic_5d = civic_5d_files[0]
print(f"Testing with: {civic_5d.name}\n")

# Load EN sheet with different parameters
xl = pd.ExcelFile(civic_5d)
en_sheet = [s for s in xl.sheet_names if "_EN" in s][0]

print(f"Sheet: {en_sheet}\n")
print("="*80)
print("TEST 1: Load with default parameters")
print("="*80)

df_default = pd.read_excel(civic_5d, sheet_name=en_sheet)
print(f"Shape: {df_default.shape}")
print(f"Total rows: {len(df_default)}\n")

# Search for "Racing Package"
racing_rows = df_default[df_default.astype(str).apply(
    lambda row: any("Racing Package" in str(val) for val in row.values),
    axis=1
)]

if len(racing_rows) > 0:
    print("[FOUND] Found 'Racing Package' rows:")
    for idx, row in racing_rows.iterrows():
        print(f"  Row {idx}: {row.values[:3]}")
else:
    print("[NOT FOUND] No 'Racing Package' rows found in default load\n")

print("\n" + "="*80)
print("TEST 2: Load with header=None (no header parsing)")
print("="*80)

df_no_header = pd.read_excel(civic_5d, sheet_name=en_sheet, header=None)
print(f"Shape: {df_no_header.shape}")
print(f"Total rows: {len(df_no_header)}\n")

# Search for "Racing Package" in this version
racing_rows_no_header = df_no_header[df_no_header.astype(str).apply(
    lambda row: any("Racing Package" in str(val) for val in row.values),
    axis=1
)]

if len(racing_rows_no_header) > 0:
    print("[FOUND] Found 'Racing Package' rows:")
    for idx, row in racing_rows_no_header.iterrows():
        print(f"  Row {idx}: {list(row.values[:5])}")
else:
    print("[NOT FOUND] No 'Racing Package' rows found with header=None\n")

print("\n" + "="*80)
print("TEST 3: Show first 20 rows as-is from Excel")
print("="*80)

df_raw = pd.read_excel(civic_5d, sheet_name=en_sheet, header=None)
print("\nFirst 20 rows (raw, no header interpretation):")
print(df_raw.head(20).to_string())

print("\n\n" + "="*80)
print("TEST 4: Look for 'Racing' in entire sheet")
print("="*80)

# Search entire raw DataFrame
for idx, row in df_raw.iterrows():
    row_text = " ".join(str(val) for val in row.values if pd.notna(val))
    if "Racing" in row_text:
        print(f"\nRow {idx}: {row_text[:100]}")
        print(f"  Full row first 5 values: {list(row.values[:5])}")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"Default load (with headers): {len(df_default)} rows")
print(f"Raw load (no headers): {len(df_raw)} rows")
print(f"Difference: {len(df_raw) - len(df_default)} rows")
print("\nIf rows are missing between default and raw loads,")
print("it means pandas is dropping rows during header interpretation.")
