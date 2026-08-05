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
    2. Apply language-specific column mapping from downstream schema
    3. Rename columns to output names
    4. Filter to required output columns
    5. Return keyed by proper sheet name (model_EN, model_FR)

    DECISION [019]: Explicit source→output mapping enables easy column additions
    """
    model_name = meta_data.get("model_name", "unknown")

    frames: Dict[str, pd.DataFrame] = {}

    for lang, df in transformed.items():
        # Build sheet key with language code (elantra_EN, elantra_FR)
        sheet_key = f"{model_name}_{lang}"[:31]

        # Apply language-specific processing
        df = _apply_output_column_mapping(df, lang)

        frames[sheet_key] = df

    return frames


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _apply_output_column_mapping(df: pd.DataFrame, language: str) -> pd.DataFrame:
    """
    Apply DECISION [019] programmable column mapping.

    Maps source columns to output columns based on language.
    Handles language-specific description/comments selection.
    """
    df = df.copy()

    # Language-specific source → output column mapping
    # Maps the actual column names from step4 transformation to final output names
    # Note: step4_transformation._split_by_language() renames:
    #   Description/Description_FR → "description" (depends on language)
    #   Comments/Comments_FR → "comments" (depends on language)
    #   Other columns keep their original names: ModelYear, ModelName, etc.

    # Map snake_case source columns (from step4) to Title Case output columns
    # NOTE: step4_transformation uses snake_case column names: year_from, model, part_number, etc.
    # Mazda-specific: package was renamed to "Package" in step4, short_model_number stays as-is
    if language == "EN":
        rename_map = {
            "year_from": "Year",
            "model_name": "ModelName",
            "part_number": "Part",
            "english_description": "Description",  # Use English description for EN sheet
            "comments_en": "Comments",              # Use English comments for EN sheet
            "msrp": "Price",
            "labour_hours": "Hours",
            "trim_level": "Trim",
            "model_number": "model_number",
            "short_model_number": "ModelNumber",
        }
    elif language == "FR":
        rename_map = {
            "year_from": "Year",
            "model_name": "ModelName",
            "part_number": "Part",
            "french_description": "Description",   # Use French description for FR sheet
            "comments_fr": "Comments",              # Use French comments for FR sheet
            "msrp": "Price",
            "labour_hours": "Hours",
            "trim_level": "Trim",
            "model_number": "model_number",
            "short_model_number": "ModelNumber",
        }
    else:
        # Fallback
        rename_map = {
            "year_from": "Year",
            "model_name": "ModelName",
            "part_number": "Part",
            "english_description": "Description",
            "comments_en": "Comments",
            "msrp": "Price",
            "labour_hours": "Hours",
            "trim_level": "Trim",
            "model_number": "model_number",
            "short_model_number": "ModelNumber",
        }

    # Apply renaming for columns that exist
    rename_subset = {k: v for k, v in rename_map.items() if k in df.columns}
    df = df.rename(columns=rename_subset)

    # Define required output columns (order matters for Excel)
    # Mazda-specific: Include Package and ModelNumber in output
    required_output_cols = [
        "Year", "ModelName", "Part", "Description", "Comments",
        "Price", "Hours", "Trim", "Package", "ModelNumber"
    ]

    # Keep only output columns that exist in the dataframe
    existing_cols = [col for col in required_output_cols if col in df.columns]

    # Filter to required columns in correct order
    if existing_cols:
        df = df[existing_cols]

    return df
