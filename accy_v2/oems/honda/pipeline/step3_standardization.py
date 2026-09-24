"""Step 3: Standardization & Packages/Kits Rollup

Standardizes data types, cleans data, and implements parent-child aggregation logic.

Will implement in Phase 4:
  - Data cleanup per section (trim whitespace, type coercion)
  - Packages/Kits rollup:
    - Parent detection (has description + price + trims; children don't)
    - Child aggregation (concatenate descriptions into comments)
    - Numeric values (keep parent; flag if empty)
    - Trim applicability (keep parent; flag if children diverge)
  - DQ logging (orphaned children, parent-child mismatches)
  - Produce unified dataframe (one row per unique part, all sections merged)
"""

from typing import Tuple, Dict, Any

import pandas as pd


def standardize(
    df: pd.DataFrame,
    metadata: Dict[str, Any],
    config: Dict[str, Any],
) -> Tuple[pd.DataFrame, Dict[str, Any], list]:
    """Standardize data and implement rollup logic.

    Args:
        df: Normalized DataFrame from Step 2
        metadata: Metadata from Steps 1-2
        config: Pipeline configuration

    Returns:
        Tuple of (standardized_dataframe, updated_metadata, dq_warnings)
    """
    # Phase 4: Implementation
    # 1. Clean data per section
    # 2. Detect parent-child relationships
    # 3. Aggregate children into parents
    # 4. Merge all sections into unified dataframe
    # 5. Extract vehicle_year from metadata
    # 6. Log DQ warnings (rollup_verification_rule, etc.)
    pass
