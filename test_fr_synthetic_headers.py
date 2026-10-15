#!/usr/bin/env python3
"""
Test: FR Header Normalization with Synthetic Data
Mimics actual Honda FR Excel structure to verify the fix works
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

print("=" * 120)
print("TEST: FR HEADER NORMALIZATION - SYNTHETIC DATA")
print("=" * 120)
print()

# Load config
config_root = Path('accy_v2/oems/honda/config')
config = ModularConfigLoader('honda', config_root).load_all()
print(f"[INFO] Config loaded. Upstream columns: {list(config['schemas']['upstream']['columns'].keys())}")
print()

# Create synthetic data that mimics actual Honda FR Excel structure
test_data_fr = {
    0: [None, None, None, None, None, None, None, None, None, None],  # Row 0 - metadata
    1: ['Civic à Hayon & Type R', None, None, None, None, None, None, None, None, None],  # Model name
    2: ['2026', None, None, None, None, None, None, None, None, None],  # Year
    3: [None, None, None, None, None, None, None, None, None, None],
    4: [None, None, None, None, None, None, None, None, None, None],
    5: [None, None, None, None, None, None, None, None, None, None],
    6: [None, None, None, None, None, None, None, None, None, None],
    7: [None, None, None, None, None, None, None, None, None, None],
    8: [None, None, None, None, None, None, None, None, None, None],
    9: [None, None, None, None, None, None, None, None, None, None],

    # Section marker
    10: ['1.0 Groupes et ensembles', None, None, None, None, None, None, None, None, None],

    # Header row - FRENCH with accents
    11: [None, None, 'La Description', 'Numéro de pièce', 'Prix net', 'Prix de liste', 'T.F.F.', 'Prix installé', 'Application', 'Sport'],

    # Trim sub-header
    12: [None, None, None, None, None, None, None, None, None, '•'],

    # Data rows
    13: [None, '08LXX-E01-XXXX', 'Racing Package', '26TYPER-001', '100', '200', '0.05', '250', 'All', '•'],
    14: [None, '08LXX-E02-XXXX', 'Chrome Kit', '26TYPER-002', '50', '100', '0.03', '120', 'All', ''],
    15: [None, '08LXX-E03-XXXX', 'Floor Mats', None, '30', '60', '0.02', '75', 'Base', '•'],
}

df_fr = pd.DataFrame(test_data_fr).T
df_fr.columns = range(len(df_fr.columns))

print("[DATA] Synthetic FR data created:")
print(f"  Rows: {df_fr.shape[0]}, Columns: {df_fr.shape[1]}")
print(f"  Raw header row (11): {list(df_fr.iloc[11])[:9]}")
print()

# Setup loggers
run_id = 'test_fr_synthetic'
dq_logger = DQLogger(run_id=run_id, source_file='synthetic_data')
pipeline_logger = PipelineLogger(run_id=run_id, log_path='accy_v2/output/pipeline_logs/honda')

# Minimal metadata
meta_data = {
    'sheet_name': '26MY_CIV5D_APP_FR',
    'language': 'FR',
    'model_name': 'Civic à Hayon & Type R',
    'vehicle_year': 2026,
    'section_structure': {}
}

# Run Step 1 to detect sections
print("[STEP 1] Running section detection...")
try:
    df_s1, meta_s1 = step1_validation.run(df_fr.copy(), config, meta_data, dq_logger, pipeline_logger)
    print(f"[OK] Step 1 complete")
    print(f"     Sections found: {len(meta_s1.get('section_structure', {}))}")
    for sect_name, bounds in meta_s1.get('section_structure', {}).items():
        print(f"       - {sect_name}: header_row={bounds.get('header_row')}, data_start={bounds.get('data_start_row')}")
except Exception as e:
    print(f"[ERROR] Step 1 failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Run Step 2 to normalize headers
print("[STEP 2] Running header normalization...")
try:
    df_s2, meta_s2 = step2_header_normalization.run(df_s1, config, meta_s1, dq_logger, pipeline_logger)
    print(f"[OK] Step 2 complete")
except Exception as e:
    print(f"[ERROR] Step 2 failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Analyze results
print("=" * 120)
print("HEADER NORMALIZATION RESULTS")
print("=" * 120)
print()

normalized_headers = meta_s2.get('normalized_headers', {})

for section_name, norm_header_list in normalized_headers.items():
    print(f"[SECTION] {section_name}")
    print()

    # Show all columns with their normalized names
    print("  Column Index | Raw → Normalized")
    print("  " + "-" * 100)

    for col_idx in range(min(10, len(norm_header_list))):
        norm_name = norm_header_list[col_idx]

        # Try to show raw value from the header row
        section_bounds = meta_s1.get('section_structure', {}).get(section_name, {})
        if section_bounds:
            header_row_idx = section_bounds.get('header_row')
            if header_row_idx is not None and header_row_idx < len(df_s1):
                raw_val = df_s1.iloc[header_row_idx, col_idx]
                raw_str = str(raw_val) if pd.notna(raw_val) else "(empty)"
            else:
                raw_str = "(unknown)"
        else:
            raw_str = "(unknown)"

        # Classify the normalized name
        canonical_names = ['description', 'part_number', 'dealer_net', 'list_price', 'frt', 'installed_price', 'application', 'comments']
        if norm_name in canonical_names:
            status = '✓ CANONICAL'
        elif norm_name.startswith('unnamed'):
            status = '  (unnamed/padding)'
        else:
            status = f'  (custom: "{norm_name}")'

        print(f"  {col_idx:13d} | {raw_str:30s} → {norm_name:25s} {status}")

    print()

    # Check for critical columns
    print("[BREAKING POINT CHECK]")
    critical = {
        'part_number': 'Part ID detection',
        'description': 'Product name',
        'dealer_net': 'Wholesale price',
        'list_price': 'Retail price'
    }

    for col_name, purpose in critical.items():
        if col_name in norm_header_list:
            print(f"  ✓ {col_name:20s} - {purpose:30s} FOUND at index {norm_header_list.index(col_name)}")
        else:
            print(f"  ✗ {col_name:20s} - {purpose:30s} MISSING - BREAKING POINT!")

    print()

# Show record type counts
print("[RECORD CLASSIFICATION]")
record_type_counts = meta_s2.get('record_type_counts', {})
for rtype, count in sorted(record_type_counts.items(), key=lambda x: -x[1]):
    print(f"  {rtype:20s}: {count:3d}")

# Check defect rate
total_data_rows = 3  # Rows 13-15 in our synthetic data
defect_count = record_type_counts.get('defect', 0)
parent_count = record_type_counts.get('parent', 0)

if defect_count > total_data_rows * 0.3:
    print(f"\n[⚠️  WARNING] Defect rate is {defect_count}/{total_data_rows} ({100*defect_count/total_data_rows:.0f}%)")
    print(f"  This suggests header normalization may still have issues!")
else:
    print(f"\n[✓ OK] Defect rate is acceptable ({defect_count}/{total_data_rows})")

print()
print("=" * 120)
print("KEYWORD MATCHING TEST")
print("=" * 120)
print()

# Test the keyword matching directly
print("[Testing _matches_keywords() function directly]")
print()

from accy_v2.oems.honda.pipeline.step2_header_normalization import _matches_keywords

test_headers_fr = [
    ('Numéro de pièce', 'part_number', config['schemas']['upstream']['columns']['part_number']['detection']['FR']['key_words']),
    ('La Description', 'description', config['schemas']['upstream']['columns']['description']['detection']['FR']['key_words']),
    ('Prix net', 'dealer_net', config['schemas']['upstream']['columns']['dealer_net']['detection']['FR']['key_words']),
    ('Prix de liste', 'list_price', config['schemas']['upstream']['columns']['list_price']['detection']['FR']['key_words']),
    ('T.F.F.', 'frt', config['schemas']['upstream']['columns']['frt']['detection']['FR']['key_words']),
    ('Prix installé', 'installed_price', config['schemas']['upstream']['columns']['installed_price']['detection']['FR']['key_words']),
]

for raw_header, canonical, keywords in test_headers_fr:
    match = _matches_keywords(raw_header, keywords)
    status = '✓ MATCH' if match else '✗ NO MATCH'
    print(f"  {raw_header:20s} → {canonical:20s} {status}")
    if not match:
        # Show why it didn't match
        col_lower = (raw_header.lower()
                     .replace('é', 'e').replace('è', 'e').replace('ê', 'e')
                     .replace('à', 'a').replace('â', 'a')
                     .replace('ç', 'c'))
        print(f"    Normalized: '{col_lower}'")
        print(f"    Rules: {keywords}")

print()
print("=" * 120)
print("TEST COMPLETE")
print("=" * 120)
