"""Step 3.5: Extract Vehicle Year

Simple utility step to extract and validate vehicle year from metadata.

Will implement in Phase 5:
  - Extract year from metadata (already populated in Step 1)
  - Validate year range (2020-2030)
  - Store in metadata for downstream use
"""

from typing import Dict, Any

import pandas as pd


def extract_vehicle_year(
    metadata: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Extract and validate vehicle year.

    Args:
        metadata: Metadata from Steps 1-3
        config: Pipeline configuration

    Returns:
        Updated metadata with vehicle_year confirmed
    """
    # Phase 5: Implementation
    # 1. Extract year from metadata
    # 2. Validate year range
    # 3. Return updated metadata
    pass
