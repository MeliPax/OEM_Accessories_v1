"""
Entry point for the Hyundai OEM pipeline (including Genesis brand routing).

Usage (run from the project root directory):
    python accy_v2/run_hyundai.py [path_to_excel_file]

If no path is provided, auto-discovers the most recent .xlsx in landing_zone/hyundai/.

Examples:
    python accy_v2/run_hyundai.py
    python accy_v2/run_hyundai.py "landing_zone/2026/Hyundia/2025-09/Hyundai_ACCY_2025-09.xlsx"
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

from oems.hyundai.pipeline.orchestrator import HyundaiPipeline

CONFIG_PATH = (
    accy_v2_dir / "oems" / "hyundai" / "config" / "hyundai_config.yaml"
)
DEFAULT_DATA_DIR = accy_v2_dir / "data" / "landing_zone" / "hyundai"


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
            # Try common landing zone path with year subdirs
            alt_path = project_root / "landing_zone" / "2026" / "Hyundia"
            alt_candidates = sorted(
                alt_path.glob("**/*.xlsx"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if alt_candidates:
                file_path = str(alt_candidates[0])
                print(f"Using (from landing_zone): {file_path}")
            else:
                print(f"No .xlsx files found in {DEFAULT_DATA_DIR}")
                print(f"Usage: python run_hyundai.py <path_to_excel_file>")
                print(f"Or place a file in: {DEFAULT_DATA_DIR}")
                sys.exit(1)
        else:
            file_path = str(candidates[0])
            print(f"Using: {file_path}")

    if not Path(file_path).exists():
        print(f"Error: file not found — {file_path}")
        sys.exit(1)

    pipeline = HyundaiPipeline()
    pipeline.run(file_path=file_path, config_path=str(CONFIG_PATH))


if __name__ == "__main__":
    main()
