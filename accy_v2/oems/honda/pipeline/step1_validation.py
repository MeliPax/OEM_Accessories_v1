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
# Part 3: Section Detection (1-2 hours)
# ============================================================================

def _detect_sections(
    en_df: pd.DataFrame,
    fr_df: pd.DataFrame,
    config: Dict[str, Any],
) -> Tuple[Dict[str, Any], list]:
    """Detect all 6 sections in EN and FR sheets.

    Args:
        en_df: English sheet DataFrame
        fr_df: French sheet DataFrame
        config: Pipeline configuration

    Returns:
        Tuple of (section_structure, warnings_list)
    """
    warnings = []
    section_config = config.get("section_config", {})

    # Load section patterns - use inline config if section_patterns.yaml not loaded
    if "sections" in config:
        sections_data = config["sections"]
    else:
        # Use default from section_patterns.yaml structure
        sections_data = {
            "packages": {"en": "1.0 Packages and Kits", "fr": "1.0 Groupes et ensembles"},
            "wheels": {"en": "2.0 Wheels and Wheel Accessories", "fr": "2.0 Jantes et accessoires de jantes"},
            "exterior": {"en": "3.0 Exterior", "fr": "3.0 Extérieur"},
            "interior": {"en": "4.0 Interior", "fr": "4.0 Intérieur"},
            "electrical": {"en": "5.0 Electrical", "fr": "5.0 Électrique"},
            "paint_pens": {"en": "6.0 Paint Pens", "fr": "6.0 Stylos à peinture"},
        }

    section_order = ["packages", "wheels", "exterior", "interior", "electrical", "paint_pens"]
    section_structure = {}
    en_section_rows = {}
    fr_section_rows = {}

    # Detect sections in EN sheet
    for section_name in section_order:
        section_data = sections_data.get(section_name, {})
        en_text = section_data.get("en", "")

        # Search for section header in EN sheet
        found_row = None

        # Check column names first (pandas uses first row with data as header)
        for col_name in en_df.columns:
            if str(col_name).strip() == en_text:
                found_row = 0  # Section header is in first row (used as column name)
                break

        # If not found in columns, search data rows
        if found_row is None:
            for idx, row in en_df.iterrows():
                for cell_val in row:
                    if str(cell_val).strip() == en_text:
                        found_row = idx
                        break
                if found_row is not None:
                    break

        if found_row is not None:
            en_section_rows[section_name] = found_row
        else:
            # Section not found
            warnings.append({
                "rule": "missing_section_rule",
                "severity": "FATAL",
                "section": section_name,
                "message": f"Section '{en_text}' not found in EN sheet",
            })

    # Detect sections in FR sheet
    for section_name in section_order:
        section_data = sections_data.get(section_name, {})
        fr_text = section_data.get("fr", "")

        # Search for section header in FR sheet
        found_row = None

        # Check column names first (pandas uses first row with data as header)
        for col_name in fr_df.columns:
            if str(col_name).strip() == fr_text:
                found_row = 0  # Section header is in first row (used as column name)
                break

        # If not found in columns, search data rows
        if found_row is None:
            for idx, row in fr_df.iterrows():
                for cell_val in row:
                    if str(cell_val).strip() == fr_text:
                        found_row = idx
                        break
                if found_row is not None:
                    break

        if found_row is not None:
            fr_section_rows[section_name] = found_row
        else:
            # Section not found in FR
            warnings.append({
                "rule": "missing_section_rule",
                "severity": "WARNING",
                "section": section_name,
                "message": f"Section '{fr_text}' not found in FR sheet",
            })

    # Check all sections found in EN
    if len(en_section_rows) < len(section_order):
        missing_sections = [s for s in section_order if s not in en_section_rows]
        if section_config.get("require_all_sections", True):
            # FATAL if all sections required
            pass  # Already logged above

    # Verify section order in EN sheet
    if section_config.get("enforce_section_order", True):
        en_rows = [en_section_rows.get(s) for s in section_order if s in en_section_rows]
        # Check if rows are in increasing order
        for i in range(len(en_rows) - 1):
            if en_rows[i] is not None and en_rows[i+1] is not None:
                if en_rows[i] >= en_rows[i+1]:
                    warnings.append({
                        "rule": "section_order_rule",
                        "severity": "WARNING",
                        "section": f"{section_order[i]} vs {section_order[i+1]}",
                        "message": f"Sections out of order: {section_order[i]} (row {en_rows[i]}) >= {section_order[i+1]} (row {en_rows[i+1]})",
                    })

    # Build section_structure dict with status
    for section_name in section_order:
        section_structure[section_name] = {
            "en_row": en_section_rows.get(section_name),
            "fr_row": fr_section_rows.get(section_name),
            "status": "found" if section_name in en_section_rows else "missing",
        }

    return section_structure, warnings


