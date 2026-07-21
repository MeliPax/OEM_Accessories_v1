from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd

from core.helpers.dq_logger import DQLogger
from core.helpers.pipeline_logger import PipelineLogger


def write_combined_output(
    all_frames: Dict[str, pd.DataFrame],
    run_stats: List[Dict],
    dq_logger: DQLogger,
    config: dict,
    run_id: str,
    pipeline_logger: PipelineLogger,
    profile_col: str = "Trim",
) -> None:
    """
    Write all accumulated model frames + Report sheet to one combined Excel file.
    File path: {oem}/{oem}_{run_id}_{timestamp}.xlsx
    Sheets: _Report (first), then {model}_{lang} sheets.

    Args:
        profile_col: Column name to use for trim/package breakdown in Model Profile (default: "Trim")
    """
    output_path = Path(config["output"]["ready_to_upload_path"])
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    oem_name = output_path.parts[-1]
    file_path = output_path / f"{oem_name}_{run_id}_{timestamp}.xlsx"

    try:
        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            _write_report_sheet(writer, run_stats, dq_logger, run_id, all_frames, profile_col)
            _write_data_issues_sheet(writer, dq_logger)
            for sheet_name, df in all_frames.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        pipeline_logger.info(f"Combined output saved: {file_path}")
    except Exception as exc:
        pipeline_logger.warning(f"Failed to save combined output: {exc}")
        raise


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _write_report_sheet(
    writer: pd.ExcelWriter,
    run_stats: List[Dict],
    dq_logger: DQLogger,
    run_id: str,
    all_frames: Dict[str, pd.DataFrame],
    profile_col: str = "Trim",
) -> None:
    """Write _Report sheet with Run Summary and Model Profile (management dashboard view)."""
    from openpyxl.styles import Alignment
    startrow = 0

    # Section 1: Run Summary (key-value pairs)
    summary_df = _build_run_summary(run_stats, dq_logger, run_id, all_frames)
    summary_df.to_excel(writer, sheet_name="_Report", startrow=startrow, index=False, header=False)
    ws = writer.sheets["_Report"]
    for row_offset in range(len(summary_df)):
        ws.row_dimensions[startrow + 1 + row_offset].height = 18
    startrow += len(summary_df) + 2

    # Section 2: Model Profile
    profile_df = _build_model_profile(run_stats, all_frames, profile_col)
    if not profile_df.empty:
        profile_df.to_excel(writer, sheet_name="_Report", startrow=startrow, index=False)
        records_out_col = profile_df.columns.get_loc("Records Out") + 1
        header_row = startrow + 1
        ws.row_dimensions[header_row].height = 20

        for row_offset in range(len(profile_df)):
            data_row = header_row + 1 + row_offset
            cell = ws.cell(row=data_row, column=records_out_col)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            trim_text = profile_df.iloc[row_offset]["Records Out"]
            line_count = trim_text.count("\n") + 1 if trim_text else 1
            ws.row_dimensions[data_row].height = max(18, line_count * 15 + 6)


