#!/usr/bin/env python3
"""
Convert all JSON configs to YAML and reorganize into per-OEM subfolders.

This script:
1. Creates per-OEM subfolders in model_lookup/configs/
2. Converts model_lookup/configs/*.json to YAML
3. Converts oems/*_config.json to YAML
4. Moves hyundai_standardization.yaml into hyundai/ subfolder
"""

import json
import yaml
from pathlib import Path
import shutil

def convert_json_to_yaml_content(json_path):
    """Load JSON and return as YAML string."""
    with open(json_path, 'r') as f:
        data = json.load(f)
    return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)

def main():
    project_root = Path(__file__).parent.parent
    configs_dir = project_root / "model_lookup" / "configs"
    oems_dir = project_root / "oems"

    print("=" * 80)
    print("PHASE 3: Convert JSON to YAML and reorganize into per-OEM subfolders")
    print("=" * 80)

    # ===== PART 1: Convert model_lookup/configs/*.json =====
    print("\n[1] Converting model_lookup/configs/ files...")

    # Extract list of OEMs from filenames (e.g., hyundai_translator.json → hyundai)
    oem_files = {}
    for json_file in configs_dir.glob("*_translator.json"):
        oem_name = json_file.stem.replace("_translator", "")
        if oem_name not in oem_files:
            oem_files[oem_name] = {}
        oem_files[oem_name]["translator"] = json_file

    for json_file in configs_dir.glob("*_classification.json"):
        oem_name = json_file.stem.replace("_classification", "")
        if oem_name not in oem_files:
            oem_files[oem_name] = {}
        oem_files[oem_name]["classification"] = json_file

    for json_file in configs_dir.glob("*_keywords.json"):
        oem_name = json_file.stem.replace("_keywords", "")
        if oem_name not in oem_files:
            oem_files[oem_name] = {}
        oem_files[oem_name]["keywords"] = json_file

    print(f"Found {len(oem_files)} OEMs with configs: {sorted(oem_files.keys())}")

    # Create per-OEM subfolders and convert files
    for oem_name, files_dict in sorted(oem_files.items()):
        oem_dir = configs_dir / oem_name
        oem_dir.mkdir(exist_ok=True, parents=True)
        print(f"\n  {oem_name}:")

        for file_type, json_path in sorted(files_dict.items()):
            yaml_filename = f"{file_type}.yaml"
            yaml_path = oem_dir / yaml_filename

            # Convert JSON to YAML
            yaml_content = convert_json_to_yaml_content(json_path)
            with open(yaml_path, 'w') as f:
                f.write(yaml_content)
            print(f"    [OK] {json_path.name} -> {yaml_path.relative_to(project_root)}")

            # Delete original JSON (backup first)
            json_backup = json_path.with_stem(json_path.stem + "_backup")
            json_path.rename(json_backup)
            json_backup.unlink()  # Actually delete instead of keeping backup
            print(f"      (removed original)")

    # ===== PART 2: Move hyundai_standardization.yaml into hyundai/ subfolder =====
    print("\n[2] Moving hyundai_standardization.yaml...")
    standardization_yaml = configs_dir / "hyundai_standardization.yaml"
    if standardization_yaml.exists():
        target_yaml = configs_dir / "hyundai" / "standardization.yaml"
        shutil.move(str(standardization_yaml), str(target_yaml))
        print(f"  [OK] {standardization_yaml.name} -> {target_yaml.relative_to(project_root)}")
    else:
        print(f"  [WARN] {standardization_yaml.name} not found (may have been moved already)")

    # ===== PART 3: Convert oems/*_config.json to YAML =====
    print("\n[3] Converting oems/*_config.json files...")
    for oem_dir in oems_dir.glob("*/config"):
        config_json = oem_dir / f"{oem_dir.parent.name}_config.json"
        if config_json.exists():
            config_yaml = config_json.with_suffix(".yaml")

            # Convert JSON to YAML
            yaml_content = convert_json_to_yaml_content(config_json)
            with open(config_yaml, 'w') as f:
                f.write(yaml_content)
            print(f"  [OK] {config_json.name} -> {config_yaml.name}")

            # Delete original JSON
            config_json.unlink()
            print(f"    (removed original)")

    print("\n" + "=" * 80)
    print("[OK] Conversion complete! All configs converted to YAML and reorganized.")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Update loaders in semantic/translator.py")
    print("2. Update loaders in semantic/classifier.py")
    print("3. Update loader in core/config_loader.py")
    print("4. Update loader in chrome_api/service.py")
    print("5. Update build functions in classifier.py")
    print("6. Run tests to verify all loaders work")

if __name__ == "__main__":
    main()
