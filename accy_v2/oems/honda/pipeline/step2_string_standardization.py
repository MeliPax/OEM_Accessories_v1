"""
Honda Step 2.5: String Standardization
Applies unicode normalization, newline removal, composite part splitting,
and trim marker mapping before Step 3 type validation.

Runs AFTER Step 2 Header Normalization, BEFORE Step 3 Standardization.
Implements Honda-specific operations defined in transformations.yaml.
"""

from typing import Any, Dict, List, Optional
import pandas as pd
import re
import unicodedata

from core.base_pipeline import PipelineFatalError
from core.helpers.dq_logger import DQLogger
from core.helpers.pipeline_logger import PipelineLogger


def run(
    working_df: pd.DataFrame,
    config: dict,
    meta_data: Dict[str, Any],
    dq_logger: DQLogger,
    pipeline_logger: PipelineLogger,
) -> pd.DataFrame:
    """
    Apply string-level standardization before type validation.

    Operations (in order):
    1. Normalize unicode (smart quotes → ASCII)
    2. Remove newlines (literal \n → space)
    3. Split composite part numbers ("X or Y" → X, note in comments)
    4. Normalize trim markers (•, ✓, S, T, E, 0, N/A → canonical)

    Args:
        working_df: DataFrame after header normalization
        config: Honda config dict (from ModularConfigLoader.load_all())
        meta_data: Pipeline metadata
        dq_logger: DQ logging interface
        pipeline_logger: Pipeline logging interface

    Returns:
        DataFrame with strings normalized and ready for type validation
    """
    sheet_name = meta_data.get("sheet_name", "unknown")
    model_name = meta_data.get("model_name", "unknown")

    df = working_df.copy()

    # Get transformations config (from transformations.yaml)
    trans_config = config.get("transformations", {})

    # 1. Normalize unicode in all string columns
    unicode_mapping = _extract_operation_params(trans_config, "normalize_unicode")
    df = _normalize_unicode(df, unicode_mapping, pipeline_logger)

    # 2. Remove newlines from description and comments
    df = _remove_newlines(df, trans_config.get("columns", {}), pipeline_logger)

    # 3. Split composite part numbers
    df = _split_composite_part_numbers(df, dq_logger, sheet_name, model_name)

    # 4. Normalize trim markers
    trim_mapping = _extract_operation_params(trans_config, "normalize_trim_markers", "mapping")
    df = _normalize_trim_markers(df, trim_mapping, pipeline_logger)

    return df


# ============================================================================
# Private Helper Functions
# ============================================================================


def _extract_operation_params(trans_config: dict, operation_name: str, param_key: str = None) -> dict:
    """
    Extract operation parameters from transformations config.

    Searches through all columns for an operation with the given name.
    For normalize_unicode, converts from_chars/to_chars lists into a mapping dict.
    For normalize_trim_markers, extracts the mapping directly.

    Args:
        trans_config: Transformations config dict
        operation_name: Name of the operation to find (e.g., "normalize_unicode")
        param_key: Optional specific parameter key to extract (e.g., "mapping")

    Returns:
        Dict of operation parameters
    """
    columns = trans_config.get("columns", {})

    for col_name, col_config in columns.items():
        operations = col_config.get("operations", [])
        for op in operations:
            if op.get("name") == operation_name:
                # Special handling for normalize_unicode: convert from_chars/to_chars to mapping
                if operation_name == "normalize_unicode":
                    from_chars = op.get("from_chars", [])
                    to_chars = op.get("to_chars", [])
                    if from_chars and to_chars and len(from_chars) == len(to_chars):
                        return dict(zip(from_chars, to_chars))
                    return {}

                # For other operations, extract the specified key or all parameters
                if param_key:
                    return op.get(param_key, {})
                else:
                    return {k: v for k, v in op.items() if k not in ["name", "description"]}

    return {}


def _normalize_unicode(
    df: pd.DataFrame,
    unicode_map: Dict[str, str],
    pipeline_logger: PipelineLogger,
) -> pd.DataFrame:
    """
    Replace smart quotes, unicode spaces, and unicode dashes with ASCII.

    Uses Python's unicodedata to normalize to NFC form, then applies
    explicit replacements for known problematic characters.
    """
    df = df.copy()

    # Build default unicode mappings if not provided
    if not unicode_map:
        unicode_map = {
            "'": "'",  # U+2018 (left single quote) → ASCII single quote
            "'": "'",  # U+2019 (right single quote) → ASCII single quote
            """: '"',  # U+201C (left double quote) → ASCII double quote
            """: '"',  # U+201D (right double quote) → ASCII double quote
            "…": "...",  # U+2026 (ellipsis) → three dots
            "–": "-",  # U+2013 (en dash) → hyphen
            "—": "-",  # U+2014 (em dash) → hyphen
        }

    for col in df.columns:
        if df[col].dtype == 'object':  # String column
            # Normalize to NFC form first (canonical decomposition)
            df[col] = df[col].apply(
                lambda v: unicodedata.normalize('NFC', str(v)) if pd.notna(v) else v
            )

            # Apply explicit character replacements
            for old_char, new_char in unicode_map.items():
                df[col] = df[col].replace(old_char, new_char, regex=False)

    return df


