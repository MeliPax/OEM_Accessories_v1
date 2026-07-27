#!/usr/bin/env python
"""
Refresh vehicle database from AutoData Solutions API.

Usage:
    python refresh_db_ads.py

Fetches Year/Make/Model/Trim data from ADS, transforms to pipeline schema,
and saves to db/db_vehicle_models.csv with full validation and standardization.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))  # accy_v2
sys.path.insert(0, str(Path(__file__).parent))  # model_lookup

from chrome_api.service import ADSService
from models.manufacture_module import save_vehicle_models_to_csv


def refresh_from_ads():
    """Refresh database from ADS API."""

    print("\n" + "=" * 70)
    print("DATABASE REFRESH FROM ADS")
    print("=" * 70)

    try:
        # Initialize ADS service
        print("\n[1/4] Initializing ADS service...")
        service = ADSService()
        print("      [OK] Credentials loaded and client initialized")

        # Archive current database
        print("\n[2/4] Archiving current database...")
        db_path = Path(__file__).parent / "db" / "db_vehicle_models.csv"
        archive_dir = db_path.parent / "archive"
        archive_dir.mkdir(exist_ok=True)

        if db_path.exists():
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            archive_path = archive_dir / f"db_vehicle_models.{timestamp}.csv"
            db_path.rename(archive_path)
            print(f"      [OK] Archived to: {archive_path.name}")
        else:
            print("      [SKIP] No existing database to archive")

        # Fetch from ADS
        print("\n[3/4] Fetching data from ADS (this may take a moment)...")
        makes = ["Hyundai", "Honda", "Kia", "Mazda", "Genesis", "Mitsubishi", "Volkswagen"]
        years = [2024, 2025, 2026]

        df = service.refresh_from_ads(makes=makes, years=years)
        print(f"      [OK] Fetched {len(df)} configurations")

        # Save to CSV with validation and standardization
        print("\n[4/4] Saving to database with validation...")
        result = save_vehicle_models_to_csv(df, str(db_path))

        if result["success"]:
            print(f"      [OK] {result['records_saved']} records saved")
            if result["duplicates"]:
                print(f"      [INFO] {result['duplicates']} duplicates skipped")
            if result["invalid_records"]:
                print(f"      [INFO] {result['invalid_records']} invalid records skipped")
        else:
            print(f"      [FAIL] {result.get('message', 'Unknown error')}")
            return 1

        # Summary
        print("\n" + "=" * 70)
        print("[SUCCESS] DATABASE REFRESH COMPLETE")
        print("=" * 70)
        print(f"Database location: {db_path}")
        print(f"Records saved: {result['records_saved']}")
        print(f"Total configurations fetched: {len(df)}")
        print("=" * 70 + "\n")

        return 0

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback

        traceback.print_exc()
        print("=" * 70 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(refresh_from_ads())
