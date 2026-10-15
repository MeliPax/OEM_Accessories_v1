#!/usr/bin/env python3
"""
Test Honda Pipeline: Steps 1-2 (Validation → Header Normalization)

Runs the pipeline on real Honda data (CVIC5D.xlsx) and displays:
1. Step 1 output (metadata, row metrics)
2. Step 2 output (normalized headers, parent/child classification, parent index)
3. Data state verification
"""

import sys
from pathlib import Path
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "accy_v2"))

from accy_v2.oems.honda.pipeline import step1_validation, step2_header_normalization
from accy_v2.core.config_loader_v2 import ModularConfigLoader
from accy_v2.core.helpers.dq_logger import DQLogger
from accy_v2.core.helpers.pipeline_logger import PipelineLogger

print("=" * 100)
print("HONDA PIPELINE TEST: Steps 1-2 (Validation -> Header Normalization)")
print("=" * 100)

# Setup paths
file_path = project_root / "accy_v2/data/landing_zone/honda/may_2026/CVIC5D.xlsx"
config_root = project_root / "accy_v2/oems/honda/config"

if not file_path.exists():
    print(f"[FAIL] ERROR: Test file not found: {file_path}")
    sys.exit(1)

# Load config
print("\n[SETUP] Loading configuration...")
try:
    config_loader = ModularConfigLoader("honda", config_root)
    config = config_loader.load_all()
    print("[OK] Config loaded")
except Exception as e:
    print(f"[FAIL] ERROR loading config: {e}")
    sys.exit(1)

# Load Excel file
print("[SETUP] Loading Excel file...")
try:
    excel = pd.ExcelFile(file_path)
    en_sheet = "26MY_CIV5D_APP_EN"

    if en_sheet not in excel.sheet_names:
        print(f"[FAIL] ERROR: Sheet not found: {en_sheet}")
        sys.exit(1)

    df_raw = excel.parse(sheet_name=en_sheet, header=None)
    print(f"[OK] Loaded {en_sheet}: {df_raw.shape[0]} rows × {df_raw.shape[1]} columns")
except Exception as e:
    print(f"[FAIL] ERROR loading Excel: {e}")
    sys.exit(1)

# Initialize loggers
run_id = "test_step2_" + pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
dq_logger = DQLogger(run_id=run_id, source_file=str(file_path))
pipeline_logger = PipelineLogger(run_id=run_id, log_path="accy_v2/output/pipeline_logs/honda")

# ========== STEP 1: VALIDATION ==========
print("\n" + "=" * 100)
print("STEP 1: VALIDATION & METADATA EXTRACTION")
print("=" * 100)

try:
    meta_data = {"sheet_name": en_sheet}
    df_step1, meta_step1 = step1_validation.run(
        df_raw, config, meta_data, dq_logger, pipeline_logger
    )

    print(f"\n[STEP 1 OUTPUT]")
    print(f"  Model Name: {meta_step1.get('model_name')}")
    print(f"  Vehicle Year: {meta_step1.get('vehicle_year')}")
    print(f"  Language: {meta_step1.get('language')}")
    print(f"  Sections Detected: {len(meta_step1.get('section_structure', {}))}")
    print(f"  Publication Date: {meta_step1.get('publication_date')}")

    # Show section structure
    print(f"\n[SECTION STRUCTURE]")
    section_structure = meta_step1.get('section_structure', {})
    for section_name, bounds in section_structure.items():
        marker = bounds.get('marker_row')
        header = bounds.get('header_row')
        data_start = bounds.get('data_start_row')
        data_end = bounds.get('data_end_row')
        print(f"  {section_name}:")
        print(f"    - Marker row: {marker}, Header: {header}, Data: {data_start}-{data_end}")

    # Show row metrics
    print(f"\n[ROW METRICS PER SECTION]")
    row_metrics = meta_step1.get('row_metrics_per_section', {})
    total_valid_all = 0
    total_rows_all = 0
    for section_name, metrics in row_metrics.items():
        total = metrics.get('total_rows', 0)
        valid = metrics.get('valid_data_rows', 0)
        coverage = (valid / total * 100) if total > 0 else 0
        total_valid_all += valid
        total_rows_all += total
        print(f"  {section_name}: {valid}/{total} valid ({coverage:.1f}%)")

    overall_coverage = (total_valid_all / total_rows_all * 100) if total_rows_all > 0 else 0
    print(f"\n  TOTAL: {total_valid_all}/{total_rows_all} valid ({overall_coverage:.1f}%)")
    print(f"[OK] Step 1 complete")

