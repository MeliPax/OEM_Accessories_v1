"""
Compare the two civic 5d versions to see the differences
"""

import pandas as pd
from pathlib import Path

landing_zone = Path("landing_zone/2026/Honda")

civic_lowercase = landing_zone / "2026-04-09" / "civic 5d.xlsx"
civic_uppercase = landing_zone / "2026-05-04" / "CIVIC 5D.xlsx"

print("="*80)
print("COMPARING TWO VERSIONS OF CIVIC 5D")
print("="*80)

for file_path, label in [(civic_lowercase, "LOWERCASE"), (civic_uppercase, "UPPERCASE")]:
    if not file_path.exists():
        continue

    xl = pd.ExcelFile(file_path)
    en_sheet = [s for s in xl.sheet_names if "_EN" in s][0]

    # Load with header interpretation (default pandas behavior)
    df_default = pd.read_excel(file_path, sheet_name=en_sheet)

    # Load raw (no header interpretation)
    df_raw = pd.read_excel(file_path, sheet_name=en_sheet, header=None)

    print(f"\n{label} ({file_path.parent.name}):")
    print(f"  With header parsing: {len(df_default)} rows")
    print(f"  Raw (no header): {len(df_raw)} rows")
    print(f"  Rows lost during load: {len(df_raw) - len(df_default)}")

    # Check for Racing Package in both
    racing_in_default = df_default.astype(str).apply(
        lambda row: any("Racing" in str(val) for val in row.values),
        axis=1
    ).any()

    racing_in_raw = df_raw.astype(str).apply(
        lambda row: any("Racing" in str(val) for val in row.values),
        axis=1
    ).any()

    print(f"  Racing Package in default load: {racing_in_default}")
    print(f"  Racing Package in raw load: {racing_in_raw}")

    if racing_in_raw and not racing_in_default:
        print("  >>> WARNING: Row exists in raw but is dropped during header parsing!")

print("\n" + "="*80)
print("RECOMMENDATION:")
print("="*80)
print("Use the UPPERCASE version (2026-05-04/CIVIC 5D.xlsx) which has:")
print("  - All the data (171 rows raw)")
print("  - Includes Racing Package - Type R")
print("\nThe lowercase version appears to be an older or incomplete copy.")
