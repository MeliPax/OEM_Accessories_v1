"""
Entry point for the Mazda OEM pipeline.

Usage (run from the OEMAccessories/ directory):
    python run_mazda.py [path_to_csv_file]

If no path is provided, auto-discovers the most recent .csv in data/landing_zone/mazda/.

Examples:
    python run_mazda.py
    python run_mazda.py "data/landing_zone/mazda/Mazda - 20251205-Mazda accessory feed.csv"
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from oems.mazda.pipeline.orchestrator import MazdaPipeline

CONFIG_PATH = (
    Path(__file__).parent / "oems" / "mazda" / "config" / "mazda_config.json"
)
DEFAULT_DATA_DIR = Path(__file__).parent / "data" / "landing_zone" / "mazda"


def main() -> None:
    if len(sys.argv) >= 2:
        file_path = sys.argv[1]
    else:
        # Auto-discover the most recent .csv file in the default directory
        csv_files = sorted(DEFAULT_DATA_DIR.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not csv_files:
            print(f"ERROR: No .csv files found in {DEFAULT_DATA_DIR}")
            sys.exit(1)
        file_path = str(csv_files[0])
        print(f"Auto-discovered: {file_path}")

    try:
        pipeline = MazdaPipeline()
        pipeline.run(file_path, str(CONFIG_PATH))
    except Exception as exc:
        print(f"Pipeline failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
