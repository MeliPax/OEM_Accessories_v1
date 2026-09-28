"""
Update notebook to use correct landing zone path
"""

import pandas as pd
from pathlib import Path

# Use the correct landing zone path
landing_zone = Path("accy_v2/data/landing_zone/honda/may_2026")

print(f"Landing zone: {landing_zone.resolve()}\n")

# Find civic 5d file
civic_5d_files = list(landing_zone.glob("*civic*5d*.xlsx"))

if not civic_5d_files:
    print("[ERROR] No civic 5d file found")
    exit(1)

civic_5d = civic_5d_files[0]
print(f"Found file: {civic_5d.name}")
print(f"File size: {civic_5d.stat().st_size / (1024**2):.2f} MB\n")

# Load and check
xl = pd.ExcelFile(civic_5d)
en_sheet = [s for s in xl.sheet_names if "_EN" in s][0]

df = pd.read_excel(civic_5d, sheet_name=en_sheet, header=None)

print(f"Sheet: {en_sheet}")
print(f"Total rows (raw): {len(df)}\n")

# Search for Racing Package
racing_found = False
for idx, row in df.iterrows():
    row_text = " ".join(str(val) for val in row.values if pd.notna(val))
    if "Racing" in row_text and "TYPER" in row_text:
        racing_found = True
        print(f"[FOUND] Racing Package at row {idx}:")
        print(f"  {row_text[:150]}")
        break

if racing_found:
    print("\n✓ This is the CORRECT file with all data!")
else:
    print("\n[NOT FOUND] Racing Package not found")

# Load with default header parsing
df_default = pd.read_excel(civic_5d, sheet_name=en_sheet)
print(f"\nWith default header parsing: {len(df_default)} rows")
print(f"Columns: {list(df_default.columns)[:5]}...")
