"""
Test Step 1 v2: Load *_APP_EN and *_APP_FR sheets and extract model data
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from accy_v2.oems.honda.pipeline.step1_validation_v2 import (
    find_parts_data_sheets,
    extract_model_name_from_sheet,
    validate_and_extract
)
import pandas as pd

def print_section(title, width=80):
    print(f"\n{'='*width}")
    print(f"  {title}")
    print(f"{'='*width}\n")

# Find test files
landing_zone = Path(r"C:\Users\paxm\OneDrive - PBS SYSTEMS\Desktop\Office\Projects\OEM Accessory project\OEM_Accessories_v1\landing_zone\2026\Honda")
files = list(landing_zone.rglob("*.xlsx"))

if not files:
    print("❌ No test files found")
    sys.exit(1)

test_file = files[0]

print_section("TEST: STEP 1 V2 - Load *_APP_EN and *_APP_FR Sheets")
print(f"Test file: {test_file.name}\n")

# ============================================================================
# Test 1: Find sheets
# ============================================================================

print_section("Test 1: Find *_APP_EN and *_APP_FR Sheets")

sheet_info = find_parts_data_sheets(str(test_file))

print(f"All sheets in file ({len(sheet_info['all_sheets'])}):")
for i, sheet in enumerate(sheet_info['all_sheets'][:15], 1):
    print(f"  {i:2d}. {sheet}")
if len(sheet_info['all_sheets']) > 15:
    print(f"  ... and {len(sheet_info['all_sheets']) - 15} more")

print(f"\nFound EN sheet: {sheet_info['found_en']}")
if sheet_info['app_en_sheet']:
    print(f"  → {sheet_info['app_en_sheet']}")

print(f"Found FR sheet: {sheet_info['found_fr']}")
if sheet_info['app_fr_sheet']:
    print(f"  → {sheet_info['app_fr_sheet']}")

if not sheet_info['found_en'] or not sheet_info['found_fr']:
    print("\n⚠️  Note: This file may not have *_APP_EN/*_APP_FR sheets")
    print("The test will show what sheets ARE available.")
    sys.exit(0)

# ============================================================================
# Test 2: Extract model names
# ============================================================================

if sheet_info['app_en_sheet'] and sheet_info['app_fr_sheet']:
    print_section("Test 2: Extract Model Name from Sheets")

    df_en = pd.read_excel(str(test_file), sheet_name=sheet_info['app_en_sheet'])
    df_fr = pd.read_excel(str(test_file), sheet_name=sheet_info['app_fr_sheet'])

    model_name_en, model_year_en = extract_model_name_from_sheet(df_en, sheet_info['app_en_sheet'], "EN")
    model_name_fr, model_year_fr = extract_model_name_from_sheet(df_fr, sheet_info['app_fr_sheet'], "FR")

    print(f"EN Sheet Model:")
    print(f"  Model: {model_name_en}")
    print(f"  Year: {model_year_en}")

    print(f"\nFR Sheet Model:")
    print(f"  Model: {model_name_fr}")
    print(f"  Year: {model_year_fr}")

    if model_name_en == model_name_fr:
        print(f"\n✓ Models match!")
    else:
        print(f"\n⚠️  Models don't match!")

    # Show first rows
    print_section("EN Sheet - First 5 Rows")
    print(df_en.head().to_string())

    print_section("FR Sheet - First 5 Rows")
    print(df_fr.head().to_string())

# ============================================================================
# Test 3: Run full validate_and_extract
# ============================================================================

print_section("Test 3: Full Step 1 Execution (validate_and_extract)")

data_dict, metadata, dq_warnings = validate_and_extract(str(test_file))

if data_dict:
    print(f"✓ Status: {metadata.get('status')}")
    print(f"\nMetadata:")
    print(json.dumps({k: v for k, v in metadata.items() if k not in ['file_path']}, indent=2, default=str))

    if dq_warnings:
        print(f"\nDQ Warnings ({len(dq_warnings)}):")
        for warning in dq_warnings:
            print(f"  [{warning['severity']}] {warning['message']}")
    else:
        print(f"\n✓ No DQ warnings")

    print(f"\nData loaded:")
    print(f"  EN: {data_dict['EN'].shape[0]} rows × {data_dict['EN'].shape[1]} columns")
    print(f"  FR: {data_dict['FR'].shape[0]} rows × {data_dict['FR'].shape[1]} columns")

    print_section("Summary")
    print(f"""
✓ Successfully loaded:
  Model: {metadata.get('model_name_en')} (Year: {metadata.get('model_year_en')})
  EN Sheet: {metadata.get('en_sheet')} - {data_dict['EN'].shape[0]} rows
  FR Sheet: {metadata.get('fr_sheet')} - {data_dict['FR'].shape[0]} rows
  Match: {'Yes' if metadata.get('model_name_match') else 'No'}
""")
else:
    print(f"❌ Failed to load data")
    print(f"\nWarnings:")
    for warning in dq_warnings:
        print(f"  [{warning['severity']}] {warning['message']}")
