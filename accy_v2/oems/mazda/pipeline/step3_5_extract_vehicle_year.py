"""
Step 3.5 — Extract Vehicle Year

Extract the vehicle year from the sheet_name or model_year column.
Stores vehicle_year in meta_data for use in step 4.5 (model lookup).

Input: standardized_df (from step 3)
Output: standardized_df (unchanged, side-effect is meta_data update)
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
    Extract vehicle year from standardized_df or sheet_name.

    Mazda: First tries to extract from model_year column if present.
    Falls back to parsing sheet_name for year prefix.

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

    vehicle_year = None

    # Try 1: Look for year_from column in the DataFrame (renamed from ModelYear by step3)
    year_col = None
    if "year_from" in standardized_df.columns:
        year_col = "year_from"
    elif "model_year" in standardized_df.columns:
        year_col = "model_year"

    if year_col is not None:
        years = standardized_df[year_col].dropna().unique()
        if len(years) > 0:
            try:
                vehicle_year = int(years[0])
                pipeline_logger.debug(f"Extracted vehicle_year {vehicle_year} from {year_col} column")
            except (ValueError, TypeError):
                pass

    # Try 2: Parse year from sheet_name (CarLineCode format may start with year)
    if vehicle_year is None:
        sheet_name = meta_data.get("sheet_name", "")
        try:
            # Mazda CarLineCodes may start with year (e.g., "2026CX5")
            year_str = "".join(c for c in sheet_name if c.isdigit())[:4]
            if len(year_str) == 4:
                vehicle_year = int(year_str)
                pipeline_logger.debug(f"Extracted vehicle_year {vehicle_year} from sheet_name '{sheet_name}'")
        except (ValueError, IndexError):
            pass

    # If still no year found, raise error
    if vehicle_year is None:
        raise PipelineFatalError(
            f"Cannot extract year from model_year column or sheet_name '{meta_data.get('sheet_name', '')}'"
        )

    # Validate year is in acceptable range
    if "model_lookup_rules" in config and "Mazda" in config["model_lookup_rules"]:
        year_range = config["model_lookup_rules"]["Mazda"].get("valid_year_range", {})
        min_year = year_range.get("min", 1900)
        max_year = year_range.get("max", 2100)

        if not (min_year <= vehicle_year <= max_year):
            raise PipelineFatalError(
                f"Year {vehicle_year} is outside valid range [{min_year}, {max_year}]"
            )

    # Store in meta_data for downstream use (model lookup in step 4.5)
    meta_data["vehicle_year"] = vehicle_year
    pipeline_logger.debug(f"Vehicle year set to: {vehicle_year}")

    return standardized_df
