#!/usr/bin/env python3
"""
Diagnostic: Check what's in actual rows to understand defect classification
"""

import sys
from pathlib import Path
import pandas as pd

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "accy_v2"))

from accy_v2.oems.honda.pipeline import step1_validation
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

run_id = "diag_" + pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
dq_logger = DQLogger(run_id=run_id, source_file=str(file_path))
pipeline_logger = PipelineLogger(run_id=run_id, log_path="accy_v2/output/pipeline_logs/honda")

# Run Step 1
meta_data = {"sheet_name": "26MY_CIV5D_APP_EN"}
df_step1, meta_step1 = step1_validation.run(
    df_raw, config, meta_data, dq_logger, pipeline_logger
)

section_structure = meta_step1.get('section_structure', {})

print("="*100)
print("DIAGNOSTIC: Examining Raw Row Data for Classification")
print("="*100)

# Look at first section
section_name = "Packages and Kits"
bounds = section_structure[section_name]
data_start = bounds.get('data_start_row')
data_end = bounds.get('data_end_row')

print(f"\nSection: {section_name}")
print(f"Data rows: {data_start}-{data_end}")
print(f"\nExpected column positions:")
print(f"  Col 2: description")
print(f"  Col 3: part number")
print(f"  Col 4: dealer net (price)")
print(f"  Col 5: list price (price)")
print(f"  Col 6: frt (price)")
print(f"  Col 7: installed price (price)")

print(f"\nSample rows with actual data:")
for row_idx in range(data_start, min(data_start + 10, data_end + 1)):
    row = df_step1.iloc[row_idx]

    col2 = str(row.iloc[2]) if pd.notna(row.iloc[2]) else "[NULL]"
    col3 = str(row.iloc[3]) if pd.notna(row.iloc[3]) else "[NULL]"
    col4 = str(row.iloc[4]) if pd.notna(row.iloc[4]) else "[NULL]"
    col5 = str(row.iloc[5]) if pd.notna(row.iloc[5]) else "[NULL]"
    col6 = str(row.iloc[6]) if pd.notna(row.iloc[6]) else "[NULL]"
    col7 = str(row.iloc[7]) if pd.notna(row.iloc[7]) else "[NULL]"

    print(f"\nRow {row_idx}:")
    print(f"  Description (col 2): {col2[:40]}")
    print(f"  Part Number (col 3): {col3[:40]}")
    print(f"  Prices (cols 4-7): {col4[:15]} | {col5[:15]} | {col6[:15]} | {col7[:15]}")

# Check what the classification logic sees
print(f"\n\nClassification Check for Row 13:")
row_13 = df_step1.iloc[13]

has_desc = pd.notna(row_13.iloc[2]) and str(row_13.iloc[2]).strip() != ""
has_part = pd.notna(row_13.iloc[3]) and str(row_13.iloc[3]).strip() != ""
has_p1 = pd.notna(row_13.iloc[4]) and str(row_13.iloc[4]).strip() != ""
has_p2 = pd.notna(row_13.iloc[5]) and str(row_13.iloc[5]).strip() != ""
has_p3 = pd.notna(row_13.iloc[6]) and str(row_13.iloc[6]).strip() != ""
has_p4 = pd.notna(row_13.iloc[7]) and str(row_13.iloc[7]).strip() != ""

print(f"  has_description: {has_desc}")
print(f"  has_part_number: {has_part}")
print(f"  has_price[0] (dealer_net): {has_p1}")
print(f"  has_price[1] (list_price): {has_p2}")
print(f"  has_price[2] (frt): {has_p3}")
print(f"  has_price[3] (installed): {has_p4}")
print(f"  has_both_product: {has_desc and has_part}")
print(f"  has_all_prices: {has_p1 and has_p2 and has_p3 and has_p4}")
print(f"  has_any_price: {has_p1 or has_p2 or has_p3 or has_p4}")

if has_desc and has_part and has_p1 and has_p2 and has_p3 and has_p4:
    print(f"\n  Expected classification: PARENT")
elif has_desc and has_part and not (has_p1 or has_p2 or has_p3 or has_p4):
    print(f"\n  Expected classification: CHILD")
else:
    print(f"\n  Expected classification: DEFECT")

print("\n" + "="*100)
