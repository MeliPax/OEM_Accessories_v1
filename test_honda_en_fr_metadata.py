#!/usr/bin/env python3
"""Test Honda EN/FR metadata extraction - comprehensive overview"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "accy_v2"))

import pandas as pd
import yaml
import uuid

from accy_v2.oems.honda.pipeline import step1_validation
from accy_v2.core.helpers.dq_logger import DQLogger
from accy_v2.core.helpers.pipeline_logger import PipelineLogger

# File and config paths
file_path = Path("accy_v2/data/landing_zone/honda/may_2026/CVIC5D.xlsx")
config_root = Path("accy_v2/oems/honda/config")

print("=" * 100)
print("HONDA EN/FR METADATA EXTRACTION TEST")
print("=" * 100)
print(f"\nFile: {file_path}")
print(f"Config Root: {config_root}\n")

if not file_path.exists():
    print(f"[ERROR] File not found: {file_path}")
    sys.exit(1)

# Load configs
print("Loading configurations...")
with open(config_root / "pipeline.yaml") as f:
    config = yaml.safe_load(f)

with open(config_root / "schemas" / "detection.yaml") as f:
    detection_config = yaml.safe_load(f)
    config["step1_detection"] = detection_config

print("[OK] Configurations loaded\n")

# Initialize loggers
run_id = str(uuid.uuid4())[:8]
dq_logger = DQLogger(run_id=run_id, source_file=str(file_path))
pipeline_logger = PipelineLogger(run_id=run_id, log_path="accy_v2/output/pipeline_logs/honda")

# Load Excel file
print("Loading Excel file...")
excel = pd.ExcelFile(file_path)
sheets = {
    name: excel.parse(sheet_name=name, header=None)
    for name in excel.sheet_names
    if "_APP_EN" in name or "_APP_FR" in name
}
print(f"[OK] Loaded {len(sheets)} sheets: {list(sheets.keys())}\n")

# Process each sheet
results = {}
for sheet_name, df in sheets.items():
    print("=" * 100)
    print(f"PROCESSING: {sheet_name}")
    print("=" * 100)

    meta_data = {"sheet_name": sheet_name}

    try:
        working_df, updated_meta = step1_validation.run(
            df, config, meta_data, dq_logger, pipeline_logger
        )
        results[sheet_name] = updated_meta

        # Print metadata extracted
        print(f"\n[OK] Metadata Extraction Successful")
        print(f"  Model: {updated_meta.get('model_name', 'N/A')}")
        print(f"  Year: {updated_meta.get('vehicle_year', 'N/A')}")
        print(f"  Language: {updated_meta.get('language', 'N/A')}")
        print(f"  Sections: {updated_meta.get('sections_detected', 0)}")
        print(f"  Total Rows: {len(df)}")

    except Exception as e:
        print(f"\n[FAIL] Error processing {sheet_name}: {e}")
        import traceback
        traceback.print_exc()
        results[sheet_name] = None

# Output comprehensive overview
print("\n\n" + "=" * 100)
print("DATA EXTRACTION OVERVIEW - DETAILED METADATA")
print("=" * 100)

for sheet_name, meta in results.items():
    if meta is None:
        print(f"\n{sheet_name}: FAILED")
        continue

    print(f"\n{'-' * 100}")
    print(f"Sheet: {sheet_name}")
    print(f"{'-' * 100}")

    # Basic info
    print(f"\nBASIC METADATA:")
    print(f"  Model Name:       {meta.get('model_name', 'N/A')}")
    print(f"  Vehicle Year:     {meta.get('vehicle_year', 'N/A')}")
    print(f"  Language:         {meta.get('language', 'N/A')}")
    print(f"  Sections Detected: {meta.get('sections_detected', 0)}")

    # Section summary
    print(f"\nSECTION STRUCTURE:")
    section_structure = meta.get('section_structure', {})
    for i, (section_name, bounds) in enumerate(section_structure.items(), 1):
        print(f"  {i}. {section_name}")
        print(f"     Marker Row: {bounds.get('marker_row')}")
        print(f"     Header Row: {bounds.get('header_row')}")
        print(f"     Data Range: rows {bounds.get('data_start_row')}-{bounds.get('data_end_row')}")

    # Row metrics per section
    print(f"\nROW METRICS BY SECTION:")
    row_metrics = meta.get('row_metrics_per_section', {})

    section_summary = {
        'total': 0,
        'valid_data': 0,
        'empty': 0,
        'publishing': 0
    }

    for section_name, metrics in row_metrics.items():
        total = metrics.get('total_rows', 0)
        valid = metrics.get('valid_data_rows', 0)
        empty = metrics.get('empty_rows', 0)
        pub = metrics.get('publishing_rows', 0)

        section_summary['total'] += total
        section_summary['valid_data'] += valid
        section_summary['empty'] += empty
        section_summary['publishing'] += pub

        print(f"\n  {section_name}:")
        print(f"    Total rows:        {total}")
        print(f"    Valid data rows:   {valid}")
        print(f"    Empty rows:        {empty}")
        print(f"    Publishing rows:   {pub}")

    # Totals
    print(f"\nTOTAL COUNTS ACROSS ALL SECTIONS:")
    print(f"  Total rows:          {section_summary['total']}")
    print(f"  Valid data rows:     {section_summary['valid_data']}")
    print(f"  Empty rows:          {section_summary['empty']}")
    print(f"  Publishing rows:     {section_summary['publishing']}")

    # Trim columns
    trim_cols = meta.get('trim_columns_per_section', {})
    print(f"\nTRIM COLUMNS:")
    for section_name, cols in trim_cols.items():
        print(f"  {section_name}: {len(cols)} trim columns")

# Final summary comparing EN vs FR
print("\n\n" + "=" * 100)
print("COMPARISON: EN vs FR")
print("=" * 100)

if len(results) == 2:
    en_data = results.get('26MY_CIV5D_APP_EN')
    fr_data = results.get('26MY_CIV5D_APP_FR')

    if en_data and fr_data:
        print(f"\n{'Metric':<30} {'EN':<20} {'FR':<20} {'Match'}")
        print("-" * 75)

        # Compare basic metrics
        en_sections = en_data.get('sections_detected', 0)
        fr_sections = fr_data.get('sections_detected', 0)
        match = "[OK]" if en_sections == fr_sections else "[FAIL]"
        print(f"{'Sections Detected':<30} {en_sections:<20} {fr_sections:<20} {match}")

        # Compare row metrics
        en_metrics = en_data.get('row_metrics_per_section', {})
        fr_metrics = fr_data.get('row_metrics_per_section', {})

        en_valid = sum(m['valid_data_rows'] for m in en_metrics.values())
        fr_valid = sum(m['valid_data_rows'] for m in fr_metrics.values())
        match = "[OK]" if en_valid == fr_valid else "[WARN]" if abs(en_valid - fr_valid) <= 5 else "[FAIL]"
        print(f"{'Valid Data Rows':<30} {en_valid:<20} {fr_valid:<20} {match}")

        en_total = sum(m['total_rows'] for m in en_metrics.values())
        fr_total = sum(m['total_rows'] for m in fr_metrics.values())
        print(f"{'Total Data Rows':<30} {en_total:<20} {fr_total:<20}")

        en_trim = sum(len(cols) for cols in en_data.get('trim_columns_per_section', {}).values())
        fr_trim = sum(len(cols) for cols in fr_data.get('trim_columns_per_section', {}).values())
        match = "[OK]" if en_trim == fr_trim else "[FAIL]"
        print(f"{'Total Trim Columns':<30} {en_trim:<20} {fr_trim:<20} {match}")

print("\n" + "=" * 100)
print("[OK] METADATA EXTRACTION COMPLETE")
print("=" * 100 + "\n")
