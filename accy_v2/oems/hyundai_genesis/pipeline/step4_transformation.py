from typing import Any, Dict, List

import pandas as pd

from core.helpers.dq_logger import DQLogger
from core.helpers.pipeline_logger import PipelineLogger


def run(
    standardized_df: pd.DataFrame,
    step2_result: Dict[str, Any],
    config: dict,
    meta_data: Dict[str, Any],
    dq_logger: DQLogger,
    pipeline_logger: PipelineLogger,
) -> Dict[str, pd.DataFrame]:
    """
    Melt trim columns into rows, split by language.
    Returns {"EN": df, "FR": df}.

    Hyundai differs from Mitsubishi: trim columns contain the actual trim name (e.g., "Preferred"),
    not an "X" marker. Filter after melt by non-null/non-empty trim value, not equality to "X".
    """
    valid_trim_cols = step2_result["valid_trim_cols"]

    # step3 already validated that all rows have at least one populated trim col via trim_applicability_required_rule
    melted_df = _melt_trim_cols(standardized_df, valid_trim_cols)

    pipeline_logger.debug(
        f"{len(standardized_df)} records -> {len(melted_df)} after melt"
    )

    return _split_by_language(melted_df, config)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _melt_trim_cols(
    df: pd.DataFrame,
    valid_trim_cols: List[str],
) -> pd.DataFrame:
    """
    Melt trim columns. Keep only rows where the melted trim value is non-null/non-empty
    (since the cell *is* the trim name, not an applicability marker).

    Note: After step3's trim_applicability_required_rule validates that every record has
    at least one populated trim column, empty trim values here are expected (parts may
    apply to only some trim levels, not all). These are silently filtered as normal
    reshape behavior, not DQ violations.

    var_name uses "trim_column" (not "trim_level") to avoid collision when
    renaming trim_value to trim_level. Final output has "trim_level" (values) and
    "trim_column" (original column names like Trim_1, Trim_2).
    """
    id_vars = [col for col in df.columns if col not in valid_trim_cols]
    melted = df.melt(
        id_vars=id_vars,
        value_vars=valid_trim_cols,
        var_name="trim_column",
        value_name="trim_value",
    )

    # Keep only rows where trim_value is non-null/non-empty
    # (parts may apply to only some trim levels; empty cells are normal filtering, not DQ issues)
    trim_mask = (
        melted["trim_value"].notna()
        & (melted["trim_value"].astype(str).str.strip().str.len() > 0)
    )

    # Rename trim_value to trim_level (the standard name expected by downstream steps)
    melted_filtered = melted[trim_mask].copy()
    melted_filtered = melted_filtered.rename(columns={"trim_value": "trim_level"})

    return melted_filtered.reset_index(drop=True)


def _split_by_language(df: pd.DataFrame, config: dict) -> Dict[str, pd.DataFrame]:
    """Split DataFrame into language-specific views (EN, FR)."""
    language_columns = config.get("language_columns", {})
    if not language_columns:
        return {"default": df}

    all_lang_cols = [col for cols in language_columns.values() for col in cols]
    result = {}

    for lang, lang_cols in language_columns.items():
        cols_to_drop = [col for col in all_lang_cols if col not in lang_cols]
        lang_df = df.drop(columns=cols_to_drop, errors="ignore").copy()

        # Rename language-specific description columns to neutral "description" and "comments"
        rename_map = {}
        for col in lang_cols:
            if col in lang_df.columns:
                if "description" in col.lower():
                    rename_map[col] = "description"
                elif "comments" in col.lower():
                    rename_map[col] = "comments"

        if rename_map:
            lang_df = lang_df.rename(columns=rename_map)

        result[lang] = lang_df

    return result
