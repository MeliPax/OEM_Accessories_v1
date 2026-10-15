#!/usr/bin/env python3
"""
Test Honda Pipeline: EN and FR data samples (top 20 rows)
Verify that parent/child classification works correctly after bug fix
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

print("=" * 120)
print("HONDA PIPELINE TEST: EN and FR Data Samples (Top 20 rows per sheet)")
print("=" * 120)

# Setup paths
file_path = project_root / "accy_v2/data/landing_zone/honda/may_2026/CVIC5D.xlsx"
config_root = project_root / "accy_v2/oems/honda/config"

if not file_path.exists():
    print(f"[FAIL] ERROR: Test file not found: {file_path}")
    sys.exit(1)

# Load config
config_loader = ModularConfigLoader("honda", config_root)
config = config_loader.load_all()

# Load Excel file
excel = pd.ExcelFile(file_path)
sheets_to_test = ["26MY_CIV5D_APP_EN", "26MY_CIV5D_APP_FR"]

for sheet_name in sheets_to_test:
    if sheet_name not in excel.sheet_names:
        print(f"\n[SKIP] Sheet not found: {sheet_name}")
        continue

    print(f"\n" + "=" * 120)
    print(f"SHEET: {sheet_name}")
    print("=" * 120)

    df_raw = excel.parse(sheet_name=sheet_name, header=None)
    print(f"\nRaw data: {df_raw.shape[0]} rows × {df_raw.shape[1]} columns")

    # Initialize loggers
    run_id = f"test_en_fr_{sheet_name.split('_')[-1]}" + pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    dq_logger = DQLogger(run_id=run_id, source_file=str(file_path))
    pipeline_logger = PipelineLogger(run_id=run_id, log_path="accy_v2/output/pipeline_logs/honda")

    # ========== STEP 1: VALIDATION ==========
    try:
        meta_data = {"sheet_name": sheet_name}
        df_step1, meta_step1 = step1_validation.run(
            df_raw, config, meta_data, dq_logger, pipeline_logger
        )
        print(f"[OK] Step 1 (Validation) complete")
    except Exception as e:
        print(f"[FAIL] Step 1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        continue

    # ========== STEP 2: HEADER NORMALIZATION ==========
    try:
        df_step2, meta_step2 = step2_header_normalization.run(
            df_step1, config, meta_step1, dq_logger, pipeline_logger
        )
        print(f"[OK] Step 2 (Header Normalization) complete")
    except Exception as e:
        print(f"[FAIL] Step 2 FAILED: {e}")
        import traceback
        traceback.print_exc()
        continue

    # ========== ANALYSIS ==========
    record_type_per_row = meta_step2.get('record_type_per_row', {})
    record_type_counts = meta_step2.get('record_type_counts', {})
    parent_row_index = meta_step2.get('parent_row_index', {})

    print(f"\n[RECORD TYPE SUMMARY]")
    print(f"  Total rows classified: {sum(record_type_counts.values())}")
    for rtype, count in sorted(record_type_counts.items(), key=lambda x: -x[1]):
        pct = (count / sum(record_type_counts.values()) * 100) if sum(record_type_counts.values()) > 0 else 0
        print(f"    {rtype:20s}: {count:4d} ({pct:5.1f}%)")

    # ========== SAMPLE DATA (TOP 20) ==========
    print(f"\n[TOP 20 ROWS CLASSIFICATION & DATA]")
    print(f"{'Row':>4} | {'Type':>15} | {'Parent':>6} | {'Description':>25} | {'Part Number':>15} | {'Prices (D|L|F|I)':>35}")
    print(f"{'-'*4}-+-{'-'*15}-+-{'-'*6}-+-{'-'*25}-+-{'-'*15}-+-{'-'*35}")

    sample_rows = sorted([k for k in record_type_per_row.keys() if k < 20])
    for row_idx in sample_rows:
        rtype = record_type_per_row.get(row_idx)
        parent = parent_row_index.get(row_idx)

        # Get data from df_step1 (before normalization)
        row = df_step1.iloc[row_idx]

        # Extract description and part number (cols 2 and 3 are typical positions)
        desc = str(row.iloc[2])[:25] if pd.notna(row.iloc[2]) else "[NULL]"
        part = str(row.iloc[3])[:15] if pd.notna(row.iloc[3]) else "[NULL]"

        # Extract prices (typically cols 4-7)
        p_dealer = str(row.iloc[4])[:5] if pd.notna(row.iloc[4]) else "N"
        p_list = str(row.iloc[5])[:5] if pd.notna(row.iloc[5]) else "N"
        p_frt = str(row.iloc[6])[:5] if pd.notna(row.iloc[6]) else "N"
        p_inst = str(row.iloc[7])[:5] if pd.notna(row.iloc[7]) else "N"
        prices = f"{p_dealer}|{p_list}|{p_frt}|{p_inst}"

        if rtype is None:
            status = "DEFECT"
            parent_str = "-"
        elif rtype in ("parent", "package_parent"):
            status = rtype.upper()
            parent_str = "-"
        else:
            status = rtype.upper()
            parent_str = str(parent) if parent is not None else "-"

        print(f"{row_idx:4d} | {status:>15} | {parent_str:>6} | {desc:>25} | {part:>15} | {prices:>35}")

    print(f"\n[DQ SUMMARY]")
    print(f"  DQ warnings logged: {dq_logger.warning_count}")

print("\n" + "=" * 120)
print("TEST COMPLETE")
print("=" * 120)
