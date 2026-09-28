"""
UPDATED LOADING CODE FOR STEP1_LOADING_PLAYGROUND.ipynb

Copy the code below into a new cell in your notebook after the setup cells.
This will load the correct file from the may_2026 landing zone with all data.
"""

# ============================================================================
# STEP 0: Load from Correct Landing Zone (may_2026)
# ============================================================================

from pathlib import Path
import pandas as pd

# Use the correct landing zone path
landing_zone = Path("accy_v2/data/landing_zone/honda/may_2026")
civic_5d_file = landing_zone / "CVIC5D.xlsx"

print(f"Loading from: {landing_zone.resolve()}\n")

if not civic_5d_file.exists():
    print(f"[ERROR] File not found: {civic_5d_file.resolve()}")
else:
    print(f"[OK] File found: {civic_5d_file.name}")
    print(f"  Size: {civic_5d_file.stat().st_size / (1024**2):.2f} MB\n")

    # Get sheet info
    xl = pd.ExcelFile(civic_5d_file)
    print(f"Sheets in file:")
    for i, sheet in enumerate(xl.sheet_names, 1):
        print(f"  {i}. {sheet}")

    # Find EN sheet (data sheet)
    en_sheets = [s for s in xl.sheet_names if "_APP_EN" in s]

    if en_sheets:
        en_sheet = en_sheets[0]
        print(f"\n[OK] Found EN sheet: {en_sheet}\n")

        # Load the data
        df_civic = pd.read_excel(civic_5d_file, sheet_name=en_sheet)

        print(f"DATA LOADED:")
        print(f"  Rows: {len(df_civic)}")
        print(f"  Columns: {len(df_civic.columns)}")
        print(f"  Shape: {df_civic.shape}\n")

        print(f"COLUMN NAMES:")
        for i, col in enumerate(df_civic.columns, 1):
            print(f"  {i:2d}. {col}")

        # Verify Racing Package is present
        print("\n" + "="*80)
        print("DATA VERIFICATION")
        print("="*80)

        racing_found = df_civic.astype(str).apply(
            lambda row: any("Racing" in str(val) for val in row.values),
            axis=1
        ).any()

        if racing_found:
            print("[OK] Racing Package - Type R found in data")
        else:
            print("[ERROR] Racing Package not found")

        print(f"\nReady to proceed with Step 2.1 (Identify Section Boundaries)")

    else:
        print("[ERROR] No _APP_EN sheet found")
        df_civic = None
