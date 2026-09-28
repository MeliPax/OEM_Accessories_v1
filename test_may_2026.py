"""
Test CVIC5D.xlsx from may_2026 landing zone
"""

import pandas as pd
from pathlib import Path

# Use exact path to CVIC5D.xlsx
civic_file = Path("accy_v2/data/landing_zone/honda/may_2026/CVIC5D.xlsx")

print(f"File: {civic_file.resolve()}\n")

if not civic_file.exists():
    print("[ERROR] File not found")
    exit(1)

# Check file info
size_mb = civic_file.stat().st_size / (1024**2)
print(f"File size: {size_mb:.2f} MB\n")

# Load and check sheets
xl = pd.ExcelFile(civic_file)
print(f"Sheets in file:")
for sheet in xl.sheet_names:
    print(f"  - {sheet}")

# Find EN sheet
en_sheet = [s for s in xl.sheet_names if "_EN" in s.upper()][0]
print(f"\nLoading sheet: {en_sheet}\n")

# Load raw (no header parsing)
df_raw = pd.read_excel(civic_file, sheet_name=en_sheet, header=None)
print(f"Total rows (raw): {len(df_raw)}")

# Search for Racing Package
print("\nSearching for 'Racing Package'...\n")

for idx, row in df_raw.iterrows():
    row_text = " ".join(str(val) for val in row.values if pd.notna(val))
    if "Racing" in row_text and "TYPER" in row_text:
        print(f"[FOUND] Row {idx}:")
        print(f"  Full text: {row_text}")
        print(f"  First 5 values: {list(row.values[:5])}")
        break
else:
    print("[NOT FOUND] Racing Package not in this file")

# Load with default header parsing
df_default = pd.read_excel(civic_file, sheet_name=en_sheet)
print(f"\nWith default header parsing: {len(df_default)} rows")
print(f"\nFirst 3 column names:")
for i, col in enumerate(df_default.columns[:3]):
    print(f"  {i+1}. {col}")
