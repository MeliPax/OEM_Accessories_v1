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
    Validate trim applicability, melt trim columns into rows, split by language.
    Returns {"EN": df, "FR": df}.
    """
    valid_trim_cols = step2_result["valid_trim_cols"]
    sheet_name = meta_data["sheet_name"]
    model_name = meta_data.get("model_name", "unknown")

    df = _validate_trim_applicability(standardized_df, valid_trim_cols, sheet_name, model_name, dq_logger)
    melted_df = _melt_trim_cols(df, valid_trim_cols)

    pipeline_logger.debug(
        f"Sheet '{sheet_name}': {len(df)} records -> {len(melted_df)} after melt"
    )

    return _split_by_language(melted_df, config)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _validate_trim_applicability(
    df: pd.DataFrame,
    valid_trim_cols: List[str],
    sheet_name: str,
    model_name: str,
    dq_logger: DQLogger,
) -> pd.DataFrame:
    if not valid_trim_cols:
        return df

    has_any_x = df[valid_trim_cols].apply(
        lambda row: row.apply(lambda v: isinstance(v, str) and v.upper() == "X").any(),
        axis=1,
    )

    for idx, row in df[~has_any_x].iterrows():
        dq_logger.log_warning(
            sheet_name=sheet_name,
            model_name=model_name,
            record_index=int(idx),
            record_snapshot=row.to_dict(),
            rule_violated="trim_applicability_rule",
            issue_description="Record applies to zero trim levels — excluded from output",
        )

    return df[has_any_x].reset_index(drop=True)


def _melt_trim_cols(df: pd.DataFrame, valid_trim_cols: List[str]) -> pd.DataFrame:
    id_vars = [col for col in df.columns if col not in valid_trim_cols]
    melted = df.melt(
        id_vars=id_vars,
        value_vars=valid_trim_cols,
        var_name="trim_level",
        value_name="applicable",
    )
    # Keep only rows where this part actually applies to the trim (value == "X")
    melted = melted[
        melted["applicable"].apply(lambda v: isinstance(v, str) and v.upper() == "X")
    ]
    return melted.drop(columns=["applicable"]).reset_index(drop=True)


def _split_by_language(df: pd.DataFrame, config: dict) -> Dict[str, pd.DataFrame]:
    language_columns = config.get("language_columns", {})
    if not language_columns:
        return {"default": df}

    all_lang_cols = [col for cols in language_columns.values() for col in cols]
    result = {}

    for lang, lang_cols in language_columns.items():
        cols_to_drop = [col for col in all_lang_cols if col not in lang_cols]
        lang_df = df.drop(columns=cols_to_drop, errors="ignore").copy()

        # Rename language-specific description and comments columns to neutral names
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
