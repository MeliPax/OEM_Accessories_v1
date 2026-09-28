#!/usr/bin/env python3
"""Test Honda Step 1 directly"""

import pandas as pd
from pathlib import Path
import traceback
import sys

sys.path.insert(0, str(Path(__file__).parent / "accy_v2"))

from accy_v2.oems.honda.pipeline.orchestrator import HondaPipeline
from accy_v2.core.config_loader_v2 import ModularConfigLoader
from accy_v2.core.helpers.dq_logger import DQLogger
from accy_v2.core.helpers.pipeline_logger import PipelineLogger

# Set up file path
file_path = Path(__file__).parent / "accy_v2/data/landing_zone/honda/may_2026/CVIC5D.xlsx"
config_root = Path(__file__).parent / "accy_v2/oems/honda/config"

print(f"File: {file_path}")
print(f"Config: {config_root}\n")

if not file_path.exists():
    print(f"[ERROR] File not found: {file_path}")
    exit(1)

try:
    # Load config
    print("Loading config...")
    config_loader = ModularConfigLoader("honda", Path(config_root))
    config = config_loader.load_all()
    print(f"Config loaded successfully")
    print(f"Config keys: {list(config.keys())}\n")

    # Create pipeline
    print("Creating Honda pipeline...")
    pipeline = HondaPipeline()
    pipeline._current_file_path = str(file_path)

    # Load file
    print(f"Loading file...")
    dfs = pipeline.load_file(str(file_path))
    print(f"Sheets loaded: {list(dfs.keys())}\n")

    # Set up loggers
    import uuid
    run_id = str(uuid.uuid4())[:8]
    dq_logger = DQLogger(run_id, str(file_path))
    log_path = Path(__file__).parent / "accy_v2/output/pipeline_logs/honda"
    log_path.mkdir(parents=True, exist_ok=True)
    pipeline_logger = PipelineLogger(run_id, str(log_path))

    # Run Step 1
    for sheet_name, df in dfs.items():
        print(f"\n{'='*80}")
        print(f"Processing sheet: {sheet_name}")
        print(f"{'='*80}")

        meta_data = {"sheet_name": sheet_name}

        print(f"Running Step 1...")
        working_df = pipeline.run_step1_validation(df, config, meta_data, dq_logger, pipeline_logger)

        print(f"\n[OK] Step 1 complete for {sheet_name}")
        print(f"Sections detected: {meta_data.get('sections_detected', 0)}")
        print(f"Working DF shape: {working_df.shape}")

except Exception as e:
    print(f"\n[ERROR] {str(e)}")
    print("\n" + "="*80)
    print("Full traceback:")
    print("="*80)
    traceback.print_exc()
    exit(1)

print("\n[OK] All sheets processed successfully")
