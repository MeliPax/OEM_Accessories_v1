#!/usr/bin/env python3
"""
Enhanced Phase 2 Integration Test with Detailed Comparative Reports
Tests Phase 1 + Phase 2 end-to-end on both EN and FR Honda data (CVIC5D.xlsx)
Produces detailed comparative analysis and defect breakdowns
"""

import sys
from pathlib import Path
import pandas as pd

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "accy_v2"))

from accy_v2.oems.honda.pipeline import step1_validation, step2_header_normalization
from accy_v2.core.helpers.dq_logger import DQLogger
from accy_v2.core.helpers.pipeline_logger import PipelineLogger
from accy_v2.core.config_loader_v2 import ModularConfigLoader

def run_phase2(sheet_name, language):
    """Run Phase 1 + Phase 2 on a sheet and return results"""

    file_path = project_root / "accy_v2/data/landing_zone/honda/may_2026/CVIC5D.xlsx"
    config_root = project_root / "accy_v2/oems/honda/config"

    if not file_path.exists():
        return None

    # Load configs using ModularConfigLoader (structure.yaml via load_all)
    config_loader = ModularConfigLoader("honda", Path(config_root))
    config = config_loader.load_all()

    # Load Excel
    excel = pd.ExcelFile(file_path)
    if sheet_name not in excel.sheet_names:
        return None

    df_raw = excel.parse(sheet_name=sheet_name, header=None)

    # Initialize loggers
    dq_logger = DQLogger(run_id=f"report_{language}", source_file=str(file_path))
    pipeline_logger = PipelineLogger(run_id=f"report_{language}", log_path="accy_v2/output/pipeline_logs/honda")

    # Phase 1
    meta_data = {"sheet_name": sheet_name}
    df_phase1, meta_phase1 = step1_validation.run(df_raw, config, meta_data, dq_logger, pipeline_logger)

    # Phase 2
    df_phase2, meta_phase2 = step2_header_normalization.run(df_phase1, config, meta_phase1, dq_logger, pipeline_logger)

    return {
        "df": df_raw,
        "meta_phase1": meta_phase1,
        "meta_phase2": meta_phase2,
        "dq_logger": dq_logger
    }

def get_section_record_counts(meta_phase2, section_structure):
    """Get record type counts per section"""
    record_types = meta_phase2.get('record_type_per_row', {})

    counts = {}
    for section_name, bounds in section_structure.items():
        start = bounds.get('data_start_row')
        end = bounds.get('data_end_row')

        # Only count rows that are IN record_types dict
        # Rows not in the dict were skipped during classification (e.g., empty rows)
        section_records = {k: v for k, v in record_types.items() if start <= k <= end}

        section_counts = {}
        for rtype in section_records.values():
            # rtype can be a string ('parent', 'child', 'subsection_label', etc.) or None for defects
            rtype_key = "defect" if rtype is None else rtype
            section_counts[rtype_key] = section_counts.get(rtype_key, 0) + 1

        counts[section_name] = section_counts

    return counts

def get_defect_rows(meta_phase2, section_structure, df, meta_phase1):
    """Get defect row details by section"""
    record_types = meta_phase2.get('record_type_per_row', {})
    column_mapping = meta_phase2.get('column_mapping', {})

    defects_by_section = {}

    for section_name, bounds in section_structure.items():
        start = bounds.get('data_start_row')
        end = bounds.get('data_end_row')

        # Only get rows that ARE in record_types AND are classified as 'defect' (None value)
        # Rows that have no entry in record_types were skipped as data cleanup (e.g., empty rows)
        defect_rows = [r for r in range(start, end + 1) if r in record_types and record_types.get(r) is None]

        if defect_rows:
            col_map = column_mapping.get(section_name, {})
            part_num_idx = None
            desc_idx = None

            for col_idx, col_name in col_map.items():
                if col_name == 'part_number':
                    part_num_idx = col_idx
                elif col_name == 'description':
                    desc_idx = col_idx

            defect_details = []
            for row_idx in defect_rows:
                row = df.iloc[row_idx]
                part_num = str(row.iloc[part_num_idx]).strip() if part_num_idx is not None and pd.notna(row.iloc[part_num_idx]) else ""
                desc = str(row.iloc[desc_idx]).strip() if desc_idx is not None and pd.notna(row.iloc[desc_idx]) else ""

                part_num_disp = part_num[:20] if part_num else "[EMPTY]"
                desc_disp = desc[:30] if desc else "[EMPTY]"

                defect_details.append({
                    "row": row_idx,
                    "part_number": part_num_disp,
                    "description": desc_disp
                })

            defects_by_section[section_name] = defect_details

    return defects_by_section

