#!/usr/bin/env python3
"""
Test: CSV Write/Read and Schema Harmonization

Tests saving data to CSV and reading it back with proper schema handling.
"""

import sys
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from chrome_api.service import ADSService
from models.manufacture_module import save_vehicle_models_to_csv


def test_csv_write_read():
    """Test writing and reading CSV."""
    print("=" * 70)
    print("TEST: CSV Write/Read")
    print("=" * 70)

    csv_path = Path(__file__).parent.parent / "db" / "test_csv_io.csv"

    # Fetch data
    print("\n[1/3] Fetching data...")
    service = ADSService()
    df = service.fetch_make("Hyundai", [2026])
    print(f"      Fetched {len(df)} rows")

    # Write to CSV
    print("[2/3] Writing to CSV...")
    result = save_vehicle_models_to_csv(df, str(csv_path))
    assert result["success"], f"Save failed: {result['message']}"
    print(f"      {result['message']}")

    # Read back
    print("[3/3] Reading from CSV...")
    df_read = pd.read_csv(csv_path)
    print(f"      Read {len(df_read)} rows, {len(df_read.columns)} columns")

    # Verify
    assert len(df_read) == len(df), f"Row count mismatch: {len(df_read)} vs {len(df)}"
    print("  [OK] Row count matches")

    assert len(df_read.columns) == 10, f"Expected 10 columns, got {len(df_read.columns)}"
    print("  [OK] Has all 10 columns")

    # Check data integrity
    assert df_read.iloc[0]["ModelNumber"] == df.iloc[0]["ModelNumber"], "Data corrupted"
    print("  [OK] Data integrity verified")

    # Show columns
    print(f"\n  Columns in CSV:")
    for col in df_read.columns:
        print(f"    - {col}")

    # Cleanup
    csv_path.unlink()

    print("\n" + "=" * 70)
    print("[SUCCESS] CSV write/read test passed")
    print("=" * 70 + "\n")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(test_csv_write_read())
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
