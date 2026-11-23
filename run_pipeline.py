#!/usr/bin/env python3
"""
Run the accessory pipeline end-to-end with actual data.

This script processes files from landing_zone and produces output files with model numbers.
Uses actual pipeline data flow - no test files created.

Usage:
    python run_pipeline.py mitsubishi                                                     (process single file)
    python run_pipeline.py mitsubishi --batch                                            (process all files in batch mode)
    python run_pipeline.py mitsubishi "accy_v2/data/landing_zone/mitsubishi/2026_Outlander_ES_EN.xlsx"
    python run_pipeline.py mazda
    python run_pipeline.py hyundai
    python run_pipeline.py genesis
    python run_pipeline.py honda                                                          (process single file)
    python run_pipeline.py honda --batch                                                 (process all files in batch)

Each OEM reads its own landing zone folder: accy_v2/data/landing_zone/<oem>/
(hyundai/ and genesis/ each hold a copy of the Hyundai/Genesis workbook; each pipeline reads its own sheet).
Batch mode adds source_file column to melted output for multi-file traceability.
"""

import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

# Add project root to path so imports work
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "accy_v2"))

# Note: OEM imports are now done lazily in get_pipeline_class() to avoid
# import errors from unrelated OEM modules that may have issues


def get_landing_zone_dir(oem: str) -> str:
    """Map OEM name to its landing zone directory: accy_v2/data/landing_zone/<oem>/."""
    return oem.lower()


def get_landing_zone_files(oem: str, file_path: str = None, batch_mode: bool = False) -> list:
    """Get files from landing_zone directory for specified OEM.

    Args:
        oem: OEM name (honda, mazda, etc.)
        file_path: Specific file to process (overrides batch_mode)
        batch_mode: If True, return ALL files; if False, return most recent

    Returns:
        List of file paths to process
    """
    project_root = Path(__file__).parent
    landing_zone_dir = get_landing_zone_dir(oem)

    # Try multiple landing zone paths (modern first, then legacy)
    possible_paths = [
        project_root / "landing_zone" / "2026" / landing_zone_dir.title(),  # landing_zone/2026/Honda
        project_root / "accy_v2" / "data" / "landing_zone" / landing_zone_dir,  # Legacy path
        project_root / "landing_zone" / landing_zone_dir,  # Flat landing_zone
    ]

    landing_zone = None
    for path in possible_paths:
        if path.exists():
            landing_zone = path
            break

    if landing_zone is None:
        raise FileNotFoundError(f"Landing zone directory not found for {landing_zone_dir}. Tried: {possible_paths}")

    if not landing_zone.exists():
        raise FileNotFoundError(f"Landing zone directory not found: {landing_zone}")

    if file_path:
        # Specific file requested
        file_to_process = project_root / file_path
        if not file_to_process.exists():
            raise FileNotFoundError(f"File not found: {file_to_process}")
        return [file_to_process]

    # Auto-discover files (recursive, handles subdirectories)
    excel_files = sorted(landing_zone.glob("**/*.xlsx"))
    csv_files = sorted(landing_zone.glob("**/*.csv"))
    all_files = excel_files + csv_files

    if not all_files:
        raise FileNotFoundError(
            f"No Excel/CSV files found in {landing_zone}"
        )

    # Return ALL files if batch mode, otherwise the file added to the folder last
    # (not the last modified: copying keeps the old modified date)
    if batch_mode:
        return all_files
    from core.helpers.landing_zone import latest_added
    return [latest_added(all_files)]


