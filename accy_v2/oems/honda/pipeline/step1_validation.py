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
    trim_columns_per_section = _validate_section_headers(
        working_df, section_structure, config, sheet_name, dq_logger, pipeline_logger
    )
    updated_meta["trim_columns_per_section"] = trim_columns_per_section
    pipeline_logger.info(f"Sheet '{sheet_name}': Trim columns identified for all sections")

    # =========================================================================
    # PHASE 5: Return working_df with complete metadata
    # =========================================================================
    return working_df, updated_meta


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


def _extract_model_name(df: pd.DataFrame, dq_logger: DQLogger, logger: PipelineLogger) -> str:
    """Extract model name from file headers (rows 0-5).

    Handles both EN ("Model Name") and FR ("Nom du modèle") labels.
    The label and value are in the same row, typically columns 2-3.
    """
    if len(df) < 6:
        return None

    # Keywords to search for (EN and FR)
    model_name_keywords = ["model name", "nom du modèle", "nom du model"]

    # Try rows 0-5 for a row containing model name label
    for idx in range(min(6, len(df))):
        row = df.iloc[idx]

        # Find which column contains the label
        label_col = None
        for col_idx, val in enumerate(row):
            if pd.notna(val):
                val_str = str(val).lower()
                if any(keyword in val_str for keyword in model_name_keywords):
                    label_col = col_idx
                    break

        # If we found the label, extract the value from the NEXT column
        if label_col is not None:
            for col_idx in range(label_col + 1, len(row)):
                val = row.iloc[col_idx]
                if pd.notna(val):
                    val_str = str(val).strip()
                    if val_str and "nan" not in val_str.lower():
                        return val_str

    return None


def _extract_vehicle_year(
    df: pd.DataFrame, meta_data: Dict, dq_logger: DQLogger, logger: PipelineLogger
) -> int:
    """Extract vehicle year from file headers or filename.

    Handles both EN ("Model Year") and FR ("Année modèle") labels.
    The label and value are in the same row, typically columns 2-3.
    """
    if len(df) < 6:
        return None

    # Keywords to search for (EN and FR)
    year_keywords = ["model year", "année modèle", "année du modèle"]

    # Try rows 0-5 for a row containing year label
    for idx in range(min(6, len(df))):
        row = df.iloc[idx]

        # Find which column contains the label
        label_col = None
        for col_idx, val in enumerate(row):
            if pd.notna(val):
                val_str = str(val).lower()
                if any(keyword in val_str for keyword in year_keywords):
                    label_col = col_idx
                    break

        # If we found the label, extract the value from the NEXT column
        if label_col is not None:
            for col_idx in range(label_col + 1, len(row)):
                val = row.iloc[col_idx]
                if pd.notna(val):
                    try:
                        year_val = int(val)
                        if 2000 <= year_val <= 2050:
                            return year_val
                    except (ValueError, TypeError):
                        pass

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
# PHASE 4: Validate section headers
# ============================================================================


def _validate_section_headers(
    df: pd.DataFrame,
    section_structure: Dict,
    config: dict,
    sheet_name: str,
    dq_logger: DQLogger,
    logger: PipelineLogger,
) -> Dict[str, list]:
    """Validate headers for each section and identify trim columns.

    For each section:
    - Header row is at data_start
    - Trim sub-header is at data_start + 1
    - Data rows start at data_start + 2

    Returns: {section_name: [list of trim column indices]}
    """
    trim_columns_per_section = {}

    for section_name, bounds in section_structure.items():
        data_start = bounds["data_start"]
        data_end = bounds["data_end"]

        if data_start >= len(df):
            logger.warning(f"Sheet '{sheet_name}': Section '{section_name}' header row out of bounds")
            trim_columns_per_section[section_name] = []
            continue

        # Header row is at data_start
        header_row = df.iloc[data_start]

        # Trim sub-header is at data_start + 1
        trim_sub_header_row = df.iloc[data_start + 1] if data_start + 1 < len(df) else None

        # Extract header column names
        headers = []
        for i, col_val in enumerate(header_row):
            if pd.isna(col_val):
                headers.append(f"_col_{i}")
            else:
                header_str = str(col_val).strip().replace("\n", " ").replace("\r", " ")
                header_str = " ".join(header_str.split())
                if header_str and header_str.lower() != "nan":
                    headers.append(header_str)
                else:
                    headers.append(f"_col_{i}")

        # Define product columns (should NOT be trim columns)
        # Include both English and French keywords
        product_col_keywords = [
            # English
            "part", "number", "description", "item", "name", "frt", "residual",
            "price", "net", "dealer", "list", "comments", "application", "installed", "cost",
            # French
            "pièce", "numero", "description", "article", "nom", "t.f.f.", "tarif", "net",
            "concessionnaire", "liste", "remarques", "commentaire", "application", "instalé",
            "coût", "numéro", "prix",
        ]

        # Identify trim columns: NOT product columns AND have actual values in trim sub-header row
        trim_cols = []
        for i, header in enumerate(headers):
            header_lower = header.lower()
            is_product = any(keyword in header_lower for keyword in product_col_keywords)

            if not is_product and not header.startswith("_col_"):
                trim_cols.append(i)
            elif header.startswith("_col_") and trim_sub_header_row is not None:
                # For unnamed columns, check if they have a value in the trim sub-header row
                trim_val = trim_sub_header_row.iloc[i]
                if pd.notna(trim_val):
                    trim_str = str(trim_val).strip()
                    # Accept as trim if it has content and looks like a trim name (not just a number like "0.0")
                    if trim_str and trim_str.lower() not in ("nan", "0", "0.0"):
                        trim_cols.append(i)

        trim_columns_per_section[section_name] = trim_cols
        data_rows = data_end - (data_start + 2) + 1 if data_start + 2 <= data_end else 0
        logger.debug(
            f"Sheet '{sheet_name}': Section '{section_name}' - "
            f"{len(headers)} total columns, {len(trim_cols)} trim columns, {data_rows} data rows"
        )

    return trim_columns_per_section
