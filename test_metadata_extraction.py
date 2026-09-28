"""Test metadata extraction from Honda data sheets"""

import pandas as pd
from pathlib import Path
from accy_v2.oems.honda.pipeline.step1_validation import extract_metadata_from_data_sheet

# Find civic 5d file
landing_zone = Path("landing_zone/2026/Honda")
civic_5d_files = list(landing_zone.glob("*civic*5d*.xlsx"))

if not civic_5d_files:
    print("❌ civic 5d.xlsx not found")
    exit(1)

civic_5d = civic_5d_files[0]
print(f"Testing with: {civic_5d.name}\n")

# Load EN sheet
xl = pd.ExcelFile(civic_5d)
en_sheet = [s for s in xl.sheet_names if "_EN" in s][0]

print(f"Loading sheet: {en_sheet}\n")

df_en = pd.read_excel(civic_5d, sheet_name=en_sheet)

# Extract metadata
meta = extract_metadata_from_data_sheet(df_en)

print("="*80)
print("METADATA EXTRACTION RESULTS")
print("="*80)
print(f"Honda Accessories Found: {meta.get('honda_accessories_found')}")
print(f"Section Marker Row: {meta.get('section_marker_row')}")
print(f"Publication Date: {meta.get('publication_date')}")

if meta.get('section_marker_row') is not None:
    print(f"\nHeader rows (before section marker):")
    print("-"*80)
    header_rows = df_en.iloc[0:meta['section_marker_row']]
    display_cols = min(5, len(header_rows.columns))
    print(header_rows.iloc[:, 0:display_cols].to_string())

print(f"\n\nFooter rows (last 3):")
print("-"*80)
footer_rows = df_en.tail(3)
display_cols = min(5, len(footer_rows.columns))
print(footer_rows.iloc[:, 0:display_cols].to_string())
