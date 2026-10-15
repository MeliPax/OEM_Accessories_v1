#!/usr/bin/env python3
"""
Test: FR Header Keyword Matching
Direct test of the _matches_keywords function for FR headers
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path.cwd() / 'accy_v2'))

from accy_v2.core.config_loader_v2 import ModularConfigLoader
from accy_v2.oems.honda.pipeline.step2_header_normalization import _matches_keywords

print("=" * 120)
print("TEST: FR HEADER KEYWORD MATCHING")
print("=" * 120)
print()

# Load config
config_root = Path('accy_v2/oems/honda/config')
config = ModularConfigLoader('honda', config_root).load_all()

upstream = config['schemas']['upstream']
columns_def = upstream['columns']

print(f"[INFO] Loaded {len(columns_def)} column definitions from upstream.yaml")
print()

# Test data: Real FR column headers from Honda Excel
fr_headers = {
    'La Description': ('description', ['description', 'part number', 'dealer net', 'list price', 'frt', 'installed price', 'application', 'comments']),
    'Numéro de pièce': ('part_number', ['description', 'part number', 'dealer net', 'list price', 'frt', 'installed price', 'application', 'comments']),
    'Prix net': ('dealer_net', ['description', 'part number', 'dealer net', 'list price', 'frt', 'installed price', 'application', 'comments']),
    'Prix de liste': ('list_price', ['description', 'part number', 'dealer net', 'list price', 'frt', 'installed price', 'application', 'comments']),
    'T.F.F.': ('frt', ['description', 'part number', 'dealer net', 'list price', 'frt', 'installed price', 'application', 'comments']),
    'Prix installé': ('installed_price', ['description', 'part number', 'dealer net', 'list price', 'frt', 'installed price', 'application', 'comments']),
    'Application': ('application', ['description', 'part number', 'dealer net', 'list price', 'frt', 'installed price', 'application', 'comments']),
}

print("[TEST 1] KEYWORD MATCHING FOR EACH FR HEADER")
print("=" * 120)
print()

results = {}

for raw_header, (expected_canonical, expected_in_list) in fr_headers.items():
    print(f"Raw Header: '{raw_header}'")
    print(f"Expected Canonical Name: '{expected_canonical}'")
    print()

    # Try matching against each column definition
    matched = False

    for col_canonical, col_spec in columns_def.items():
        detection = col_spec.get('detection', {})
        fr_rules = detection.get('FR', {})
        keywords = fr_rules.get('key_words', {})

        # Test the match
        if _matches_keywords(raw_header, keywords):
            status = '✓ MATCH'
            if col_canonical == expected_canonical:
                status += ' (CORRECT)'
                matched = True
            else:
                status += f' (WRONG! Expected {expected_canonical})'
                matched = False
            print(f"  {status}: {col_canonical}")

    if not matched:
        print(f"  ✗ NO MATCH FOUND!")
        # Show normalization for debugging
        col_lower = (raw_header.lower()
                     .replace('é', 'e').replace('è', 'e').replace('ê', 'e')
                     .replace('à', 'a').replace('â', 'a')
                     .replace('ç', 'c'))
        print(f"  Normalized: '{col_lower}'")
        print(f"  Rules for {expected_canonical}:")
        fr_rules = columns_def[expected_canonical].get('detection', {}).get('FR', {})
        keywords = fr_rules.get('key_words', {})
        print(f"    {keywords}")

    results[raw_header] = matched
    print()

# Summary
print("=" * 120)
print("[SUMMARY]")
print("=" * 120)
print()

pass_count = sum(1 for v in results.values() if v)
fail_count = len(results) - pass_count

for header, matched in results.items():
    status = '✓ PASS' if matched else '✗ FAIL'
    print(f"  {status}: {header}")

print()
print(f"Results: {pass_count}/{len(results)} PASS")

if fail_count == 0:
    print()
    print("🎉 ALL FR HEADERS NORMALIZE CORRECTLY!")
    print("   The fix is working properly - FR headers are matching their canonical names.")
else:
    print()
    print(f"⚠️  {fail_count} FR HEADERS FAILED TO MATCH!")
    print("   This indicates breaking points in the normalization process.")

print()
print("=" * 120)
print("TEST 2: ACCENT STRIPPING VERIFICATION")
print("=" * 120)
print()

test_accents = [
    ('Numéro', 'numero'),
    ('pièce', 'piece'),
    ('Prix', 'prix'),
    ('La', 'la'),
    ('T.F.F.', 't.f.f.'),
]

print("[Verifying accent normalization]")
print()

for original, expected in test_accents:
    normalized = (original.lower()
                  .replace('é', 'e').replace('è', 'e')
                  .replace('ç', 'c'))

    status = '✓' if normalized == expected else '✗'
    print(f"  {status} '{original}' → '{normalized}' (expected '{expected}')")

print()
print("=" * 120)
