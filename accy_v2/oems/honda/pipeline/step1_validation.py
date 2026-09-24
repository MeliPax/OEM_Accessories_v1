"""Step 1: Validation & Metadata Extraction

Validates Honda Excel file structure, extracts metadata, and logs validation results.

Part 1: Sheet Validation — Load workbook, verify EN/FR sheets exist
Part 2: Metadata Extraction — Two-level fallback (top 5 rows → regex search)
Part 3: Section Detection — Find all 6 sections, verify order
Part 4: Column Validation — Check headers, extract trim columns
Part 5: DQ Logging — Accumulate warnings with severity
Part 6: Output & Returns — Build metadata dict, return three outputs
"""

from pathlib import Path
from typing import Tuple, Dict, Any, Optional
import re

import openpyxl
import pandas as pd


class ValidationError(Exception):
    """Raised when FATAL validation errors occur."""
    pass


# ============================================================================
# Part 1: Sheet Validation (1-2 hours)
# ============================================================================

def _load_sheets(
    excel_file: str,
    config: Dict[str, Any],
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, str]]:
    """Load EN and FR sheets from Excel workbook.

    Args:
        excel_file: Path to Excel file
        config: Pipeline configuration

    Returns:
        Tuple of (en_df, fr_df, sheet_names_dict)

    Raises:
        ValidationError: If sheets don't exist or can't be loaded
    """
    file_path = Path(excel_file)

    # Load workbook to list sheet names
    try:
        wb = openpyxl.load_workbook(file_path, data_only=True)
    except Exception as e:
        raise ValidationError(f"Cannot read Excel file: {file_path}") from e

    sheet_names = wb.sheetnames

    # Find EN and FR sheets matching pattern *_APP_EN and *_APP_FR
    en_sheet = None
    fr_sheet = None

    for name in sheet_names:
        if name.endswith("_APP_EN") or name.endswith("APP_EN"):
            en_sheet = name
        elif name.endswith("_APP_FR") or name.endswith("APP_FR"):
            fr_sheet = name

    if not en_sheet or not fr_sheet:
        missing = []
        if not en_sheet:
            missing.append("EN sheet (*_APP_EN)")
        if not fr_sheet:
            missing.append("FR sheet (*_APP_FR)")
        raise ValidationError(
            f"Missing required sheets: {', '.join(missing)}. "
            f"Found sheets: {sheet_names}"
        )

    # Load sheets into DataFrames
    try:
        en_df = pd.read_excel(file_path, sheet_name=en_sheet, dtype=str)
        fr_df = pd.read_excel(file_path, sheet_name=fr_sheet, dtype=str)
    except Exception as e:
        raise ValidationError(f"Cannot read EN or FR sheet: {e}") from e

    return en_df, fr_df, {
        "en_sheet_name": en_sheet,
        "fr_sheet_name": fr_sheet,
    }


# ============================================================================
# Part 2: Metadata Extraction (1-2 hours)
# ============================================================================

def _level_1_quick_scan(
    df: pd.DataFrame,
    config: Dict[str, Any],
    language: str = "en",
) -> Tuple[Optional[str], Optional[int]]:
    """Scan top 5 rows for model name and year keywords.

    Args:
        df: DataFrame to scan
        config: Pipeline configuration
        language: "en" or "fr"

    Returns:
        Tuple of (model_name, model_year) or (None, None) if not found
    """
    l1_config = config["metadata_extraction"]["level_1_quick_scan"]
    rows_to_scan = l1_config["rows_to_scan"]

    keywords_config = l1_config["keywords"]
    model_name_keywords = keywords_config["model_name"][language]
    model_year_keywords = keywords_config["model_year"][language]

    model_name = None
    model_year = None

    # Look for keywords in COLUMN NAMES; adjacent column name is the value
    col_list = df.columns.tolist()
    for idx, col_name in enumerate(col_list):
        col_name_lower = str(col_name).strip().lower()

        # Check if column name is a model_name keyword
        if col_name_lower in [k.lower() for k in model_name_keywords] and not model_name:
            # Get next column name as the value
            if idx + 1 < len(col_list):
                model_name = col_list[idx + 1]

        # Check if column name is a model_year keyword
        if col_name_lower in [k.lower() for k in model_year_keywords] and not model_year:
            # Get next column name and try to parse as year
            if idx + 1 < len(col_list):
                try:
                    year = int(col_list[idx + 1])
                    if 2000 <= year <= 2050:
                        model_year = year
                except ValueError:
                    pass

    # Fallback: search data rows if year not found in column names
    if not model_year:
        search_df = df.iloc[:rows_to_scan].fillna("")
        for idx, row in search_df.iterrows():
            row_list = row.tolist()
            for keyword in model_year_keywords:
                # Check each cell in the row
                for col_idx, cell_val in enumerate(row_list):
                    if str(cell_val).strip().lower() == keyword.lower():
                        # Found keyword, try next cell value in same row
                        if col_idx + 1 < len(row_list):
                            try:
                                year = int(str(row_list[col_idx + 1]).strip())
                                if 2000 <= year <= 2050:
                                    model_year = year
                                    break
                            except ValueError:
                                pass
                if model_year:
                    break
            if model_year:
                break

    return model_name, model_year


