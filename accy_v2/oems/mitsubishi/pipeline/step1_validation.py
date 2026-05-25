import re
from typing import Any, Dict

import pandas as pd

from core.base_pipeline import PipelineFatalError
from core.helpers.dq_logger import DQLogger
from core.helpers.header_helpers import (
    clean_column_name,
    promote_header_row,
    strip_df_string_values,
)
from core.helpers.pipeline_logger import PipelineLogger


def run(
    df_raw: pd.DataFrame,
    config: dict,
    meta_data: Dict[str, Any],
    dq_logger: DQLogger,
    pipeline_logger: PipelineLogger,
) -> pd.DataFrame:
    """
    Validate the raw sheet and return a header-promoted, column-cleaned working_df.
    Populates meta_data in-place with model_name.
    Raises PipelineFatalError for structural issues (FATAL).
    Logs DQ_WARNINGs for data-level issues (profitability).
    """
    sheet_name = meta_data["sheet_name"]

    _validate_sheet_name(sheet_name, config)
    _extract_meta_data(df_raw, sheet_name, meta_data)
    _validate_header_keywords(df_raw, sheet_name, config)
    _validate_trim_boundaries(df_raw, sheet_name, config)

    working_df = _build_working_df(df_raw)

    working_df = _validate_non_null_columns(working_df, sheet_name, meta_data, config, dq_logger)
    _validate_data_types(working_df, sheet_name, config)
    _check_profitability(working_df, sheet_name, meta_data, dq_logger)

    return working_df


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _validate_sheet_name(sheet_name: str, config: dict) -> None:
    pattern = config.get("sheet_name_pattern", r"^\d{4}\s+.+")
    if not re.match(pattern, sheet_name, re.IGNORECASE):
        raise PipelineFatalError(
            f"Sheet name '{sheet_name}' does not match expected pattern '{pattern}'"
        )
    non_acceptable = [s.lower() for s in config["non_acceptable_sheet_names"]]
    if sheet_name.lower() in non_acceptable:
        raise PipelineFatalError(f"Sheet '{sheet_name}' is in the non-acceptable list")


def _extract_meta_data(
    df_raw: pd.DataFrame, sheet_name: str, meta_data: Dict[str, Any]
) -> None:
    if df_raw.shape[0] < 2:
        raise PipelineFatalError(f"Sheet '{sheet_name}' has fewer than 2 rows")

    raw_model_name = df_raw.iloc[0, 0]
    if pd.isna(raw_model_name):
        raise PipelineFatalError(
            f"Sheet '{sheet_name}': cell (0,0) is empty — model name missing"
        )

    name = str(raw_model_name).strip()
    name = re.sub(r"\s*-\s*", "-", name)
    name = re.sub(r"\s{2,}", " ", name).strip().replace(" ", "_").lower()
    meta_data["model_name"] = name


def _validate_header_keywords(
    df_raw: pd.DataFrame, sheet_name: str, config: dict
) -> None:
    header_row = [str(v).lower().strip() for v in df_raw.iloc[1].tolist()]
    column_definition = config["column_definition"]

    for std_col in config["required_columns"]:
        must_have = [
            k.lower() for k in column_definition[std_col]["key_words"]["must_have"]
        ]
        found = any(all(kw in cell for kw in must_have) for cell in header_row)
        if not found:
            raise PipelineFatalError(
                f"Sheet '{sheet_name}': required column '{std_col}' "
                f"(keywords: {must_have}) not found in header row"
            )


def _validate_trim_boundaries(
    df_raw: pd.DataFrame, sheet_name: str, config: dict
) -> None:
    header_row = [str(v).lower().strip() for v in df_raw.iloc[1].tolist()]
    bounds = config["trim_bounds_config"]

    left_kws = [k.lower() for k in bounds["left_bound"]["must_contain"]]
    right_kws = [k.lower() for k in bounds["right_bound"]["must_contain_one_of"]]

    left_found = any(all(k in cell for k in left_kws) for cell in header_row)
    right_found = any(any(k in cell for k in right_kws) for cell in header_row)

    if not left_found:
        raise PipelineFatalError(
            f"Sheet '{sheet_name}': left trim boundary column (keywords: {left_kws}) not found"
        )
    if not right_found:
        raise PipelineFatalError(
            f"Sheet '{sheet_name}': right trim boundary column (keywords: {right_kws}) not found"
        )


