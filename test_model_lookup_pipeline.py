"""
Test and validate the model number lookup pipeline end-to-end.

This script runs the pipeline and provides comprehensive reporting on:
- Total records processed
- Records with model numbers captured
- Records excluded (and why)
- Sample of successful and failed captures
- Model number distribution

Usage:
    python test_model_lookup_pipeline.py mitsubishi [excel_file]
    python test_model_lookup_pipeline.py mazda [csv_file]

Examples:
    python test_model_lookup_pipeline.py mitsubishi
    python test_model_lookup_pipeline.py mitsubishi "landing_zone/mitsubishi/2026_Outlander_ES_EN.xlsx"
    python test_model_lookup_pipeline.py mazda
"""

import sys
import json
from pathlib import Path
from datetime import datetime
import pandas as pd

# Setup paths
project_root = Path(__file__).parent
accy_v2_dir = project_root / "accy_v2"
model_lookup_dir = project_root / "model_lookup"

sys.path.insert(0, str(accy_v2_dir))
sys.path.insert(0, str(model_lookup_dir))
sys.path.insert(0, str(project_root))


def run_mitsubishi_test(file_path=None):
    """Run Mitsubishi pipeline with validation."""
    from oems.mitsubishi.pipeline.orchestrator import MitsubishiPipeline

    config_path = accy_v2_dir / "oems" / "mitsubishi" / "config" / "mitsubishi_config.json"
    default_dir = accy_v2_dir / "data" / "landing_zone" / "mitsubishi"

    if not file_path:
        candidates = sorted(default_dir.glob("*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidates:
            print(f"ERROR: No .xlsx files found in {default_dir}")
            return False
        file_path = str(candidates[0])
        print(f"Auto-discovered file: {file_path}")

    if not Path(file_path).exists():
        print(f"ERROR: File not found — {file_path}")
        return False

    print("\n" + "="*80)
    print("MITSUBISHI PIPELINE TEST")
    print("="*80)
    print(f"File: {file_path}")
    print(f"Config: {config_path}")

    try:
        pipeline = MitsubishiPipeline()
        pipeline.run(file_path=file_path, config_path=str(config_path))
        print("\n✓ Pipeline execution completed")
        return True
    except Exception as exc:
        print(f"\n✗ Pipeline failed: {exc}")
        import traceback
        traceback.print_exc()
        return False


def run_mazda_test(file_path=None):
    """Run Mazda pipeline with validation."""
    from oems.mazda.pipeline.orchestrator import MazdaPipeline

    config_path = accy_v2_dir / "oems" / "mazda" / "config" / "mazda_config.json"
    default_dir = accy_v2_dir / "data" / "landing_zone" / "mazda"

    if not file_path:
        candidates = sorted(default_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidates:
            print(f"ERROR: No .csv files found in {default_dir}")
            return False
        file_path = str(candidates[0])
        print(f"Auto-discovered file: {file_path}")

    if not Path(file_path).exists():
        print(f"ERROR: File not found — {file_path}")
        return False

    print("\n" + "="*80)
    print("MAZDA PIPELINE TEST")
    print("="*80)
    print(f"File: {file_path}")
    print(f"Config: {config_path}")

    try:
        pipeline = MazdaPipeline()
        pipeline.run(file_path=file_path, config_path=str(config_path))
        print("\n✓ Pipeline execution completed")
        return True
    except Exception as exc:
        print(f"\n✗ Pipeline failed: {exc}")
        import traceback
        traceback.print_exc()
        return False


def analyze_results(oem_name):
    """Analyze and report pipeline results."""
    print("\n" + "="*80)
    print("RESULTS ANALYSIS")
    print("="*80)

    # Find most recent output files
    dq_report_dir = accy_v2_dir / "output" / "dq_reports" / oem_name.lower()
    output_dir = accy_v2_dir / "output" / "ready_to_upload" / oem_name.lower()

    if not dq_report_dir.exists():
        print("ERROR: No DQ report found")
        return False

    # Find latest DQ report
    dq_files = sorted(dq_report_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not dq_files:
        print("ERROR: No DQ report files found")
        return False

    latest_dq = dq_files[0]
    print(f"\nDQ Report: {latest_dq}")

    # Read DQ report
    try:
        with open(latest_dq, 'r') as f:
            dq_data = json.load(f)
    except Exception as e:
        print(f"ERROR reading DQ report: {e}")
        return False

    # Analyze warnings
    warnings = dq_data.get("warnings", [])
    model_lookup_warnings = [w for w in warnings if w.get("rule_violated") == "model_number_lookup_rule"]

    print(f"\nTotal warnings in DQ report: {len(warnings)}")
    print(f"Model number lookup warnings: {len(model_lookup_warnings)}")

    # Categorize failures
    no_match = [w for w in model_lookup_warnings if "No model number found" in w.get("issue_description", "")]
    ambiguous = [w for w in model_lookup_warnings if "Ambiguous match" in w.get("issue_description", "")]
    errors = [w for w in model_lookup_warnings if "Error during" in w.get("issue_description", "")]

    print(f"  - No model found: {len(no_match)}")
    print(f"  - Ambiguous (multiple matches): {len(ambiguous)}")
    print(f"  - Lookup errors: {len(errors)}")

    # Sample failures
    if no_match:
        print(f"\nSample 'No Match' Failures:")
        for w in no_match[:3]:
            snapshot = w.get("record_snapshot", {})
            issue = w.get("issue_description", "")
            print(f"  - Row {w.get('record_index')}: {issue}")
            if "trim" in str(snapshot).lower() or "description" in str(snapshot).lower():
                for key in ["trim_level", "description", "model_name"]:
                    if key in snapshot:
                        print(f"    {key}: {snapshot[key]}")

    if ambiguous:
        print(f"\nSample 'Ambiguous Match' Failures:")
        for w in ambiguous[:3]:
            snapshot = w.get("record_snapshot", {})
            issue = w.get("issue_description", "")
            print(f"  - Row {w.get('record_index')}: {issue}")

    # Check output files
    if output_dir.exists():
        output_files = list(output_dir.glob("*.xlsx"))
        if output_files:
            latest_output = sorted(output_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
            print(f"\nOutput file: {latest_output}")
            try:
                # Read and analyze output
                excel = pd.ExcelFile(latest_output)
                print(f"Sheets: {excel.sheet_names}")

                for sheet in excel.sheet_names:
                    df = pd.read_excel(latest_output, sheet_name=sheet)
                    print(f"\nSheet '{sheet}':")
                    print(f"  - Total records: {len(df)}")

                    if "model_number" in df.columns:
                        with_model = df["model_number"].notna().sum()
                        print(f"  - Records with model_number: {with_model}")

                        # Sample successful captures
                        if with_model > 0:
                            print(f"\n  Sample captured model numbers:")
                            samples = df[df["model_number"].notna()][["model_name", "trim_level", "model_number"]].head(5)
                            for idx, row in samples.iterrows():
                                print(f"    - {row.get('model_name', 'N/A')} / {row.get('trim_level', 'N/A')}: {row.get('model_number', 'N/A')}")

                    if "vehicle_year" in df.columns:
                        print(f"  - Year range: {df['vehicle_year'].min()} - {df['vehicle_year'].max()}")

            except Exception as e:
                print(f"  Warning: Could not read output file: {e}")
        else:
            print("\nNo output files found yet")
    else:
        print(f"\nOutput directory does not exist: {output_dir}")

    return True


def print_summary(oem_name, success):
    """Print final summary."""
    print("\n" + "="*80)
    print("PIPELINE TEST SUMMARY")
    print("="*80)

    if success:
        print("✓ Pipeline executed successfully")
        print("\nNext steps:")
        print("1. Check the DQ report for any excluded records")
        print(f"2. Review output file in: {accy_v2_dir}/output/ready_to_upload/{oem_name.lower()}/")
        print("3. Verify model_number and vehicle_year columns are populated")
        print("4. Check READINESS_CHECKLIST.md for troubleshooting")
    else:
        print("✗ Pipeline execution failed")
        print("\nCheck the error messages above and:")
        print("1. Verify data files exist in landing_zone/")
        print("2. Check database connection")
        print("3. Review READINESS_CHECKLIST.md for prerequisites")

    print("\n" + "="*80 + "\n")


def main():
    """Main test runner."""
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nUsage: python test_model_lookup_pipeline.py {mitsubishi|mazda} [file_path]")
        sys.exit(1)

    oem = sys.argv[1].lower()
    file_path = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"\nStarting {oem.upper()} Pipeline Test")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Run appropriate pipeline
    if oem == "mitsubishi":
        success = run_mitsubishi_test(file_path)
        if success:
            analyze_results("Mitsubishi")
        print_summary("mitsubishi", success)

    elif oem == "mazda":
        success = run_mazda_test(file_path)
        if success:
            analyze_results("Mazda")
        print_summary("mazda", success)

    else:
        print(f"ERROR: Unknown OEM '{oem}'")
        print("Supported OEMs: mitsubishi, mazda")
        sys.exit(1)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
