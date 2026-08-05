from typing import Any, Dict
import re

import pandas as pd

from core.base_pipeline import PipelineFatalError
from core.helpers.column_mapper import assert_required_columns, map_all_columns
from core.helpers.dq_logger import DQLogger
from core.helpers.pipeline_logger import PipelineLogger
from core.helpers.trim_helpers import validate_trim_by_datatype


def run(
    working_df: pd.DataFrame,
    config: dict,
    meta_data: Dict[str, Any],
    dq_logger: DQLogger,
    pipeline_logger: PipelineLogger,
) -> Dict[str, Any]:
    """
    Map columns to standard names and identify valid trim columns.

    Returns:
        {
            "col_mapping":         {original_col: standard_name | None},
            "valid_trim_cols":     [col_name, ...],
            "trim_validation_log": {col_name: {result, expected_data_rate, unique_col_data}}
        }
    """
    sheet_name = meta_data["sheet_name"]
    model_name = meta_data.get("model_name", "unknown")

    # Map all columns to standard names
    col_mapping = map_all_columns(working_df, config["column_definition"])
    pipeline_logger.debug(f"Column mapping for '{sheet_name}': {col_mapping}")

    # Assert all required columns have a match — FATAL if not
    try:
        assert_required_columns(col_mapping, config["required_columns"])
    except ValueError as exc:
        raise PipelineFatalError(str(exc)) from exc

    # Identify trim column candidates using trim_column_patterns from upstream.yaml
    trim_pattern = config.get("trim_column_patterns", "")
    if not trim_pattern:
        raise PipelineFatalError(f"Sheet '{sheet_name}': no trim column pattern defined in config")

    candidates = [
        col for col in working_df.columns
        if re.match(trim_pattern, col, re.IGNORECASE)
    ]
    pipeline_logger.debug(f"Trim candidates for '{sheet_name}' (pattern={trim_pattern}): {candidates}")

    # Filter out structural category-header columns that are never valid trim levels
    exclusion_keywords = [k.lower() for k in config.get("trim_exclusion_keywords", [])]
    if exclusion_keywords:
        excluded = [c for c in candidates if any(k in c.lower() for k in exclusion_keywords)]
        candidates = [c for c in candidates if c not in excluded]
        if excluded:
            pipeline_logger.debug(
                f"Sheet '{sheet_name}': excluded {len(excluded)} category column(s) from trim candidates: {excluded}"
            )

    # Validate candidates by data content (if trim_validation_config is defined)
    trim_log = {}
    if config.get("trim_validation_config"):
        valid_trim_cols, trim_log = validate_trim_by_datatype(
            working_df, candidates, config["trim_validation_config"]
        )

        # Log any failed candidates as DQ warnings
        for col, result in trim_log.items():
            if result["result"] == "fail":
                dq_logger.log_warning(
                    sheet_name=sheet_name,
                    model_name=model_name,
                    record_index=-1,
                    record_snapshot=result,
                    rule_violated="trim_candidate_failed_validation",
                    issue_description=(
                        f"Column '{col}' failed trim validation — "
                        f"expected_data_rate={result['expected_data_rate']}%, "
                        f"unique_values={result['unique_col_data']}"
                    ),
                )
    else:
        # If no trim validation config, accept all candidates as valid trim columns
        valid_trim_cols = candidates
        pipeline_logger.debug(f"Sheet '{sheet_name}': trim validation config not defined, accepting all candidates")

    pipeline_logger.debug(f"Valid trim cols for '{sheet_name}': {valid_trim_cols}")

    return {
        "col_mapping": col_mapping,
        "valid_trim_cols": valid_trim_cols,
        "trim_validation_log": trim_log,
    }
