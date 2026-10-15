#!/usr/bin/env python3
"""
Test: Column matching logic debug
Why are all rows classified as defects?
"""

import sys
from pathlib import Path
import pandas as pd

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "accy_v2"))

from accy_v2.oems.honda.pipeline import step1_validation, step2_header_normalization
from accy_v2.core.config_loader_v2 import ModularConfigLoader
from accy_v2.core.helpers.dq_logger import DQLogger
from accy_v2.core.helpers.pipeline_logger import PipelineLogger

# Setup
file_path = project_root / "accy_v2/data/landing_zone/honda/may_2026/CVIC5D.xlsx"
config_root = project_root / "accy_v2/oems/honda/config"

config_loader = ModularConfigLoader("honda", config_root)
config = config_loader.load_all()

excel = pd.ExcelFile(file_path)
df_raw = excel.parse(sheet_name="26MY_CIV5D_APP_EN", header=None)

run_id = "coltest_" + pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
dq_logger = DQLogger(run_id=run_id, source_file=str(file_path))
pipeline_logger = PipelineLogger(run_id=run_id, log_path="accy_v2/output/pipeline_logs/honda")

# Run Step 1
meta_data = {"sheet_name": "26MY_CIV5D_APP_EN"}
df_step1, meta_step1 = step1_validation.run(
    df_raw, config, meta_data, dq_logger, pipeline_logger
)

# Run Step 2
df_step2, meta_step2 = step2_header_normalization.run(
    df_step1, config, meta_step1, dq_logger, pipeline_logger
)

print("="*100)
print("DEBUG: Column Matching Test")
print("="*100)

section_name = "Packages and Kits"
column_mapping = meta_step2.get('column_mapping', {})
section_mapping = column_mapping.get(section_name, {})

print(f"\nSection: {section_name}")
print(f"Column Mapping: {section_mapping}")

# Test the _check_column logic manually
row_idx = 13
row = df_step1.iloc[row_idx]

print(f"\nRow {row_idx} values:")
for col_idx in range(10):
    val = row.iloc[col_idx]
    norm_name = section_mapping.get(col_idx, "??")
    print(f"  Col {col_idx}: norm_name='{norm_name}', value='{val}'")

# Test function to replicate _check_column
def test_check_column(col_name, row, norm_names):
    """Test if column has data"""
    print(f"\n  Looking for column: '{col_name}'")
    for col_idx, norm_name in norm_names.items():
        print(f"    Checking col_idx={col_idx}, norm_name='{norm_name}'")
        if norm_name == col_name:
            val = row.iloc[col_idx]
            has_data = pd.notna(val) and str(val).strip() != ""
            print(f"      MATCH! Value='{val}', has_data={has_data}")
            return has_data
    print(f"    NO MATCH FOUND")
    return False

print(f"\nColumn Matching Tests:")
has_desc = test_check_column("description", row, section_mapping)
has_part = test_check_column("part number", row, section_mapping)
has_dealer_net = test_check_column("dealer net", row, section_mapping)
has_list_price = test_check_column("list price", row, section_mapping)
has_frt = test_check_column("frt", row, section_mapping)
has_installed = test_check_column("installed price", row, section_mapping)

print(f"\nResults for Row 13:")
print(f"  has_description: {has_desc}")
print(f"  has_part_number: {has_part}")
print(f"  has_dealer_net: {has_dealer_net}")
print(f"  has_list_price: {has_list_price}")
print(f"  has_frt: {has_frt}")
print(f"  has_installed_price: {has_installed}")
print(f"  Has all prices: {has_dealer_net and has_list_price and has_frt and has_installed}")
print(f"\nExpected classification: PARENT (has both products + all prices)")
print(f"Actual record_type: {meta_step2.get('record_type_per_row', {}).get(row_idx, 'UNKNOWN')}")

print("\n" + "="*100)
