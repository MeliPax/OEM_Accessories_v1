#!/usr/bin/env python
"""
Refresh vehicle database from AutoData Solutions API.

Usage:
    python refresh_db_ads.py

Fetches Year/Make/Model/Trim data from ADS, transforms to pipeline schema,
and saves to db/db_vehicle_models.csv with full validation and standardization.
"""

import sys
import uuid
from pathlib import Path
from datetime import datetime

# Add project to path (accy_v2 MUST be first to avoid model_lookup/core shadowing accy_v2/core)
sys.path.insert(0, str(Path(__file__).parent))  # model_lookup
sys.path.insert(0, str(Path(__file__).parent.parent))  # accy_v2

from chrome_api.service import ADSService
from models.manufacture_module import save_vehicle_models_to_csv
from core.helpers.pipeline_logger import PipelineLogger
from core.helpers.dq_logger import DQLogger


def refresh_from_ads(makes=None, years=None):
    """
    Refresh database from ADS API.

    Args:
        makes: List of makes to fetch (default: all available)
        years: List of years to fetch (default: [2024, 2025, 2026])
    """
    # Use defaults if not provided
    if makes is None:
        makes = ["Hyundai", "Honda", "Kia", "Mazda", "Genesis", "Mitsubishi", "Volkswagen"]
    if years is None:
        years = [2024, 2025, 2026]

    # Create run ID and loggers
    run_id = uuid.uuid4().hex[:8]
    pipeline_log_path = str(Path(__file__).parent.parent / "output" / "pipeline_logs" / "ads_refresh")
    dq_report_path = str(Path(__file__).parent.parent / "output" / "dq_reports" / "ads_refresh")

    pipeline_logger = PipelineLogger(run_id, pipeline_log_path)
    dq_logger = DQLogger(run_id, source_file="ADS API")

    print("\n" + "=" * 70)
    print("DATABASE REFRESH FROM ADS")
    print("=" * 70)
    print(f"Makes: {', '.join(makes)}")
    print(f"Years: {', '.join(map(str, years))}")
    print("=" * 70)

    try:
        # Initialize ADS service
        print("\n[1/4] Initializing ADS service...")
        service = ADSService(pipeline_logger=pipeline_logger, dq_logger=dq_logger)
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
        df = service.refresh_from_ads(makes=makes, years=years)
        print(f"      [OK] Fetched {len(df)} configurations")

        # Save to CSV with validation and standardization
        print("\n[4/4] Saving to database with validation...")
        result = save_vehicle_models_to_csv(
            df,
            str(db_path),
            key_columns=["Manufacturer", "ModelYear", "ModelNumber", "Package"],
            dq_logger=dq_logger,
        )

        if result["success"]:
            print(f"      [OK] {result['records_saved']} records saved")
            if result["duplicates"]:
                print(f"      [INFO] {result['duplicates']} duplicates skipped")
            if result["invalid_records"]:
                print(f"      [INFO] {result['invalid_records']} invalid records skipped")
        else:
            print(f"      [FAIL] {result.get('message', 'Unknown error')}")
            return 1

        # Write DQ report
        dq_logger.write_dq_report(dq_report_path)

        # Summary
        print("\n" + "=" * 70)
        print("[SUCCESS] DATABASE REFRESH COMPLETE")
        print("=" * 70)
        print(f"Database location: {db_path}")
        print(f"Records saved: {result['records_saved']}")
        print(f"Total configurations fetched: {len(df)}")
        print(f"Pipeline log: {pipeline_log_path}")
        print(f"DQ report: {dq_report_path}")
        print("=" * 70 + "\n")

        return 0

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback

        traceback.print_exc()
        print("=" * 70 + "\n")
        return 1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Refresh vehicle database from AutoData Solutions API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch all makes (default)
  python refresh_db_ads.py

  # Fetch specific makes
  python refresh_db_ads.py --makes Hyundai Mazda Genesis

  # Fetch specific makes and years
  python refresh_db_ads.py --makes Hyundai Mazda Genesis --years 2024 2025 2026
        """,
    )
    parser.add_argument(
        "--makes",
        nargs="+",
        help="List of makes to fetch (default: all available)",
        default=None,
    )
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        help="List of years to fetch (default: 2024 2025 2026)",
        default=None,
    )

    args = parser.parse_args()
    sys.exit(refresh_from_ads(makes=args.makes, years=args.years))