# ============================================================================
# Part 4: Column Validation (1-2 hours)
# ============================================================================

def _validate_columns(
    en_df: pd.DataFrame,
    fr_df: pd.DataFrame,
    config: Dict[str, Any],
    section_structure: Dict[str, Any],
) -> Tuple[Dict[str, Any], list]:
    """Validate column headers and extract trim columns per section.

    Args:
        en_df: English sheet DataFrame
        fr_df: French sheet DataFrame
        config: Pipeline configuration
        section_structure: Section boundaries from Part 3

    Returns:
        Tuple of (column_metadata, warnings_list)
    """
    warnings = []
    column_metadata = {}

    # Expected columns from config
    expected_en_cols = config.get("column_headers", {}).get("en", [
        "Description", "Part Number", "Dealer Net", "List Price", "FRT", "Installed Price"
    ])
    expected_fr_cols = config.get("column_headers", {}).get("fr", [
        "La description", "Numéro de pièce", "Prix net", "Prix de liste", "T.F.F.", "Prix installé"
    ])

    # Column name mappings (standardized names for downstream processing)
    column_mappings_en = {
        "Description": "description",
        "Part Number": "part_number",
        "Dealer Net": "dealer_net",
        "List Price": "list_price",
        "FRT": "frt",
        "Installed Price": "installed_price",
    }

    column_mappings_fr = {
        "La description": "description",
        "Numéro de pièce": "part_number",
        "Prix net": "dealer_net",
        "Prix de liste": "list_price",
        "T.F.F.": "frt",
        "Prix installé": "installed_price",
    }

    section_order = ["packages", "wheels", "exterior", "interior", "electrical", "paint_pens"]
    trim_columns_dict = {}
    en_trim_columns_by_section = {}
    fr_trim_columns_by_section = {}

    # Validate columns and extract trim columns for each section
    for section_name in section_order:
        section_data = section_structure.get(section_name, {})
        en_row = section_data.get("en_row")
        fr_row = section_data.get("fr_row")

        if en_row is None:
            continue  # Section not found, already logged as FATAL in Part 3

        # Determine header row: if section_row == 0, section header IS in df.columns
        # and the ACTUAL headers are at df.iloc[0] (first data row)
        # Otherwise, headers are at section_row + 1
        if en_row == 0:
            # Section header is in column names, actual headers are in first data row
            if len(en_df) == 0:
                warnings.append({
                    "rule": "invalid_header_row_rule",
                    "severity": "WARNING",
                    "section": section_name,
                    "message": f"EN section has no data rows (cannot read headers)",
                })
                en_trim_columns_by_section[section_name] = []
                continue
            en_header_row = en_df.iloc[0]
            en_headers = [str(h).strip() for h in en_header_row]
        else:
            # Headers are in the row immediately after section header
            header_row_idx = en_row + 1
            if header_row_idx >= len(en_df):
                warnings.append({
                    "rule": "invalid_header_row_rule",
                    "severity": "WARNING",
                    "section": section_name,
                    "message": f"EN section header row {header_row_idx} out of bounds (sheet has {len(en_df)} rows)",
                })
                en_trim_columns_by_section[section_name] = []
                continue

            # Read header row from EN sheet
            en_header_row = en_df.iloc[header_row_idx]
            en_headers = [str(h).strip() for h in en_header_row]

            # Check for missing expected columns
            missing_en = [col for col in expected_en_cols if col not in en_headers]
            if missing_en:
                warnings.append({
                    "rule": "missing_columns_rule",
                    "severity": "WARNING",
                    "section": section_name,
                    "message": f"EN section missing columns: {', '.join(missing_en)}",
                })

            # Extract trim columns (after "Installed Price" until stop marker or end)
            trim_cols = []
            if "Installed Price" in en_headers:
                price_idx = en_headers.index("Installed Price")
                stop_markers = ["application", "notes", "remarks", ""]
                for idx in range(price_idx + 1, len(en_headers)):
                    col_name = en_headers[idx]
                    col_lower = str(col_name).lower().strip()
                    # Stop if we hit a marker or empty column
                    if col_lower in stop_markers or not col_lower or col_lower == "nan":
                        break
                    # Filter out NaN values
                    if col_lower != "nan":
                        trim_cols.append(col_name)
            else:
                warnings.append({
                    "rule": "missing_price_column_rule",
                    "severity": "WARNING",
                    "section": section_name,
                    "message": f"EN section missing 'Installed Price' column (cannot extract trim columns)",
                })

            en_trim_columns_by_section[section_name] = trim_cols

        # Validate FR headers (if section exists in FR sheet)
        if fr_row is not None:
            if fr_row == 0:
                # Section header is in column names, actual headers are in first data row
                if len(fr_df) == 0:
                    warnings.append({
                        "rule": "invalid_header_row_rule",
                        "severity": "WARNING",
                        "section": section_name,
                        "message": f"FR section has no data rows (cannot read headers)",
                    })
                    fr_trim_columns_by_section[section_name] = []
                    continue
                fr_header_row = fr_df.iloc[0]
                fr_headers = [str(h).strip() for h in fr_header_row]
            else:
                # Headers are in the row immediately after section header
                header_row_idx_fr = fr_row + 1
                if header_row_idx_fr >= len(fr_df):
                    warnings.append({
                        "rule": "invalid_header_row_rule",
                        "severity": "WARNING",
                        "section": section_name,
                        "message": f"FR section header row {header_row_idx_fr} out of bounds (sheet has {len(fr_df)} rows)",
                    })
                    fr_trim_columns_by_section[section_name] = []
                    continue

                # Read header row from FR sheet
                fr_header_row = fr_df.iloc[header_row_idx_fr]
                fr_headers = [str(h).strip() for h in fr_header_row]

            # Check for missing expected columns
            missing_fr = [col for col in expected_fr_cols if col not in fr_headers]
            if missing_fr:
                warnings.append({
                    "rule": "missing_columns_rule",
                    "severity": "WARNING",
                    "section": section_name,
                    "message": f"FR section missing columns: {', '.join(missing_fr)}",
                })

            # Extract trim columns from FR sheet
            trim_cols_fr = []
            if "Prix installé" in fr_headers:
                price_idx_fr = fr_headers.index("Prix installé")
                stop_markers = ["application", "notes", "remarques", ""]
                for idx in range(price_idx_fr + 1, len(fr_headers)):
                    col_name = fr_headers[idx]
                    col_lower = str(col_name).lower().strip()
                    if col_lower in stop_markers or not col_lower or col_lower == "nan":
                        break
                    # Filter out NaN values
                    if col_lower != "nan":
                        trim_cols_fr.append(col_name)
            else:
                warnings.append({
                    "rule": "missing_price_column_rule",
                    "severity": "WARNING",
                    "section": section_name,
                    "message": f"FR section missing 'Prix installé' column",
                })

            fr_trim_columns_by_section[section_name] = trim_cols_fr
        else:
            fr_trim_columns_by_section[section_name] = []

    # Build final trim columns structure (EN trim columns are primary)
    trim_columns_dict = {
        section_name: {
            "en_trims": en_trim_columns_by_section.get(section_name, []),
            "fr_trims": fr_trim_columns_by_section.get(section_name, []),
        }
        for section_name in section_order
    }

    column_metadata["column_mappings_en"] = column_mappings_en
    column_metadata["column_mappings_fr"] = column_mappings_fr
    column_metadata["trim_columns"] = trim_columns_dict

    return column_metadata, warnings


