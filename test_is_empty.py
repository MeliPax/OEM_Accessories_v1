#!/usr/bin/env python3
"""Test if _is_row_completely_empty works correctly"""

import sys
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path.cwd() / 'accy_v2'))

from accy_v2.oems.honda.pipeline.step2_header_normalization import _is_row_completely_empty

file_path = Path('accy_v2/data/landing_zone/honda/may_2026/CVIC5D.xlsx')

print("Testing _is_row_completely_empty() function")
print("=" * 80)
print()

df_en = pd.read_excel(file_path, sheet_name='26MY_CIV5D_APP_EN', header=None, engine='openpyxl')

# Test on defect rows
test_rows = [17, 21, 25]

for row_idx in test_rows:
    row = df_en.iloc[row_idx]
    result = _is_row_completely_empty(row)
    print(f"Row {row_idx}: _is_row_completely_empty() = {result}")
    print(f"  Row data: {list(row)}")
    print()

# Also test on a known data row
print("Test on a known data row (row 13 - should have data):")
row = df_en.iloc[13]
result = _is_row_completely_empty(row)
print(f"Row 13: _is_row_completely_empty() = {result}")
print(f"  Row data (first 10 cols): {list(row)[:10]}")
