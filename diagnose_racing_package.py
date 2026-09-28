"""
Deep diagnostic to find if "Racing Package - Type R" or "26TYPER-RACE" exists
"""

import pandas as pd
from pathlib import Path

# Find civic 5d file
landing_zone = Path("landing_zone/2026/Honda")
civic_5d_files = list(landing_zone.rglob("*civic*5d*.xlsx"))

if not civic_5d_files:
    print("[ERROR] civic 5d.xlsx not found")
    exit(1)

civic_5d = civic_5d_files[0]
print(f"Analyzing: {civic_5d.name}\n")

# Load raw (no header interpretation)
xl = pd.ExcelFile(civic_5d)
en_sheet = [s for s in xl.sheet_names if "_EN" in s][0]
df_raw = pd.read_excel(civic_5d, sheet_name=en_sheet, header=None)

print(f"Total rows in sheet: {len(df_raw)}\n")

print("="*80)
print("SEARCHING FOR:")
print("  - 'Racing'")
print("  - 'TYPER'")
print("  - '26TYPER'")
print("  - 'Type R'")
print("="*80)

search_terms = ["Racing", "TYPER", "26TYPER"]
found_indices = []

for idx, row in df_raw.iterrows():
    row_text = " ".join(str(val) for val in row.values if pd.notna(val))
    for term in search_terms:
        if term in row_text:
            found_indices.append(idx)
            print(f"\n[Row {idx}] Found '{term}':")
            print(f"  Text: {row_text[:200]}")
            print(f"  Values: {list(row.values[:6])}")
            break

if not found_indices:
    print("\n[NOT FOUND] None of the search terms appear in the spreadsheet!")
    print("\nThis suggests either:")
    print("  1. The 'Racing Package - Type R' row doesn't exist in this file")
    print("  2. It's spelled differently than expected")
    print("  3. It's in a different sheet (not the _EN sheet)")

    # Check other sheets
    print("\n" + "="*80)
    print("Checking OTHER SHEETS for 'Racing':")
    print("="*80)

    for sheet_name in xl.sheet_names:
        df_test = pd.read_excel(civic_5d, sheet_name=sheet_name, header=None)
        for idx, row in df_test.iterrows():
            row_text = " ".join(str(val) for val in row.values if pd.notna(val))
            if "Racing" in row_text or "TYPER" in row_text:
                print(f"\n[FOUND in {sheet_name}] Row {idx}: {row_text[:100]}")
else:
    print(f"\n[FOUND] Located at rows: {found_indices}")

    # Show the rows in context
    print("\n" + "="*80)
    print("SHOWING CONTEXT (5 rows before and after):")
    print("="*80)

    for found_idx in found_indices:
        start = max(0, found_idx - 5)
        end = min(len(df_raw), found_idx + 6)

        print(f"\nRows {start} to {end} (found at row {found_idx}):")
        print(df_raw.iloc[start:end].to_string())
