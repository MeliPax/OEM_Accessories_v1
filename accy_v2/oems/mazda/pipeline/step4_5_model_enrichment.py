"""
Step 4.5 — Model Enrichment / Lookup

For Mazda, this step is typically a no-op since use_model_lookup is false.
Model numbers are already provided in the TrimLevel field from the source data.

Input: {EN: df, FR: df} from step 4
Output: {EN: df, FR: df} (unchanged, or with model_number pre-populated if available)
"""

from typing import Any, Dict

import pandas as pd

from core.helpers.dq_logger import DQLogger
from core.helpers.pipeline_logger import PipelineLogger


def run(
    transformed: Dict[str, pd.DataFrame],
    meta_data: Dict[str, Any],
    config: Dict[str, Any],
    dq_logger: DQLogger,
    pipeline_logger: PipelineLogger,
) -> Dict[str, pd.DataFrame]:
    """
    No-op enrichment for Mazda (model numbers already in source data).

    Mazda's TrimLevel field contains the full model number (e.g., "123456AA00").
    This was already extracted and renamed to short_model_number in step 3.
    No additional lookup needed.

    Args:
        transformed: {EN: df, FR: df} from step 4
        meta_data: Pipeline metadata
        config: Pipeline config
        dq_logger: DQ logger
        pipeline_logger: Pipeline logger

    Returns:
        {EN: df, FR: df} (unchanged)
    """

    pipeline_logger.debug("Mazda model enrichment: use_model_lookup is false, no action needed")

    # Mazda already has model numbers from the source
    # If step 3 created short_model_number column, that's the model number
    # Otherwise, model_number column should be empty

    for lang in ["EN", "FR"]:
        if lang in transformed:
            df = transformed[lang]
            # Ensure model_number column exists (may be empty for Mazda)
            if "model_number" not in df.columns:
                df["model_number"] = None

    return transformed