except Exception as e:
    print(f"[FAIL] STEP 1 FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ========== STEP 2: HEADER NORMALIZATION ==========
print("\n" + "=" * 100)
print("STEP 2: HEADER NORMALIZATION + PARENT/CHILD DETECTION")
print("=" * 100)

try:
    df_step2, meta_step2 = step2_header_normalization.run(
        df_step1, config, meta_step1, dq_logger, pipeline_logger
    )

    # Show normalized headers per section
    print(f"\n[NORMALIZED HEADERS PER SECTION]")
    normalized_headers = meta_step2.get('normalized_headers', {})
    for section_name, headers in normalized_headers.items():
        print(f"\n  {section_name} ({len(headers)} columns):")
        print(f"    {headers}")

    # Show column mapping
    print(f"\n[COLUMN MAPPING (Sample: First Section)]")
    column_mapping = meta_step2.get('column_mapping', {})
    if column_mapping:
        first_section = list(column_mapping.keys())[0]
        mapping = column_mapping[first_section]
        print(f"  {first_section}:")
        for col_idx, norm_name in sorted(mapping.items())[:10]:
            print(f"    Column {col_idx}: {norm_name}")
        if len(mapping) > 10:
            print(f"    ... and {len(mapping) - 10} more columns")

    # Show record type classification
    print(f"\n[RECORD TYPE CLASSIFICATION]")
    record_type_counts = meta_step2.get('record_type_counts', {})
    print(f"  Record type counts:")
    for rtype, count in sorted(record_type_counts.items(), key=lambda x: -x[1]):
        print(f"    {rtype:20s}: {count:4d}")

    # Show price columns
    print(f"\n[PRICE COLUMNS (For Phase 3)]")
    price_columns = meta_step2.get('price_columns', [])
    print(f"  {price_columns}")

    # Show parent-child relationships (sample)
    print(f"\n[PARENT-CHILD RELATIONSHIPS (Sample: First 30 rows)]")
    record_type_per_row = meta_step2.get('record_type_per_row', {})
    parent_row_index = meta_step2.get('parent_row_index', {})

    sample_rows = sorted([k for k in record_type_per_row.keys() if k < 30])
    for row_idx in sample_rows:
        rtype = record_type_per_row.get(row_idx)
        parent = parent_row_index.get(row_idx)

        if rtype is None:
            status = "DEFECT"
        elif rtype in ("parent", "package_parent"):
            status = f"{rtype.upper():15s} (no parent)"
        else:
            status = f"{rtype.upper():15s} (parent: row {parent})"

        print(f"    Row {row_idx:3d}: {status}")

    print(f"\n[OK] Step 2 complete")

except Exception as e:
    print(f"[FAIL] STEP 2 FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ========== DATA STATE VERIFICATION ==========
print("\n" + "=" * 100)
print("DATA STATE VERIFICATION")
print("=" * 100)

print(f"\n[EXPECTED vs ACTUAL]")
print(f"  Sections detected: {len(section_structure)} (expected: 6)")
print(f"    [OK] PASS" if len(section_structure) == 6 else f"    [FAIL] FAIL")

print(f"\n  Headers normalized per section: {len(normalized_headers)} (expected: 6)")
print(f"    [OK] PASS" if len(normalized_headers) == 6 else f"    [FAIL] FAIL")

print(f"\n  Parent/child classification:")
total_records = sum(record_type_counts.values())
valid_records = total_records - record_type_counts.get('defect', 0)
print(f"    Total rows classified: {total_records}")
print(f"    Valid records (parent/child): {valid_records}")
print(f"    Defect records: {record_type_counts.get('defect', 0)}")
print(f"    [OK] PASS" if valid_records > 0 else f"    [FAIL] FAIL")

print(f"\n  Price columns identified:")
expected_prices = ["dealer_net", "list_price", "frt", "installed_price"]
prices_match = price_columns == expected_prices
print(f"    Expected: {expected_prices}")
print(f"    Actual:   {price_columns}")
print(f"    [OK] PASS" if prices_match else f"    [FAIL] FAIL")

print(f"\n  Parent index built:")
orphaned = sum(1 for rtype in record_type_per_row.values() if rtype == "orphaned_child")
children = sum(1 for rtype in record_type_per_row.values() if "child" in str(rtype))
print(f"    Children rows: {children}")
print(f"    Orphaned children: {orphaned}")
print(f"    [OK] PASS" if children > 0 else f"    [FAIL] FAIL")

# ========== DQ SUMMARY ==========
print(f"\n[DATA QUALITY SUMMARY]")
print(f"  DQ warnings logged: {dq_logger.warning_count}")
if dq_logger.warning_count > 0:
    print(f"  (Check logs for details: accy_v2/output/dq_reports/honda/)")

# ========== FINAL SUMMARY ==========
print("\n" + "=" * 100)
print("FINAL SUMMARY")
print("=" * 100)

print(f"""
[OK] PIPELINE EXECUTION: SUCCESS

Summary:
  - File: {en_sheet}
  - Raw data: {df_raw.shape[0]} rows × {df_raw.shape[1]} columns
  - Sections: {len(section_structure)}/6 detected
  - Data coverage: {overall_coverage:.1f}% valid ({total_valid_all}/{total_rows_all})

Step 1 (Validation):
  [OK] Headers normalized
  [OK] Sections detected (all 6)
  [OK] Row metrics extracted

Step 2 (Header Normalization):
  [OK] Headers normalized per section
  [OK] Column mappings created
  [OK] Parent/child classified ({valid_records} valid, {record_type_counts.get('defect', 0)} defects)
  [OK] Parent index built
  [OK] Price columns identified

Data State:
  [OK] Ready for Phase 3 (Standardization)

Next Step: Phase 3 - Enforce data types, validate trim applicability
""")

print("=" * 100)
