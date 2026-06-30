import re
from typing import Any, Dict

import pandas as pd

from core.base_pipeline import PipelineFatalError
from core.helpers.column_mapper import assert_required_columns, map_all_columns
from core.helpers.dq_logger import DQLogger
from core.helpers.pipeline_logger import PipelineLogger


def run(
    working_df: pd.DataFrame,
    config: dict,
    meta_data: Dict[str, Any],
    dq_logger: DQLogger,
    pipeline_logger: PipelineLogger,
) -> Dict[str, Any]:
    """
    Map columns to standard names and identify valid trim columns via dynamic regex.

    Hyundai differs from Mitsubishi: trim columns are identified by name pattern
    (^Trim\s+\d+$) + presence of data, not by column position + "X" sentinel validation.

    Returns:
        {
            "col_mapping":         {original_col: standard_name | None},
            "valid_trim_cols":     [col_name, ...],
            "trim_validation_log": {} (empty for Hyundai; not used)
        }
    """
    group_key = meta_data.get("group_key", "unknown")
    model_name = meta_data.get("model_name", "unknown")

    # Map all columns to standard names using column_definition
    col_mapping = map_all_columns(working_df, config["column_definition"])
    pipeline_logger.debug(f"Column mapping for '{group_key}': {col_mapping}")

    # Assert all required columns have a match — FATAL if not
    try:
        assert_required_columns(col_mapping, config["required_columns"])
    except ValueError as exc:
        raise PipelineFatalError(str(exc)) from exc

    # Identify trim columns via dynamic regex: ^Trim\s+\d+$ + has non-empty data
    valid_trim_cols = _identify_trim_columns_by_regex(working_df, group_key, pipeline_logger)

    if not valid_trim_cols:
        raise PipelineFatalError(
            f"Group '{group_key}': no valid trim columns found matching pattern '^Trim \\d+$' with data"
        )

    pipeline_logger.debug(f"Valid trim cols for '{group_key}': {valid_trim_cols}")

    return {
        "col_mapping": col_mapping,
        "valid_trim_cols": valid_trim_cols,
        "trim_validation_log": {},
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _identify_trim_columns_by_regex(
    working_df: pd.DataFrame,
    group_key: str,
    pipeline_logger: PipelineLogger,
) -> list:
    """
    Identify trim columns by regex pattern: ^Trim\s+\d+$ (case-insensitive).
    Filter to only columns with at least one non-null, non-empty value.
    """
    trim_cols = []

    for col in working_df.columns:
        # Check name pattern
        if not re.match(r"^trim\s+\d+$", col, re.IGNORECASE):
            continue

        # Check for data: at least one non-null, non-empty cell
        has_data = (
            working_df[col]
            .dropna()
            .astype(str)
            .str.strip()
            .str.len()
            .gt(0)
            .any()
        )

        if has_data:
            trim_cols.append(col)

    if trim_cols:
        pipeline_logger.info(
            f"Group '{group_key}': identified {len(trim_cols)} trim column(s): {trim_cols}"
        )

    return trim_cols
