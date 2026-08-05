from typing import Any, Dict

import pandas as pd


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

    DECISION [019]: Explicit source→output mapping enables easy column additions
    All column naming is driven by YAML, not hardcoded.
    """
    model_name = meta_data.get("model_name", "unknown")

    frames: Dict[str, pd.DataFrame] = {}

    for lang, df in transformed.items():
        # Build sheet key with language code (elantra_EN, elantra_FR)
        sheet_key = f"{model_name}_{lang}"[:31]

        # Apply language-specific processing (read mapping from downstream.yaml)
        df = _apply_output_column_mapping(df, lang, config)

        frames[sheet_key] = df

    return frames


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _apply_output_column_mapping(df: pd.DataFrame, language: str, config: dict) -> pd.DataFrame:
    """
    Apply DECISION [019] programmable column mapping from downstream.yaml.

    Reads sheet definitions for the target language from downstream schema
    and applies source→output column mapping.
    """
    df = df.copy()

    # Get downstream schema from config
    downstream_schema = config.get("downstream_schema", {})
    sheets = downstream_schema.get("sheets", {})

    # Find the sheet(s) for this language
    # Usually there's a single sheet per language (e.g., Accessories_EN, Accessories_FR)
    sheet_for_lang = None
    for sheet_name, sheet_def in sheets.items():
        if sheet_def.get("language") == language:
            sheet_for_lang = sheet_def
            break

    # If no sheet found for this language, return df unchanged
    if not sheet_for_lang:
        return df

    # Build rename map from column definitions in the sheet
    rename_map = {}
    required_output_cols = []

    for col_def in sheet_for_lang.get("columns", []):
        output_col = col_def.get("output_column")
        source_col = col_def.get("source_column")

        if output_col and source_col:
            rename_map[source_col] = output_col
            required_output_cols.append(output_col)

    # Apply renaming for columns that exist in the dataframe
    rename_subset = {k: v for k, v in rename_map.items() if k in df.columns}
    df = df.rename(columns=rename_subset)

    # Keep only output columns that exist in the dataframe, in the order specified by YAML
    existing_cols = [col for col in required_output_cols if col in df.columns]

    # Filter to required columns in correct order
    if existing_cols:
        df = df[existing_cols]

    return df
