"""
Entry point for the Genesis OEM pipeline.

Usage (run from the project root directory):
    python accy_v2/run_genesis.py [path_to_excel_file]

If no path is provided, auto-discovers the most recent .xlsx in landing_zone/hyundai_genesis/
(shared with Hyundai pipeline, as both process the same source workbook).

Examples:
    python accy_v2/run_genesis.py
    python accy_v2/run_genesis.py "data/landing_zone/hyundai_genesis/Hyundai_Genesis_ACCY.xlsx"
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

from oems.genesis.pipeline.orchestrator import GenesisPipeline

CONFIG_DIR = accy_v2_dir / "oems" / "genesis" / "config"
DEFAULT_DATA_DIR = accy_v2_dir / "data" / "landing_zone" / "hyundai_genesis"


def main() -> None:
    if len(sys.argv) >= 2:
        file_path = sys.argv[1]
    else:
        # Auto-discover most recently modified .xlsx in the default data folder
        candidates = sorted(
            DEFAULT_DATA_DIR.glob("*.xlsx"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            print(f"No .xlsx files found in {DEFAULT_DATA_DIR}")
            print(f"Usage: python run_genesis.py <path_to_excel_file>")
            print(f"Or place a file in: {DEFAULT_DATA_DIR}")
            sys.exit(1)
        file_path = str(candidates[0])
        print(f"Using: {file_path}")

    if not Path(file_path).exists():
        print(f"Error: file not found — {file_path}")
        sys.exit(1)

    pipeline = GenesisPipeline()
    pipeline.run(file_path=file_path, config_root=str(CONFIG_DIR))


if __name__ == "__main__":
    main()
