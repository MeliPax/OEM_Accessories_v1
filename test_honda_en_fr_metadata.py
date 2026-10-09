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

# Final summary comparing EN vs FR - Side-by-side with sections
print("\n\n" + "=" * 120)
print("COMPARISON: EN vs FR - SECTION-BY-SECTION WITH METRICS")
print("=" * 120)

if len(results) == 2:
    en_data = results.get('26MY_CIV5D_APP_EN')
    fr_data = results.get('26MY_CIV5D_APP_FR')

    if en_data and fr_data:
        en_metrics = en_data.get('row_metrics_per_section', {})
        fr_metrics = fr_data.get('row_metrics_per_section', {})
        en_trim_cols = en_data.get('trim_columns_per_section', {})
        fr_trim_cols = fr_data.get('trim_columns_per_section', {})

        # Helper function to calculate variance
        def get_variance_str(en_val, fr_val):
            if en_val == fr_val:
                return "[OK]"
            else:
                diff = en_val - fr_val
                if diff > 0:
                    return f"+{diff}"
                else:
                    return str(diff)

        # Get all section names - EN and FR have different names for same sections
        en_section_names = list(en_metrics.keys())
        fr_section_names = list(fr_metrics.keys())

        # Match sections by order (they should be in same order even with different names)
        # Print each section with metrics side-by-side
        for idx, (en_section_name, fr_section_name) in enumerate(zip(en_section_names, fr_section_names)):
            en_section = en_metrics.get(en_section_name, {})
            fr_section = fr_metrics.get(fr_section_name, {})
            en_trim = len(en_trim_cols.get(en_section_name, []))
            fr_trim = len(fr_trim_cols.get(fr_section_name, []))

            # Display both EN and FR section names
            section_display = f"{en_section_name} / {fr_section_name}"

            en_total = en_section.get('total_rows', 0)
            fr_total = fr_section.get('total_rows', 0)
            en_valid = en_section.get('valid_data_rows', 0)
            fr_valid = fr_section.get('valid_data_rows', 0)
            en_empty = en_section.get('empty_rows', 0)
            fr_empty = fr_section.get('empty_rows', 0)
            en_pub = en_section.get('publishing_rows', 0)
            fr_pub = fr_section.get('publishing_rows', 0)

            # Calculate coverage percentages
            en_coverage = (en_valid / en_total * 100) if en_total > 0 else 0
            fr_coverage = (fr_valid / fr_total * 100) if fr_total > 0 else 0

            print(f"\n{'-' * 120}")
            print(f"SECTION: {section_display}")
            print(f"{'-' * 120}")
            print(f"{'Metric':<35} {'EN':<25} {'FR':<25} {'Variance':<20}")
            print(f"{'-' * 120}")

            # Total Rows
            print(f"{'Total Rows':<35} {en_total:<25} {fr_total:<25} {get_variance_str(en_total, fr_total):<20}")

            # Valid Data Rows
            print(f"{'Valid Data Rows':<35} {en_valid:<25} {fr_valid:<25} {get_variance_str(en_valid, fr_valid):<20}")

            # Empty Rows
            print(f"{'Empty Rows':<35} {en_empty:<25} {fr_empty:<25} {get_variance_str(en_empty, fr_empty):<20}")

            # Publishing Rows
            print(f"{'Publishing Rows':<35} {en_pub:<25} {fr_pub:<25} {get_variance_str(en_pub, fr_pub):<20}")

            # Trim Columns
            print(f"{'Trim Columns':<35} {en_trim:<25} {fr_trim:<25} {get_variance_str(en_trim, fr_trim):<20}")

            # Coverage Percentage
            en_cov_str = f"{en_coverage:.1f}%"
            fr_cov_str = f"{fr_coverage:.1f}%"
            cov_diff = round(en_coverage - fr_coverage, 1)
            coverage_var = "[OK]" if cov_diff == 0 else f"+{cov_diff}%" if cov_diff > 0 else f"{cov_diff}%"
            print(f"{'Coverage %':<35} {en_cov_str:<25} {fr_cov_str:<25} {coverage_var:<20}")

        # Print TOTAL summary
        print(f"\n{'=' * 120}")
        print(f"TOTAL SUMMARY")
        print(f"{'=' * 120}")
        print(f"{'Metric':<35} {'EN':<25} {'FR':<25} {'Variance':<20}")
        print(f"{'-' * 120}")

        en_total_rows = sum(m.get('total_rows', 0) for m in en_metrics.values())
        fr_total_rows = sum(m.get('total_rows', 0) for m in fr_metrics.values())
        print(f"{'Total Rows':<35} {en_total_rows:<25} {fr_total_rows:<25} {get_variance_str(en_total_rows, fr_total_rows):<20}")

        en_valid_rows = sum(m.get('valid_data_rows', 0) for m in en_metrics.values())
        fr_valid_rows = sum(m.get('valid_data_rows', 0) for m in fr_metrics.values())
        print(f"{'Valid Data Rows':<35} {en_valid_rows:<25} {fr_valid_rows:<25} {get_variance_str(en_valid_rows, fr_valid_rows):<20}")

        en_empty_rows = sum(m.get('empty_rows', 0) for m in en_metrics.values())
        fr_empty_rows = sum(m.get('empty_rows', 0) for m in fr_metrics.values())
        print(f"{'Empty Rows':<35} {en_empty_rows:<25} {fr_empty_rows:<25} {get_variance_str(en_empty_rows, fr_empty_rows):<20}")

        en_pub_rows = sum(m.get('publishing_rows', 0) for m in en_metrics.values())
        fr_pub_rows = sum(m.get('publishing_rows', 0) for m in fr_metrics.values())
        print(f"{'Publishing Rows':<35} {en_pub_rows:<25} {fr_pub_rows:<25} {get_variance_str(en_pub_rows, fr_pub_rows):<20}")

        en_total_trim = sum(len(cols) for cols in en_trim_cols.values())
        fr_total_trim = sum(len(cols) for cols in fr_trim_cols.values())
        print(f"{'Trim Columns':<35} {en_total_trim:<25} {fr_total_trim:<25} {get_variance_str(en_total_trim, fr_total_trim):<20}")

        en_total_coverage = (en_valid_rows / en_total_rows * 100) if en_total_rows > 0 else 0
        fr_total_coverage = (fr_valid_rows / fr_total_rows * 100) if fr_total_rows > 0 else 0
        en_cov_str = f"{en_total_coverage:.1f}%"
        fr_cov_str = f"{fr_total_coverage:.1f}%"
        cov_diff = round(en_total_coverage - fr_total_coverage, 1)
        coverage_var = "[OK]" if cov_diff == 0 else f"+{cov_diff}%" if cov_diff > 0 else f"{cov_diff}%"
        print(f"{'Coverage %':<35} {en_cov_str:<25} {fr_cov_str:<25} {coverage_var:<20}")

print("\n" + "=" * 120)
print("[OK] METADATA EXTRACTION COMPLETE")
print("=" * 120 + "\n")
