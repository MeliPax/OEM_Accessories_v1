r"""Step 1: Honda Data Loading & Validation

Validate Honda row-grouped data and return a working_df with extracted metadata.

For each sheet:
1. Validate sheet name (_APP_EN or _APP_FR)
2. Detect language from sheet name
3. Extract model name and year from file headers (rows 0-5)
4. Identify section boundaries using regex pattern ^\d+\.\d+\s+
5. Validate all 6 required sections present and in order
6. For each section: extract header row, identify trim columns
7. Return working_df (unchanged) with complete metadata populated

Section structure (from playground_2):
  - Marker row: Contains section identifier (e.g., "1.0 Packages and Kits")
  - Header row: First row after marker (data_start)
  - Trim sub-header: Second row after marker (data_start + 1)
  - Data rows: Start at data_start + 2
"""

from typing import Any, Dict, Tuple
import pandas as pd
import re

from accy_v2.core.base_pipeline import PipelineFatalError
from accy_v2.core.helpers.dq_logger import DQLogger
from accy_v2.core.helpers.pipeline_logger import PipelineLogger


def run(
    df_raw: pd.DataFrame,
    config: dict,
    meta_data: Dict[str, Any],
    dq_logger: DQLogger,
    pipeline_logger: PipelineLogger,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Validate Honda section-based data and return working_df with metadata.

    Args:
        df_raw: Raw DataFrame from ExcelFile.parse(header=None)
        config: Honda pipeline configuration
        meta_data: Dict to populate with Honda-specific metadata
        dq_logger: DQ logging interface
        pipeline_logger: Pipeline logging interface

    Returns:
        Tuple of (working_df, updated_metadata)
    """
    try:
        if df_raw is None or df_raw.empty:
            raise PipelineFatalError("Raw dataframe is empty")

        working_df = df_raw.copy()
        updated_meta = {}

        # =========================================================================
        # PHASE 1: Sheet-level validation
        # =========================================================================
        sheet_name = meta_data.get("sheet_name", "unknown")
        _validate_sheet_name(sheet_name, pipeline_logger)

        language = _detect_language(sheet_name, pipeline_logger)
        updated_meta["language"] = language
        pipeline_logger.info(f"Sheet '{sheet_name}': Language detected as {language}")

        # =========================================================================
        # PHASE 2: Extract metadata from file headers (rows 0-5)
        # =========================================================================
        model_name = _extract_model_name(working_df, dq_logger, pipeline_logger)
        if not model_name:
            raise PipelineFatalError(f"Sheet '{sheet_name}': Could not extract model name from file headers")
        updated_meta["model_name"] = model_name
        pipeline_logger.info(f"Sheet '{sheet_name}': Model name extracted: {model_name}")

        vehicle_year = _extract_vehicle_year(working_df, meta_data, dq_logger, pipeline_logger)
        if vehicle_year:
            updated_meta["vehicle_year"] = vehicle_year
            pipeline_logger.info(f"Sheet '{sheet_name}': Vehicle year extracted: {vehicle_year}")

        # =========================================================================
        # PHASE 3: Identify section boundaries
        # =========================================================================
        section_structure = _identify_section_boundaries(working_df, config, dq_logger, pipeline_logger)

        if not section_structure:
            raise PipelineFatalError(f"Sheet '{sheet_name}': No sections detected")

        _validate_required_sections(section_structure, config, sheet_name, pipeline_logger)

        updated_meta["section_structure"] = section_structure
        updated_meta["sections_detected"] = len(section_structure)
        pipeline_logger.info(f"Sheet '{sheet_name}': {len(section_structure)} sections detected")

        # =========================================================================
        # PHASE 4: Validate headers per section
        # =========================================================================
        trim_columns_per_section, row_metrics_per_section = _validate_section_headers(
            working_df, section_structure, config, sheet_name, dq_logger, pipeline_logger
        )
        updated_meta["trim_columns_per_section"] = trim_columns_per_section
        updated_meta["row_metrics_per_section"] = row_metrics_per_section
        pipeline_logger.info(f"Sheet '{sheet_name}': Trim columns and row metrics identified for all sections")

        # =========================================================================
        # PHASE 5: Return working_df with complete metadata
        # =========================================================================
        return working_df, updated_meta

    except Exception as e:
        print(f"[DEBUG ERROR] Exception in run(): {e}")
        import traceback
        traceback.print_exc()
        raise


# ============================================================================
# PHASE 1: Sheet-level validation
# ============================================================================


def _validate_sheet_name(sheet_name: str, logger: PipelineLogger) -> None:
    """Verify sheet name matches Honda pattern (_APP_EN or _APP_FR)."""
    if not ("_APP_EN" in sheet_name or "_APP_FR" in sheet_name):
        raise PipelineFatalError(
            f"Sheet '{sheet_name}': Must match pattern _APP_EN or _APP_FR (found: {sheet_name})"
        )


def _detect_language(sheet_name: str, logger: PipelineLogger) -> str:
    """Detect language from sheet name."""
    if "_APP_EN" in sheet_name:
        return "EN"
    elif "_APP_FR" in sheet_name:
        return "FR"
    else:
        raise PipelineFatalError(f"Could not detect language from sheet name: {sheet_name}")


# ============================================================================
# PHASE 2: Extract metadata from file headers
# ============================================================================


def _find_first_section_marker_row(df: pd.DataFrame) -> int or None:
    r"""Find the row number of the first section marker.

    Section markers follow pattern: ^\d+\.\d+\s+(.+)$
    Used to limit metadata search (metadata must appear BEFORE first section).
    """
    df_str = df.astype(str)
    section_pattern = r"^\d+\.\d+\s+(.+)$"

    for idx, row in df_str.iterrows():
        for cell_value in row.values:
            cell_str = str(cell_value).strip()
            if re.match(section_pattern, cell_str):
                return idx

    return None


def _find_metadata_value(
    df: pd.DataFrame,
    keywords: list,
    search_limit_row: int or None,
    logger: PipelineLogger
) -> str or None:
    """Find and extract metadata value by searching for keyword labels.

    Args:
        df: DataFrame to search
        keywords: List of keywords to search for (case-insensitive, substring match)
        search_limit_row: Stop searching at this row (e.g., first section marker row)
        logger: Pipeline logger

    Returns:
        Extracted value (from column after label), or None if not found
    """
    if len(df) == 0:
        return None

    # Determine search range
    max_row = search_limit_row if search_limit_row is not None else len(df)

    for idx in range(min(max_row, len(df))):
        row = df.iloc[idx]

        # Scan all columns for keyword
        for col_idx, val in enumerate(row):
            if pd.notna(val):
                val_str = str(val).lower()
                if any(keyword in val_str for keyword in keywords):
                    # Found keyword label, extract value from next non-empty column
                    for col_idx_next in range(col_idx + 1, len(row)):
                        val_next = row.iloc[col_idx_next]
                        if pd.notna(val_next):
                            val_str_next = str(val_next).strip()
                            if val_str_next and "nan" not in val_str_next.lower():
                                return val_str_next

    return None


def _extract_model_name(df: pd.DataFrame, dq_logger: DQLogger, logger: PipelineLogger) -> str:
    """Extract model name from file headers using dynamic keyword detection.

    Searches from row 0 up to the first section marker.
    Handles both EN ("Model Name") and FR ("Nom du modèle") labels.
    """
    if len(df) == 0:
        return None

    # Find where metadata must end (at first section marker)
    first_marker_row = _find_first_section_marker_row(df)

    # Keywords from config
    model_name_keywords = ["model name", "nom du modèle", "nom du model"]

    return _find_metadata_value(df, model_name_keywords, first_marker_row, logger)


def _extract_vehicle_year(
    df: pd.DataFrame, meta_data: Dict, dq_logger: DQLogger, logger: PipelineLogger
) -> int:
    """Extract vehicle year from file headers using dynamic keyword detection.

    Searches from row 0 up to the first section marker.
    Handles both EN ("Model Year") and FR ("Année modèle") labels.
    Returns integer year in valid range (2000-2050), or None.
    """
    if len(df) == 0:
        return None

    # Find where metadata must end (at first section marker)
    first_marker_row = _find_first_section_marker_row(df)

    # Keywords from config
    year_keywords = ["model year", "année modèle", "année du modèle"]

    # Find the value as string
    year_str = _find_metadata_value(df, year_keywords, first_marker_row, logger)

    if year_str:
        try:
            year_val = int(year_str)
            if 2000 <= year_val <= 2050:
                return year_val
        except (ValueError, TypeError):
            pass

    return None


# ============================================================================
# Header and Trim Sub-Header Detection (Dynamic)
# ============================================================================


def _find_header_row(
    df: pd.DataFrame,
    marker_row: int,
    header_keywords_en: list,
    header_keywords_fr: list,
    max_scan: int = 10,
    logger: PipelineLogger = None
) -> (int, list) or (None, None):
    """Find header row by scanning for column name keywords.

    Args:
        df: DataFrame
        marker_row: Row index of section marker
        header_keywords_en: English column name keywords
        header_keywords_fr: French column name keywords
        max_scan: Max rows to scan after marker
        logger: Optional logger for debug messages

    Returns:
        Tuple of (header_row_index, column_names_list) or (None, None)
    """
    # Scan from marker_row + 1 up to max_scan rows
    for scan_offset in range(1, max_scan + 1):
        candidate_row_idx = marker_row + scan_offset
        if candidate_row_idx >= len(df):
            break

        row = df.iloc[candidate_row_idx]

        # Extract column names from this row
        headers = []
        keyword_count = 0

        for i, col_val in enumerate(row):
            if pd.isna(col_val):
                headers.append(f"_col_{i}")
            else:
                header_str = str(col_val).strip().replace("\n", " ").replace("\r", " ")
                header_str = " ".join(header_str.split())
                if header_str and header_str.lower() != "nan":
                    headers.append(header_str)
                    # Count if this is a known column keyword
                    header_lower = header_str.lower()
                    if any(kw in header_lower for kw in header_keywords_en + header_keywords_fr):
                        keyword_count += 1
                else:
                    headers.append(f"_col_{i}")

        # If we found enough keywords, this is the header row
        if keyword_count >= 2:  # At least 2 product columns (description, part number)
            if logger:
                logger.debug(f"Found header row at index {candidate_row_idx}: {keyword_count} keywords matched")
            return candidate_row_idx, headers

    return None, None


def _is_trim_value(val) -> bool:
    """Check if value looks like a trim name (not numeric, not "0", has content).

    Trim values in sub-header row are typically:
    - Capitalized names: "SPORT", "Type R", "EX-L"
    - Or applicability markers: "•", "T", "E", "X"
    """
    if pd.isna(val):
        return False

    val_str = str(val).strip()
    if not val_str or val_str.lower() == "nan":
        return False

    # Exclude purely numeric values and placeholders
    if val_str in ("0", "0.0"):
        return False

    # If it's all digits, it's not a trim value
    if val_str.isdigit():
        return False

    # Otherwise, it's a valid trim value (has text content)
    return True


def _find_trim_subheader_row(
    df: pd.DataFrame,
    header_row_idx: int,
    product_cols: list,
    applicability_markers: list,
    max_scan: int = 5,
    logger: PipelineLogger = None
) -> int or None:
    """Find trim sub-header row by scanning for applicability markers and trim values.

    Args:
        df: DataFrame
        header_row_idx: Index of header row (to start scanning after it)
        product_cols: Indices of product columns (to exclude from trim detection)
        applicability_markers: List of applicability markers to look for
        max_scan: Max rows to scan after header
        logger: Optional logger

    Returns:
        Index of trim sub-header row, or None if not found
    """
    # Scan from header_row_idx + 1
    for scan_offset in range(1, max_scan + 1):
        candidate_row_idx = header_row_idx + scan_offset
        if candidate_row_idx >= len(df):
            break

        row = df.iloc[candidate_row_idx]

        # Count trim columns with actual values
        trim_count = 0
        for col_idx in range(len(row)):
            # Skip product columns
            if col_idx in product_cols:
                continue

            val = row.iloc[col_idx]
            if _is_trim_value(val):
                trim_count += 1

        # If we found enough trim values, this is the trim sub-header
        if trim_count >= 2:  # At least 2 trim columns with values
            if logger:
                logger.debug(f"Found trim sub-header row at index {candidate_row_idx}: {trim_count} trim columns")
            return candidate_row_idx

    return None


# ============================================================================
# PHASE 3: Identify section boundaries
# ============================================================================


def _identify_section_boundaries(
    df: pd.DataFrame, config: dict, dq_logger: DQLogger, logger: PipelineLogger
) -> Dict[str, Dict]:
    r"""Identify all section boundaries using regex pattern.

    Section marker pattern: ^\d+\.\d+\s+(.+)$
    Returns: {section_name: {marker_row, data_start, data_end, ...}}
    """
    df_str = df.astype(str)
    section_pattern = r"^\d+\.\d+\s+(.+)$"
    section_starts = []

    # Find all section markers
    for idx, row in df_str.iterrows():
        for cell_value in row.values:
            cell_str = str(cell_value).strip()
            match = re.match(section_pattern, cell_str)
            if match:
                section_name = match.group(1).strip()
                section_starts.append((idx, section_name, cell_str))
                break

    # Build section boundaries
    sections = {}
    for i, (marker_row, section_name, marker_text) in enumerate(section_starts):
        # Data starts AFTER the marker row
        data_start = marker_row + 1

        # Data ends BEFORE the next section marker (or at end of dataframe)
        if i + 1 < len(section_starts):
            next_marker_row = section_starts[i + 1][0]
            data_end = next_marker_row - 1
        else:
            # Last section: goes to end of dataframe
            data_end = len(df) - 1

        # Count rows in this section
        if data_start <= data_end:
            total_rows = data_end - data_start + 1

            # Count empty vs non-empty rows
            empty_rows = 0
            non_empty_rows = 0
            for row_idx in range(data_start, data_end + 1):
                if _is_row_empty(df.iloc[row_idx]):
                    empty_rows += 1
                else:
                    non_empty_rows += 1
        else:
            total_rows = 0
            empty_rows = 0
            non_empty_rows = 0

        sections[section_name] = {
            "marker_row": marker_row,
            "data_start": data_start,
            "data_end": data_end,
            "total_rows": total_rows,
            "empty_rows": empty_rows,
            "non_empty_rows": non_empty_rows,
        }

    return sections


def _is_row_empty(row: pd.Series) -> bool:
    """Check if a row is completely empty (all NaN or all whitespace)."""
    for val in row.values:
        if pd.notna(val):
            val_str = str(val).strip()
            if val_str and val_str.lower() != "nan":
                return False
    return True


# ============================================================================
# PHASE 3b: Validate required sections
# ============================================================================


def _validate_required_sections(
    section_structure: Dict, config: dict, sheet_name: str, logger: PipelineLogger
) -> None:
    """Verify all required sections present and have data rows."""
    # Config might be nested under 'step1' key
    step1_config = config.get("step1", config) if isinstance(config, dict) else config
    required_section_count = step1_config.get("expected_section_count", 6) if isinstance(step1_config, dict) else 6

    if len(section_structure) < required_section_count:
        raise PipelineFatalError(
            f"Sheet '{sheet_name}': Expected {required_section_count} sections, found {len(section_structure)}"
        )

    # Check each section has at least one non-empty row
    for section_name, bounds in section_structure.items():
        if bounds["non_empty_rows"] == 0:
            raise PipelineFatalError(f"Sheet '{sheet_name}': Section '{section_name}' has no data rows")


# ============================================================================
# PHASE 3b: Row classification & counting helpers
# ============================================================================


def _is_empty_row(row: pd.Series) -> bool:
    """Check if a row is completely empty (all NaN or all whitespace)."""
    for val in row.values:
        if pd.notna(val):
            val_str = str(val).strip()
            if val_str and val_str.lower() != "nan":
                return False
    return True


def _is_publishing_row(row: pd.Series) -> bool:
    """Detect footer rows containing publication metadata."""
    for val in row.values:
        if pd.notna(val):
            val_str = str(val).lower()
            # Check for common publication/metadata markers
            if any(marker in val_str for marker in ["publication", "last updated", "data as of", "effective"]):
                return True
    return False


def _is_valid_data_row(
    row: pd.Series, product_cols: list, price_cols: list
) -> bool:
    """Row is valid if it has EITHER:
    1. COMPLETE RECORD (Option A - STRICT): BOTH product columns (Part Number AND Description)
    2. PARTIAL RECORD (Option C - INCLUSIVE): ANY product/price column with data

    Combines strict validation for complete records with inclusive counting for partial records.
    Returns True if either condition is met.
    """
    if not product_cols and not price_cols:
        return False

    # Count product columns with data
    product_cols_with_data = 0
    for col_idx in product_cols:
        if col_idx < len(row):
            val = row.iloc[col_idx]
            if pd.notna(val):
                val_str = str(val).strip()
                if val_str and val_str.lower() != "nan":
                    product_cols_with_data += 1

    # OPTION A (STRICT): Complete record with BOTH product columns
    if product_cols and product_cols_with_data >= len(product_cols):
        return True

    # OPTION C (INCLUSIVE): Accept row if it has ANY product or price column data
    all_key_cols = product_cols + price_cols
    for col_idx in all_key_cols:
        if col_idx < len(row):
            val = row.iloc[col_idx]
            if pd.notna(val):
                val_str = str(val).strip()
                if val_str and val_str.lower() != "nan":
                    return True

    # No data in any key column
    return False


def _identify_empty_columns(df: pd.DataFrame) -> list:
    """Return list of column indices that are entirely empty (all NaN)."""
    empty_cols = []
    for col_idx in range(len(df.columns)):
        if df.iloc[:, col_idx].isna().all():
            empty_cols.append(col_idx)
    return empty_cols


# ============================================================================
# PHASE 4: Validate section headers
# ============================================================================


def _validate_section_headers(
    df: pd.DataFrame,
    section_structure: Dict,
    config: dict,
    sheet_name: str,
    dq_logger: DQLogger,
    logger: PipelineLogger,
) -> tuple:
    """Validate headers for each section and identify trim columns using DYNAMIC detection.

    For each section:
    1. Find header row by scanning for column name keywords (NOT fixed offset)
    2. Find trim sub-header row by scanning for applicability markers (NOT fixed offset)
    3. Data rows start immediately after trim sub-header

    Returns: (trim_columns_per_section, row_metrics_per_section)
    """
    # Extract detection config (passed by orchestrator)
    detection_config = config.get("step1_detection", {}) if isinstance(config, dict) else {}
    if not isinstance(detection_config, dict):
        detection_config = {}

    logger.debug(f"detection_config type={type(detection_config)}, keys={list(detection_config.keys()) if isinstance(detection_config, dict) else 'N/A'}")

    section_detect_config = detection_config.get("section_detection", {}) if isinstance(detection_config, dict) else {}
    if not isinstance(section_detect_config, dict):
        section_detect_config = {}

    # Get keywords from config (with defensive type checking)
    header_row_detect = section_detect_config.get("header_row_detection", {}) if isinstance(section_detect_config, dict) else {}
    if not isinstance(header_row_detect, dict):
        header_row_detect = {}
    # Debug: show what we got from the config
    logger.debug(f"section_detect_config type={type(section_detect_config)}, keys={list(section_detect_config.keys()) if isinstance(section_detect_config, dict) else 'N/A'}")
    logger.debug(f"header_row_detect type={type(header_row_detect)}, keys={list(header_row_detect.keys()) if isinstance(header_row_detect, dict) else 'N/A'}")

    header_keywords_en = header_row_detect.get("keywords_en", [])
    header_keywords_fr = header_row_detect.get("keywords_fr", [])
    max_scan_header = header_row_detect.get("max_scan_rows", 10)

    # Debug: log what keywords we got
    logger.debug(f"Header detection config: keywords_en={header_keywords_en}, keywords_fr={header_keywords_fr}, max_scan={max_scan_header}")

    trim_subheader_detect = section_detect_config.get("trim_subheader_row_detection", {}) if isinstance(section_detect_config, dict) else {}
    if not isinstance(trim_subheader_detect, dict):
        trim_subheader_detect = {}
    applicability_markers = trim_subheader_detect.get("applicability_markers", [])
    max_scan_trim = trim_subheader_detect.get("max_scan_rows", 5)

    # Product column keywords (for identifying trim columns)
    col_detect_config = detection_config.get("column_detection", {}) if isinstance(detection_config, dict) else {}
    if not isinstance(col_detect_config, dict):
        col_detect_config = {}

    product_col_keywords = []
    product_col_kw = col_detect_config.get("product_column_keywords", {}) if isinstance(col_detect_config, dict) else {}
    if isinstance(product_col_kw, dict):
        product_col_keywords.extend(product_col_kw.get("en", []))
        product_col_keywords.extend(product_col_kw.get("fr", []))

    if not product_col_keywords:
        # Fallback to hardcoded keywords if config not available
        product_col_keywords = [
            "part", "number", "description", "item", "name", "frt", "residual",
            "price", "net", "dealer", "list", "comments", "application", "installed", "cost",
            "pièce", "numero", "article", "nom", "t.f.f.", "tarif",
            "concessionnaire", "liste", "remarques", "commentaire", "instalé", "coût", "numéro", "prix",
        ]

    trim_columns_per_section = {}
    row_metrics_per_section = {}

    for section_name, bounds in section_structure.items():
        try:
            marker_row = bounds["marker_row"]
            data_end = bounds["data_end"]
        except TypeError as e:
            print(f"[DEBUG] Error accessing bounds dict for section '{section_name}': bounds type={type(bounds)}, bounds={bounds}")
            logger.warning(f"Section '{section_name}': Invalid bounds structure")
            continue

        # =====================================================================
        # DYNAMICALLY FIND HEADER ROW (NOT fixed offset)
        # =====================================================================
        header_row_idx, headers = _find_header_row(
            df, marker_row, header_keywords_en, header_keywords_fr, max_scan_header, logger
        )

        if header_row_idx is None:
            logger.warning(f"Sheet '{sheet_name}': Section '{section_name}' - Could not find header row")
            trim_columns_per_section[section_name] = []
            continue

        # =====================================================================
        # Identify product and trim column indices based on header names
        # =====================================================================
        product_col_indices = []
        trim_col_indices_candidate = []

        for i, header in enumerate(headers):
            header_lower = header.lower()
            is_product = any(keyword in header_lower for keyword in product_col_keywords)

            if is_product:
                product_col_indices.append(i)
            else:
                trim_col_indices_candidate.append(i)

        # =====================================================================
        # DYNAMICALLY FIND TRIM SUB-HEADER ROW (NOT fixed offset)
        # =====================================================================
        trim_subheader_row_idx = _find_trim_subheader_row(
            df, header_row_idx, product_col_indices, applicability_markers, max_scan_trim, logger
        )

        # Determine actual trim columns based on whether trim sub-header was found
        trim_cols = []
        if trim_subheader_row_idx is not None:
            # We found a trim sub-header, so identify which candidate columns actually have trim values
            trim_row = df.iloc[trim_subheader_row_idx]
            for col_idx in trim_col_indices_candidate:
                if col_idx < len(trim_row) and _is_trim_value(trim_row.iloc[col_idx]):
                    trim_cols.append(col_idx)

            # Also check unnamed columns (starting with "_col_") for trim values
            for col_idx in range(len(headers)):
                if headers[col_idx].startswith("_col_") and col_idx not in product_col_indices:
                    if col_idx < len(trim_row) and _is_trim_value(trim_row.iloc[col_idx]):
                        trim_cols.append(col_idx)

            data_start_row = trim_subheader_row_idx + 1  # Data starts after trim sub-header
        else:
            # No trim sub-header found, data might start right after header
            data_start_row = header_row_idx + 2
            logger.debug(f"Sheet '{sheet_name}': Section '{section_name}' - No trim sub-header found, using fallback offset")

        trim_columns_per_section[section_name] = sorted(set(trim_cols))  # Remove duplicates, sort

        # =====================================================================
        # Count data rows with detailed metrics
        # =====================================================================

        # Identify price column indices
        price_col_indices = []
        for i, header in enumerate(headers):
            header_lower = header.lower()
            # Price columns
            if any(kw in header_lower for kw in ["price", "cost", "hours", "msrp", "frt", "installed",
                                                   "prix", "coût", "tarif", "t.f.f."]):
                price_col_indices.append(i)

        # Count rows in this section (using dynamically detected data_start_row)
        if data_start_row <= data_end:
            total_rows = data_end - data_start_row + 1
            valid_data_rows = 0
            empty_rows = 0
            publishing_rows = 0
            found_publishing_row = False

            # Count each row
            for row_idx in range(data_start_row, data_end + 1):
                row = df.iloc[row_idx]

                if _is_publishing_row(row):
                    publishing_rows += 1
                    found_publishing_row = True  # Mark that we've found publishing footer
                elif found_publishing_row:
                    # All rows after a publishing row are part of the footer
                    publishing_rows += 1
                elif _is_empty_row(row):
                    empty_rows += 1
                elif _is_valid_data_row(row, product_col_indices, price_col_indices):
                    valid_data_rows += 1
        else:
            total_rows = 0
            valid_data_rows = 0
            empty_rows = 0
            publishing_rows = 0

        # Identify empty columns
        empty_cols = _identify_empty_columns(df)

        # Store row metrics (using dynamically detected row indices)
        row_metrics_per_section[section_name] = {
            "marker_row": marker_row,
            "header_row": header_row_idx,
            "trim_sub_header_row": trim_subheader_row_idx,
            "data_start_row": data_start_row,
            "data_end_row": data_end,
            "total_rows": total_rows,
            "valid_data_rows": valid_data_rows,
            "empty_rows": empty_rows,
            "publishing_rows": publishing_rows,
            "empty_columns": empty_cols,
        }

        # Debug logging with detailed row breakdown (only show non-zero counts)
        row_details = []
        if empty_rows > 0:
            row_details.append(f"{empty_rows} empty")
        if publishing_rows > 0:
            row_details.append(f"{publishing_rows} publishing")

        row_details_str = f" (including {', '.join(row_details)})" if row_details else ""

        empty_cols_str = f"\n  - Empty columns: {empty_cols}" if empty_cols else ""

        logger.debug(
            f"Sheet '{sheet_name}': Section '{section_name}'\n"
            f"  - {len(headers)} total columns, {len(trim_cols)} trim columns\n"
            f"  - Total rows: {total_rows}{row_details_str}\n"
            f"  - Valid data rows: {valid_data_rows}{empty_cols_str}"
        )

    return trim_columns_per_section, row_metrics_per_section
