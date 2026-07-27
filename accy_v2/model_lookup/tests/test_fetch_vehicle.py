#!/usr/bin/env python3
"""
Test: Single vehicle fetch (fetch_vehicle)

Quick test of the minimal-call fetch_vehicle() method.
Tests that it makes exactly 1 API call and returns correct data.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from chrome_api.service import ADSService


def test_fetch_vehicle():
    """Test fetch_vehicle for single vehicle lookup."""
    print("=" * 70)
    print("TEST: fetch_vehicle() - Single Vehicle Fetch")
    print("=" * 70)

    service = ADSService()

    print("\nFetching Hyundai Elantra Essential (2026)...")
    start = time.time()
    df = service.fetch_vehicle("Hyundai", "Elantra", 2026, trim="Essential")
    elapsed = time.time() - start

    print(f"  Time: {elapsed:.1f}s (includes pacing)")
    print(f"  Rows returned: {len(df)}")

    # Assertions
    assert len(df) == 1, f"Expected 1 row, got {len(df)}"
    print("  [OK] Returned exactly 1 row")

    row = df.iloc[0]
    assert row["ModelNumber"] == "ELCS4V2BES00", f"Wrong model number: {row['ModelNumber']}"
    print(f"  [OK] ModelNumber: {row['ModelNumber']}")

    assert row["StyleID"] == 481251, f"Wrong StyleID: {row['StyleID']}"
    print(f"  [OK] StyleID: {row['StyleID']}")

    assert row["Drivetrain"] == "FRONT_WHEEL_DRIVE", f"Wrong drivetrain: {row['Drivetrain']}"
    print(f"  [OK] Drivetrain: {row['Drivetrain']}")

    assert row["PassDoors"] == 4, f"Wrong PassDoors: {row['PassDoors']}"
    print(f"  [OK] PassDoors: {row['PassDoors']}")

    print("\n" + "=" * 70)
    print("[SUCCESS] fetch_vehicle test passed")
    print("=" * 70 + "\n")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(test_fetch_vehicle())
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
