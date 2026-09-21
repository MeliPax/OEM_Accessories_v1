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

# Add project root to path for proper package imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # project root

from accy_v2.model_lookup.chrome_api.service import ADSService
from accy_v2.model_lookup.models.manufacture_module import save_vehicle_models_to_csv
from accy_v2.core.helpers.pipeline_logger import PipelineLogger
from accy_v2.core.helpers.dq_logger import DQLogger
from accy_v2.model_lookup.logging_config import setup_logging, get_logger


def refresh_from_ads(makes=None, years=None, no_archive=False):
    """
    Fetch vehicle data from ADS API and save to CSV.

    Fetches vehicle data from AutoData Solutions API and saves to CSV with:
      - Engine type extraction (using ENGINE_TYPE keywords from classification)
      - Translator-based keyword normalization
      - Comprehensive logging (console + file)
      - Optional database archival before refresh
      - Deduplication and standardization

    Args:
        makes: List of makes to fetch (default: all available)
        years: List of years to fetch (default: [2024, 2025, 2026])
        no_archive: If True, skip archival step and append to existing data.
                   If False (default), archive current DB before refresh (destructive).

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
    mode_str = "APPEND MODE (no archive)" if no_archive else "REFRESH MODE (with archive)"
    logger.info("=" * 80)
    logger.info(f"DATABASE REFRESH FROM ADS STARTED ({mode_str})")
    logger.info("=" * 80)
    logger.info(f"Run ID: {run_id}")
    logger.info(f"Makes: {', '.join(makes)}")
    logger.info(f"Years: {', '.join(map(str, years))}")
    logger.info(f"Archive mode: {'disabled' if no_archive else 'enabled'}")
    logger.info(f"Log file: {log_file}")
    logger.info("=" * 80)

    # Print to console
    print("\n" + "=" * 70)
    print(f"DATABASE REFRESH FROM ADS ({mode_str})")
    print("=" * 70)
    print(f"Makes: {', '.join(makes)}")
    print(f"Years: {', '.join(map(str, years))}")
    print(f"Archive: {'disabled (will append to existing data)' if no_archive else 'enabled (will replace existing data)'}")
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

        # Get db_path early (used by both archive and save steps)
        db_path = Path(__file__).parent / "db" / "db_vehicle_models.csv"

        # Step 2: Archive current database (optional, based on no_archive flag)
        if not no_archive:
            logger.info("\n[Step 2/4] Archiving current database...")
            print("\n[2/4] Archiving current database...")
            try:
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
            step_fetch = 3
            step_save = 4
            total_steps = 4
        else:
            logger.info("\n[Step 2/3] (Archival skipped - append mode enabled)")
            print("\n[2/3] (Archival skipped - will append to existing data)")
            step_fetch = 2
            step_save = 3
            total_steps = 3

        # Step 3 or 2: Fetch from ADS
        logger.info(f"\n[Step {step_fetch}/{total_steps}] Fetching data from ADS API...")
        print(f"\n[{step_fetch}/{total_steps}] Fetching data from ADS (this may take a moment)...")
        try:
            logger.debug(f"Fetching for makes: {makes} | years: {years}")
            df = service.refresh_from_ads(makes=makes, years=years)
            logger.info(f"ADS fetch complete | Total records: {len(df)} | Columns: {len(df.columns)}")
            logger.debug(f"DataFrame columns: {list(df.columns)}")
            print(f"      [OK] Fetched {len(df)} configurations")
        except Exception as e:
            logger.error(f"FAILED to fetch from ADS | Error: {str(e)}")
            raise

        # Step 4 or 3: Save to CSV with validation and standardization
        logger.info(f"\n[Step {step_save}/{total_steps}] Saving to database with validation and standardization...")
        print(f"\n[{step_save}/{total_steps}] Saving to database with validation...")
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
        completion_msg = "DATABASE REFRESH COMPLETE - SUCCESS" if not no_archive else "DATABASE APPEND COMPLETE - SUCCESS"
        logger.info("\n" + "=" * 80)
        logger.info(completion_msg)
        logger.info("=" * 80)
        logger.info(f"Mode: {'append (no archive)' if no_archive else 'refresh (with archive)'}")
        logger.info(f"Database location: {db_path}")
        logger.info(f"Records saved: {result['records_saved']}")
        logger.info(f"Total configurations fetched: {len(df)}")
        logger.info(f"Pipeline log path: {pipeline_log_path}")
        logger.info(f"DQ report path: {dq_report_path}")
        logger.info(f"Structured log file: {log_file}")
        logger.info("=" * 80)

        print("\n" + "=" * 70)
        print(f"[SUCCESS] {completion_msg}")
        print("=" * 70)
        print(f"Mode: {'append (no archive)' if no_archive else 'refresh (with archive)'}")
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
  # Full refresh (archives current DB, then replaces with new data)
  python refresh_db_ads.py --makes Hyundai Mazda Genesis

  # Targeted append (adds new makes without archiving/replacing)
  python refresh_db_ads.py --makes Mitsubishi --no-archive

  # Specific makes and years with archive
  python refresh_db_ads.py --makes Hyundai --years 2024 2025 2026

  # Specific makes and years without archive (append mode)
  python refresh_db_ads.py --makes Mitsubishi --years 2023 2024 2025 --no-archive
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
    parser.add_argument(
        "--no-archive",
        action="store_true",
        help="Skip database archival; append new data to existing database instead of replacing it. "
             "Use this for targeted updates (e.g., add Mitsubishi without touching Hyundai data).",
    )

    args = parser.parse_args()
    sys.exit(refresh_from_ads(makes=args.makes, years=args.years, no_archive=args.no_archive))
