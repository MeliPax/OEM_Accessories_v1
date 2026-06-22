"""
Simple command to populate vehicle database by manufacturer.

Usage:
    python populate_vehicle_database.py Mitsubishi
    python populate_vehicle_database.py Mazda Honda Toyota
    python populate_vehicle_database.py --list
    python populate_vehicle_database.py --help

Examples:
    python populate_vehicle_database.py Mitsubishi
    python populate_vehicle_database.py Mazda
    python populate_vehicle_database.py Mitsubishi Honda Mazda
"""

import sys
from pathlib import Path
from datetime import datetime


def setup_paths():
    """Setup Python paths for imports."""
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root / "model_lookup"))
    sys.path.insert(0, str(project_root))
    return project_root


def list_manufacturers():
    """List all available manufacturers in database."""
    from model_lookup.engine import load_env, create_engine_from_env
    from sqlalchemy import text

    try:
        load_env()
        engine = create_engine_from_env()

        with engine.begin() as conn:
            result = conn.execute(
                text("""
                    SELECT DISTINCT ManufacturerName
                    FROM Manufacturer
                    WHERE ManufacturerStatus = 0
                    ORDER BY ManufacturerName
                """)
            )
            manufacturers = [row[0] for row in result]

        if manufacturers:
            print("\nAvailable manufacturers in database:")
            for mfg in manufacturers:
                print(f"  - {mfg}")
            print()
            return manufacturers
        else:
            print("\nNo manufacturers found in database")
            return []

    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}")
        print("Make sure .env file is configured with database credentials")
        return []


def populate_database(manufacturers, csv_path="model_lookup/db/db_vehicle_models.csv"):
    """Populate vehicle database for given manufacturers."""
    from model_lookup.engine import load_env, create_engine_from_env
    from model_lookup.models.manufacture_module import batch_save_manufacturer_models

    try:
        # Load environment
        load_env()
        engine = create_engine_from_env()

        print("\n" + "="*80)
        print("VEHICLE DATABASE POPULATION")
        print("="*80)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"CSV Path: {csv_path}")
        print(f"Manufacturers: {', '.join(manufacturers)}")
        print("="*80 + "\n")

        # Run batch save
        results = batch_save_manufacturer_models(engine, manufacturers, csv_path=csv_path)

        # Print summary
        print("\n" + "="*80)
        print("POPULATION SUMMARY")
        print("="*80)

        total_processed = results["summary"]["total_processed"]
        total_saved = results["summary"]["total_saved"]
        total_duplicates = results["summary"]["total_duplicates"]
        total_invalid = results["summary"]["total_invalid"]
        errors = results["summary"]["errors"]

        print(f"\nTotal records processed: {total_processed}")
        print(f"Records saved to CSV: {total_saved}")
        print(f"Duplicates (skipped): {total_duplicates}")
        print(f"Invalid records: {total_invalid}")

        # Per-manufacturer results
        print("\nPer-manufacturer results:")
        for make, result in results.get("manufacturers", {}).items():
            status = result.get("status", "unknown")
            if status == "success":
                print(
                    f"  ✓ {make}: {result.get('records_saved', 0)} saved, "
                    f"{result.get('duplicates', 0)} duplicates"
                )
            elif status == "no_data":
                print(f"  ⚠ {make}: No bulletin data found")
            elif status == "no_valid_records":
                print(f"  ⚠ {make}: No valid records in bulletin")
            else:
                print(f"  ✗ {make}: {result.get('message', 'Unknown error')}")

        # Show errors if any
        if errors:
            print(f"\nErrors ({len(errors)}):")
            for error in errors:
                print(f"  - {error}")

        # Final status
        print("\n" + "="*80)
        if not errors and total_saved > 0:
            print("✓ DATABASE POPULATION SUCCESSFUL")
            print(f"✓ CSV file ready: {csv_path}")
        elif not errors:
            print("⚠ No new records were saved (may be all duplicates)")
        else:
            print("✗ DATABASE POPULATION HAD ERRORS")
            print("Check messages above and retry")
        print("="*80 + "\n")

        return True

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    setup_paths()

    # Handle help
    if len(sys.argv) < 2 or "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        sys.exit(0)

    # Handle list
    if "--list" in sys.argv:
        list_manufacturers()
        sys.exit(0)

    # Get manufacturers from args
    manufacturers = [arg for arg in sys.argv[1:] if not arg.startswith("-")]

    if not manufacturers:
        print(__doc__)
        print("ERROR: Please specify at least one manufacturer")
        sys.exit(1)

    # Validate manufacturers (optional - just show warning)
    available = list_manufacturers()
    if available:
        for mfg in manufacturers:
            if mfg not in available:
                print(f"⚠ Warning: '{mfg}' not found in database")
                print(f"   Available: {', '.join(available)}")

    # Populate
    success = populate_database(manufacturers)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
