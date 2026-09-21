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
    2. Add Year from metadata (extracted from sheet name during pipeline)
    3. Apply language-specific column mapping from downstream schema
    4. Rename columns to output names
    5. Filter to required output columns
    6. Return keyed by proper sheet name (outlander_EN, outlander_FR)

    DECISION [019]: Explicit source→output mapping enables easy column additions.
    Column mapping is driven entirely by YAML config, not hardcoded.

    Note: Mitsubishi requires year_from injection from metadata (unlike Hyundai/Mazda
    which have it as an upstream column). The model_name is now provided as a real
    column from Step 1 onward (no late injection needed).
    """
    model_name = meta_data.get("model_name", "unknown")
    vehicle_year = meta_data.get("vehicle_year")  # Extracted from sheet name in earlier steps
    downstream_schema = config.get("downstream_schema", {})

    frames: Dict[str, pd.DataFrame] = {}

    for lang, df in transformed.items():
        # Build sheet key with language code (outlander_EN, outlander_FR)
        sheet_key = f"{model_name}_{lang}"[:31]

        df = df.copy()

        # Add Year column from metadata (Mitsubishi-specific: no year_from in upstream data)
        if vehicle_year:
            df.insert(0, "year_from", vehicle_year)

        # Add model_name column (dropped during standardization, re-inject for output)
        df["model_name"] = model_name

        # Apply language-specific column mapping from downstream schema
        df = apply_downstream_column_mapping(df, downstream_schema, lang)

        frames[sheet_key] = df

    return frames
