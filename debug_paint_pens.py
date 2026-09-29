#!/usr/bin/env python3
"""Debug Paint Pens section row counting"""

import pandas as pd
from pathlib import Path
import re

file_path = Path("accy_v2/data/landing_zone/honda/may_2026/CVIC5D.xlsx")
en_df = pd.read_excel(file_path, sheet_name="26MY_CIV5D_APP_EN", header=None)

print(f"Total DataFrame rows: {len(en_df)}")

# Find all section markers
section_pattern = r"^\d+\.\d+\s+(.+)$"
sections = []

for idx in range(len(en_df)):
    for val in en_df.iloc[idx]:
        if pd.notna(val):
            val_str = str(val).strip()
            match = re.match(section_pattern, val_str)
            if match:
                section_name = match.group(1).strip()
                sections.append((idx, section_name))
                break

# Paint Pens is the last section
if len(sections) >= 6:
    paint_pens_marker_row = sections[-1][0]
    
    header_row = paint_pens_marker_row + 1
    trim_sub_header_row = header_row + 1
    data_start_row = trim_sub_header_row + 1
    data_end_row = len(en_df) - 1
    
    print(f"\nPaint Pens Section:")
    print(f"  Marker row: {paint_pens_marker_row}")
    print(f"  Header row: {header_row}")
    print(f"  Trim sub-header row: {trim_sub_header_row}")
    print(f"  Data rows: {data_start_row} to {data_end_row}")
    print(f"  Total rows to analyze: {data_end_row - data_start_row + 1}")
    
    print("\n" + "=" * 120)
    print("ROW-BY-ROW ANALYSIS")
    print("=" * 120)
    
    valid_count = 0
    empty_count = 0
    publishing_count = 0
    
    for row_idx in range(data_start_row, data_end_row + 1):
        row = en_df.iloc[row_idx]
        
        # Check if row is empty
        is_empty = True
        for val in row.values:
            if pd.notna(val):
                val_str = str(val).strip()
                if val_str and val_str.lower() != "nan":
                    is_empty = False
                    break
        
        # Check if publishing row
        is_publishing = False
        for val in row.values:
            if pd.notna(val):
                val_str = str(val).lower()
                if any(m in val_str for m in ["publication", "last updated", "data as of", "effective"]):
                    is_publishing = True
                    break
        
        # Check for valid data (both Part Number and Description)
        part_num = str(en_df.iloc[row_idx, 3]).strip() if pd.notna(en_df.iloc[row_idx, 3]) else ""
        desc = str(en_df.iloc[row_idx, 2]).strip() if pd.notna(en_df.iloc[row_idx, 2]) else ""
        
        if is_publishing:
            status = "PUBLISHING"
            publishing_count += 1
        elif is_empty:
            status = "EMPTY"
            empty_count += 1
        elif part_num and desc:
            status = "VALID DATA"
            valid_count += 1
        else:
            status = f"INCOMPLETE (Part#:{bool(part_num)} Desc:{bool(desc)})"
        
        print(f"Row {row_idx}: {status:25s} | PartNum: {part_num[:25]:25s} | Desc: {desc[:35]:35s}")
    
    print("\n" + "=" * 120)
    print("COUNTS")
    print("=" * 120)
    print(f"Valid data rows: {valid_count}")
    print(f"Empty rows: {empty_count}")
    print(f"Publishing rows: {publishing_count}")
    print(f"Total: {valid_count + empty_count + publishing_count}")
    print(f"Total data rows analyzed: {data_end_row - data_start_row + 1}")
