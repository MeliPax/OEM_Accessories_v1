#!/usr/bin/env python3
"""
Debug: Check column mappings from Step 2
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

run_id = 'debug_colmapping'
dq_logger = DQLogger(run_id=run_id, source_file=str(file_path))
pipeline_logger = PipelineLogger(run_id=run_id, log_path='accy_v2/output/pipeline_logs/honda')

meta_data = {'sheet_name': '26MY_CIV5D_APP_EN'}
df_step1, meta_step1 = step1_validation.run(df_raw, config, meta_data, dq_logger, pipeline_logger)
df_step2, meta_step2 = step2_header_normalization.run(df_step1, config, meta_step1, dq_logger, pipeline_logger)

print("=" * 120)
print("COLUMN MAPPING DEBUG")
print("=" * 120)

column_mapping = meta_step2.get('column_mapping', {})

print(f"\n[COLUMN MAPPING FOR 'Packages and Kits']")
mapping = column_mapping.get('Packages and Kits', {})
print(f"  Mapping (first 15 entries):")
for col_idx in sorted(mapping.keys())[:15]:
    norm_name = mapping[col_idx]
    print(f"    Col {col_idx:2d}: {norm_name}")

print(f"\n[RAW DATA - ROW 11 (HEADER), ROW 12 (TRIM SUBHEADER), ROW 13 (DATA)]")
for row_idx in [11, 12, 13]:
    row = df_step1.iloc[row_idx]
    print(f"\n  Row {row_idx}:")
    for col_idx in range(10):
        val = row.iloc[col_idx]
        norm_name = mapping.get(col_idx, "???")
        print(f"    Col {col_idx}: '{val}' -> '{norm_name}'")

print("\n" + "=" * 120)
