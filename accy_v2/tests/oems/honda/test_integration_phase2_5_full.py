#!/usr/bin/env python3
"""
Full Integration Test: Honda Pipeline Steps 1-2.5
Runs the complete pipeline on real Honda data and reports results.

Run: python test_integration_phase2_5_full.py
"""

import pandas as pd
from pathlib import Path
import sys
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from accy_v2.oems.honda.pipeline import step1_validation, step2_header_normalization, step2_string_standardization
from accy_v2.core.helpers.dq_logger import DQLogger
from accy_v2.core.helpers.pipeline_logger import PipelineLogger
from accy_v2.core.config_loader_v2 import ModularConfigLoader


def print_section(title):
    """Print section header"""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def run_full_integration_test():
    """Run full pipeline integration test"""

    print_section("HONDA PIPELINE: FULL INTEGRATION TEST (Steps 1-2.5)")
    print(f"Test Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Load real data
    file_path = project_root / "accy_v2" / "data" / "landing_zone" / "honda" / "may_2026" / "CVIC5D.xlsx"

    if not file_path.exists():
        print(f"ERROR: Test file not found: {file_path}")
        return False

    print(f"Data Source: {file_path.name}")

    # Load config
    config_root = project_root / "accy_v2" / "oems" / "honda" / "config"
    config_loader = ModularConfigLoader("honda", config_root)
    config = config_loader.load_all()
    print(f"Config Loaded: {len(config)} sections\n")

    # Setup logging
    dq_logger = DQLogger(run_id="integration_test", source_file=str(file_path))
    pipeline_logger = PipelineLogger(
        run_id="integration_test",
        log_path="accy_v2/output/pipeline_logs/honda"
    )

    # Load EN sheet
    excel = pd.ExcelFile(file_path)
    en_sheet = "26MY_CIV5D_APP_EN"
    df_raw = excel.parse(sheet_name=en_sheet, header=None)

    print(f"Sheet: {en_sheet}")
    print(f"Raw Data Shape: {df_raw.shape} (rows x columns)\n")

    # ========================================================================
    # STEP 1: VALIDATION
    # ========================================================================
    print_section("STEP 1: VALIDATION")

    meta_data = {"sheet_name": en_sheet}

    try:
        df_step1, meta_step1 = step1_validation.run(
            df_raw.copy(), config, meta_data, dq_logger, pipeline_logger
        )

        print(f"[PASS] Step 1 Complete\n")
        print(f"  Model: {meta_step1.get('model_name', 'N/A')}")
        print(f"  Year: {meta_step1.get('vehicle_year', 'N/A')}")
        print(f"  Language: {meta_step1.get('language', 'N/A')}")
        print(f"  Sections Detected: {meta_step1.get('sections_detected', 0)}")
        print(f"  Output Shape: {df_step1.shape}")

        if 'row_metrics_per_section' in meta_step1:
            print(f"\n  Section Details:")
            for section, metrics in meta_step1['row_metrics_per_section'].items():
                valid = metrics.get('valid_data_rows', 0)
                total = metrics.get('total_rows', 0)
                print(f"    - {section}: {valid}/{total} valid rows")

    except Exception as e:
        print(f"[FAIL] Step 1 FAILED: {e}")
        return False

    # ========================================================================
    # STEP 2: HEADER NORMALIZATION
    # ========================================================================
    print_section("STEP 2: HEADER NORMALIZATION")

    try:
        df_step2, meta_step2 = step2_header_normalization.run(
            df_step1.copy(), config, meta_step1, dq_logger, pipeline_logger
        )

        print(f"[PASS] Step 2 Complete\n")
        print(f"  Headers Normalized: {len(meta_step2.get('normalized_headers', {}))}")
        print(f"  Output Shape: {df_step2.shape}")

        if 'record_type_counts' in meta_step2:
            print(f"\n  Record Classification:")
            for record_type, count in meta_step2['record_type_counts'].items():
                print(f"    - {record_type}: {count}")

        if 'parent_row_index' in meta_step2:
            print(f"\n  Parent-Child Relationships: {len(meta_step2['parent_row_index'])} rows mapped")

    except Exception as e:
        print(f"[FAIL] Step 2 FAILED: {e}")
        return False

    # ========================================================================
    # STEP 2.5: STRING STANDARDIZATION
    # ========================================================================
    print_section("STEP 2.5: STRING STANDARDIZATION")

    try:
        df_step2_5 = step2_string_standardization.run(
            df_step2.copy(), config, meta_step2, dq_logger, pipeline_logger
        )

        print(f"[PASS] Step 2.5 Complete\n")
        print(f"  Operations Applied:")
        print(f"    1. normalize_unicode() - Smart quotes -> ASCII")
        print(f"    2. remove_newlines() - Literal \\n -> spaces")
        print(f"    3. split_composite() - 'part1 or part2' -> primary + notes")
        print(f"    4. normalize_trim_markers() - Markers -> canonical states")
        print(f"\n  Output Shape: {df_step2_5.shape}")

    except Exception as e:
        print(f"[FAIL] Step 2.5 FAILED: {e}")
        return False

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print_section("INTEGRATION TEST SUMMARY")

    print(f"Status: [PASS] ALL STEPS PASSED\n")

    print(f"Data Flow:")
    print(f"  Raw Data:        {df_raw.shape}")
    print(f"  After Step 1:    {df_step1.shape}")
    print(f"  After Step 2:    {df_step2.shape}")
    print(f"  After Step 2.5:  {df_step2_5.shape}")

    print(f"\nMetadata Captured:")
    print(f"  Model: {meta_step1.get('model_name')}")
    print(f"  Year: {meta_step1.get('vehicle_year')}")
    print(f"  Language: {meta_step1.get('language')}")
    print(f"  Sections: {meta_step1.get('sections_detected')}")
    print(f"  Total Records: {sum(meta_step2.get('record_type_counts', {}).values())}")

    print(f"\nDQ Logger:")
    print(f"  Warnings Logged: {dq_logger.warning_count}")

    print(f"\nLog Files:")
    log_dir = Path("accy_v2/output/pipeline_logs/honda")
    if log_dir.exists():
        log_files = sorted(log_dir.glob("pipeline_integration_test_*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
        if log_files:
            print(f"  Latest: {log_files[0].name}")

    print(f"\nTest Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n{'='*80}")

    return True


if __name__ == "__main__":
    success = run_full_integration_test()
    sys.exit(0 if success else 1)