# ============================================================================
# Part 5: DQ Logging (30-60 min) — SCAFFOLD
# ============================================================================

def _build_dq_warnings(warnings_list: list) -> list:
    """Consolidate and format DQ warnings from all validation parts.

    Args:
        warnings_list: List of warning dicts from parts 3-4
                      Expected format: {rule, severity, section, message}

    Returns:
        List of consolidated DQ warning records, ordered by severity (FATAL → WARNING)
    """
    if not warnings_list:
        return []

    # Define severity ordering (lower index = higher priority)
    severity_order = {"FATAL": 0, "ERROR": 1, "WARNING": 2}

    # Sort warnings by severity (FATAL first, then ERROR, then WARNING)
    sorted_warnings = sorted(
        warnings_list,
        key=lambda w: (severity_order.get(w.get("severity"), 3), w.get("section", ""))
    )

    # Format each warning for output
    formatted_warnings = []
    for warning in sorted_warnings:
        # Ensure all required fields are present
        formatted_warning = {
            "rule": warning.get("rule", "unknown_rule"),
            "severity": warning.get("severity", "WARNING"),
            "section": warning.get("section", "unknown"),
            "message": warning.get("message", "No message provided"),
        }
        formatted_warnings.append(formatted_warning)

    return formatted_warnings


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

    # Check for FATAL section errors
    fatal_warnings = [w for w in section_warnings if w.get("severity") == "FATAL"]
    if fatal_warnings:
        fatal_msg = "; ".join([w.get("message", "Unknown error") for w in fatal_warnings])
        raise ValidationError(f"Section detection failed: {fatal_msg}")

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
