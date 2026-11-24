"""
Entry point for the Mazda OEM pipeline.

Usage (run from the project root directory):
    python accy_v2/run_mazda.py [path_to_input_file]

If no path is provided, uses the standard pick: the .xlsx or .csv file added to
accy_v2/data/landing_zone/mazda/ last (same as `python run_pipeline.py mazda`).

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

from core.helpers.landing_zone import latest_input_file
from oems.mazda.pipeline.orchestrator import MazdaPipeline

CONFIG_DIR = accy_v2_dir / "oems" / "mazda" / "config"
DEFAULT_DATA_DIR = accy_v2_dir / "data" / "landing_zone" / "mazda"


def main() -> None:
    if len(sys.argv) >= 2:
        file_path = sys.argv[1]
    else:
        # Standard pick: the .xlsx/.csv file added to the landing zone folder last
        try:
            file_path = str(latest_input_file(DEFAULT_DATA_DIR))
        except FileNotFoundError as exc:
            print(f"ERROR: {exc}")
            sys.exit(1)
        print(f"Auto-discovered: {file_path}")

    try:
        pipeline = MazdaPipeline()
        pipeline.run(file_path, str(CONFIG_DIR))
    except Exception as exc:
        print(f"Pipeline failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
