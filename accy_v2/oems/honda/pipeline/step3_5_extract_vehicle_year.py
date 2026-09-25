"""Step 3.5: Extract Vehicle Year

Extract and validate vehicle year from metadata (set by Step 1).
Store vehicle_year in metadata for use in Step 4.5 (model lookup).
"""

from typing import Dict, Any
import logging

import pandas as pd


logger = logging.getLogger(__name__)


def extract_vehicle_year(
    metadata: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Extract and validate vehicle year from metadata.

    Honda Step 1 extracts and stores vehicle_year in metadata during file parsing.
    This step validates the year is in acceptable range and stores it for downstream use.

    Args:
        metadata: Metadata from Steps 1-3 (contains vehicle_year from Step 1)
        config: Pipeline configuration (contains valid year range)

    Returns:
        Updated metadata with vehicle_year confirmed and validated

    Raises:
        ValueError: If vehicle_year is missing or outside valid range
    """
    # Extract year from metadata (set by Step 1)
    vehicle_year = metadata.get("vehicle_year")
    model_name = metadata.get("model_name", "unknown")

    if vehicle_year is None:
        raise ValueError(f"vehicle_year not found in metadata for model '{model_name}'")

    # Convert to int if string
    try:
        vehicle_year = int(vehicle_year)
    except (ValueError, TypeError) as e:
        raise ValueError(f"vehicle_year '{vehicle_year}' cannot be converted to int: {e}")

    # Validate year range from config
    valid_year_range = config.get("valid_year_range", {})
    min_year = valid_year_range.get("min", 2020)
    max_year = valid_year_range.get("max", 2030)

    if not (min_year <= vehicle_year <= max_year):
        raise ValueError(
            f"vehicle_year {vehicle_year} is outside valid range [{min_year}, {max_year}] "
            f"for model '{model_name}'"
        )

    # Store validated year in metadata for downstream use
    metadata["vehicle_year"] = vehicle_year
    logger.debug(f"Model '{model_name}': validated vehicle_year={vehicle_year}")

    return metadata
