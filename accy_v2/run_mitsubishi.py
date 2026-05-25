"""
Entry point for the Mitsubishi OEM pipeline.

Usage (run from the OEMAccessories/ directory):
    python run_mitsubishi.py [path_to_excel_file]

If no path is provided, auto-discovers the most recent .xlsx in data/landing_zone/mitsubishi/.

Examples:
    python run_mitsubishi.py
    python run_mitsubishi.py "data/landing_zone/mitsubishi/Accessory Guide - February26.xlsx"
"""

import sys
from pathlib import Path

# Ensure OEMAccessories/ is on the path so absolute imports (core.*, oems.*) resolve correctly
sys.path.insert(0, str(Path(__file__).parent))

from oems.mitsubishi.pipeline.orchestrator import MitsubishiPipeline

CONFIG_PATH = (
    Path(__file__).parent / "oems" / "mitsubishi" / "config" / "mitsubishi_config.json"
)
DEFAULT_DATA_DIR = Path(__file__).parent / "data" / "landing_zone" / "mitsubishi"


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
            print(f"Usage: python run_mitsubishi.py <path_to_excel_file>")
            print(f"Or place a file in: {DEFAULT_DATA_DIR}")
            sys.exit(1)
        file_path = str(candidates[0])
        print(f"Using: {file_path}")

    if not Path(file_path).exists():
        print(f"Error: file not found — {file_path}")
        sys.exit(1)

    pipeline = MitsubishiPipeline()
    pipeline.run(file_path=file_path, config_path=str(CONFIG_PATH))


if __name__ == "__main__":
    main()
