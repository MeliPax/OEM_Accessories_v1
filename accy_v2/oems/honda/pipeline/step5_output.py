"""Step 5: Output Generation & DQ Reporting

Generates Excel workbook with language-specific sheets, raw data audit trail,
confidence metrics, and data quality warnings.
"""

from typing import Tuple, Dict, Any, Optional
import os
from datetime import datetime

import pandas as pd
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from accy_v2.core.helpers.output_column_mapper import apply_downstream_column_mapping


def prepare_frames(
    transformed_dict: Dict[str, pd.DataFrame],
    metadata: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, pd.DataFrame]:
    """Apply column mapping per language and prepare output frames.

    Args:
        transformed_dict: Dictionary of {lang: DataFrame} or {section: DataFrame}
        metadata: Metadata from pipeline
        config: Pipeline configuration

    Returns:
        Dictionary of {sheet_name: DataFrame} ready for Excel output
    """
    model_name = metadata.get("model_name", "unknown")
    downstream_schema = config.get("downstream_schema", {})

    frames: Dict[str, pd.DataFrame] = {}

    # Handle both EN/FR split and regular dataframes
    for lang_or_section, df in transformed_dict.items():
        if df is None or df.empty:
            continue

        # Determine sheet name and language
        if lang_or_section in ["EN", "FR"]:
            sheet_key = f"Accessories_{lang_or_section}"
            language = lang_or_section
        else:
            # Non-language keyed data (raw data, confidence, DQ)
            sheet_key = lang_or_section
            language = "MIXED"

        # Apply column mapping if available
        if language in ["EN", "FR"]:
            df = apply_downstream_column_mapping(df, downstream_schema, language)

        frames[sheet_key] = df

    return frames


def prepare_raw_data_sheet(df: pd.DataFrame, metadata: Dict[str, Any]) -> pd.DataFrame:
    """Create raw data sheet with source tracking and merge confidence.

    Args:
        df: Main enriched DataFrame
        metadata: Pipeline metadata (contains reconciliation_map, en/fr status)

    Returns:
        DataFrame for RawData sheet
    """
    raw_data_cols = {
        "part_number": df.get("part_number", pd.Series(dtype=str)),
        "model": df.get("model", pd.Series(dtype=str)),
        "year_from": df.get("year_from", pd.Series(dtype=int)),
        "en_found": True if "description" in df.columns else False,
        "fr_found": True if "description_fr" in df.columns else False,
        "merge_confidence": df.get("merge_confidence", pd.Series(dtype=float)),
        "reconciliation_status": df.get("reconciliation_status", pd.Series(dtype=str)),
    }

    raw_data = pd.DataFrame(raw_data_cols)
    return raw_data


def prepare_confidence_sheet(df: pd.DataFrame) -> pd.DataFrame:
    """Create confidence metrics sheet with model lookup quality scores.

    Args:
        df: Main enriched DataFrame with model_status and confidence scores

    Returns:
        DataFrame for Confidence sheet
    """
    confidence_cols = [
        "part_number",
        "model",
        "model_number",
        "model_status",
        "merge_confidence",
    ]

    confidence_data = df[[col for col in confidence_cols if col in df.columns]].copy()

    # Add computed confidence from model_status
    status_confidence_map = {
        "EXACT_MATCH": 0.95,
        "HIGH_CONFIDENCE": 0.80,
        "LOW_CONFIDENCE": 0.50,
        "NOT_FOUND": 0.0,
    }
    confidence_data["confidence"] = confidence_data.get("model_status", pd.Series()).map(
        status_confidence_map
    )

    return confidence_data


