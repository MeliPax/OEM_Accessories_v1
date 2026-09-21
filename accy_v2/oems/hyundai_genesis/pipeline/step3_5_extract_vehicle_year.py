"""
Step 3.5 — Extract Vehicle Year

Extract the vehicle year from the row data (already available in meta_data)
and validate it against config. Stores vehicle_year in meta_data for use in step 4.5 (model lookup).

Hyundai differs from Mitsubishi: year is already known from the group key
(set by orchestrator's load_file() during groupby), not parsed from sheet name.
"""

from typing import Any, Dict

import pandas as pd

from core.base_pipeline import PipelineFatalError
from core.helpers.pipeline_logger import PipelineLogger


def run(
    standardized_df: pd.DataFrame,
    meta_data: Dict[str, Any],
    config: Dict[str, Any],
    pipeline_logger: PipelineLogger,
) -> pd.DataFrame:
    """
    Extract vehicle year from meta_data (set by orchestrator during load_file groupby).

    Args:
        standardized_df: DataFrame from step 3
        meta_data: Pipeline metadata dict (contains year_from from group key)
        config: Pipeline config (contains valid_year_range)
        pipeline_logger: Pipeline logger

    Returns:
        standardized_df (unchanged)

    Raises:
        PipelineFatalError: If year is missing or invalid
    """
    group_key = meta_data.get("group_key", "unknown")
    year_from = meta_data.get("year_from")

    if year_from is None:
        # Fallback: try to extract from the first row's data if available
        col_lower = {c.lower(): c for c in standardized_df.columns}
        year_col = next(
            (orig for lower, orig in col_lower.items() if "year_from" in lower), None
        )
        if year_col and len(standardized_df) > 0:
            try:
                year_from = int(standardized_df.iloc[0][year_col])
            except (ValueError, TypeError):
                pass

        if year_from is None:
            raise PipelineFatalError(
                f"Group '{group_key}': vehicle year not found in meta_data or data"
            )

    try:
        vehicle_year = int(year_from)
    except (ValueError, TypeError):
        raise PipelineFatalError(
            f"Group '{group_key}': year '{year_from}' cannot be converted to int"
        )

    # Validate year is in acceptable range (check manufacturer in meta_data)
    manufacturer = meta_data.get("manufacturer", "Hyundai")
    if manufacturer in config.get("model_lookup_rules", {}):
        year_range = config["model_lookup_rules"][manufacturer].get("valid_year_range", {})
        min_year = year_range.get("min", 1900)
        max_year = year_range.get("max", 2100)

        if not (min_year <= vehicle_year <= max_year):
            raise PipelineFatalError(
                f"Group '{group_key}': year {vehicle_year} is outside valid range "
                f"[{min_year}, {max_year}]"
            )

    # Store in meta_data for downstream use (model lookup in step 4.5)
    meta_data["vehicle_year"] = vehicle_year
    pipeline_logger.debug(f"Group '{group_key}': extracted vehicle_year={vehicle_year}")

    return standardized_df
