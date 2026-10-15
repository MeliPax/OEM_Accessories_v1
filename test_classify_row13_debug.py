#!/usr/bin/env python3
"""
Debug: Trace classification of row 13 in detail
"""

import sys, pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path.cwd() / 'accy_v2'))

from accy_v2.oems.honda.pipeline import step1_validation, step2_header_normalization
from accy_v2.core.config_loader_v2 import ModularConfigLoader
from accy_v2.core.helpers.dq_logger import DQLogger
from accy_v2.core.helpers.pipeline_logger import PipelineLogger

file_path = Path('accy_v2/data/landing_zone/honda/may_2026/CVIC5D.xlsx')
config_root = Path('accy_v2/oems/honda/config')

config = ModularConfigLoader('honda', config_root).load_all()
excel = pd.ExcelFile(file_path)
df_raw = excel.parse(sheet_name='26MY_CIV5D_APP_EN', header=None)

run_id = 'debug_row13'
dq_logger = DQLogger(run_id=run_id, source_file=str(file_path))
pipeline_logger = PipelineLogger(run_id=run_id, log_path='accy_v2/output/pipeline_logs/honda')

meta_data = {'sheet_name': '26MY_CIV5D_APP_EN'}
df_step1, meta_step1 = step1_validation.run(df_raw, config, meta_data, dq_logger, pipeline_logger)

print("=" * 120)
print("ROW 13 DEBUG - BEFORE STEP 2")
print("=" * 120)

row_13 = df_step1.iloc[13]
print(f"\nRow 13 raw values (first 10 columns):")
for i in range(10):
    val = row_13.iloc[i]
    print(f"  Col {i}: {val} (type: {type(val).__name__})")

print(f"\nSpecific columns:")
print(f"  Col 2 (description): '{row_13.iloc[2]}'")
print(f"  Col 3 (part_number): '{row_13.iloc[3]}'")
print(f"  Col 4 (dealer_net): {row_13.iloc[4]}")
print(f"  Col 5 (list_price): {row_13.iloc[5]}")
print(f"  Col 6 (frt): {row_13.iloc[6]}")
print(f"  Col 7 (installed_price): {row_13.iloc[7]}")

# Check if values are not null
print(f"\nValue checks:")
print(f"  pd.notna(col2): {pd.notna(row_13.iloc[2])}")
print(f"  pd.notna(col3): {pd.notna(row_13.iloc[3])}")
print(f"  pd.notna(col4): {pd.notna(row_13.iloc[4])}")
print(f"  pd.notna(col5): {pd.notna(row_13.iloc[5])}")
print(f"  pd.notna(col6): {pd.notna(row_13.iloc[6])}")
print(f"  pd.notna(col7): {pd.notna(row_13.iloc[7])}")

# Check string values
print(f"\nString checks (after strip):")
desc_str = str(row_13.iloc[2]).strip() if pd.notna(row_13.iloc[2]) else ""
part_str = str(row_13.iloc[3]).strip() if pd.notna(row_13.iloc[3]) else ""
print(f"  col2.strip() != '': {desc_str != ''} ('{desc_str}')")
print(f"  col3.strip() != '': {part_str != ''} ('{part_str}')")

# Now run Step 2
print("\n" + "=" * 120)
print("RUNNING STEP 2")
print("=" * 120)

df_step2, meta_step2 = step2_header_normalization.run(df_step1, config, meta_step1, dq_logger, pipeline_logger)

# Check results
print(f"\n[ROW 13 CLASSIFICATION RESULT]")
record_type_per_row = meta_step2.get('record_type_per_row', {})
rtype = record_type_per_row.get(13)
print(f"  record_type: {rtype}")

print(f"\n" + "=" * 120)
