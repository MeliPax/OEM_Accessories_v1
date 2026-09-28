#!/usr/bin/env python3
"""Debug section detection"""

import pandas as pd
from pathlib import Path
import re

file_path = Path("accy_v2/data/landing_zone/honda/may_2026/CVIC5D.xlsx")

en_df = pd.read_excel(file_path, sheet_name="26MY_CIV5D_APP_EN", header=None)

print("="*100)
print("SECTION DETECTION - Finding section markers")
print("="*100)

df_str = en_df.astype(str)
section_pattern = r"^\d+\.\d+\s+(.+)$"
section_starts = []

for idx, row in df_str.iterrows():
    for cell_value in row.values:
        cell_str = str(cell_value).strip()
        match = re.match(section_pattern, cell_str)
        if match:
            section_name = match.group(1).strip()
            section_starts.append((idx, section_name, cell_str))
            print(f"  Found marker at row {idx}: '{section_name}'")
            break

print("\n" + "="*100)
print("SECTION BOUNDARIES CALCULATION")
print("="*100)

for i, (marker_row, section_name, marker_text) in enumerate(section_starts):
    data_start = marker_row + 1

    if i + 1 < len(section_starts):
        next_marker_row = section_starts[i + 1][0]
        data_end = next_marker_row - 1
    else:
        data_end = len(en_df) - 1

    print(f"\n{section_name}:")
    print(f"  marker_row: {marker_row}")
    print(f"  data_start: {data_start} (should be header row)")
    print(f"  data_end: {data_end}")

    # Show what's actually at these rows
    marker_row_content = en_df.iloc[marker_row, 2] if marker_row < len(en_df) else "OUT OF BOUNDS"
    data_start_content = en_df.iloc[data_start, 2] if data_start < len(en_df) else "OUT OF BOUNDS"

    print(f"  Row {marker_row} contains: '{marker_row_content}'")
    print(f"  Row {data_start} contains: '{data_start_content}'")