def get_pipeline_class(oem: str):
    """Get the appropriate pipeline class for the OEM.

    Uses lazy loading to avoid import errors from unrelated OEM modules.
    """
    oem_lower = oem.lower()

    if oem_lower == "mitsubishi":
        try:
            from accy_v2.oems.mitsubishi.orchestrator import MitsubishiPipeline
            return MitsubishiPipeline
        except ImportError as e:
            raise ImportError(f"Mitsubishi pipeline import failed: {e}. Please check accy_v2/oems/mitsubishi/")
    elif oem_lower == "mazda":
        try:
            from accy_v2.oems.mazda.orchestrator import MazdaPipeline
            return MazdaPipeline
        except ImportError as e:
            raise ImportError(f"Mazda pipeline import failed: {e}. Please check accy_v2/oems/mazda/")
    elif oem_lower == "hyundai":
        try:
            from accy_v2.oems.hyundai.orchestrator import HyundaiPipeline
            return HyundaiPipeline
        except ImportError as e:
            raise ImportError(f"Hyundai pipeline import failed: {e}. Please check accy_v2/oems/hyundai/")
    elif oem_lower == "genesis":
        try:
            from accy_v2.oems.genesis.orchestrator import GenesisPipeline
            return GenesisPipeline
        except ImportError as e:
            raise ImportError(f"Genesis pipeline import failed: {e}. Please check accy_v2/oems/genesis/")
    elif oem_lower == "honda":
        try:
            from accy_v2.oems.honda.orchestrator import HondaPipeline
            return HondaPipeline
        except ImportError as e:
            raise ImportError(f"Honda pipeline import failed: {e}. Please check accy_v2/oems/honda/")
    else:
        raise ValueError(f"Unknown OEM: {oem}. Supported: mitsubishi, mazda, hyundai, genesis, honda")


def get_config_root(oem: str) -> str:
    """Get config root directory for OEM (supports modular config structure)."""
    project_root = Path(__file__).parent
    oem_lower = oem.lower()
    config_root = project_root / f"accy_v2/oems/{oem_lower}/config"

    if not config_root.exists():
        raise FileNotFoundError(f"Config directory not found: {config_root}")

    # Check that pipeline.yaml exists (required file in modular structure)
    pipeline_yaml = config_root / "pipeline.yaml"
    if not pipeline_yaml.exists():
        raise FileNotFoundError(f"pipeline.yaml not found in {config_root}")

    return str(config_root)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    oem = sys.argv[1]

    # Parse arguments: check for --batch flag or specific file
    batch_mode = False
    file_path = None

    for arg in sys.argv[2:]:
        if arg == "--batch":
            batch_mode = True
        elif not arg.startswith("-"):
            file_path = arg

    print("\n" + "=" * 80)
    print(f"PIPELINE: {oem.upper()}")
    if batch_mode:
        print("MODE: BATCH PROCESSING (multiple files)")
    else:
        print("MODE: SINGLE FILE")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    try:
        # Get files to process
        files = get_landing_zone_files(oem, file_path, batch_mode=batch_mode)
        print(f"Files to process: {len(files)}")
        for f in files:
            print(f"  - {f.relative_to(Path.cwd())}")
        print()

        # Get pipeline and config
        pipeline_class = get_pipeline_class(oem)
        config_root = get_config_root(oem)
        pipeline = pipeline_class()

        print(f"Config: {config_root}\n")

        # Process each file
        for file_to_process in files:
            print(f"Processing: {file_to_process.name}")
            print("-" * 80)
            try:
                pipeline.run(str(file_to_process), config_root)
                print(f"[OK] Pipeline completed for {file_to_process.name}\n")
            except Exception as e:
                print(f"[ERROR] Pipeline failed: {str(e)}\n")
                raise

        print("=" * 80)
        print("[OK] PIPELINE EXECUTION COMPLETE")
        print("=" * 80)

        if batch_mode:
            print(f"\nBatch Summary:")
            print(f"  - Files processed: {len(files)}")
            print(f"  - Mode: Batch (all files with source_file tracking in FlatData sheets)")

        print("\nNext steps:")
        print(f"1. Check output files in: accy_v2/output/ready_to_upload/{oem.lower()}/")
        print(f"2. Review DQ report in: accy_v2/output/dq_reports/{oem.lower()}/")
        print(f"3. Check pipeline log in: accy_v2/output/pipeline_logs/{oem.lower()}/")
        print()

    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
