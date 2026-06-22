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
    Extract vehicle year from sheet_name and store in meta_data.

    Sheet name format: YYYY_ModelName_Language (e.g., "2026_Outlander_ES_EN")

    This step:
    1. Extracts the 4-digit year from the sheet_name
    2. Validates year against configured valid_year_range
    3. Stores it in meta_data["vehicle_year"]
    4. Returns the DataFrame unchanged

    Args:
        standardized_df: DataFrame from Step 3 (unchanged)
        meta_data: Metadata dict to be updated in-place with vehicle_year
        config: Configuration containing valid_year_range
        pipeline_logger: Pipeline logger for debug messages

    Returns:
        standardized_df (unchanged)

    Raises:
        PipelineFatalError: If year cannot be extracted or is out of valid range
    """

    sheet_name = meta_data.get("sheet_name", "unknown")

    try:
        # Get valid year range from config
        oem_config = config.get("model_lookup_rules", {}).get("Mitsubishi", {})
        year_range = oem_config.get("valid_year_range", {"min": 1900, "max": 2100})
        min_year = year_range.get("min", 1900)
        max_year = year_range.get("max", 2100)

        # Extract first 4 digits (YYYY format)
        match = re.match(r"^(\d{4})", sheet_name)

        if not match:
            raise PipelineFatalError(
                f"Sheet '{sheet_name}': Could not extract 4-digit year from beginning. "
                f"Expected format: YYYY_ModelName_Language"
            )

        vehicle_year = int(match.group(1))

        # Validate year is within configured range
        if vehicle_year < min_year or vehicle_year > max_year:
            raise PipelineFatalError(
                f"Sheet '{sheet_name}': Extracted year {vehicle_year} is outside "
                f"valid range ({min_year}-{max_year})"
            )

        # Store in meta_data for downstream steps
        meta_data["vehicle_year"] = vehicle_year

        pipeline_logger.debug(f"Extracted vehicle_year: {vehicle_year} from sheet '{sheet_name}'")

        return standardized_df

    except PipelineFatalError:
        raise
    except Exception as e:
        raise PipelineFatalError(
            f"Sheet '{sheet_name}': Unexpected error extracting vehicle year: {str(e)}"
        )
