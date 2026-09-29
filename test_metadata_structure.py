#!/usr/bin/env python3
"""Verify metadata structure contains row metrics"""

import pandas as pd
from pathlib import Path
from accy_v2.oems.honda.pipeline import step1_validation

# Load Honda data
file_path = Path("accy_v2/data/landing_zone/honda/may_2026/CVIC5D.xlsx")
en_df = pd.read_excel(file_path, sheet_name="26MY_CIV5D_APP_EN", header=None)

# Load config
import yaml
with open("accy_v2/oems/honda/config/pipeline.yaml") as f:
    config = yaml.safe_load(f)

# Mock loggers
from accy_v2.core.helpers.dq_logger import DQLogger
from accy_v2.core.helpers.pipeline_logger import PipelineLogger

dq_logger = DQLogger()
pipeline_logger = PipelineLogger()

# Run Step 1
meta_data = {
    "file_path": str(file_path),
    "sheet_name": "26MY_CIV5D_APP_EN",
}

working_df, updated_meta = step1_validation.run(
    en_df, config, meta_data, dq_logger, pipeline_logger
)

print("=" * 80)
print("METADATA STRUCTURE - Row Metrics per Section")
print("=" * 80)

if "row_metrics_per_section" in updated_meta:
    row_metrics = updated_meta["row_metrics_per_section"]
    for section_name, metrics in row_metrics.items():
        print(f"\n{section_name}:")
        for key, value in metrics.items():
            print(f"  {key}: {value}")
else:
    print("ERROR: 'row_metrics_per_section' not found in metadata!")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
total_sections = len(updated_meta.get("row_metrics_per_section", {}))
total_valid = sum(m["valid_data_rows"] for m in updated_meta.get("row_metrics_per_section", {}).values())
total_empty = sum(m["empty_rows"] for m in updated_meta.get("row_metrics_per_section", {}).values())
total_pub = sum(m["publishing_rows"] for m in updated_meta.get("row_metrics_per_section", {}).values())

print(f"Sections: {total_sections}")
print(f"Total valid data rows (all sections): {total_valid}")
print(f"Total empty rows (all sections): {total_empty}")
print(f"Total publishing rows (all sections): {total_pub}")