def _build_working_df(df_raw: pd.DataFrame) -> pd.DataFrame:
    working_df = promote_header_row(df_raw)
    working_df.columns = [clean_column_name(str(c)).lower() for c in working_df.columns]
    working_df = strip_df_string_values(working_df)
    working_df = working_df.dropna(axis=1, how="all")
    return working_df


def _validate_non_null_columns(
    working_df: pd.DataFrame,
    sheet_name: str,
    meta_data: Dict[str, Any],
    config: dict,
    dq_logger: DQLogger,
) -> pd.DataFrame:
    df = working_df.copy()
    col_lower = {c.lower(): c for c in df.columns}
    threshold = config.get("non_null_threshold", 0.5)
    exclude_mask = pd.Series(False, index=df.index)

    for std_col in config["non_null_columns"]:
        actual_col = next(
            (orig for lower, orig in col_lower.items() if std_col in lower), None
        )
        if actual_col is None:
            raise PipelineFatalError(
                f"Sheet '{sheet_name}': expected non-null column '{std_col}' not found"
            )
        null_mask = df[actual_col].isna() | (
            df[actual_col].astype(str).str.strip() == ""
        )
        null_rate = null_mask.sum() / max(len(df), 1)
        if null_rate >= threshold:
            raise PipelineFatalError(
                f"Sheet '{sheet_name}': column '{actual_col}' has {null_mask.sum()} null/empty values "
                f"({null_rate:.0%}) — exceeds threshold of {threshold:.0%}, sheet skipped"
            )
        for idx, row in df[null_mask].iterrows():
            dq_logger.log_warning(
                sheet_name=sheet_name,
                model_name=meta_data.get("model_name", "unknown"),
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
    working_df: pd.DataFrame, sheet_name: str, config: dict
) -> None:
    col_lower = {c.lower(): c for c in working_df.columns}

    for std_col in config["col_data_type_dict"].get("to_float", []):
        actual_col = next(
            (orig for lower, orig in col_lower.items() if std_col in lower), None
        )
        if actual_col is None:
            continue
        non_null = working_df[actual_col].dropna()
        bad = non_null[pd.to_numeric(non_null, errors="coerce").isna()]
        if not bad.empty:
            raise PipelineFatalError(
                f"Sheet '{sheet_name}': column '{actual_col}' contains non-numeric values: "
                f"{bad.head(3).tolist()}"
            )


def _check_profitability(
    working_df: pd.DataFrame,
    sheet_name: str,
    meta_data: Dict[str, Any],
    dq_logger: DQLogger,
) -> None:
    col_lower = {c.lower(): c for c in working_df.columns}
    dnp_col = next((orig for lower, orig in col_lower.items() if "dnp" in lower), None)
    msrp_col = next(
        (orig for lower, orig in col_lower.items() if "msrp" in lower), None
    )

    if dnp_col is None or msrp_col is None:
        return

    for idx, row in working_df.iterrows():
        try:
            dnp = float(row[dnp_col])
            msrp = float(row[msrp_col])
        except (ValueError, TypeError):
            continue

        if dnp <= 0 or msrp <= 0:
            dq_logger.log_warning(
                sheet_name=sheet_name,
                model_name=meta_data.get("model_name", "unknown"),
                record_index=int(idx),
                record_snapshot=row.to_dict(),
                rule_violated="profitability_rule",
                issue_description=f"DNP={dnp} or MSRP={msrp} must be > 0",
            )
        elif msrp <= dnp:
            dq_logger.log_warning(
                sheet_name=sheet_name,
                model_name=meta_data.get("model_name", "unknown"),
                record_index=int(idx),
                record_snapshot=row.to_dict(),
                rule_violated="profitability_rule",
                issue_description=f"MSRP ({msrp}) must be greater than DNP ({dnp})",
            )
