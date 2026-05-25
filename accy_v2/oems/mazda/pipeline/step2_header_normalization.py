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
    Map columns to standard names.
    Mazda has no trim columns — trim is encoded in the model_number field.
    Returns: { "col_mapping": ..., "valid_trim_cols": [], "trim_validation_log": {} }
    """
    sheet_name = meta_data["sheet_name"]

    # Map all columns to standard names
    col_mapping = map_all_columns(working_df, config["column_definition"])
    pipeline_logger.debug(f"Column mapping for '{sheet_name}': {col_mapping}")

    # Assert all required columns have a match — FATAL if not
    try:
        assert_required_columns(col_mapping, config["required_columns"])
    except ValueError as exc:
        raise PipelineFatalError(str(exc)) from exc

    return {
        "col_mapping": col_mapping,
        "valid_trim_cols": [],
        "trim_validation_log": {},
    }
