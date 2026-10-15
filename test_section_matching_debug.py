#!/usr/bin/env python3
"""
Debug: Check what section names are extracted from Step 1
and verify config matching logic
"""

import sys
from pathlib import Path
import pandas as pd

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "accy_v2"))

from accy_v2.oems.honda.pipeline import step1_validation
from accy_v2.core.config_loader_v2 import ModularConfigLoader
from accy_v2.core.helpers.dq_logger import DQLogger
from accy_v2.core.helpers.pipeline_logger import PipelineLogger

# Setup
file_path = project_root / "accy_v2/data/landing_zone/honda/may_2026/CVIC5D.xlsx"
config_root = project_root / "accy_v2/oems/honda/config"

config_loader = ModularConfigLoader("honda", config_root)
config = config_loader.load_all()

excel = pd.ExcelFile(file_path)
df_raw = excel.parse(sheet_name="26MY_CIV5D_APP_EN", header=None)

run_id = "debug_sections"
dq_logger = DQLogger(run_id=run_id, source_file=str(file_path))
pipeline_logger = PipelineLogger(run_id=run_id, log_path="accy_v2/output/pipeline_logs/honda")

meta_data = {"sheet_name": "26MY_CIV5D_APP_EN"}
df_step1, meta_step1 = step1_validation.run(
    df_raw, config, meta_data, dq_logger, pipeline_logger
)

print("=" * 100)
print("SECTION MATCHING DEBUG")
print("=" * 100)

section_structure = meta_step1.get('section_structure', {})

print("\n[SECTION NAMES FROM STEP 1]")
for section_name in section_structure.keys():
    print(f"  - '{section_name}'")

print("\n[CONFIG KEYS]")
print(f"  Config keys: {list(config.keys())}")

print("\n[SCHEMAS KEYS]")
schemas = config.get("schemas", {})
print(f"  schemas keys: {list(schemas.keys())}")

print("\n[SECTION DEFINITIONS FROM CONFIG]")
# Try different paths
detection_config = schemas.get("structure", {})  # Try from schemas/structure.yaml
print(f"  schemas.structure keys: {list(detection_config.keys())}")
section_classification = detection_config.get("section_classification", {})

for section_def in section_classification.get("sections", []):
    name = section_def.get("name", "")
    is_pkg = section_def.get("is_package", False)
    markers_en = section_def.get("markers_en", [])
    print(f"  - name='{name}', is_package={is_pkg}, markers_en={markers_en}")

print("\n[MATCHING TEST]")
for section_name in section_structure.keys():
    print(f"\nSection from Step 1: '{section_name}'")

    # Test exact name match
    for section_def in section_classification.get("sections", []):
        config_name = section_def.get("name", "").lower()
        section_lower = section_name.lower()
        match = (section_lower == config_name)
        print(f"  vs config name '{section_def.get('name')}': {match}")
        if match:
            print(f"    -> is_package={section_def.get('is_package', False)}")
            break
    else:
        print(f"  -> NO MATCH FOUND (all defaults to is_package=False)")

print("\n" + "=" * 100)
