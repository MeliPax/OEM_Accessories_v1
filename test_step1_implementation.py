"""
TEST STEP 1: Verify implementation of data loading and metadata extraction.

This test:
1. Loads a Honda Excel file using Step 1 logic
2. Extracts all metadata
3. Prints results for verification
"""

import sys
import json
from pathlib import Path

# Import Step 1 implementation
sys.path.insert(0, str(Path.cwd()))
from accy_v2.oems.honda.pipeline.step1_validation import (
    validate_and_extract,
    extract_metadata_from_file,
    extract_model_from_sheet_name
)


def print_section(title, width=80):
    print(f"\n{'='*width}")
    print(f"  {title}")
    print(f"{'='*width}\n")


def test_step1_single_file():
    """Test Step 1 with a single Honda file."""

    print_section("TEST: STEP 1 IMPLEMENTATION")

    # Find test file
    landing_zone = Path(r"C:\Users\paxm\OneDrive - PBS SYSTEMS\Desktop\Office\Projects\OEM Accessory project\OEM_Accessories_v1\landing_zone\2026\Honda")
    files = list(landing_zone.rglob("*.xlsx"))

    if not files:
        print("❌ No test files found")
        return False

    test_file = files[0]
    print(f"Test file: {test_file.name}\n")

    # ========================================================================
    # TEST 1: Extract metadata from file
    # ========================================================================

    print_section("TEST 1: Extract File-Level Metadata")

    metadata = extract_metadata_from_file(str(test_file))

    print(f"File Name: {metadata['file_name']}")
    print(f"Model Year: {metadata['model_year']}")
    print(f"Manufacture Validated: {metadata['manufacture_validated']}")
    print(f"Publication Date: {metadata['publication_date']}")
    print(f"Models Found: {metadata['models_in_file']}")
    print(f"Primary Sheet: {metadata['primary_sheet']}")
    print(f"\nSheet Summary:")
    for key, value in metadata['sheet_summary'].items():
        print(f"  {key}: {value}")

    # Verify key extractions
    assert metadata['model_year'], "❌ Model year should be extracted"
    print(f"\n✓ Model year extracted: {metadata['model_year']}")

    assert metadata['primary_sheet'], "❌ Primary sheet should be identified"
    print(f"✓ Primary sheet identified: {metadata['primary_sheet']}")

    assert metadata['models_in_file'], "❌ Models should be found"
    print(f"✓ Models found: {metadata['models_in_file']}")

    # ========================================================================
    # TEST 2: Full validate_and_extract
    # ========================================================================

    print_section("TEST 2: Full Step 1 Execution (validate_and_extract)")

    data_dict, full_metadata, dq_warnings = validate_and_extract(str(test_file))

    if data_dict is None:
        print("❌ Failed to load data")
        print(f"Errors: {dq_warnings}")
        return False

    print(f"Status: {full_metadata.get('status')}")
    print(f"Data shape: {full_metadata.get('data_shape')}")
    print(f"Wide format detected: {full_metadata.get('wide_format_detected')}")
    print(f"Trim columns: {full_metadata.get('trim_columns', [])}")

    # Check data
    df_en = data_dict.get("EN")
    assert df_en is not None, "❌ EN data should be loaded"
    assert len(df_en) > 0, "❌ Data should not be empty"

    print(f"\n✓ Data loaded: {len(df_en)} rows × {len(df_en.columns)} columns")
    print(f"✓ Columns: {list(df_en.columns)}")
    print(f"\nFirst row sample:")
    print(df_en.iloc[0, :3].to_string())

    # Check DQ warnings
    if dq_warnings:
        print(f"\nDQ Warnings ({len(dq_warnings)}):")
        for warning in dq_warnings:
            print(f"  - [{warning['severity']}] {warning['message']}")
    else:
        print(f"\n✓ No DQ warnings")

    # ========================================================================
    # TEST 3: Verify metadata extraction
    # ========================================================================

    print_section("TEST 3: Metadata Verification")

    checks = [
        ("Model Year", full_metadata.get('model_year') is not None),
        ("Manufacture Validated", full_metadata.get('manufacture_validated')),
        ("Primary Sheet", full_metadata.get('primary_sheet') is not None),
        ("Models Identified", len(full_metadata.get('models_in_file', [])) > 0),
        ("Data Loaded", len(df_en) > 0),
        ("Wide Format Detected", full_metadata.get('wide_format_detected')),
        ("Trim Columns Found", len(full_metadata.get('trim_columns', [])) > 0),
    ]

    passed = 0
    for check_name, check_result in checks:
        status = "✓" if check_result else "✗"
        print(f"{status} {check_name}: {check_result}")
        if check_result:
            passed += 1

    print(f"\n{passed}/{len(checks)} checks passed")

    # ========================================================================
    # TEST 4: Print full metadata as JSON
    # ========================================================================

    print_section("Full Metadata Output (JSON)")

    # Clean metadata for JSON
    clean_metadata = {k: v for k, v in full_metadata.items() if k != 'error'}
    print(json.dumps(clean_metadata, indent=2, default=str))

    # ========================================================================
    # Summary
    # ========================================================================

    print_section("SUMMARY")

    all_passed = all(check for _, check in checks)
    if all_passed:
        print("✓ ALL TESTS PASSED")
        print(f"\nStep 1 successfully:")
        print(f"  1. Extracted model year: {full_metadata.get('model_year')}")
        print(f"  2. Identified models: {', '.join(full_metadata.get('models_in_file', []))}")
        print(f"  3. Loaded data: {len(df_en)} rows")
        print(f"  4. Detected wide format with trim columns: {full_metadata.get('trim_columns', [])[:3]}")
        return True
    else:
        print("❌ SOME TESTS FAILED")
        return False


if __name__ == "__main__":
    success = test_step1_single_file()
    sys.exit(0 if success else 1)
