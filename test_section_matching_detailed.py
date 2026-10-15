#!/usr/bin/env python3
"""
Debug: Detailed section matching for both EN and FR
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

# Get the detection config
detection_config = config.get("schemas", {}).get("structure", {})
section_classification = detection_config.get("section_classification", {})

print("=" * 120)
print("SECTION MATCHING - DETAILED DEBUG")
print("=" * 120)

print("\n[CONFIG SECTION DEFINITIONS]")
for section_def in section_classification.get("sections", []):
    name = section_def.get("name", "")
    is_pkg = section_def.get("is_package", False)
    markers_en = section_def.get("markers_en", [])
    markers_fr = section_def.get("markers_fr", [])
    print(f"\n  name='{name}' (is_package={is_pkg})")
    print(f"    markers_en={markers_en}")
    print(f"    markers_fr={markers_fr}")

# Test EN sheet
print("\n" + "=" * 120)
print("EN SHEET - SECTION MATCHING")
print("=" * 120)

excel = pd.ExcelFile(file_path)
df_raw_en = excel.parse(sheet_name="26MY_CIV5D_APP_EN", header=None)

run_id = "debug_en"
dq_logger = DQLogger(run_id=run_id, source_file=str(file_path))
pipeline_logger = PipelineLogger(run_id=run_id, log_path="accy_v2/output/pipeline_logs/honda")

meta_data = {"sheet_name": "26MY_CIV5D_APP_EN"}
df_step1_en, meta_step1_en = step1_validation.run(
    df_raw_en, config, meta_data, dq_logger, pipeline_logger
)

section_structure_en = meta_step1_en.get('section_structure', {})

for section_name in section_structure_en.keys():
    print(f"\nEN Section from Step 1: '{section_name}'")

    # Test matching logic
    found = False
    for section_def in section_classification.get("sections", []):
        config_name = section_def.get("name", "").lower()
        markers_en = [m.lower() for m in section_def.get("markers_en", [])]
        markers_fr = [m.lower() for m in section_def.get("markers_fr", [])]
        all_markers = [config_name] + markers_en + markers_fr

        print(f"  Checking against config name '{section_def.get('name')}':")
        print(f"    all_markers={all_markers}")
        print(f"    section_name.lower()='{section_name.lower()}'")
        print(f"    Match: {section_name.lower() in all_markers}")

        if section_name.lower() in all_markers:
            print(f"    -> MATCHED! is_package={section_def.get('is_package', False)}")
            found = True
            break

    if not found:
        print(f"  NO MATCH FOUND")

# Test FR sheet
print("\n" + "=" * 120)
print("FR SHEET - SECTION MATCHING")
print("=" * 120)

df_raw_fr = excel.parse(sheet_name="26MY_CIV5D_APP_FR", header=None)

run_id = "debug_fr"
dq_logger = DQLogger(run_id=run_id, source_file=str(file_path))
pipeline_logger = PipelineLogger(run_id=run_id, log_path="accy_v2/output/pipeline_logs/honda")

meta_data = {"sheet_name": "26MY_CIV5D_APP_FR"}
df_step1_fr, meta_step1_fr = step1_validation.run(
    df_raw_fr, config, meta_data, dq_logger, pipeline_logger
)

section_structure_fr = meta_step1_fr.get('section_structure', {})

for section_name in section_structure_fr.keys():
    print(f"\nFR Section from Step 1: '{section_name}'")

    # Test matching logic
    found = False
    for section_def in section_classification.get("sections", []):
        config_name = section_def.get("name", "").lower()
        markers_en = [m.lower() for m in section_def.get("markers_en", [])]
        markers_fr = [m.lower() for m in section_def.get("markers_fr", [])]
        all_markers = [config_name] + markers_en + markers_fr

        print(f"  Checking against config name '{section_def.get('name')}':")
        print(f"    all_markers={all_markers}")
        print(f"    section_name.lower()='{section_name.lower()}'")
        print(f"    Match: {section_name.lower() in all_markers}")

        if section_name.lower() in all_markers:
            print(f"    -> MATCHED! is_package={section_def.get('is_package', False)}")
            found = True
            break

    if not found:
        print(f"  NO MATCH FOUND")

print("\n" + "=" * 120)
