"""
Verify that the pipeline is running all steps including model number lookup.

Usage:
    python verify_pipeline_execution.py
    python verify_pipeline_execution.py mitsubishi
"""

import sys
import json
from pathlib import Path


def verify_pipeline():
    """Verify pipeline execution."""
    project_root = Path(__file__).parent
    log_dir = project_root / "accy_v2" / "output" / "pipeline_logs" / "mitsubishi"
    output_dir = project_root / "accy_v2" / "output" / "ready_to_upload" / "mitsubishi"
    dq_dir = project_root / "accy_v2" / "output" / "dq_reports" / "mitsubishi"

    print("\n" + "="*80)
    print("PIPELINE EXECUTION VERIFICATION")
    print("="*80)

    # 1. Check if new log files exist
    if not log_dir.exists():
        print("\n[ERROR] ERROR: No pipeline logs found")
        print(f"  Expected: {log_dir}")
        return False

    log_files = sorted(log_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not log_files:
        print("\n[ERROR] ERROR: No log files found")
        return False

    latest_log = log_files[0]
    print(f"\n[OK] Latest log file: {latest_log.name}")

    # 2. Check log file contents
    print("\nChecking log file for required steps...")
    with open(latest_log, 'r') as f:
        log_content = f.read()

    steps_to_check = {
        "Step 3.5 (Extract Year)": [
            "run_step3_5_extract_vehicle_year",
            "vehicle_year",
            "Extracted vehicle_year",
        ],
        "Step 4.5 (Model Enrichment)": [
            "run_step4_5_model_enrichment",
            "model_number_lookup",
            "Model Enrichment",
        ],
    }

    found_steps = {}
    for step_name, keywords in steps_to_check.items():
        found = any(kw in log_content for kw in keywords)
        found_steps[step_name] = found
        status = "[OK]" if found else "[MISSING]"
        print(f"  {status} {step_name}")

    # 3. Check output file
    print("\nChecking output file...")
    if not output_dir.exists():
        print(f"  [ERROR] Output directory not found: {output_dir}")
    else:
        output_files = list(output_dir.glob("*.xlsx"))
        if not output_files:
            print(f"  [ERROR] No output files found in {output_dir}")
        else:
            latest_output = sorted(output_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
            print(f"  [OK] Found output file: {latest_output.name}")

            # Check if it has model_number column
            try:
                import pandas as pd
                df = pd.read_excel(latest_output)
                has_model_number = "model_number" in df.columns
                has_vehicle_year = "vehicle_year" in df.columns

                print(f"\n  Columns in output file:")
                print(f"    - model_number: {'[OK]' if has_model_number else '[ERROR]'}")
                print(f"    - vehicle_year: {'[OK]' if has_vehicle_year else '[ERROR]'}")

                if has_model_number:
                    captured = df["model_number"].notna().sum()
                    total = len(df)
                    rate = captured / total * 100 if total > 0 else 0
                    print(f"\n  Model number capture:")
                    print(f"    - Total records: {total}")
                    print(f"    - With model_number: {captured}")
                    print(f"    - Capture rate: {rate:.1f}%")
            except Exception as e:
                print(f"  [WARNING] Could not read output file: {e}")

    # 4. Check DQ report
    print("\nChecking DQ report...")
    if not dq_dir.exists():
        print(f"  [ERROR] DQ report directory not found: {dq_dir}")
    else:
        dq_files = sorted(dq_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not dq_files:
            print(f"  [ERROR] No DQ report files found")
        else:
            latest_dq = dq_files[0]
            print(f"  [OK] Found DQ report: {latest_dq.name}")

            try:
                with open(latest_dq, 'r') as f:
                    dq_data = json.load(f)

                warnings = dq_data.get("warnings", [])
                model_warnings = [w for w in warnings if w.get("rule_violated") == "model_number_lookup_rule"]

                print(f"\n  DQ Report summary:")
                print(f"    - Total warnings: {len(warnings)}")
                print(f"    - Model lookup warnings: {len(model_warnings)}")

                if model_warnings:
                    no_match = len([w for w in model_warnings if "No model number found" in w.get("issue_description", "")])
                    ambiguous = len([w for w in model_warnings if "Ambiguous match" in w.get("issue_description", "")])
                    errors = len([w for w in model_warnings if "Error during" in w.get("issue_description", "")])

                    print(f"      - No match: {no_match}")
                    print(f"      - Ambiguous: {ambiguous}")
                    print(f"      - Errors: {errors}")
            except Exception as e:
                print(f"  [WARNING] Could not read DQ report: {e}")

    # 5. Final assessment
    print("\n" + "="*80)
    print("ASSESSMENT")
    print("="*80)

    all_steps_found = all(found_steps.values())

    if all_steps_found:
        print("\n[OK] Pipeline is running ALL required steps including model number lookup")
        print("\nNext steps:")
        print("1. Check the capture rate above (should be >95%)")
        print("2. If capture rate is low, check DQ report for why model numbers weren't found")
        print("3. Consider updating trim abbreviations in config if needed")
    else:
        missing = [s for s, found in found_steps.items() if not found]
        print(f"\n[ERROR] Pipeline is NOT running all steps!")
        print(f"\nMissing steps:")
        for step in missing:
            print(f"  - {step}")
        print("\nFIX: You need to run the pipeline AGAIN after my recent changes:")
        print("  python test_model_lookup_pipeline.py mitsubishi")

    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    verify_pipeline()