def _remove_newlines(
    df: pd.DataFrame,
    columns_config: Dict[str, Any],
    pipeline_logger: PipelineLogger,
) -> pd.DataFrame:
    """
    Remove literal \n from string columns (primarily description and comments).
    Replace with space and collapse multiple spaces.
    """
    df = df.copy()

    # Columns to clean of newlines
    newline_columns = ['description', 'description_fr', 'comments', 'comments_fr']

    for col in newline_columns:
        if col in df.columns and df[col].dtype == 'object':
            # Replace \n with space
            df[col] = df[col].str.replace(r'\n', ' ', regex=True)

            # Collapse multiple spaces into one
            df[col] = df[col].str.replace(r'\s+', ' ', regex=True)

            # Trim leading/trailing spaces
            df[col] = df[col].str.strip()

    return df


def _split_composite_part_numbers(
    df: pd.DataFrame,
    dq_logger: DQLogger,
    sheet_name: str,
    model_name: str,
) -> pd.DataFrame:
    """
    Handle composite part numbers like "480-670-6545-SP or 480-670-6545-GB".
    Keep first value (left-priority), note original in comments.
    """
    df = df.copy()

    if 'part_number' not in df.columns:
        return df

    # Find rows with "or" delimiter (English) or "ou" (French)
    composite_mask = df['part_number'].astype(str).str.contains(r'\s(or|ou)\s', regex=True, na=False)

    composite_rows = df[composite_mask]

    for idx, row in composite_rows.iterrows():
        original = row['part_number']

        # Split on "or" or "ou" and take first value
        parts = re.split(r'\s+(or|ou)\s+', original)
        primary = parts[0].strip() if parts else original

        # Log to DQ logger
        dq_logger.log_info(
            sheet_name=sheet_name,
            model_name=model_name,
            record_index=int(idx),
            rule_name="composite_part_number_split",
            issue_description=f"Composite part number detected and split",
            issue_detail=f"Original: '{original}' → Primary: '{primary}'",
        )

        # Update part number
        df.at[idx, 'part_number'] = primary

        # Append note to comments
        comments = df.at[idx, 'comments']
        if pd.isna(comments) or str(comments).strip() == '':
            df.at[idx, 'comments'] = f"[Composite parts: {original}]"
        else:
            current_comment = str(comments).strip()
            df.at[idx, 'comments'] = f"{current_comment} | [Composite parts: {original}]"

    return df


def _normalize_trim_markers(
    df: pd.DataFrame,
    marker_mapping: Dict[str, Any],
    pipeline_logger: PipelineLogger,
) -> pd.DataFrame:
    """
    Map special characters and placeholder values to canonical trim states.

    Examples:
      "•" → "applicable"
      "✓" → "applicable"
      "S" → "standard"
      "T" → "tire_change"
      "E" → "exchange"
      "0", "0.0", "", "N/A" → None (null)
    """
    df = df.copy()

    # Build default marker mapping if not provided
    if not marker_mapping:
        marker_mapping = {
            "•": "applicable",
            "✓": "applicable",
            "S": "standard",
            "T": "tire_change",
            "E": "exchange",
            "0": None,
            "0.0": None,
            "": None,
            "N/A": None,
            "N/a": None,
            "na": None,
        }

    # Identify trim columns (all columns that aren't core product/price/meta columns)
    core_cols = {
        'model_name', 'model_year', 'part_number', 'description',
        'description_fr', 'dealer_net', 'list_price', 'frt',
        'installed_price', 'comments', 'comments_fr', 'application'
    }

    trim_cols = [col for col in df.columns if col not in core_cols]

    # Apply marker mapping to trim columns
    for col in trim_cols:
        if df[col].dtype == 'object':  # String column
            df[col] = df[col].apply(
                lambda v: marker_mapping.get(str(v).strip(), v) if pd.notna(v) else None
            )

    return df