print("=" * 120)
print("PHASE 2 DETAILED COMPARATIVE REPORT - EN vs FR")
print("=" * 120)

# Run both sheets
results = {
    "EN": run_phase2("26MY_CIV5D_APP_EN", "EN"),
    "FR": run_phase2("26MY_CIV5D_APP_FR", "FR")
}

if not all(results.values()):
    print("ERROR: Could not load both sheets")
    sys.exit(1)

en_result = results["EN"]
fr_result = results["FR"]

# ============================================================================
# SECTION 1: GLOBAL OVERVIEW
# ============================================================================

print("\n" + "=" * 120)
print("SECTION 1: GLOBAL RECORD TYPE COMPARISON (EN vs FR)")
print("=" * 120)

en_counts = en_result["meta_phase2"].get('record_type_counts', {})
fr_counts = fr_result["meta_phase2"].get('record_type_counts', {})

print(f"\n{'Record Type':<20} {'EN':<15} {'FR':<15} {'Difference':<15} {'Status':<10}")
print("-" * 75)

all_types = set(list(en_counts.keys()) + list(fr_counts.keys()))
for rtype in sorted(all_types):
    en_count = en_counts.get(rtype, 0)
    fr_count = fr_counts.get(rtype, 0)
    diff = fr_count - en_count
    status = "[MATCH]" if en_count == fr_count else "[DIFF]"

    print(f"{rtype:<20} {en_count:<15} {fr_count:<15} {diff:+<15} {status:<10}")

en_total = sum(en_counts.values())
fr_total = sum(fr_counts.values())
print("-" * 75)
print(f"{'TOTAL':<20} {en_total:<15} {fr_total:<15} {fr_total - en_total:+<15}")

# ============================================================================
# SECTION 2: SECTION-BY-SECTION BREAKDOWN
# ============================================================================

print("\n" + "=" * 120)
print("SECTION 2: RECORD TYPE COUNTS BY SECTION (EN vs FR)")
print("=" * 120)

en_section_counts = get_section_record_counts(en_result["meta_phase2"], en_result["meta_phase1"].get('section_structure', {}))
fr_section_counts = get_section_record_counts(fr_result["meta_phase2"], fr_result["meta_phase1"].get('section_structure', {}))

for section_name in sorted(en_section_counts.keys()):
    en_sec_counts = en_section_counts.get(section_name, {})
    fr_sec_counts = fr_section_counts.get(section_name, {})

    print(f"\n{section_name}:")
    print(f"  {'Type':<20} {'EN':<10} {'FR':<10} {'Status':<10}")
    print(f"  {'-'*50}")

    all_types = set(list(en_sec_counts.keys()) + list(fr_sec_counts.keys()))
    for rtype in sorted(all_types):
        en_count = en_sec_counts.get(rtype, 0)
        fr_count = fr_sec_counts.get(rtype, 0)
        status = "[OK]" if en_count == fr_count else "[DIFF]"
        print(f"  {rtype:<20} {en_count:<10} {fr_count:<10} {status:<10}")

# ============================================================================
# SECTION 3: DEFECT ANALYSIS - ENGLISH SHEET
# ============================================================================

