#!/usr/bin/env python
"""
Quick setup script to enable logging in the Honda pipeline.
Run this before executing the pipeline to add logging instrumentation.

Usage:
    python honda_logs/setup_logging.py
"""

import sys
from pathlib import Path

def setup_logging():
    """Setup and instrument the notebook with logging"""

    print("="*100)
    print("HONDA PIPELINE LOGGING SETUP")
    print("="*100)

    # Check notebook exists
    script_dir = Path(__file__).parent.parent / "scripts"
    notebook_path = script_dir / "honda_processor.ipynb"

    if not notebook_path.exists():
        print(f"\nERROR: Notebook not found at {notebook_path}")
        return False

    print(f"\nFound notebook: {notebook_path}")

    # Check if logging is already added
    with open(notebook_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    if 'from honda_logs import' in content:
        print("\nLogging already enabled in notebook!")
        print("\nYou can now:")
        print("1. Run the pipeline in the notebook")
        print("2. Check honda_logs/ directory for execution logs")
        print("3. Open honda_logs/<timestamp>/pipeline.log to see detailed trace")
        return True

    # Attempt to add logging
    print("\nAdding logging instrumentation to notebook...")

    try:
        from .instrument_notebook import instrument_notebook
        instrument_notebook(str(notebook_path))

        print("\n" + "="*100)
        print("SUCCESS: Logging has been enabled!")
        print("="*100)
        print("\nNext steps:")
        print("1. Open the notebook: scripts/honda_processor.ipynb")
        print("2. Run all cells to execute the pipeline")
        print("3. Check honda_logs/<timestamp>/ for execution logs")
        print("\nLog files will include:")
        print("  - pipeline.log     : Full execution trace")
        print("  - steps.json       : Pipeline steps with timing")
        print("  - data_checks.json : Data quality metrics")
        print("  - errors.json      : Any errors encountered")

        return True

    except Exception as e:
        print(f"\nERROR during instrumentation: {e}")
        print("\nYou can manually add logging by:")
        print("1. See honda_logs/README.md for instructions")
        print("2. Alternatively, run the pipeline now and check for issues")
        return False


if __name__ == '__main__':
    success = setup_logging()
    sys.exit(0 if success else 1)
