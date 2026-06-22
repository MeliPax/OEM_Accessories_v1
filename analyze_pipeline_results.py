#!/usr/bin/env python3
"""
Analyze pipeline results and show model number capture statistics.

Reads output files and DQ reports to provide insights on:
- How many model numbers were successfully captured
- Which trims failed and why
- Success rate by OEM
- Detailed failure analysis

Usage:
    python analyze_pipeline_results.py mitsubishi
    python analyze_pipeline_results.py mazda
"""

import sys
import json
from pathlib import Path
from datetime import datetime
import pandas as pd


def find_latest_dq_report(oem: str) -> Path:
    """Find the most recent DQ report for the OEM."""
    project_root = Path(__file__).parent
    dq_dir = project_root / "accy_v2" / "output" / "dq_reports" / oem.lower()

    if not dq_dir.exists():
        return None

    reports = sorted(dq_dir.glob("dq_report_*.json"))
    return reports[-1] if reports else None


def find_latest_output_file(oem: str) -> Path:
    """Find the most recent output file for the OEM."""
    project_root = Path(__file__).parent
    output_dir = project_root / "accy_v2" / "output" / "ready_to_upload" / oem.lower()

    if not output_dir.exists():
        return None

    files = sorted(output_dir.glob("*.xlsx"))
    return files[-1] if files else None


def analyze_dq_report(report_path: Path) -> dict:
    """Analyze DQ report for model lookup failures."""
    with open(report_path, "r") as f:
        data = json.load(f)

    warnings = data.get("warnings", [])
    model_lookup_warnings = [
        w for w in warnings if w.get("rule_violated") == "model_number_lookup_rule"
    ]

    failure_types = {
        "no_match_found": [],
        "ambiguous_multiple_matches": [],
        "no_keywords": [],
        "lookup_error": [],
    }

    for warning in model_lookup_warnings:
        details = warning.get("details", {})
        result_type = details.get("lookup_result", "unknown")

        if result_type in failure_types:
            failure_types[result_type].append(details)

    return {
        "total_warnings": len(warnings),
        "model_lookup_warnings": len(model_lookup_warnings),
        "failure_types": failure_types,
        "raw_warnings": model_lookup_warnings,
    }


def analyze_output_file(file_path: Path) -> dict:
    """Analyze output Excel file for model number coverage."""
    try:
        excel_file = pd.ExcelFile(file_path)
        sheet_names = excel_file.sheet_names

        # Filter to data sheets (exclude Report sheet)
        data_sheets = [s for s in sheet_names if s != "Report"]

        total_rows = 0
        total_with_model_numbers = 0
        sheets_info = []

        for sheet_name in data_sheets:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            sheet_total = len(df)
            total_rows += sheet_total

            # Count rows with model_number
            if "model_number" in df.columns:
                has_model = df["model_number"].notna().sum()
                total_with_model_numbers += has_model

                sheets_info.append({
                    "sheet": sheet_name,
                    "total_rows": sheet_total,
                    "rows_with_model": has_model,
                    "capture_rate": f"{(has_model / sheet_total * 100):.1f}%" if sheet_total > 0 else "N/A",
                })

        return {
            "total_rows": total_rows,
            "total_with_model_numbers": total_with_model_numbers,
            "capture_rate": f"{(total_with_model_numbers / total_rows * 100):.1f}%" if total_rows > 0 else "N/A",
            "sheets": sheets_info,
        }
    except Exception as e:
        return {"error": str(e)}


def print_header(text: str):
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(text)
    print("=" * 80)


def print_subheader(text: str):
    """Print a formatted subheader."""
    print(f"\n{text}")
    print("-" * 80)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    oem = sys.argv[1].lower()

    print_header(f"PIPELINE RESULTS ANALYSIS: {oem.upper()}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Find DQ report
    dq_report_path = find_latest_dq_report(oem)
    if not dq_report_path:
        print(f"[ERROR] No DQ report found for {oem}")
        sys.exit(1)

    print(f"DQ Report: {dq_report_path.relative_to(Path.cwd())}")

    # Find output file
    output_file_path = find_latest_output_file(oem)
    if not output_file_path:
        print(f"[ERROR] No output file found for {oem}")
        sys.exit(1)

    print(f"Output File: {output_file_path.relative_to(Path.cwd())}\n")

    # Analyze DQ report
    print_subheader("Data Quality Summary")
    dq_analysis = analyze_dq_report(dq_report_path)

    print(f"Total warnings: {dq_analysis['total_warnings']}")
    print(f"Model lookup warnings: {dq_analysis['model_lookup_warnings']}")

    if dq_analysis["model_lookup_warnings"] > 0:
        print("\nFailure breakdown:")
        for failure_type, failures in dq_analysis["failure_types"].items():
            if failures:
                print(f"  - {failure_type}: {len(failures)}")

    # Analyze output file
    print_subheader("Output File Analysis")
    file_analysis = analyze_output_file(output_file_path)

    if "error" in file_analysis:
        print(f"[ERROR] {file_analysis['error']}")
    else:
        print(f"Total rows: {file_analysis['total_rows']}")
        print(f"Rows with model_number: {file_analysis['total_with_model_numbers']}")
        print(f"Capture rate: {file_analysis['capture_rate']}")

        if file_analysis["sheets"]:
            print("\nPer-sheet breakdown:")
            for sheet_info in file_analysis["sheets"]:
                print(f"  Sheet '{sheet_info['sheet']}':")
                print(f"    - Total rows: {sheet_info['total_rows']}")
                print(f"    - With model numbers: {sheet_info['rows_with_model']}")
                print(f"    - Capture rate: {sheet_info['capture_rate']}")

    # Show sample failures
    if dq_analysis["model_lookup_warnings"] > 0:
        print_subheader("Sample Failure Details")

        for failure_type, failures in dq_analysis["failure_types"].items():
            if failures:
                print(f"\n{failure_type.upper().replace('_', ' ')}:")
                for i, failure in enumerate(failures[:3]):  # Show first 3
                    print(f"  #{i+1}")
                    if "trim_name" in failure:
                        print(f"     Trim: {failure['trim_name']}")
                    if "keywords_searched" in failure:
                        print(f"     Keywords: {failure['keywords_searched']}")
                    if "message" in failure:
                        print(f"     Message: {failure['message']}")
                    if "matches_found" in failure:
                        print(f"     Matches: {failure['matches_found']}")

                if len(failures) > 3:
                    print(f"  ... and {len(failures) - 3} more")

    # Summary
    print_header("SUMMARY")
    if file_analysis.get("capture_rate") and "%" in file_analysis["capture_rate"]:
        rate_val = float(file_analysis["capture_rate"].rstrip("%"))
        if rate_val >= 95:
            status = "[OK] Excellent capture rate"
        elif rate_val >= 80:
            status = "[OK] Good capture rate"
        else:
            status = "[WARNING] Low capture rate"
        print(f"{status}: {file_analysis['capture_rate']}")

    if dq_analysis["model_lookup_warnings"] > 0:
        print(f"[WARNING] {dq_analysis['model_lookup_warnings']} model lookup warnings")
        print("Review details above to debug trim name/keyword issues")
    else:
        print("[OK] All model numbers successfully captured!")

    print("\n")


if __name__ == "__main__":
    main()
