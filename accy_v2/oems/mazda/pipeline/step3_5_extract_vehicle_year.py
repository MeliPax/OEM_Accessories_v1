import re
from typing import Any, Dict

import pandas as pd

from core.base_pipeline import PipelineFatalError
from core.helpers.pipeline_logger import PipelineLogger


def run(
    standardized_df: pd.DataFrame,
    meta_data: Dict[str, Any],
    config: dict,
    pipeline_logger: PipelineLogger,
) -> pd.DataFrame:
    """
    Extract vehicle year from sheet_name/data and store in meta_data.

    For Mazda CSV files, the year information may be in a different format than
    Mitsubishi Excel files. This function extracts the year from the data or sheet_name.

    Args:
        standardized_df: DataFrame from Step 3 (may contain year information)
        meta_data: Metadata dict to be updated in-place with vehicle_year
        config: Configuration containing valid_year_range
        pipeline_logger: Pipeline logger for debug messages

    Returns:
        standardized_df (unchanged)

    Raises:
        PipelineFatalError: If year cannot be extracted or is out of valid range
    """

    try:
        # Get valid year range from config
        oem_config = config.get("model_lookup_rules", {}).get("Mazda", {})
        year_range = oem_config.get("valid_year_range", {"min": 1900, "max": 2100})
        min_year = year_range.get("min", 1900)
        max_year = year_range.get("max", 2100)

        # For Mazda, check if there's a ModelYear column in the data
        if "model_year" in standardized_df.columns:
            # Get the most common year (should be same for all rows in a batch)
            years = standardized_df["model_year"].dropna().unique()
            if len(years) > 0:
                vehicle_year = int(years[0])

                # Validate year is within configured range
                if vehicle_year < min_year or vehicle_year > max_year:
                    raise PipelineFatalError(
                        f"Extracted year {vehicle_year} is outside valid range ({min_year}-{max_year})"
                    )

                meta_data["vehicle_year"] = vehicle_year
                pipeline_logger.debug(f"Extracted vehicle_year from data: {vehicle_year}")
                return standardized_df

        # Fallback: try to extract from sheet_name if available
        sheet_name = meta_data.get("sheet_name", "unknown")
        match = re.match(r"^(\d{4})", sheet_name)

        if match:
            vehicle_year = int(match.group(1))

            # Validate year is within configured range
            if vehicle_year < min_year or vehicle_year > max_year:
                raise PipelineFatalError(
                    f"Sheet '{sheet_name}': Extracted year {vehicle_year} is outside "
                    f"valid range ({min_year}-{max_year})"
                )

            meta_data["vehicle_year"] = vehicle_year
            pipeline_logger.debug(f"Extracted vehicle_year from sheet: {vehicle_year}")
            return standardized_df

        # If we reach here, no year found
        raise PipelineFatalError(
            f"Could not extract vehicle_year from Mazda data. "
            f"Expected 'model_year' column or year in sheet_name."
        )

    except PipelineFatalError:
        raise
    except Exception as e:
        raise PipelineFatalError(f"Error extracting vehicle year: {str(e)}")