def _level_2_regex_search(
    df: pd.DataFrame,
    config: Dict[str, Any],
    language: str = "en",
) -> Tuple[Optional[str], Optional[int]]:
    """Regex search entire sheet for model name and year.

    Args:
        df: DataFrame to search
        config: Pipeline configuration
        language: "en" or "fr"

    Returns:
        Tuple of (model_name, model_year) or (None, None) if not found
    """
    l2_config = config["metadata_extraction"]["level_2_regex_search"]
    patterns = l2_config["patterns"]

    model_name_pattern = patterns["model_name"][language]
    model_year_pattern = patterns["model_year"][language]

    model_name = None
    model_year = None

    # Search line-by-line to avoid DataFrame string representation issues
    for col in df.columns:
        for val in df[col].fillna("").astype(str):
            # Search model name
            if not model_name:
                match = re.search(model_name_pattern, val)
                if match:
                    model_name = match.group(2).strip()
            # Search model year
            if not model_year:
                match = re.search(model_year_pattern, val)
                if match:
                    try:
                        model_year = int(match.group(2))
                    except (ValueError, IndexError):
                        pass

    return model_name, model_year


def _extract_metadata(
    en_df: pd.DataFrame,
    fr_df: pd.DataFrame,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Extract model name and year from sheets.

    Args:
        en_df: English sheet DataFrame
        fr_df: French sheet DataFrame
        config: Pipeline configuration

    Returns:
        Dictionary with extracted metadata

    Raises:
        ValidationError: If both levels fail
    """
    metadata = {}

    # Try Level 1 (quick scan)
    model_name, model_year = _level_1_quick_scan(en_df, config, "en")

    # If Level 1 fails on specific fields, try Level 2 (regex) for those fields only
    if not model_name or not model_year:
        l2_name, l2_year = _level_2_regex_search(en_df, config, "en")
        if not model_name:
            model_name = l2_name
        if not model_year:
            model_year = l2_year

    # Validate extraction
    val_config = config["metadata_extraction"]["validation"]
    year_min = val_config["year_range_min"]
    year_max = val_config["year_range_max"]

    if not model_name or not model_name.strip():
        raise ValidationError("Model name extraction failed at both levels")

    if not model_year or not (year_min <= model_year <= year_max):
        raise ValidationError(
            f"Model year extraction failed or out of range. "
            f"Got: {model_year}, expected: [{year_min}, {year_max}]"
        )

    metadata["model_name"] = model_name.strip()
    metadata["vehicle_year"] = model_year

    return metadata


# ============================================================================
# Part 3: Section Detection (1-2 hours) — SCAFFOLD
# ============================================================================

def _detect_sections(
    en_df: pd.DataFrame,
    fr_df: pd.DataFrame,
    config: Dict[str, Any],
) -> Tuple[Dict[str, Any], list]:
    """Detect all 6 sections in EN and FR sheets.

    Returns:
        Tuple of (section_structure, warnings)
    """
    # TODO: Implement Part 3
    # Load section patterns from config
    # Search for each section header (EN and FR)
    # Verify all 6 found, verify order
    # Return section_structure dict with row numbers
    return {}, []


# ============================================================================
# Part 4: Column Validation (1-2 hours) — SCAFFOLD
# ============================================================================

def _validate_columns(
    en_df: pd.DataFrame,
    fr_df: pd.DataFrame,
    config: Dict[str, Any],
    section_structure: Dict[str, Any],
) -> Tuple[Dict[str, Any], list]:
    """Validate column headers and extract trim columns.

    Returns:
        Tuple of (column_metadata, warnings)
    """
    # TODO: Implement Part 4
    # For each section: validate headers, extract trim columns
    # Create column name mappings (EN→canonical, FR→canonical)
    # Return column_metadata dict
    return {}, []


# ============================================================================
# Part 5: DQ Logging (30-60 min) — SCAFFOLD
# ============================================================================

def _build_dq_warnings(warnings_list: list) -> list:
    """Convert warnings collected during validation to DQ format.

    Args:
        warnings_list: List of warning dicts from parts 3-4

    Returns:
        List of DQ warning records
    """
    # TODO: Implement Part 5
    # Consolidate all warnings from parts 3-4
    # Return list of {rule, severity, section, message} dicts
    return warnings_list


# ============================================================================
# Part 6: Main Validate Function
# ============================================================================

def validate(
    excel_file: str,
    config: Dict[str, Any],
) -> Tuple[Tuple[pd.DataFrame, pd.DataFrame], Dict[str, Any], list]:
    """Validate Honda Excel file and extract metadata.

    Args:
        excel_file: Path to Honda Excel workbook (EN + FR sheets)
        config: Pipeline configuration (from pipeline.yaml)

    Returns:
        Tuple of ((en_df, fr_df), metadata_dict, dq_warnings_list)

    Raises:
        ValidationError: If FATAL validation errors occur
    """
    # Part 1: Load sheets
    en_df, fr_df, sheet_names = _load_sheets(excel_file, config)

    # Part 2: Extract metadata
    metadata = _extract_metadata(en_df, fr_df, config)
    metadata.update(sheet_names)

    # Part 3: Detect sections
    section_structure, section_warnings = _detect_sections(en_df, fr_df, config)
    metadata["section_structure"] = section_structure

    # Part 4: Validate columns
    column_metadata, column_warnings = _validate_columns(
        en_df, fr_df, config, section_structure
    )
    metadata.update(column_metadata)

    # Part 5: Consolidate DQ warnings
    all_warnings = section_warnings + column_warnings
    dq_warnings = _build_dq_warnings(all_warnings)

    # Part 6: Return
    metadata["validation_status"] = "PASS" if not dq_warnings else "PASS_WITH_WARNINGS"

    return (en_df, fr_df), metadata, dq_warnings
