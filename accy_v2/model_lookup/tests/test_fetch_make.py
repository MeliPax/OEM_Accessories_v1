#!/usr/bin/env python3
"""
Test: Fetch entire make/year (fetch_make)

Tests the fetch_make() method for getting all trims for one OEM/year.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from chrome_api.service import ADSService


def test_fetch_make():
    """Test fetch_make for complete OEM/year data."""
    print("=" * 70)
    print("TEST: fetch_make() - Complete Make/Year Fetch")
    print("=" * 70)

    service = ADSService()

    print("\nFetching all Hyundai 2026 trims...")
    df = service.fetch_make("Hyundai", [2026])

    print(f"  Rows returned: {len(df)}")
    assert len(df) == 62, f"Expected 62 rows, got {len(df)}"
    print("  [OK] Retrieved 62 rows for Hyundai 2026")

    # Check manufacturer
    makes = df["Manufacturer"].unique().tolist()
    assert makes == ["HYUNDAI"], f"Expected only HYUNDAI, got {makes}"
    print("  [OK] All rows are HYUNDAI")

    # Check year
    years = df["ModelYear"].unique().tolist()
    assert years == [2026], f"Expected only 2026, got {years}"
    print("  [OK] All rows are year 2026")

    # Check schema
    expected_cols = 9
    assert len(df.columns) == expected_cols, f"Expected {expected_cols} columns, got {len(df.columns)}"
    print(f"  [OK] Has all {expected_cols} columns")

    # Check critical columns are populated
    assert df["ModelNumber"].notna().all(), "ModelNumber has nulls"
    assert df["Package"].notna().all(), "Package has nulls"
    assert df["Drivetrain"].notna().all(), "Drivetrain has nulls"
    print("  [OK] All critical columns populated")

    # Show sample
    print(f"\n  Sample rows:")
    for i in range(3):
        row = df.iloc[i]
        print(
            f"    {row['ModelNumber']:15} | {row['Description'][:25]:25} | Package={row['Package']}"
        )

    print("\n" + "=" * 70)
    print("[SUCCESS] fetch_make test passed")
    print("=" * 70 + "\n")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(test_fetch_make())
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
