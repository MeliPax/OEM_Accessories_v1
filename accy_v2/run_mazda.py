"""
Entry point for the Mazda OEM pipeline.

Usage (run from the project root directory):
    python accy_v2/run_mazda.py [path_to_csv_file]

If no path is provided, auto-discovers the most recent .csv in landing_zone/mazda/.

Examples:
    python accy_v2/run_mazda.py
    python accy_v2/run_mazda.py "landing_zone/mazda/Mazda - 20251205-Mazda accessory feed.csv"
"""

import sys
from pathlib import Path

# Add directories to path for imports
accy_v2_dir = Path(__file__).parent
project_root = accy_v2_dir.parent
model_lookup_dir = project_root / "model_lookup"

sys.path.insert(0, str(accy_v2_dir))      # For core.*, oems.* imports
sys.path.insert(0, str(model_lookup_dir)) # For model_lookup internal imports
sys.path.insert(0, str(project_root))     # For model_lookup package import

from oems.mazda.pipeline.orchestrator import MazdaPipeline

CONFIG_PATH = (
    accy_v2_dir / "oems" / "mazda" / "config" / "mazda_config.json"
)
DEFAULT_DATA_DIR = accy_v2_dir / "data" / "landing_zone" / "mazda"


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
