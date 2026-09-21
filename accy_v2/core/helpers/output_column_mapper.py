"""Shared YAML-driven column mapping for output formatting (DECISION [019])."""

from typing import Any, Dict
import pandas as pd


def apply_downstream_column_mapping(
    df: pd.DataFrame, downstream_schema: dict, language: str
) -> pd.DataFrame:
    """
    Rename and filter columns per downstream_schema for a given language.

    Implements DECISION [019]: column mapping is driven by YAML, not hardcoded.
    This enables OEMs to add/modify output columns by editing downstream.yaml only.

    Args:
        df: DataFrame to transform
        downstream_schema: Parsed downstream.yaml with sheets and column definitions
        language: Language code (EN, FR, etc.) to select the correct sheet

    Returns:
        DataFrame with columns renamed and filtered per schema definition
    """
    df = df.copy()

    # DEBUG: Print actual columns in source DataFrame
    import sys
    print(f"[OUTPUT_MAPPER DEBUG] Source columns: {list(df.columns)}", file=sys.stderr)

    # Get all sheet definitions
    sheets = downstream_schema.get("sheets", {})

    # Find the sheet definition for this language
    sheet_for_lang = None
    for sheet_name, sheet_def in sheets.items():
        if sheet_def.get("language") == language:
            sheet_for_lang = sheet_def
            break

    # If no sheet found for this language, return df unchanged
    if not sheet_for_lang:
        return df

    # Build rename map and list of required output columns
    rename_map = {}
    required_output_cols = []

    for col_def in sheet_for_lang.get("columns", []):
        output_col = col_def.get("output_column")
        source_col = col_def.get("source_column")

        if output_col and source_col:
            rename_map[source_col] = output_col
            required_output_cols.append(output_col)

    print(f"[OUTPUT_MAPPER DEBUG] Rename map: {rename_map}", file=sys.stderr)
    print(f"[OUTPUT_MAPPER DEBUG] Required output columns: {required_output_cols}", file=sys.stderr)

    # Apply renaming only for columns that exist in the dataframe
    rename_subset = {k: v for k, v in rename_map.items() if k in df.columns}
    print(f"[OUTPUT_MAPPER DEBUG] Rename subset (columns that exist): {rename_subset}", file=sys.stderr)
    df = df.rename(columns=rename_subset)
    print(f"[OUTPUT_MAPPER DEBUG] After rename, columns: {list(df.columns)}", file=sys.stderr)

    # Keep only output columns that exist, in the order specified by YAML
    existing_cols = [col for col in required_output_cols if col in df.columns]

    if existing_cols:
        df = df[existing_cols]

    return df
