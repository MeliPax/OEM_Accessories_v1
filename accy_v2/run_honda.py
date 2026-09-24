#!/usr/bin/env python
"""
Honda Pipeline Orchestrator

Entry point for running the Honda accessory pipeline.

Usage:
  python run_honda.py [options]

Options:
  --input DIR           Input directory (default: landing_zone/honda/)
  --output DIR          Output directory (default: output/)
  --batch-id ID         Batch ID (default: auto-generated from timestamp)
  --dry-run             Don't write outputs (testing mode)
  --help                Show this message

Example:
  python run_honda.py --input landing_zone/honda/2026/2026-09/
  python run_honda.py --dry-run
"""

import sys
import argparse
from pathlib import Path

from accy_v2.oems.honda.orchestrator import HondaPipeline


def main():
    parser = argparse.ArgumentParser(
        description="Honda Accessory Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example: python run_honda.py --input landing_zone/honda/2026/2026-09/",
    )

    parser.add_argument(
        "--input",
        default="landing_zone/honda/",
        help="Input directory (default: landing_zone/honda/)",
    )
    parser.add_argument(
        "--output",
        default="output/",
        help="Output directory (default: output/)",
    )
    parser.add_argument(
        "--batch-id",
        default=None,
        help="Batch ID (default: auto-generated from timestamp)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't write outputs (testing mode)",
    )

    args = parser.parse_args()

    try:
        pipeline = HondaPipeline(
            input_dir=args.input,
            output_dir=args.output,
            batch_id=args.batch_id,
            dry_run=args.dry_run,
        )

        results = pipeline.run()

        print("\n" + "=" * 60)
        print("Honda Pipeline Execution Results")
        print("=" * 60)
        for key, value in results.items():
            print(f"{key:.<40} {value}")
        print("=" * 60 + "\n")

        return 0

    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
