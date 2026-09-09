from typing import Any, Dict, Optional

import pandas as pd

from core.helpers.output_column_mapper import apply_downstream_column_mapping
from core.helpers.orphan_record_validator import flag_orphaned_records
from core.helpers.dq_logger import DQLogger


def prepare_frames(
    transformed: Dict[str, pd.DataFrame],
    meta_data: Dict[str, Any],
    config: dict,
    dq_logger: Optional[DQLogger] = None,
) -> Dict[str, pd.DataFrame]:
    """
    Prepare output frames using programmable downstream schema.

    Process:
    1. For each language (EN, FR from transformed dict)
    2. Apply language-specific column mapping from downstream schema
    3. Rename columns to output names
    4. Filter to required output columns
    5. Flag orphaned records (null model numbers) as cross-OEM safety net
    6. Return keyed by proper sheet name (model_EN, model_FR)

    DECISION [019]: Explicit source→output mapping enables easy column additions.
    Column mapping is driven entirely by YAML config, not hardcoded.
    """
    model_name = meta_data.get("model_name", "unknown")
    downstream_schema = config.get("downstream_schema", {})

    frames: Dict[str, pd.DataFrame] = {}

    for lang, df in transformed.items():
        # Build sheet key with language code (elantra_EN, elantra_FR)
        sheet_key = f"{model_name}_{lang}"[:31]

        # Apply language-specific column mapping from downstream schema
        df = apply_downstream_column_mapping(df, downstream_schema, lang)

        # Flag orphaned records (null model numbers) — safety net for upstream failures
        df = flag_orphaned_records(df, dq_logger, sheet_key, model_number_column="Model")

        frames[sheet_key] = df

    return frames
