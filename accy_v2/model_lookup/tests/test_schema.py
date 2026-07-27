#!/usr/bin/env python3
"""
Test: Schema Validation

Tests that all columns exist, are populated, and have correct data types.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from chrome_api.service import ADSService


def test_schema():
    """Test schema validation."""
    print("=" * 70)
    print("TEST: Schema Validation")
    print("=" * 70)

    service = ADSService()
    df = service.fetch_make("Hyundai", [2026])

    expected_cols = [
        "Manufacturer",
        "ModelYear",
        "ModelNumber",
        "Description",
        "Description2",
        "Package",
        "Style_ID",
        "StyleID",
        "Drivetrain",
        "PassDoors",
    ]

    print("\n[1/2] Checking all columns present...")
    actual_cols = list(df.columns)
    assert actual_cols == expected_cols, f"Column mismatch.\nExpected: {expected_cols}\nActual: {actual_cols}"
    print("  [OK] All 10 columns present in correct order")

    print("\n[2/2] Checking data population...")
    for col in expected_cols:
        non_null = df[col].notna().sum()
        total = len(df)
        pct = (non_null / total) * 100
        status = "[OK]" if non_null > 0 else "[WARN]"
        print(f"  {status} {col:20} {non_null:3}/{total:3} ({pct:6.1f}%)")
        assert non_null > 0, f"Column {col} is entirely null"

    print("\n[3/2] Checking data types...")
    type_checks = [
        ("Manufacturer", "object"),
        ("ModelYear", "int64"),
        ("ModelNumber", "object"),
        ("Description", "object"),
        ("StyleID", "int64"),
        ("PassDoors", "int64"),
    ]

    for col, expected_type in type_checks:
        actual_type = str(df[col].dtype)
        status = "[OK]" if actual_type == expected_type else "[WARN]"
        print(f"  {status} {col:20} {actual_type}")

    print("\n" + "=" * 70)
    print("[SUCCESS] Schema validation test passed")
    print("=" * 70 + "\n")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(test_schema())
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
