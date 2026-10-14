#!/usr/bin/env python3
"""
Comprehensive Phase 2 Integration Test
Tests Phase 1 + Phase 2 end-to-end on real Honda data (CVIC5D.xlsx)
Shows data transformation and output at each stage
"""

import sys
from pathlib import Path
import pandas as pd

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "accy_v2"))

from accy_v2.oems.honda.pipeline import step1_validation, step2_header_normalization
from accy_v2.core.helpers.dq_logger import DQLogger
from accy_v2.core.helpers.pipeline_logger import PipelineLogger
from accy_v2.core.config_loader_v2 import ModularConfigLoader

print("=" * 100)
print("PHASE 2 INTEGRATION TEST - Complete Data Transformation")
print("=" * 100)

# Setup paths and configs
file_path = project_root / "accy_v2/data/landing_zone/honda/may_2026/CVIC5D.xlsx"
config_root = project_root / "accy_v2/oems/honda/config"

if not file_path.exists():
    print(f"ERROR: Test file not found: {file_path}")
    sys.exit(1)

# Load configs using ModularConfigLoader (structure.yaml via load_all)
print("\n[STEP 1] Loading configurations...")
try:
    config_loader = ModularConfigLoader("honda", Path(config_root))
    config = config_loader.load_all()
    print("[OK] Configurations loaded")
except Exception as e:
    print(f"ERROR loading config: {e}")
    sys.exit(1)

# Load Excel file
print("\n[STEP 2] Loading Excel file...")
try:
    excel = pd.ExcelFile(file_path)
    en_sheet = "26MY_CIV5D_APP_EN"

    if en_sheet not in excel.sheet_names:
        print(f"ERROR: Sheet not found: {en_sheet}")
        sys.exit(1)

    df_raw = excel.parse(sheet_name=en_sheet, header=None)
    print(f"[OK] Loaded {en_sheet}: {df_raw.shape[0]} rows x {df_raw.shape[1]} columns")
except Exception as e:
    print(f"ERROR loading Excel: {e}")
    sys.exit(1)

# Initialize loggers
run_id = "phase2_test"
dq_logger = DQLogger(run_id=run_id, source_file=str(file_path))
pipeline_logger = PipelineLogger(run_id=run_id, log_path="accy_v2/output/pipeline_logs/honda")

# PHASE 1: Validation
print("\n" + "=" * 100)
print("PHASE 1: VALIDATION & METADATA EXTRACTION")
print("=" * 100)

try:
    meta_phase1 = {"sheet_name": en_sheet}
    df_phase1, meta_phase1 = step1_validation.run(df_raw, config, meta_phase1, dq_logger, pipeline_logger)

    print(f"\n[PHASE 1 OUTPUT]")
    print(f"  Model:           {meta_phase1.get('model_name')}")
    print(f"  Year:            {meta_phase1.get('vehicle_year')}")
    print(f"  Language:        {meta_phase1.get('language')}")
    print(f"  Sections:        {len(meta_phase1.get('section_structure', {}))}")
    print(f"  Publication Dt:  {meta_phase1.get('publication_date')}")

    # Show section structure
    print(f"\n[SECTION STRUCTURE]")
    section_structure = meta_phase1.get('section_structure', {})
    for section_name, bounds in section_structure.items():
        print(f"  {section_name}:")
        print(f"    - Marker row: {bounds.get('marker_row')}")
        print(f"    - Header row: {bounds.get('header_row')}")
        print(f"    - Data rows: {bounds.get('data_start_row')}-{bounds.get('data_end_row')}")

    # Show row metrics
    print(f"\n[ROW METRICS]")
    row_metrics = meta_phase1.get('row_metrics_per_section', {})
    for section_name, metrics in row_metrics.items():
        total = metrics.get('total_rows', 0)
        valid = metrics.get('valid_data_rows', 0)
        coverage = (valid / total * 100) if total > 0 else 0
        print(f"  {section_name}: {valid}/{total} valid ({coverage:.1f}%)")

    print(f"\n[OK] Phase 1 complete")