def prepare_dq_sheet(dq_warnings: list) -> pd.DataFrame:
    """Create DQ sheet with all warnings aggregated by rule type.

    Args:
        dq_warnings: List of DQ warning dictionaries from pipeline

    Returns:
        DataFrame for DQ sheet
    """
    if not dq_warnings:
        return pd.DataFrame(
            columns=[
                "part_number",
                "model",
                "rule_type",
                "severity",
                "message",
                "section",
            ]
        )

    dq_data = []
    for warning in dq_warnings:
        dq_data.append(
            {
                "part_number": warning.get("part_number", ""),
                "model": warning.get("model", ""),
                "rule_type": warning.get("rule_type", ""),
                "severity": warning.get("severity", "WARNING"),
                "message": warning.get("message", ""),
                "section": warning.get("section", ""),
            }
        )

    return pd.DataFrame(dq_data)


def _format_excel_sheet(ws, df: pd.DataFrame, sheet_name: str):
    """Apply formatting to Excel worksheet.

    Args:
        ws: openpyxl worksheet object
        df: DataFrame to format
        sheet_name: Name of sheet (for conditional formatting)
    """
    # Header formatting
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    for cell in ws[1]:
        if cell.value:
            cell.fill = header_fill
            cell.font = header_font
            cell.border = thin_border
            cell.alignment = Alignment(horizontal="center", vertical="center")

    # Data formatting
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
        for cell in row:
            cell.border = thin_border

            # Conditional formatting for Status column (DQ sheet)
            if "Status" in str(cell.column_letter) and "DQ" in sheet_name:
                if cell.value == "NOT_FOUND":
                    cell.fill = PatternFill(start_color="FFB6C6", end_color="FFB6C6", fill_type="solid")
                elif cell.value == "LOW_CONFIDENCE":
                    cell.fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
                elif cell.value == "HIGH_CONFIDENCE":
                    cell.fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
                elif cell.value == "EXACT_MATCH":
                    cell.fill = PatternFill(start_color="70AD47", end_color="70AD47", fill_type="solid")

    # Set column widths
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column].width = adjusted_width


