"""Step 4: Transformation & EN/FR Reconciliation

Transforms data to long format and implements EN/FR reconciliation.

Will implement in Phase 4:
  - Load FR sheet independently
  - Normalize composite part numbers (both EN & FR)
  - Create reconciliation map with confidence scoring
  - Melt trims to long format (separately for EN and FR)
  - Apply reconciliation map for intelligent join
  - Add merge_confidence metadata column
  - Track join quality metrics
"""

from typing import Tuple, Dict, Any

import pandas as pd


def transform(
    df_en: pd.DataFrame,
    df_fr: pd.DataFrame,
    metadata: Dict[str, Any],
    config: Dict[str, Any],
) -> Tuple[pd.DataFrame, Dict[str, Any], list]:
    """Transform data and reconcile EN/FR sheets.

    Args:
        df_en: Standardized EN DataFrame from Step 3
        df_fr: Standardized FR DataFrame from Step 3
        metadata: Metadata from Steps 1-3
        config: Pipeline configuration

    Returns:
        Tuple of (transformed_dataframe, updated_metadata, dq_warnings)
    """
    # Phase 4: Implementation
    # Step 4a: EN/FR Reconciliation
    #   - Load and standardize both sheets
    #   - Normalize composite part numbers
    #   - Create reconciliation map
    #   - Store in metadata

    # Step 4b: Trim Melting & Reconciliation-Aware Join
    #   - Melt EN trims to long format
    #   - Melt FR trims to long format
    #   - Apply reconciliation map
    #   - Join EN and FR via map (not simple left-join)
    #   - Add merge_confidence metadata
    #   - Track join quality
    pass
