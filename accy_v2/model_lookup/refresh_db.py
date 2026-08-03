#!/usr/bin/env python
"""
Simple database refresh command.
Run from terminal: python refresh_db.py
"""
import sys
from pathlib import Path
from datetime import datetime

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))  # accy_v2
sys.path.insert(0, str(Path(__file__).parent))  # model_lookup

from engine import load_env, create_engine_from_env
from models.manufacture_module import batch_save_manufacturer_models

def refresh_database():
    """Refresh the entire vehicle database."""

    print("\n" + "=" * 70)
    print("DATABASE REFRESH")
    print("=" * 70)

    try:
        # Load environment and create engine
        print("\n[1/4] Connecting to OEM database...")
        load_env()
        engine = create_engine_from_env()
        print("      [OK] Connected")

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

        # Create fresh database with headers
        print("\n[3/4] Creating fresh database...")
        headers = "VehicleID,Manufacturer,ModelNumber,ModelName,Year,Description,Category,Subcategory,VehicleType,FuelType,Transmission,Drivetrrain,Seating,Wheelbase,Length,Width,Height,Weight,MSRP"
        db_path.write_text(headers, encoding="utf-8")
        print("      [OK] Fresh database created")

        # Run batch ingestion
        print("\n[4/4] Ingesting OEM data (this may take a minute)...")
        manufactures = ["Hyundai", "Honda", "Kia", "Mazda", "Genesis", "Mitsubishi", "Volkswagen"]
        batch_save_manufacturer_models(engine, manufactures)
        print("      [OK] Ingestion complete")

        # Summary
        print("\n" + "=" * 70)
        print("[SUCCESS] DATABASE REFRESH SUCCESSFUL")
        print("=" * 70)
        print(f"Database location: {db_path}")
        print(f"Rows added: Check the database file")
        print("=" * 70 + "\n")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        print("=" * 70 + "\n")
        sys.exit(1)

if __name__ == "__main__":
    refresh_database()
