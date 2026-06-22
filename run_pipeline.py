#!/usr/bin/env python3
"""
Run the accessory pipeline end-to-end with actual data.

This script processes files from landing_zone and produces output files with model numbers.
Uses actual pipeline data flow - no test files created.

Usage:
    python run_pipeline.py mitsubishi
    python run_pipeline.py mitsubishi "accy_v2/data/landing_zone/mitsubishi/2026_Outlander_ES_EN.xlsx"
    python run_pipeline.py mazda
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path so imports work
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "accy_v2"))
sys.path.insert(0, str(project_root / "model_lookup"))

from accy_v2.oems.mitsubishi.pipeline.orchestrator import MitsubishiPipeline
from accy_v2.oems.mazda.pipeline.orchestrator import MazdaPipeline


def get_landing_zone_files(oem: str, file_path: str = None) -> list:
    """Get files from landing_zone directory for specified OEM."""
    project_root = Path(__file__).parent
    landing_zone = project_root / "accy_v2" / "data" / "landing_zone" / oem.lower()

    if not landing_zone.exists():
        raise FileNotFoundError(f"Landing zone directory not found: {landing_zone}")

    if file_path:
        # Specific file requested
        file_to_process = project_root / file_path
        if not file_to_process.exists():
            raise FileNotFoundError(f"File not found: {file_to_process}")
        return [file_to_process]

    # Auto-discover files
    excel_files = sorted(landing_zone.glob("*.xlsx"))
    csv_files = sorted(landing_zone.glob("*.csv"))
    all_files = excel_files + csv_files

    if not all_files:
        raise FileNotFoundError(
            f"No Excel/CSV files found in {landing_zone}"
        )

    # Return most recent file
    return [max(all_files, key=lambda f: f.stat().st_mtime)]


def get_pipeline_class(oem: str):
    """Get the appropriate pipeline class for the OEM."""
    oem_lower = oem.lower()

    if oem_lower == "mitsubishi":
        return MitsubishiPipeline
    elif oem_lower == "mazda":
        return MazdaPipeline
    else:
        raise ValueError(f"Unknown OEM: {oem}. Supported: mitsubishi, mazda")


def get_config_path(oem: str) -> str:
    """Get config file path for OEM."""
    project_root = Path(__file__).parent
    oem_lower = oem.lower()
    config_path = project_root / f"accy_v2/oems/{oem_lower}/config/{oem_lower}_config.json"

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    return str(config_path)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    oem = sys.argv[1]
    file_path = sys.argv[2] if len(sys.argv) > 2 else None

    print("\n" + "=" * 80)
    print(f"PIPELINE TEST: {oem.upper()}")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    try:
        # Get files to process
        files = get_landing_zone_files(oem, file_path)
        print(f"Files to process: {len(files)}")
        for f in files:
            print(f"  - {f.relative_to(Path.cwd())}")
        print()

        # Get pipeline and config
        pipeline_class = get_pipeline_class(oem)
        config_path = get_config_path(oem)
        pipeline = pipeline_class()

        print(f"Config: {config_path}\n")

        # Process each file
        for file_to_process in files:
            print(f"Processing: {file_to_process.name}")
            print("-" * 80)
            try:
                pipeline.run(str(file_to_process), config_path)
                print(f"[OK] Pipeline completed for {file_to_process.name}\n")
            except Exception as e:
                print(f"[ERROR] Pipeline failed: {str(e)}\n")
                raise

        print("=" * 80)
        print("[OK] PIPELINE EXECUTION COMPLETE")
        print("=" * 80)
        print("\nNext steps:")
        print("1. Check output files in: accy_v2/output/ready_to_upload/{oem}/")
        print("2. Review DQ report in: accy_v2/output/dq_reports/{oem}/")
        print("3. Check pipeline log in: accy_v2/output/pipeline_logs/{oem}/")
        print()

    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