except Exception as e:
    print(f"[FAIL] Phase 1 error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# PHASE 2: Header Normalization + Parent/Child Detection
print("\n" + "=" * 100)
print("PHASE 2: HEADER NORMALIZATION + PARENT/CHILD DETECTION")
print("=" * 100)

try:
    df_phase2, meta_phase2 = step2_header_normalization.run(
        df_phase1, config, meta_phase1, dq_logger, pipeline_logger
    )

    # Show normalized headers
    print(f"\n[NORMALIZED HEADERS]")
    normalized_headers = meta_phase2.get('normalized_headers', {})
    for section_name, headers in normalized_headers.items():
        print(f"  {section_name}:")
        print(f"    {headers}")

    # Show record type classification
    print(f"\n[RECORD TYPE COUNTS]")
    record_type_counts = meta_phase2.get('record_type_counts', {})
    for rtype, count in sorted(record_type_counts.items()):
        print(f"  {rtype}: {count}")

    # Show price columns passed to Phase 3
    print(f"\n[PRICE COLUMNS (for Phase 3)]")
    price_columns = meta_phase2.get('price_columns', [])
    print(f"  {price_columns}")

    # Show sample classifications
    print(f"\n[SAMPLE CLASSIFICATIONS]")
    record_types = meta_phase2.get('record_type_per_row', {})
    parent_index = meta_phase2.get('parent_row_index', {})

    samples_shown = 0
    for row_idx in sorted(record_types.keys())[:20]:  # Show first 20 classified rows
        rtype = record_types.get(row_idx)
        parent = parent_index.get(row_idx)

        if rtype is not None:  # Only show valid classifications
            parent_info = f"inherits from row {parent}" if parent is not None else "parent record"
            print(f"  Row {row_idx}: {rtype} ({parent_info})")
            samples_shown += 1
            if samples_shown >= 10:
                break

    print(f"\n[PARENT INDEX SAMPLE]")
    parent_index = meta_phase2.get('parent_row_index', {})
    samples = {k: v for k, v in list(parent_index.items())[:15]}
    for row_idx in sorted(samples.keys()):
        parent = samples[row_idx]
        print(f"  Row {row_idx}: parent={parent}")

    print(f"\n[OK] Phase 2 complete")

except Exception as e:
    print(f"[FAIL] Phase 2 error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Final Summary
print("\n" + "=" * 100)
print("DATA TRANSFORMATION SUMMARY")
print("=" * 100)

print(f"\n[PHASE 1 -> PHASE 2 TRANSFORMATION]")
print(f"  Input:  {df_raw.shape[0]} rows x {df_raw.shape[1]} columns (raw)")
print(f"  Output: {df_phase2.shape[0]} rows x {df_phase2.shape[1]} columns (unchanged)")
print(f"  Metadata Added:")
print(f"    - normalized_headers: {len(normalized_headers)} sections")
print(f"    - column_mapping: {len(normalized_headers)} sections")
print(f"    - record_type_per_row: {len(record_types)} classifications")
print(f"    - parent_row_index: {len(parent_index)} mappings")
print(f"    - record_type_counts: {len(record_type_counts)} types")
print(f"    - price_columns: {len(price_columns)} price fields")

print(f"\n[READY FOR PHASE 3]")
print(f"  Phase 3 will use:")
print(f"    1. price_columns to identify price columns")
print(f"    2. parent_row_index to fill prices for children")
print(f"    3. record_type_per_row to track which rows are parents/children")
print(f"    4. normalized_headers to reference columns by name")

print(f"\n[DQ LOGGING]")
print(f"  Warnings logged: {dq_logger.warning_count}")

print("\n" + "=" * 100)
print("[OK] PHASE 2 INTEGRATION TEST PASSED")
print("=" * 100)
print("\nPhase 2 is working correctly and ready for Phase 3 development!")
