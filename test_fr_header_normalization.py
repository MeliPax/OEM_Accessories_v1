#!/usr/bin/env python3
"""
Test: FR Header Normalization
Focus on verifying that French headers normalize correctly to canonical names
"""

import sys
import pandas as pd
import logging
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path.cwd() / 'accy_v2'))

from accy_v2.oems.honda.pipeline import step1_validation, step2_header_normalization
from accy_v2.core.config_loader_v2 import ModularConfigLoader
from accy_v2.core.helpers.dq_logger import DQLogger
from accy_v2.core.helpers.pipeline_logger import PipelineLogger

# Silence verbose loggers
logging.getLogger('accy_v2').setLevel(logging.WARNING)

file_path = Path('accy_v2/data/landing_zone/honda/may_2026/CVIC5D.xlsx')
config_root = Path('accy_v2/oems/honda/config')

print("=" * 100)
print("TEST: FR HEADER NORMALIZATION & BREAKING POINTS")
print("=" * 100)
print()

# Load config
config = ModularConfigLoader('honda', config_root).load_all()
print(f"[INFO] Config loaded. Upstream columns: {list(config['schemas']['upstream']['columns'].keys())}")
print()

# Test both sheets
for sheet_name in ['26MY_CIV5D_APP_EN', '26MY_CIV5D_APP_FR']:
    print(f"\n{'='*100}")
    print(f"SHEET: {sheet_name}")
    print(f"{'='*100}")

    try:
        # Load sheet (use openpyxl in read-only mode to avoid lock issues)
        df = pd.read_excel(file_path, sheet_name=sheet_name, header=None, engine='openpyxl')
        print(f"[OK] Sheet loaded: {df.shape[0]} rows × {df.shape[1]} columns")

        # Setup loggers
        run_id = f'test_header_{sheet_name}'
        dq_logger = DQLogger(run_id=run_id, source_file=str(file_path))
        pipeline_logger = PipelineLogger(run_id=run_id, log_path='accy_v2/output/pipeline_logs/honda')

        # Minimal metadata
        meta_data = {
            'sheet_name': sheet_name,
            'language': 'FR' if 'FR' in sheet_name else 'EN',
            'model_name': 'Test Model',
            'vehicle_year': 2026,
            'section_structure': {}
        }

        # Run Step 1 to detect sections
        print(f"[STEP 1] Running section detection...")
        try:
            df_s1, meta_s1 = step1_validation.run(df, config, meta_data, dq_logger, pipeline_logger)
            print(f"[OK] Step 1 complete. Sections found: {len(meta_s1.get('section_structure', {}))}")
        except Exception as e:
            print(f"[ERROR] Step 1 failed: {e}")
            import traceback
            traceback.print_exc()
            continue

        # Run Step 2 to normalize headers
        print(f"[STEP 2] Running header normalization...")
        try:
            df_s2, meta_s2 = step2_header_normalization.run(df_s1, config, meta_s1, dq_logger, pipeline_logger)
            print(f"[OK] Step 2 complete")
        except Exception as e:
            print(f"[ERROR] Step 2 failed: {e}")
            import traceback
            traceback.print_exc()
            continue

        # Analyze headers
        print(f"\n[HEADER ANALYSIS]")
        normalized_headers = meta_s2.get('normalized_headers', {})

        # Check all sections
        for section_name, norm_header_list in normalized_headers.items():
            print(f"\n  Section: {section_name}")

            # Show first 10 columns
            for col_idx, norm_name in enumerate(norm_header_list[:10]):
                if norm_name.startswith('unnamed'):
                    marker = ' (unnamed/trim)'
                elif norm_name in ['description', 'part_number', 'dealer_net', 'list_price', 'frt', 'installed_price', 'application', 'comments']:
                    marker = ' ✓ (canonical)'
                else:
                    marker = f' (CUSTOM: "{norm_name}")'

                print(f"    Col {col_idx}: {norm_name}{marker}")

        # Check for missing canonical names
        print(f"\n[CANONICAL NAMES CHECK]")
        required_canonical = ['description', 'part_number', 'dealer_net', 'list_price', 'frt', 'installed_price']

        for section_name, norm_header_list in normalized_headers.items():
            missing = []
            for req in required_canonical:
                if req not in norm_header_list:
                    missing.append(req)

            if missing:
                print(f"  ⚠️  Section '{section_name}': MISSING {missing}")
            else:
                print(f"  ✓ Section '{section_name}': All required canonical names present")

        # Show record type counts
        print(f"\n[RECORD TYPE COUNTS]")
        record_type_counts = meta_s2.get('record_type_counts', {})
        for rtype, count in sorted(record_type_counts.items(), key=lambda x: -x[1]):
            print(f"  {rtype:20s}: {count:3d}")

        # Check for defects
        defect_count = record_type_counts.get('defect', 0)
        if defect_count > 50:
            print(f"\n[WARNING] High defect count ({defect_count}). This suggests header normalization may be failing.")
        else:
            print(f"\n[OK] Defect count is reasonable ({defect_count}).")

    except Exception as e:
        print(f"[ERROR] Failed to process {sheet_name}: {e}")
        import traceback
        traceback.print_exc()

print()
print("=" * 100)
print("TEST COMPLETE")
print("=" * 100)
