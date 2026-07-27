#!/usr/bin/env python3
"""
Comprehensive test suite for ADS API integration.

Tests all fetch methods, schema validation, CSV I/O, and data quality.
"""

import sys
import time
import pandas as pd
from pathlib import Path
from datetime import datetime

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from chrome_api.service import ADSService
from models.manufacture_module import save_vehicle_models_to_csv


def print_header(title):
    """Print formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_test(name, passed, details=""):
    """Print test result."""
    status = "[OK]" if passed else "[FAIL]"
    print(f"{status} {name}")
    if details:
        print(f"     {details}")


class TestADSIntegration:
    """Test suite for ADS integration."""

    def __init__(self):
        self.test_count = 0
        self.pass_count = 0
        self.fail_count = 0
        self.test_csv = Path(__file__).parent / "db" / "test_ads_integration.csv"

    def run_test(self, test_func):
        """Run a single test and track results."""
        self.test_count += 1
        try:
            test_func()
            self.pass_count += 1
        except AssertionError as e:
            self.fail_count += 1
            print(f"[FAIL] {test_func.__name__}: {e}")
        except Exception as e:
            self.fail_count += 1
            print(f"[ERROR] {test_func.__name__}: {e}")

    def cleanup(self):
        """Remove test CSV if it exists."""
        if self.test_csv.exists():
            self.test_csv.unlink()

    def summary(self):
        """Print test summary."""
        print_header("TEST SUMMARY")
        print(f"Total:  {self.test_count}")
        print(f"Passed: {self.pass_count}")
        print(f"Failed: {self.fail_count}")

        if self.fail_count == 0:
            print("\n[SUCCESS] ALL TESTS PASSED")
            return 0
        else:
            print(f"\n[FAILED] {self.fail_count} TEST(S) FAILED")
            return 1

    # =========================================================================
    # TEST SUITE
    # =========================================================================

    def test_credentials_loaded(self):
        """Test 1: Credentials can be loaded."""
        from chrome_api.config import load_ads_env
        config = load_ads_env()
        assert config["base_url"], "Base URL not loaded"
        assert config["api_user"], "API user not loaded"
        assert config["api_password"], "API password not loaded"
        print_test("test_credentials_loaded", True, f"User: {config['api_user']}")

    def test_service_initialization(self):
        """Test 2: ADSService initializes without error."""
        service = ADSService()
        assert service.client is not None, "Client not initialized"
        assert service.make_map is not None, "Make map not loaded"
        print_test("test_service_initialization", True, f"Makes available: {len(service.make_map)}")

    def test_fetch_vehicle_single_call(self):
        """Test 3: fetch_vehicle makes exactly 1 API call."""
        service = ADSService()
        start = time.time()
        df = service.fetch_vehicle("Hyundai", "Elantra", 2026, trim="Essential")
        elapsed = time.time() - start

        assert len(df) == 1, f"Expected 1 row, got {len(df)}"
        assert df.iloc[0]["ModelNumber"] == "ELCS4V2BES00", "Wrong model number"
        assert df.iloc[0]["StyleID"] == 481251, "Wrong StyleID"
        assert df.iloc[0]["Drivetrain"] == "FRONT_WHEEL_DRIVE", "Wrong drivetrain"
        print_test("test_fetch_vehicle_single_call", True, f"1 row in {elapsed:.1f}s (includes pacing)")

    def test_fetch_make_complete(self):
        """Test 4: fetch_make returns all rows for Hyundai 2026."""
        service = ADSService()
        df = service.fetch_make("Hyundai", [2026])

        assert len(df) == 62, f"Expected 62 rows, got {len(df)}"
        assert df["Manufacturer"].unique().tolist() == ["HYUNDAI"], "Wrong manufacturer"
        assert df["ModelYear"].unique().tolist() == [2026], "Wrong year"
        print_test("test_fetch_make_complete", True, f"{len(df)} rows fetched")

    def test_schema_10_columns(self):
        """Test 5: Schema has all 10 required columns."""
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

        assert list(df.columns) == expected_cols, f"Column mismatch. Got: {list(df.columns)}"
        print_test("test_schema_10_columns", True, f"All 10 columns present")

    def test_columns_populated(self):
        """Test 6: All columns have data (non-null)."""
        service = ADSService()
        df = service.fetch_make("Hyundai", [2026])

        for col in df.columns:
            non_null = df[col].notna().sum()
            assert non_null > 0, f"Column {col} is entirely null"

        print_test("test_columns_populated", True, f"All {len(df.columns)} columns populated")

    def test_style_id_is_numeric(self):
        """Test 7: StyleID column contains numeric values."""
        service = ADSService()
        df = service.fetch_make("Hyundai", [2026])

        assert df["StyleID"].dtype in ["int64", "int32"], f"StyleID is {df['StyleID'].dtype}, expected numeric"
        assert df["StyleID"].nunique() == len(df), "StyleID should be unique per trim"
        print_test(
            "test_style_id_is_numeric",
            True,
            f"Numeric StyleIDs: {df['StyleID'].min()}-{df['StyleID'].max()}",
        )

    def test_drivetrain_values(self):
        """Test 8: Drivetrain has expected values."""
        service = ADSService()
        df = service.fetch_make("Hyundai", [2026])

        valid_drivetrains = {"FRONT_WHEEL_DRIVE", "ALL_WHEEL_DRIVE", "REAR_WHEEL_DRIVE"}
        actual = set(df["Drivetrain"].unique())
        assert actual.issubset(valid_drivetrains), f"Invalid drivetrains: {actual - valid_drivetrains}"
        print_test("test_drivetrain_values", True, f"Drivetrains: {sorted(actual)}")

    def test_csv_write_and_read(self):
        """Test 9: Data can be written to and read from CSV."""
        service = ADSService()
        df = service.fetch_make("Hyundai", [2026])

        # Save
        result = save_vehicle_models_to_csv(df, str(self.test_csv))
        assert result["success"], f"Save failed: {result['message']}"
        assert self.test_csv.exists(), "CSV file not created"

        # Read back
        df_read = pd.read_csv(self.test_csv)
        assert len(df_read) == len(df), f"Row count mismatch after read: {len(df_read)} vs {len(df)}"
        assert len(df_read.columns) == 10, f"Column count mismatch: {len(df_read.columns)} vs 10"

        print_test("test_csv_write_and_read", True, f"{len(df_read)} rows, {len(df_read.columns)} cols")

    def test_csv_column_harmonization(self):
        """Test 10: CSV harmonizes columns when schema changes."""
        # Create initial 7-column CSV
        df_7col = pd.DataFrame({
            "Manufacturer": ["HYUNDAI"],
            "ModelYear": [2025],
            "ModelNumber": ["OLD001"],
            "Description": ["Old Model"],
            "Description2": [""],
            "Package": ["Base"],
            "Style_ID": ["4dr Car"],
        })
        df_7col.to_csv(self.test_csv, index=False)

        # Append 10-column data
        df_10col = pd.DataFrame({
            "Manufacturer": ["HYUNDAI"],
            "ModelYear": [2026],
            "ModelNumber": ["NEW001"],
            "Description": ["New Model"],
            "Description2": [""],
            "Package": ["Essential"],
            "Style_ID": ["4dr Car"],
            "StyleID": [481251],
            "Drivetrain": ["FRONT_WHEEL_DRIVE"],
            "PassDoors": [4],
        })

        result = save_vehicle_models_to_csv(df_10col, str(self.test_csv))
        df_final = pd.read_csv(self.test_csv)

        assert len(df_final) == 2, f"Expected 2 rows, got {len(df_final)}"
        assert len(df_final.columns) == 10, f"Expected 10 columns, got {len(df_final.columns)}"
        assert df_final.iloc[0]["ModelNumber"] == "OLD001", "Old row lost"
        assert df_final.iloc[1]["ModelNumber"] == "NEW001", "New row lost"

        print_test("test_csv_column_harmonization", True, f"7-col + 10-col = 10-col harmonized")

    def test_no_duplicates(self):
        """Test 11: No duplicate model numbers in fetch."""
        service = ADSService()
        df = service.fetch_make("Hyundai", [2026])

        key_cols = ["Manufacturer", "ModelYear", "ModelNumber"]
        dupes = df.duplicated(subset=key_cols, keep=False).sum()
        assert dupes == 0, f"Found {dupes} duplicate rows"
        print_test("test_no_duplicates", True, f"No duplicates on key columns")

    def test_rate_limiting(self):
        """Test 12: Rate limiting is working (should take ~12s for 62 rows)."""
        service = ADSService()
        start = time.time()
        df = service.fetch_make("Hyundai", [2026])
        elapsed = time.time() - start

        min_expected = len(df) * 0.5 * 0.9  # Allow 10% variance
        assert elapsed >= min_expected, f"Too fast: {elapsed:.1f}s < {min_expected:.1f}s"
        print_test("test_rate_limiting", True, f"{len(df)} rows in {elapsed:.1f}s (paced)")

    def test_dump_all_multiple_makes(self):
        """Test 13: dump_all can fetch multiple makes."""
        service = ADSService()
        df = service.dump_all(makes=["Hyundai", "Genesis"], years=[2026])

        assert len(df) > 62, f"Expected > 62 rows, got {len(df)}"
        makes = set(df["Manufacturer"].unique())
        assert makes == {"HYUNDAI", "GENESIS"}, f"Expected 2 makes, got {makes}"
        print_test("test_dump_all_multiple_makes", True, f"{len(df)} rows, {len(makes)} makes")

    def test_dump_all_with_callback(self):
        """Test 14: dump_all processes save callbacks correctly."""
        service = ADSService()
        callback_invokes = []

        def save_callback(make, df):
            callback_invokes.append((make, len(df)))

        df = service.dump_all(makes=["Hyundai"], years=[2026], save_callback=save_callback)

        assert len(callback_invokes) == 1, f"Expected 1 callback invoke, got {len(callback_invokes)}"
        assert callback_invokes[0][0] == "Hyundai", "Wrong make in callback"
        print_test("test_dump_all_with_callback", True, f"Callback invoked {len(callback_invokes)}x")

    def test_data_quality_sample(self):
        """Test 15: Sample data quality checks."""
        service = ADSService()
        df = service.fetch_make("Hyundai", [2026])

        # Check ModelNumber format (should be alphanumeric, 12 chars typically)
        assert df["ModelNumber"].str.len().min() > 0, "Empty ModelNumber"

        # Check Description is not empty
        assert df["Description"].str.len().min() > 0, "Empty Description"

        # Check PassDoors is reasonable (typically 2, 4, or 5)
        assert df["PassDoors"].min() >= 2, "PassDoors too low"
        assert df["PassDoors"].max() <= 5, "PassDoors too high"

        print_test("test_data_quality_sample", True, f"Data quality checks passed")


def main():
    """Run all tests."""
    print_header("ADS INTEGRATION TEST SUITE")

    tester = TestADSIntegration()

    # Run tests
    print_header("RUNNING TESTS")
    tester.run_test(tester.test_credentials_loaded)
    tester.run_test(tester.test_service_initialization)
    tester.run_test(tester.test_fetch_vehicle_single_call)
    tester.run_test(tester.test_fetch_make_complete)
    tester.run_test(tester.test_schema_10_columns)
    tester.run_test(tester.test_columns_populated)
    tester.run_test(tester.test_style_id_is_numeric)
    tester.run_test(tester.test_drivetrain_values)
    tester.run_test(tester.test_csv_write_and_read)
    tester.run_test(tester.test_csv_column_harmonization)
    tester.run_test(tester.test_no_duplicates)
    tester.run_test(tester.test_rate_limiting)
    tester.run_test(tester.test_dump_all_multiple_makes)
    tester.run_test(tester.test_dump_all_with_callback)
    tester.run_test(tester.test_data_quality_sample)

    # Cleanup
    tester.cleanup()

    # Summary
    exit_code = tester.summary()

    print("\n" + "=" * 70)
    print(f"Test suite completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70 + "\n")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