def generate_output(
    df: pd.DataFrame,
    metadata: Dict[str, Any],
    config: Dict[str, Any],
    dq_warnings: list,
    output_dir: Optional[str] = None,
    run_id: str = "",
    flat_data_en: Optional[pd.DataFrame] = None,
    flat_data_fr: Optional[pd.DataFrame] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Generate Excel workbook with sheets (Accessories_EN/FR, FlatData_EN/FR, RawData, Confidence, DQ).

    Args:
        df: Enriched DataFrame from Step 4.5 (combined EN/FR)
        metadata: Metadata from all steps
        config: Pipeline configuration
        dq_warnings: All DQ warnings from pipeline
        output_dir: Output directory (default: accy_v2/output/honda)
        run_id: Run identifier for filename
        flat_data_en: Flat (melted) EN DataFrame from Step 4
        flat_data_fr: Flat (melted) FR DataFrame from Step 4

    Returns:
        Tuple of (output_file_path, output_metrics)
    """
    if output_dir is None:
        output_dir = os.path.join("accy_v2", "output", "honda")

    os.makedirs(output_dir, exist_ok=True)

    # Prepare output frames
    model_name = metadata.get("model_name", "unknown")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Split EN and FR if present in same dataframe
    df_en = df.copy()
    df_fr = df.copy() if "description_fr" in df.columns else None

    # Create output file
    filename = f"honda_{run_id}_{timestamp}.xlsx"
    output_path = os.path.join(output_dir, filename)

    wb = Workbook()
    wb.remove(wb.active)  # Remove default sheet

    # Add Accessories_EN sheet
    if not df_en.empty:
        ws_en = wb.create_sheet("Accessories_EN")
        en_mapped = apply_downstream_column_mapping(
            df_en, config.get("downstream_schema", {}), "EN"
        )
        if not en_mapped.empty:
            for r_idx, row in enumerate(dataframe_to_rows(en_mapped, index=False, header=True), 1):
                for c_idx, value in enumerate(row, 1):
                    ws_en.cell(row=r_idx, column=c_idx, value=value)
            _format_excel_sheet(ws_en, en_mapped, "Accessories_EN")

    # Add Accessories_FR sheet if present
    if df_fr is not None and not df_fr.empty:
        ws_fr = wb.create_sheet("Accessories_FR")
        fr_mapped = apply_downstream_column_mapping(
            df_fr, config.get("downstream_schema", {}), "FR"
        )
        if not fr_mapped.empty:
            for r_idx, row in enumerate(dataframe_to_rows(fr_mapped, index=False, header=True), 1):
                for c_idx, value in enumerate(row, 1):
                    ws_fr.cell(row=r_idx, column=c_idx, value=value)
            _format_excel_sheet(ws_fr, fr_mapped, "Accessories_FR")

    # Add FlatData_EN sheet (melted/standardized data before enrichment)
    if flat_data_en is not None and not flat_data_en.empty:
        ws_flat_en = wb.create_sheet("FlatData_EN")
        for r_idx, row in enumerate(dataframe_to_rows(flat_data_en, index=False, header=True), 1):
            for c_idx, value in enumerate(row, 1):
                ws_flat_en.cell(row=r_idx, column=c_idx, value=value)
        _format_excel_sheet(ws_flat_en, flat_data_en, "FlatData_EN")

    # Add FlatData_FR sheet (melted/standardized data before enrichment)
    if flat_data_fr is not None and not flat_data_fr.empty:
        ws_flat_fr = wb.create_sheet("FlatData_FR")
        for r_idx, row in enumerate(dataframe_to_rows(flat_data_fr, index=False, header=True), 1):
            for c_idx, value in enumerate(row, 1):
                ws_flat_fr.cell(row=r_idx, column=c_idx, value=value)
        _format_excel_sheet(ws_flat_fr, flat_data_fr, "FlatData_FR")

    # Add RawData sheet
    raw_data = prepare_raw_data_sheet(df_en, metadata)
    if not raw_data.empty:
        ws_raw = wb.create_sheet("RawData")
        for r_idx, row in enumerate(dataframe_to_rows(raw_data, index=False, header=True), 1):
            for c_idx, value in enumerate(row, 1):
                ws_raw.cell(row=r_idx, column=c_idx, value=value)
        _format_excel_sheet(ws_raw, raw_data, "RawData")

    # Add Confidence sheet
    confidence = prepare_confidence_sheet(df_en)
    if not confidence.empty:
        ws_conf = wb.create_sheet("Confidence")
        for r_idx, row in enumerate(dataframe_to_rows(confidence, index=False, header=True), 1):
            for c_idx, value in enumerate(row, 1):
                ws_conf.cell(row=r_idx, column=c_idx, value=value)
        _format_excel_sheet(ws_conf, confidence, "Confidence")

    # Add DQ sheet
    dq_sheet = prepare_dq_sheet(dq_warnings)
    if not dq_sheet.empty:
        ws_dq = wb.create_sheet("DQ")
        for r_idx, row in enumerate(dataframe_to_rows(dq_sheet, index=False, header=True), 1):
            for c_idx, value in enumerate(row, 1):
                ws_dq.cell(row=r_idx, column=c_idx, value=value)
        _format_excel_sheet(ws_dq, dq_sheet, "DQ")

    # Write workbook
    wb.save(output_path)

    # Generate output metrics
    output_metrics = {
        "output_file": output_path,
        "timestamp": timestamp,
        "model": model_name,
        "total_parts": len(df_en),
        "exact_match_count": len(df_en[df_en.get("model_status", "") == "EXACT_MATCH"]),
        "high_confidence_count": len(df_en[df_en.get("model_status", "") == "HIGH_CONFIDENCE"]),
        "low_confidence_count": len(df_en[df_en.get("model_status", "") == "LOW_CONFIDENCE"]),
        "not_found_count": len(df_en[df_en.get("model_status", "") == "NOT_FOUND"]),
        "dq_warning_count": len(dq_warnings),
        "en_fr_reconciled": len(df_fr) if df_fr is not None else 0,
    }

    return output_path, output_metrics
