#!/usr/bin/env python3
"""
Test: Part Number Fallback Logic
Verify that parent records with empty part number column use column 1 fallback
"""

import sys, pandas as pd
import logging
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path.cwd() / 'accy_v2'))

from accy_v2.oems.honda.pipeline import step1_validation, step2_header_normalization
from accy_v2.core.config_loader_v2 import ModularConfigLoader
from accy_v2.core.helpers.dq_logger import DQLogger
from accy_v2.core.helpers.pipeline_logger import PipelineLogger

# Silence some loggers
logging.getLogger('accy_v2').setLevel(logging.WARNING)

file_path = Path('accy_v2/data/landing_zone/honda/may_2026/CVIC5D.xlsx')
config_root = Path('accy_v2/oems/honda/config')

config = ModularConfigLoader('honda', config_root).load_all()

print("=" * 100)
print("TEST: PART NUMBER FALLBACK LOGIC")
print("=" * 100)
print()

# Create a minimal test dataframe
test_data = {
    0: ['', '', 'Description', 'Part Number', 'Dealer Net', 'List Price', 'FRT', 'Installed Price', 'Application', '', '', '', '', '', '', '', 'Comments'],
    1: ['', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', ''],  # Trim subheader
    # Parent with part number filled (normal case)
    2: ['', '08LXX-E01-XXXX', 'Sedan Package', '123456', '100', '150', '50', '200', 'L', '', '', '', '', '', '', '', ''],
    # Parent with EMPTY part number column but col1 has fallback (test case)
    3: ['', '08LXX-E02-XXXX', 'Coupe Package', '', '100', '150', '50', '200', 'L', '', '', '', '', '', '', '', ''],
    # Subsection label (should not be affected)
    4: ['', '08LXX-E03-XXXX', 'Roof Attachments', '', '', '', '', '', '', '', '', '', '', '', '', '', ''],
    # Child with prices empty
    5: ['', '08LXX-E04-XXXX', 'Chrome Kit', '234567', '', '', '', '', 'L', '', '', '', '', '', '', '', ''],
}

df_test = pd.DataFrame(test_data).T
df_test.columns = range(len(df_test.columns))

print("[DATA] Test data:")
print("  Row 2: Normal parent (col1 + col3 both filled)")
print("  Row 3: Parent with fallback (col1 filled, col3 EMPTY) <- TEST CASE")
print("  Row 4: Subsection label (col1 + desc, no col3)")
print("  Row 5: Child record (col1 + desc, empty prices)")
print()

# Minimal metadata
meta_data = {
    'sheet_name': '26MY_CIV5D_APP_EN',
    'language': 'EN',
    'model_name': 'Civic Hatch',
    'vehicle_year': 2026,
    'section_structure': {
        'Test Section': {
            'marker_row': 0,
            'header_row': 0,
            'data_start_row': 2,
            'data_end_row': 5
        }
    }
}

# Setup loggers
run_id = 'test_fallback'
dq_logger = DQLogger(run_id=run_id, source_file=str(file_path))
pipeline_logger = PipelineLogger(run_id=run_id, log_path='accy_v2/output/pipeline_logs/honda')

# Run Step 2
print("[STEP 2] Running header normalization with fallback logic...")
try:
    df_output, meta_output = step2_header_normalization.run(df_test, config, meta_data, dq_logger, pipeline_logger)
    print("[OK] Step 2 completed")
except Exception as e:
    print(f"[ERROR] Step 2 failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("=" * 100)
print("RESULTS")
print("=" * 100)
print()

record_types = meta_output.get('record_type_per_row', {})
column_mapping = meta_output.get('column_mapping', {})

print("[CLASSIFICATION RESULTS]")
for row_idx in sorted([2, 3, 4, 5]):
    rtype = record_types.get(row_idx, 'unknown')
    print(f"  Row {row_idx}: {rtype}")
print()

print("[PART NUMBER VALUES AFTER STEP 2]")
for row_idx in sorted([2, 3, 4, 5]):
    col1_val = df_output.iloc[row_idx, 1]
    col3_val = df_output.iloc[row_idx, 3]
    rtype = record_types.get(row_idx, 'unknown')
    print(f"  Row {row_idx} ({rtype:20s}): Col1='{col1_val}' -> Col3='{col3_val}'")
print()

print("=" * 100)
print("EVALUATION")
print("=" * 100)
print()

# Check key conditions
issues = []

# Row 2: Should be parent, col3 unchanged
if record_types.get(2) not in ('parent', 'package_parent'):
    issues.append("Row 2: Expected 'parent' classification")
if df_output.iloc[2, 3] != '123456':
    issues.append("Row 2: Col3 should remain '123456'")

# Row 3: TEST CASE - Should be parent with col3 filled from col1
if record_types.get(3) not in ('parent', 'package_parent'):
    issues.append("Row 3 (FALLBACK TEST): Expected 'parent' classification (not defect!)")
    print("  [WARN] Row 3 classified as", record_types.get(3), "- fallback logic may not be working")
else:
    print("  [PASS] Row 3 correctly classified as parent (fallback part number recognized)")

if df_output.iloc[3, 3] == '08LXX-E02-XXXX':
    print("  [PASS] Row 3 part number filled from column 1 fallback")
elif df_output.iloc[3, 3] == '':
    issues.append("Row 3 (FALLBACK TEST): Col3 should be filled with '08LXX-E02-XXXX'")
    print("  [WARN] Row 3 part number NOT filled - check if post-processing ran")
else:
    print(f"  [INFO] Row 3 part number is '{df_output.iloc[3, 3]}'")

# Row 4: Subsection label should NOT be affected
if record_types.get(4) == 'subsection_label':
    print("  [PASS] Row 4 correctly identified as subsection_label")
else:
    issues.append(f"Row 4: Expected 'subsection_label', got '{record_types.get(4)}'")

# Row 5: Child should remain child
if record_types.get(5) not in ('child', 'package_child'):
    issues.append(f"Row 5: Expected 'child', got '{record_types.get(5)}'")
else:
    print("  [PASS] Row 5 correctly classified as child")

print()
if issues:
    print("[ISSUES FOUND]")
    for issue in issues:
        print(f"  ❌ {issue}")
    print()
    print("Status: FALLBACK LOGIC NEEDS REVIEW")
else:
    print("[PASS] All evaluations passed!")
    print()
    print("Status: FALLBACK LOGIC WORKING CORRECTLY [OK]")

print()
print("=" * 100)
