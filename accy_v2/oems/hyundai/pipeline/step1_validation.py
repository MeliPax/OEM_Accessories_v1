from typing import Any, Dict

import pandas as pd

from core.base_pipeline import PipelineFatalError
from core.helpers.column_mapper import map_all_columns
from core.helpers.dq_logger import DQLogger
from core.helpers.header_helpers import strip_df_string_values
from core.helpers.pipeline_logger import PipelineLogger


def run(
    df_raw: pd.DataFrame,
    config: dict,
    meta_data: Dict[str, Any],
    dq_logger: DQLogger,
    pipeline_logger: PipelineLogger,
) -> pd.DataFrame:
    """
    Validate Hyundai row-grouped data and return a working_df.

    Note: Unlike Mitsubishi, df_raw here is ALREADY header-promoted and column-cleaned
    (load_file() does this before grouping). No sheet-name parsing needed since Hyundai
    is a single Master sheet grouped by (year, model).

    Extract metadata from special columns added by load_file(): group_key, year_from,
    model_name, manufacturer. These are removed before returning the working_df.
    """
    working_df = df_raw.copy()

    # Extract metadata columns (added by load_file) before stripping
    if "__group_key__" in working_df.columns:
        meta_data["group_key"] = working_df["__group_key__"].iloc[0]
    if "__year_from__" in working_df.columns:
        meta_data["year_from"] = working_df["__year_from__"].iloc[0]
    if "__model_name__" in working_df.columns:
        meta_data["model_name"] = working_df["__model_name__"].iloc[0]
    if "__manufacturer__" in working_df.columns:
        meta_data["manufacturer"] = working_df["__manufacturer__"].iloc[0]

    group_key = meta_data.get("group_key", "unknown")
    model_name = meta_data.get("model_name", "unknown")

    # Remove metadata columns from the dataframe
    working_df = working_df.drop(
        columns=[c for c in working_df.columns if c.startswith("__")],
        errors="ignore",
    )

    working_df = strip_df_string_values(working_df)
    working_df = working_df.dropna(axis=1, how="all")

    if len(working_df) == 0:
        raise PipelineFatalError(f"Group '{group_key}': no data rows after cleanup")

    _validate_required_columns(working_df, group_key, config)
    working_df = _validate_non_null_columns(working_df, group_key, model_name, config, dq_logger)
    _validate_data_types(working_df, group_key, config)
    _check_profitability(working_df, group_key, model_name, dq_logger, config)

    return working_df


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _validate_required_columns(
    working_df: pd.DataFrame, group_key: str, config: dict
) -> None:
    col_lower = {c.lower(): c for c in working_df.columns}
    column_definition = config["column_definition"]

    for std_col in config["required_columns"]:
        if std_col not in column_definition:
            continue
        key_words = column_definition[std_col]["key_words"]["must_have"]
        must_have = [k.lower() for k in key_words]

        found = any(
            all(kw in cell_lower for kw in must_have)
            for cell_lower in col_lower.keys()
        )
        if not found:
            raise PipelineFatalError(
                f"Group '{group_key}': required column '{std_col}' "
                f"(keywords: {must_have}) not found in header row"
            )


def _validate_non_null_columns(
    working_df: pd.DataFrame,
    group_key: str,
    model_name: str,
    config: dict,
    dq_logger: DQLogger,
) -> pd.DataFrame:
    df = working_df.copy()
    threshold = config.get("non_null_threshold", 0.5)
    exclude_mask = pd.Series(False, index=df.index)

    # Use map_all_columns to map semantic names to actual column names
    col_mapping = map_all_columns(df, config["column_definition"])

    for std_col in config["non_null_columns"]:
        # Find actual column using mapping from map_all_columns
        actual_col = col_mapping.get(std_col)
        if actual_col is None:
            raise PipelineFatalError(
                f"Group '{group_key}': expected non-null column '{std_col}' not found"
            )

        null_mask = df[actual_col].isna() | (df[actual_col].astype(str).str.strip() == "")
        null_rate = null_mask.sum() / max(len(df), 1)

        if null_rate >= threshold:
            raise PipelineFatalError(
                f"Group '{group_key}': column '{actual_col}' has {null_mask.sum()} null/empty values "
                f"({null_rate:.0%}) — exceeds threshold of {threshold:.0%}"
            )

        for idx, row in df[null_mask].iterrows():
            dq_logger.log_warning(
                sheet_name=group_key,
                model_name=model_name,
                record_index=int(idx),
                record_snapshot=row.to_dict(),
                rule_violated="non_null_column_rule",
                issue_description=(
                    f"Column '{actual_col}' is null/empty — record excluded from output"
                ),
            )
        exclude_mask |= null_mask

    return df[~exclude_mask].reset_index(drop=True)


def _validate_data_types(
    working_df: pd.DataFrame, group_key: str, config: dict
) -> None:
    # Use map_all_columns to find columns
    col_mapping = map_all_columns(working_df, config["column_definition"])

    for std_col in config["col_data_type_dict"].get("to_float", []):
        actual_col = col_mapping.get(std_col)
        if actual_col is None:
            continue

        non_null = working_df[actual_col].dropna()
        bad = non_null[pd.to_numeric(non_null, errors="coerce").isna()]
        if not bad.empty:
            raise PipelineFatalError(
                f"Group '{group_key}': column '{actual_col}' contains non-numeric values: "
                f"{bad.head(3).tolist()}"
            )


def _check_profitability(
    working_df: pd.DataFrame,
    group_key: str,
    model_name: str,
    dq_logger: DQLogger,
    config: dict,
) -> None:
    # Use map_all_columns to find dnet and msrp columns
    col_mapping = map_all_columns(working_df, config["column_definition"])

    dnet_col = col_mapping.get("dnet")
    msrp_col = col_mapping.get("msrp")

    if dnet_col is None or msrp_col is None:
        return

    for idx, row in working_df.iterrows():
        try:
            dnet = float(row[dnet_col])
            msrp = float(row[msrp_col])
        except (ValueError, TypeError):
            continue

        if dnet <= 0 or msrp <= 0:
            dq_logger.log_warning(
                sheet_name=group_key,
                model_name=model_name,
                record_index=int(idx),
                record_snapshot=row.to_dict(),
                rule_violated="profitability_rule",
                issue_description=f"DNET={dnet} or MSRP={msrp} must be > 0",
            )
        elif msrp <= dnet:
            dq_logger.log_warning(
                sheet_name=group_key,
                model_name=model_name,
                record_index=int(idx),
                record_snapshot=row.to_dict(),
                rule_violated="profitability_rule",
                issue_description=f"MSRP ({msrp}) must be greater than DNET ({dnet})",
            )
