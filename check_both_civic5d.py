"""
Check both versions of civic 5d file
"""

import pandas as pd
from pathlib import Path

landing_zone = Path("landing_zone/2026/Honda")

# Find both versions
civic_lowercase = landing_zone / "2026-04-09" / "civic 5d.xlsx"
civic_uppercase = landing_zone / "2026-05-04" / "CIVIC 5D.xlsx"

files_to_check = [
    (civic_lowercase, "LOWERCASE: 2026-04-09/civic 5d.xlsx"),
    (civic_uppercase, "UPPERCASE: 2026-05-04/CIVIC 5D.xlsx")
]

for file_path, label in files_to_check:
    if not file_path.exists():
        print(f"[NOT FOUND] {label}\n")
        continue

    print("="*80)
    print(f"CHECKING: {label}")
    print("="*80)

    # Check file size and modification time
    size_mb = file_path.stat().st_size / (1024**2)
    print(f"File size: {size_mb:.2f} MB\n")

    # Load and search
    try:
        xl = pd.ExcelFile(file_path)
        en_sheet = [s for s in xl.sheet_names if "_EN" in s][0]
        df = pd.read_excel(file_path, sheet_name=en_sheet, header=None)

        print(f"Sheet: {en_sheet}")
        print(f"Total rows: {len(df)}\n")

        # Search for Racing Package
        found = False
        for idx, row in df.iterrows():
            row_text = " ".join(str(val) for val in row.values if pd.notna(val))
            if "Racing" in row_text or "TYPER" in row_text or "26TYPER" in row_text:
                print(f"[FOUND] Row {idx}: {row_text[:150]}")
                found = True

        if not found:
            print("[NOT FOUND] 'Racing', 'TYPER', or '26TYPER' not in this file")

    except Exception as e:
        print(f"[ERROR] {e}\n")

    print()