print("\n" + "=" * 120)
print("SECTION 3: DEFECT ANALYSIS - ENGLISH SHEET")
print("=" * 120)

en_defects = get_defect_rows(
    en_result["meta_phase2"],
    en_result["meta_phase1"].get('section_structure', {}),
    en_result["df"],
    en_result["meta_phase1"]
)

if en_defects:
    for section_name in sorted(en_defects.keys()):
        defect_list = en_defects[section_name]
        print(f"\n{section_name}: {len(defect_list)} defects")
        print(f"  {'Row':<8} {'Part Number':<25} {'Description':<35}")
        print(f"  {'-'*68}")

        for defect in defect_list[:10]:  # Show first 10
            print(f"  {defect['row']:<8} {defect['part_number']:<25} {defect['description']:<35}")

        if len(defect_list) > 10:
            print(f"  ... and {len(defect_list) - 10} more")
else:
    print("\nNo defects found in EN sheet!")

# ============================================================================
# SECTION 4: DEFECT ANALYSIS - FRENCH SHEET
# ============================================================================

print("\n" + "=" * 120)
print("SECTION 4: DEFECT ANALYSIS - FRENCH SHEET")
print("=" * 120)

fr_defects = get_defect_rows(
    fr_result["meta_phase2"],
    fr_result["meta_phase1"].get('section_structure', {}),
    fr_result["df"],
    fr_result["meta_phase1"]
)

if fr_defects:
    for section_name in sorted(fr_defects.keys()):
        defect_list = fr_defects[section_name]
        print(f"\n{section_name}: {len(defect_list)} defects")
        print(f"  {'Row':<8} {'Part Number':<25} {'Description':<35}")
        print(f"  {'-'*68}")

        for defect in defect_list[:10]:  # Show first 10
            print(f"  {defect['row']:<8} {defect['part_number']:<25} {defect['description']:<35}")

        if len(defect_list) > 10:
            print(f"  ... and {len(defect_list) - 10} more")
else:
    print("\nNo defects found in FR sheet!")

# ============================================================================
# SECTION 5: DEFECT COMPARISON SUMMARY
# ============================================================================

print("\n" + "=" * 120)
print("SECTION 5: DEFECT COUNT SUMMARY")
print("=" * 120)

print(f"\n{'Section':<40} {'EN Defects':<15} {'FR Defects':<15}")
print("-" * 70)

all_sections = set(list(en_section_counts.keys()) + list(fr_section_counts.keys()))
for section_name in sorted(all_sections):
    en_defect_count = en_section_counts.get(section_name, {}).get('defect', 0)
    fr_defect_count = fr_section_counts.get(section_name, {}).get('defect', 0)

    print(f"{section_name:<40} {en_defect_count:<15} {fr_defect_count:<15}")

# ============================================================================
# FINAL SUMMARY
# ============================================================================

print("\n" + "=" * 120)
print("SUMMARY & NEXT STEPS")
print("=" * 120)

en_match = en_counts == fr_counts
print(f"\nEN and FR record counts match: {en_match}")

if en_match:
    print("[OK] Both sheets have identical classification results")
    print("   Ready to proceed to Phase 3 with confidence!")
else:
    print("[WARN] Differences detected between EN and FR sheets")
    print("\nKey differences:")

    for rtype in all_types:
        en_count = en_counts.get(rtype, 0)
        fr_count = fr_counts.get(rtype, 0)
        if en_count != fr_count:
            print(f"  - {rtype}: EN={en_count}, FR={fr_count} (diff: {fr_count - en_count:+d})")

    print("\nDebug steps:")
    print("  1. Check 'Defect Analysis' sections for rows causing issues")
    print("  2. Verify column name normalization for FR sheet")
    print("  3. Check if section boundaries differ between sheets")

print("\n" + "=" * 120)
print("[OK] DETAILED REPORT COMPLETE")
print("=" * 120)
