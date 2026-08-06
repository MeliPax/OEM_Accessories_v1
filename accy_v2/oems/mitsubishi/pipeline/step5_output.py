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
    2. Add Year from metadata (extracted from sheet name during pipeline)
    3. Add Model extracted from trim_level (first part before delimiter)
    4. Apply language-specific column mapping from downstream schema
    5. Rename columns to output names
    6. Filter to required output columns
    7. Return keyed by proper sheet name (model_EN, model_FR)

    DECISION [019]: Explicit source→output mapping enables easy column additions
    """
    model_name = meta_data.get("model_name", "unknown")
    vehicle_year = meta_data.get("vehicle_year")  # Extracted from sheet name in earlier steps

    frames: Dict[str, pd.DataFrame] = {}

    for lang, df in transformed.items():
        # Build sheet key with language code (elantra_EN, elantra_FR)
        sheet_key = f"{model_name}_{lang}"[:31]

        # Add Year column from metadata if available
        if vehicle_year:
            df = df.copy()
            df.insert(0, "year_from", vehicle_year)

        # Extract Model from trim_level (first part before any delimiter)
        if "trim_level" in df.columns:
            df = df.copy()
            df["model"] = df["trim_level"].apply(_extract_model_from_trim)

        # Apply language-specific processing
        df = _apply_output_column_mapping(df, lang)

        frames[sheet_key] = df

    return frames


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _extract_model_from_trim(trim_value: str) -> str:
    """
    Extract model code from trim level.
    Examples:
      'es_s-awc' → 'es'
      'es_fwd' → 'es'
      'noir_awc' → 'noir'
      'gt_s-awc' → 'gt'
      'gt-p' → 'gt-p' (PHEV variant, keep as-is)
      'gt-premium' → 'gt-premium' (keep as-is)
    """
    if not isinstance(trim_value, str):
        return str(trim_value) if trim_value else "unknown"

    # Split on underscore and take first part (handles: es_s-awc → es)
    if "_" in trim_value:
        return trim_value.split("_")[0].lower()

    # Return as-is if no underscore (handles: es, gt-p, gt-premium, etc.)
    return trim_value.lower()


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
    if language == "EN":
        rename_map = {
            "year_from": "Year",
            "model": "Model",
            "part_number": "Part",
            "english_description": "Description",  # Use English description for EN sheet
            "comments_en": "Comments",              # Use English comments for EN sheet
            "msrp": "Price",
            "labour_hours": "Hours",
            "trim_level": "Trim",
        }
    elif language == "FR":
        rename_map = {
            "year_from": "Year",
            "model": "Model",
            "part_number": "Part",
            "french_description": "Description",   # Use French description for FR sheet
            "comments_fr": "Comments",              # Use French comments for FR sheet
            "msrp": "Price",
            "labour_hours": "Hours",
            "trim_level": "Trim",
        }
    else:
        # Fallback
        rename_map = {
            "year_from": "Year",
            "model": "Model",
            "part_number": "Part",
            "english_description": "Description",
            "comments_en": "Comments",
            "msrp": "Price",
            "labour_hours": "Hours",
            "trim_level": "Trim",
        }

    # Apply renaming for columns that exist
    rename_subset = {k: v for k, v in rename_map.items() if k in df.columns}
    df = df.rename(columns=rename_subset)

    # Define required output columns (order matters for Excel)
    required_output_cols = [
        "Year", "Model", "Part", "Description", "Comments",
        "Price", "Hours", "Trim"
    ]

    # Keep only output columns that exist in the dataframe
    existing_cols = [col for col in required_output_cols if col in df.columns]

    # Filter to required columns in correct order
    if existing_cols:
        df = df[existing_cols]

    return df
