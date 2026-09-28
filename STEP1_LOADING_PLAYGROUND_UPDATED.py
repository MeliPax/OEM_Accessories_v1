"""
STEP1_LOADING_PLAYGROUND - UPDATED WITH CORRECT DATA SOURCE

This is the complete updated code for the notebook.
Copy each section into a new notebook cell.

Data source: accy_v2/data/landing_zone/honda/may_2026/CVIC5D.xlsx
Updated: Sep 28, 2026
"""

print("""
================================================================================
STEP 1: LOAD CIVIC 5D FROM CORRECT DATA SOURCE
================================================================================
""")

# ============================================================================
# SECTION 1: Load Data from may_2026 Landing Zone
# ============================================================================

from pathlib import Path
import pandas as pd

landing_zone = Path("accy_v2/data/landing_zone/honda/may_2026")
civic_5d_file = landing_zone / "CVIC5D.xlsx"

print(f"Loading from: {landing_zone.resolve()}\n")

if not civic_5d_file.exists():
    print(f"[ERROR] File not found")
    exit(1)

print(f"[OK] File found: {civic_5d_file.name}")
print(f"  Size: {civic_5d_file.stat().st_size / (1024**2):.2f} MB")
print(f"  Location: {landing_zone.resolve()}\n")

# List all files
excel_files = list(landing_zone.glob("*.xlsx*"))
print(f"Total Honda files in may_2026: {len(excel_files)}\n")

for i, file in enumerate(excel_files, 1):
    size_mb = file.stat().st_size / (1024**2)
    print(f"{i:2d}. {file.name:<50} ({size_mb:.2f} MB)")

# ============================================================================
# SECTION 2: Load EN and FR Sheets
# ============================================================================

print("\n" + "="*80)
print("STEP 2: IDENTIFY SHEETS")
print("="*80 + "\n")

xl = pd.ExcelFile(civic_5d_file)
sheet_names = xl.sheet_names

print(f"Sheets in file:")
for i, sheet in enumerate(sheet_names, 1):
    print(f"  {i}. {sheet}")

# Find EN and FR sheets
en_sheets = [s for s in sheet_names if "_APP_EN" in s]
fr_sheets = [s for s in sheet_names if "_APP_FR" in s]
select_province = [s for s in sheet_names if "SELECT" in s.upper()]

print(f"\nEN Sheets: {en_sheets}")
print(f"FR Sheets: {fr_sheets}")
print(f"Select Province: {select_province}")

# ============================================================================
# SECTION 3: Load EN Sheet Data
# ============================================================================

print("\n" + "="*80)
print("STEP 3: LOAD EN SHEET DATA")
print("="*80 + "\n")

en_sheet = en_sheets[0] if en_sheets else None

if en_sheet:
    df_civic = pd.read_excel(civic_5d_file, sheet_name=en_sheet)

    print(f"Sheet: {en_sheet}")
    print(f"Data shape: {len(df_civic)} rows x {len(df_civic.columns)} columns\n")

    print(f"Column names:")
    for i, col in enumerate(df_civic.columns, 1):
        print(f"  {i:2d}. {col}")

    print(f"\nFirst 5 rows:")
    print(df_civic.head())
else:
    print("[ERROR] No EN sheet found")
    df_civic = None

# ============================================================================
# SECTION 4: Verify Data (Racing Package Check)
# ============================================================================

print("\n" + "="*80)
print("STEP 4: VERIFY DATA INTEGRITY")
print("="*80 + "\n")

if df_civic is not None:
    # Check for Racing Package
    racing_found = df_civic.astype(str).apply(
        lambda row: any("Racing" in str(val) for val in row.values),
        axis=1
    ).any()

    if racing_found:
        print("[OK] Racing Package - Type R found in data")

        # Find and display the row
        for idx, row in df_civic.iterrows():
            row_text = " ".join(str(val) for val in row.values if pd.notna(val))
            if "Racing" in row_text and "TYPER" in row_text:
                print(f"\n  Location: Row {idx}")
                print(f"  Content: {row_text[:150]}")
                break
    else:
        print("[ERROR] Racing Package not found - data may be incomplete")

    # Check data completeness
    print(f"\nData completeness check:")
    print(f"  Total rows: {len(df_civic)}")
    print(f"  Total columns: {len(df_civic.columns)}")
    print(f"  Null values: {df_civic.isnull().sum().sum()}")
    print(f"\n[OK] Data loaded successfully from may_2026 landing zone")
else:
    print("[ERROR] Could not verify data")

print("\n" + "="*80)
print("READY FOR STEP 2: SECTION BOUNDARY IDENTIFICATION")
print("="*80)
