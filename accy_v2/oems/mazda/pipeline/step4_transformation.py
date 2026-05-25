from typing import Any, Dict

import pandas as pd

from core.helpers.pipeline_logger import PipelineLogger


def run(
    standardized_df: pd.DataFrame,
    step2_result: Dict,
    config: dict,
    meta_data: Dict[str, Any],
    dq_logger,
    pipeline_logger: PipelineLogger,
) -> Dict[str, pd.DataFrame]:
    """
    Split by language — Mazda has no trim melting (trim is already per-row as package).
    Drops opposite-language columns for each output dataframe.
    Renames language-specific description/comments to neutral 'description'/'comments'.
    Returns {"EN": df, "FR": df}.
    """
    sheet_name = meta_data["sheet_name"]
    language_columns = config.get("language_columns", {})

    if not language_columns:
        return {"default": standardized_df}

    all_lang_cols = [col for cols in language_columns.values() for col in cols]
    result = {}

    for lang, lang_cols in language_columns.items():
        cols_to_drop = [col for col in all_lang_cols if col not in lang_cols]
        lang_df = standardized_df.drop(columns=cols_to_drop, errors="ignore").copy()

        # Rename language-specific columns to neutral names
        rename_map = {col: "description" if "description" in col else "comments" for col in lang_cols if col in lang_df.columns}
        lang_df = lang_df.rename(columns=rename_map)

        # Rename package column to match rate importer requirement
        if "package" in lang_df.columns:
            lang_df = lang_df.rename(columns={"package": "Package"})

        result[lang] = lang_df

    pipeline_logger.debug(f"Sheet '{sheet_name}': split into {list(result.keys())} languages")

    return result
