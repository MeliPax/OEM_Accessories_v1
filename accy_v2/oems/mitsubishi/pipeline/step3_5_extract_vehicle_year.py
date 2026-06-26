"""
Step 3.5 — Extract Vehicle Year

Extract the vehicle year from the sheet name and validate it against config.
Stores vehicle_year in meta_data for use in step 4.5 (model lookup).

Input: standardized_df (from step 3)
Output: standardized_df (unchanged, side-effect is meta_data update)
"""

from typing import Any, Dict

import pandas as pd

from core.helpers.pipeline_logger import PipelineLogger


def run(
    standardized_df: pd.DataFrame,
    meta_data: Dict[str, Any],
    config: Dict[str, Any],
    pipeline_logger: PipelineLogger,
) -> pd.DataFrame:
    """
    Extract vehicle year from sheet_name.

    Mitsubishi sheet names follow format: YYYY ModelName Language
    Example: "2026 Outlander ES EN"

    Args:
        standardized_df: DataFrame from step 3
        meta_data: Pipeline metadata dict (will be updated with vehicle_year)
        config: Pipeline config (contains valid_year_range)
        pipeline_logger: Pipeline logger

    Returns:
        standardized_df (unchanged)

    Raises:
        PipelineFatalError: If year cannot be extracted or is invalid
    """
    from core.base_pipeline import PipelineFatalError

    sheet_name = meta_data.get("sheet_name", "")

    # Extract year from start of sheet name (first 4 characters should be YYYY)
    try:
        year_str = sheet_name.split()[0]
        vehicle_year = int(year_str)
    except (IndexError, ValueError):
        raise PipelineFatalError(
            f"Cannot extract year from sheet_name '{sheet_name}'. "
            "Expected format: YYYY ModelName Language (e.g., '2026 Outlander ES EN')"
        )

    # Validate year is in acceptable range
    if "model_lookup_rules" in config and "Mitsubishi" in config["model_lookup_rules"]:
        year_range = config["model_lookup_rules"]["Mitsubishi"].get("valid_year_range", {})
        min_year = year_range.get("min", 1900)
        max_year = year_range.get("max", 2100)

        if not (min_year <= vehicle_year <= max_year):
            raise PipelineFatalError(
                f"Year {vehicle_year} from sheet_name '{sheet_name}' is outside valid range "
                f"[{min_year}, {max_year}]"
            )

    # Store in meta_data for downstream use (model lookup in step 4.5)
    meta_data["vehicle_year"] = vehicle_year
    pipeline_logger.debug(f"Extracted vehicle_year: {vehicle_year} from sheet_name '{sheet_name}'")

    return standardized_df
