from typing import Any, Dict

import pandas as pd

from core.helpers.output_column_mapper import apply_downstream_column_mapping


def prepare_frames(
    transformed: Dict[str, pd.DataFrame],
    meta_data: Dict[str, Any],
    config: dict,
) -> Dict[str, pd.DataFrame]:
    """
    Prepare output frames using programmable downstream schema.

    Process:
    1. For each language (EN, FR from transformed dict)
    2. Read language-specific column mapping from downstream.yaml
    3. Rename columns to output names
    4. Filter to required output columns (in order from YAML)
    5. Return keyed by proper sheet name (model_EN, model_FR)

    DECISION [019]: Explicit source→output mapping enables easy column additions.
    All column naming is driven by YAML, not hardcoded.
    """
    model_name = meta_data.get("model_name", "unknown")
    downstream_schema = config.get("downstream_schema", {})

    frames: Dict[str, pd.DataFrame] = {}

    for lang, df in transformed.items():
        # Build sheet key with language code (elantra_EN, elantra_FR)
        sheet_key = f"{model_name}_{lang}"[:31]

        # Apply language-specific column mapping from downstream schema
        df = apply_downstream_column_mapping(df, downstream_schema, lang)

        frames[sheet_key] = df

    return frames
