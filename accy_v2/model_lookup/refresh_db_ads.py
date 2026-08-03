#!/usr/bin/env python
"""
Refresh vehicle database from AutoData Solutions API.

Usage:
    python refresh_db_ads.py [--makes MAKE1 MAKE2 ...] [--years 2024 2025 ...]

Fetches Year/Make/Model/Trim data from ADS, transforms to pipeline schema,
and saves to db/db_vehicle_models.csv with full validation and standardization.

Features:
  - Configuration-driven engine_type extraction (ENGINE_TYPE keywords + translator)
  - Comprehensive logging: console (INFO+) and file (DEBUG+)
  - Database archival before refresh
  - DQ validation and reporting
"""

import sys
import uuid
import logging
from pathlib import Path
from datetime import datetime

# Add project to path (accy_v2 MUST be first to avoid model_lookup/core shadowing accy_v2/core)
sys.path.insert(0, str(Path(__file__).parent))  # model_lookup
sys.path.insert(0, str(Path(__file__).parent.parent))  # accy_v2

from chrome_api.service import ADSService
from models.manufacture_module import save_vehicle_models_to_csv
from core.helpers.pipeline_logger import PipelineLogger
from core.helpers.dq_logger import DQLogger
from logging_config import setup_logging, get_logger


def refresh_from_ads(makes=None, years=None):
    """
    Refresh database from ADS API.

    Fetches vehicle data from AutoData Solutions API and saves to CSV with:
      - Engine type extraction (using ENGINE_TYPE keywords from classification)
      - Translator-based keyword normalization
      - Comprehensive logging (console + file)
      - Database validation and archival

    Args:
        makes: List of makes to fetch (default: all available)
        years: List of years to fetch (default: [2024, 2025, 2026])

    Returns:
        0 on success, 1 on failure

    Logs:
        - INFO: Major steps (init, fetch, save, complete)
        - DEBUG: Detailed progress by OEM/year
        - ERROR: Failures with context
    """
    # Initialize logging
    log_file = setup_logging()
    logger = get_logger("refresh_db_ads")

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

    # Log startup
    logger.info("=" * 80)
    logger.info("DATABASE REFRESH FROM ADS STARTED")
    logger.info("=" * 80)
    logger.info(f"Run ID: {run_id}")
    logger.info(f"Makes: {', '.join(makes)}")
    logger.info(f"Years: {', '.join(map(str, years))}")
    logger.info(f"Log file: {log_file}")
    logger.info("=" * 80)

    # Print to console
    print("\n" + "=" * 70)
    print("DATABASE REFRESH FROM ADS")
    print("=" * 70)
    print(f"Makes: {', '.join(makes)}")
    print(f"Years: {', '.join(map(str, years))}")
    print(f"Log file: {log_file}")
    print("=" * 70)

    try:
        # Step 1: Initialize ADS service
        logger.info("\n[Step 1/4] Initializing ADS service...")
        print("\n[1/4] Initializing ADS service...")
        try:
            service = ADSService(pipeline_logger=pipeline_logger, dq_logger=dq_logger)
            logger.info("ADS service initialized successfully | Credentials loaded and client ready")
            print("      [OK] Credentials loaded and client initialized")
        except Exception as e:
            logger.error(f"FAILED to initialize ADS service | Error: {str(e)}")
            raise

        # Step 2: Archive current database
        logger.info("\n[Step 2/4] Archiving current database...")
        print("\n[2/4] Archiving current database...")
        try:
            db_path = Path(__file__).parent / "db" / "db_vehicle_models.csv"
            archive_dir = db_path.parent / "archive"
            archive_dir.mkdir(exist_ok=True)

            if db_path.exists():
                timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
                archive_path = archive_dir / f"db_vehicle_models.{timestamp}.csv"
                db_path.rename(archive_path)
                logger.info(f"Database archived | File: {archive_path.name} | Size: {archive_path.stat().st_size} bytes")
                print(f"      [OK] Archived to: {archive_path.name}")
            else:
                logger.debug("No existing database to archive")
                print("      [SKIP] No existing database to archive")
        except Exception as e:
            logger.error(f"FAILED to archive database | Error: {str(e)}")
            raise

        # Step 3: Fetch from ADS
        logger.info("\n[Step 3/4] Fetching data from ADS API...")
        print("\n[3/4] Fetching data from ADS (this may take a moment)...")
        try:
            logger.debug(f"Fetching for makes: {makes} | years: {years}")
            df = service.refresh_from_ads(makes=makes, years=years)
            logger.info(f"ADS fetch complete | Total records: {len(df)} | Columns: {len(df.columns)}")
            logger.debug(f"DataFrame columns: {list(df.columns)}")
            print(f"      [OK] Fetched {len(df)} configurations")
        except Exception as e:
            logger.error(f"FAILED to fetch from ADS | Error: {str(e)}")
            raise

        # Step 4: Save to CSV with validation and standardization
        logger.info("\n[Step 4/4] Saving to database with validation and standardization...")
        print("\n[4/4] Saving to database with validation...")
        try:
            logger.debug(f"Saving to: {db_path} | Key columns: Manufacturer, ModelYear, ModelNumber, Package")
            result = save_vehicle_models_to_csv(
                df,
                str(db_path),
                key_columns=["Manufacturer", "ModelYear", "ModelNumber", "Package"],
                dq_logger=dq_logger,
            )

            if result["success"]:
                logger.info(f"CSV save SUCCESS | Records saved: {result['records_saved']}")
                print(f"      [OK] {result['records_saved']} records saved")
                if result.get("duplicates"):
                    logger.info(f"Duplicates skipped: {result['duplicates']}")
                    print(f"      [INFO] {result['duplicates']} duplicates skipped")
                if result.get("invalid_records"):
                    logger.info(f"Invalid records skipped: {result['invalid_records']}")
                    print(f"      [INFO] {result['invalid_records']} invalid records skipped")
            else:
                error_msg = result.get('message', 'Unknown error')
                logger.error(f"CSV save FAILED | Error: {error_msg}")
                print(f"      [FAIL] {error_msg}")
                return 1
        except Exception as e:
            logger.error(f"FAILED to save to CSV | Error: {str(e)}")
            raise

        # Write DQ report
        try:
            logger.debug(f"Writing DQ report to: {dq_report_path}")
            dq_logger.write_dq_report(dq_report_path)
            logger.info(f"DQ report written | Path: {dq_report_path}")
        except Exception as e:
            logger.warning(f"Failed to write DQ report | Error: {str(e)}")

        # Summary and completion
        logger.info("\n" + "=" * 80)
        logger.info("DATABASE REFRESH COMPLETE - SUCCESS")
        logger.info("=" * 80)
        logger.info(f"Database location: {db_path}")
        logger.info(f"Records saved: {result['records_saved']}")
        logger.info(f"Total configurations fetched: {len(df)}")
        logger.info(f"Pipeline log path: {pipeline_log_path}")
        logger.info(f"DQ report path: {dq_report_path}")
        logger.info(f"Structured log file: {log_file}")
        logger.info("=" * 80)

        print("\n" + "=" * 70)
        print("[SUCCESS] DATABASE REFRESH COMPLETE")
        print("=" * 70)
        print(f"Database location: {db_path}")
        print(f"Records saved: {result['records_saved']}")
        print(f"Total configurations fetched: {len(df)}")
        print(f"Pipeline log: {pipeline_log_path}")
        print(f"DQ report: {dq_report_path}")
        print(f"Structured log: {log_file}")
        print("=" * 70 + "\n")

        return 0

    except Exception as e:
        logger.critical(f"FATAL ERROR | Database refresh aborted | Error: {str(e)}")
        import traceback
        logger.debug(f"Traceback:\n{traceback.format_exc()}")

        print(f"\n[ERROR] {e}")
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