def _build_run_summary(
    run_stats: List[Dict],
    dq_logger: DQLogger,
    run_id: str,
    all_frames: Dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Build Run Summary section: key-value table with aggregate stats + manager insights."""
    from collections import Counter

    source_file = run_stats[0].get("source_file", "unknown") if run_stats else "unknown"
    sheets_processed = len(run_stats)
    total_warnings = dq_logger.warning_count
    total_records_in = sum(s.get("records_in", 0) for s in run_stats)
    total_records_out = sum(s.get("records_out", 0) for s in run_stats)
    pct_warnings = round(total_warnings / total_records_in * 100) if total_records_in > 0 else 0

    # Manager analytics
    unique_models = len({s.get("model_name") for s in run_stats if s.get("model_name")})
    sheets_with_issues = len({r["sheet_name"] for r in dq_logger.records})
    sheets_clean = sheets_processed - sheets_with_issues

    # Trim coverage: successful trims vs failed trim lookups
    successful_trims = sum(
        df["Trim"].nunique()
        for key, df in all_frames.items()
        if key.endswith("_EN") and "Trim" in df.columns
    )
    failed_trims = sum(
        1 for r in dq_logger.records
        if r["rule_violated"] == "model_number_lookup_rule"
    )
    total_trims = successful_trims + failed_trims
    pct_trim_coverage = round(successful_trims / total_trims * 100, 1) if total_trims > 0 else 100.0

    # DQ warnings by rule with percentages (most common first)
    if dq_logger.records:
        rule_counts = Counter(r["rule_violated"] for r in dq_logger.records)
        dq_by_rule = " | ".join(
            f"{rule}: {count} ({round(count / total_warnings * 100)}%)"
            for rule, count in rule_counts.most_common()
        )
    else:
        dq_by_rule = "None"

    # Model lookup issues by type (categorized by issue_description prefix)
    lookup_records = [r for r in dq_logger.records if r["rule_violated"] == "model_number_lookup_rule"]
    if lookup_records:
        total_lookup = len(lookup_records)
        def _categorize_lookup_issue(issue: str) -> str:
            if issue.startswith("No keywords"):
                return "No Keywords"
            if issue.startswith("No confident"):
                return "No Match"
            if issue.startswith("Error"):
                return "Lookup Error"
            return "Other"
        lookup_counts = Counter(_categorize_lookup_issue(r["issue_description"]) for r in lookup_records)
        lookup_by_type = " | ".join(
            f"{cat}: {count} ({round(count / total_lookup * 100)}%)"
            for cat, count in lookup_counts.most_common()
        )
    else:
        lookup_by_type = "None"

    # Sheets/Models label: collapse if they're the same, otherwise show both
    if sheets_processed == unique_models:
        sheets_models_label = "Sheets/Models Processed"
        sheets_models_value = f"{sheets_processed} (1 model per sheet)"
    else:
        sheets_models_label = "Sheets/Models Processed"
        sheets_models_value = f"{sheets_processed} sheets, {unique_models} unique models"

    # Sheet issue percentages
    pct_sheets_with_issues = round(sheets_with_issues / sheets_processed * 100) if sheets_processed > 0 else 0
    pct_sheets_clean = round(sheets_clean / sheets_processed * 100) if sheets_processed > 0 else 0

    summary_data = [
        ["Run ID", run_id],
        ["Source File", source_file],
        ["Generated At", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")],
        [sheets_models_label, sheets_models_value],
        ["Source Accessories", f"{total_records_in} rows (wide-format input, after step 1 validation)"],
        ["Output Records", f"{total_records_out} rows (EN + FR trim-level combinations, post-processing)"],
        ["Trim Coverage", f"{successful_trims} of {total_trims} unique model-trim combos matched ({pct_trim_coverage}%)"] if total_trims > 0 else ["Trim Coverage", "No trims processed"],
        ["Total DQ Warnings", f"{total_warnings} ({pct_warnings}% of source accessories)"],
        ["DQ Warnings by Rule", dq_by_rule],
        ["Model Lookup Issues", lookup_by_type],
        ["Sheets with Issues", f"{sheets_with_issues} of {sheets_processed} sheets ({pct_sheets_with_issues}%)"],
        ["Clean Sheets", f"{sheets_clean} of {sheets_processed} sheets ({pct_sheets_clean}%)"],
    ]
    return pd.DataFrame(summary_data, columns=["Key", "Value"])


def _build_model_profile(
    run_stats: List[Dict],
    all_frames: Dict[str, pd.DataFrame],
    profile_col: str = "Trim",
) -> pd.DataFrame:
    """Build Model Profile section: one row per model with trim/package breakdown in Records Out cell.
    Aggregates all sheet_names for the same model into a single row (for consolidated multi-year models).
    """
    if not run_stats:
        return pd.DataFrame()

    from collections import defaultdict
    model_lang_frames: dict = defaultdict(dict)
    for key, df in all_frames.items():
        for suffix in ("_EN", "_FR"):
            if key.endswith(suffix):
                model_lang_frames[key[:-len(suffix)]][suffix[1:]] = df
                break

    # Aggregate by model_name: combine all sheets and stats belonging to the same model
    agg: dict = {}
    for stat in run_stats:
        model_name = stat.get("model_name", "unknown")
        entry = agg.setdefault(model_name, {"sheets": [], "records_in": 0, "dq_warnings": 0})
        entry["sheets"].append(stat.get("sheet_name", "unknown"))
        entry["records_in"] += stat.get("records_in", 0)
        entry["dq_warnings"] += stat.get("dq_warnings", 0)

    data = []
    for model_name, entry in agg.items():
        lang_frames = model_lang_frames.get(model_name, {})
        records_out = _build_trim_records_out_text(lang_frames, profile_col)

        data.append({
            "Model": model_name,
            "Sheet": ", ".join(entry["sheets"]),
            "Records In": entry["records_in"],
            "Records Out": records_out,
            "DQ Warnings": entry["dq_warnings"],
        })
    return pd.DataFrame(data)


def _build_trim_records_out_text(lang_frames: Dict[str, pd.DataFrame], profile_col: str = "Trim") -> str:
    """Format trim/package counts as a multi-line string: 'ES (127 EN | 127 FR)' per line."""
    if not lang_frames:
        return ""

    all_trims: set = set()
    for df in lang_frames.values():
        if profile_col in df.columns:
            all_trims.update(df[profile_col].dropna().unique())

    if not all_trims:
        return ""

    lines = []
    for trim in sorted(all_trims):
        parts = []
        for lang in ("EN", "FR"):
            if lang in lang_frames and profile_col in lang_frames[lang].columns:
                count = int((lang_frames[lang][profile_col] == trim).sum())
                parts.append(f"{count} {lang}")
        lines.append(f"{trim} ({' | '.join(parts)})")
    return "\n".join(lines)


def _write_data_issues_sheet(
    writer: pd.ExcelWriter,
    dq_logger: DQLogger,
) -> None:
    """Write _Data_Issues sheet with DQ Records table (data steward view). Skip if no issues."""
    dq_records_df = _build_dq_records(dq_logger)
    if dq_records_df.empty:
        return

    dq_records_df.to_excel(writer, sheet_name="_Data_Issues", index=False, startrow=0)
    ws = writer.sheets["_Data_Issues"]

    # Column widths (openpyxl API, not XlsxWriter)
    ws.column_dimensions["A"].width = 25   # Sheet
    ws.column_dimensions["B"].width = 20   # Model
    ws.column_dimensions["C"].width = 12   # Record Index
    ws.column_dimensions["D"].width = 25   # Rule
    ws.column_dimensions["E"].width = 60   # Issue (wide — holds detailed failure messages)
    ws.column_dimensions["F"].width = 18   # Part Number
    ws.column_dimensions["G"].width = 45   # Description

    # Format header row
    header_row = 1
    ws.row_dimensions[header_row].height = 20

    # Format data rows
    for row_offset in range(len(dq_records_df)):
        ws.row_dimensions[header_row + 1 + row_offset].height = 18


def _build_dq_records(dq_logger: DQLogger) -> pd.DataFrame:
    """Build DQ Records table: all issues requiring review."""
    if not dq_logger.records:
        return pd.DataFrame()

    data = []
    for record in dq_logger.records:
        snapshot = record.get("record_snapshot", {})
        part_number = snapshot.get("part_number", "")
        description = snapshot.get("english_description") or snapshot.get("description", "")

        data.append({
            "Sheet": record.get("sheet_name", ""),
            "Model": record.get("model_name", ""),
            "Record Index": record.get("record_index", -1),
            "Rule": record.get("rule_violated", ""),
            "Issue": record.get("issue_description", ""),
            "Part Number": part_number,
            "Description": description,
        })
    return pd.DataFrame(data)
