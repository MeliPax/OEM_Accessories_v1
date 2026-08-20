import re
from typing import Any, Dict

import pandas as pd

from core.base_pipeline import PipelineFatalError
from core.helpers.column_mapper import map_all_columns
from core.helpers.dq_logger import DQLogger
from core.helpers.header_helpers import (
    clean_column_name,
    promote_header_row,
    strip_df_string_values,
)
from core.helpers.pipeline_logger import PipelineLogger
from core.helpers.trim_helpers import identify_candidate_trim_columns, validate_trim_by_datatype


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

    IMPORTANT: _build_working_df() runs FIRST so all header validation uses cleaned columns,
    not raw text. This ensures step1 and step2 validate against the same column representations.
    """
    sheet_name = meta_data["sheet_name"]

    _extract_meta_data(df_raw, sheet_name, meta_data)

    # Build working_df FIRST (Part A, step 1 of plan) — now all validators use cleaned headers
    working_df = _build_working_df(df_raw)

    # Validate using cleaned headers
    _validate_header_keywords(working_df, sheet_name, config)
    _validate_trim_boundaries(working_df, sheet_name, config)

    working_df = _drop_brochure_records(working_df, config, pipeline_logger, sheet_name)
    working_df = _trim_to_data_range(working_df, config, pipeline_logger, sheet_name)

    working_df = _validate_non_null_columns(working_df, sheet_name, meta_data, config, dq_logger)
    _validate_data_types(working_df, sheet_name, config)
    _check_profitability(working_df, sheet_name, meta_data, dq_logger)

    # Standardize model_name as a real column from Step 1 onward (matching Hyundai)
    working_df["model_name"] = meta_data["model_name"]

    return working_df


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


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
    working_df: pd.DataFrame, sheet_name: str, config: dict
) -> None:
    """Validate that all required columns are detected in the working_df (cleaned headers)."""
    header_row = [str(v).lower() for v in working_df.columns]
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
    working_df: pd.DataFrame, sheet_name: str, config: dict
) -> None:
    """
    Validate that trim columns exist using content-based validation (Part A, step 4 of plan).
    Matches step2_header_normalization.py logic exactly for consistency.

    Process:
    1. Map all columns to canonical names
    2. Identify candidates: unmapped columns + exclusion filter
    3. If trim_validation_config defined: content-validate candidates
    4. Raise FATAL only if zero candidates pass
    """
    # Map columns to canonical names
    col_mapping = map_all_columns(working_df, config.get("column_definition", {}))

    # Identify candidates: unmapped columns, minus structural junk (exclusion keywords)
    exclusion_keywords = config.get("trim_exclusion_keywords", [])
    candidates = identify_candidate_trim_columns(col_mapping, exclusion_keywords)

    if not candidates:
        raise PipelineFatalError(
            f"Sheet '{sheet_name}': no trim column candidates found after keyword filtering"
        )

    # If trim_validation_config defined, validate candidates by data content
    if config.get("trim_validation_config"):
        valid_trim_cols, trim_log = validate_trim_by_datatype(
            working_df, candidates, config["trim_validation_config"]
        )
        if not valid_trim_cols:
            raise PipelineFatalError(
                f"Sheet '{sheet_name}': no trim columns passed content validation. "
                f"Candidates: {candidates}, validation results: {trim_log}"
            )
    # If no trim_validation_config, accept all candidates (defensive fallback)
    else:
        valid_trim_cols = candidates


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


def _trim_to_data_range(
    working_df: pd.DataFrame,
    config: dict,
    pipeline_logger: PipelineLogger,
    sheet_name: str,
) -> pd.DataFrame:
    """
    Remove tail rows (after last legit part record) by checking ALL required non-null columns.
    A row is "legitimate" only if it has part_number AND all other required fields populated.
    """
    df = working_df.copy()
    col_lower = {c.lower(): c for c in df.columns}

    # Map required non-null columns to their actual column names
    required_cols = config.get("non_null_columns", ["part_number"])
    actual_cols = {}

    for req_col in required_cols:
        actual_col = next(
            (orig for lower, orig in col_lower.items() if req_col in lower), None
        )
        if actual_col is None:
            pipeline_logger.debug(
                f"Sheet '{sheet_name}': required column '{req_col}' not found, skipping trim"
            )
            return df
        actual_cols[req_col] = actual_col

    # Build mask: row has ALL required fields non-null and non-empty
    legit_mask = pd.Series(True, index=df.index)
    for req_col, actual_col in actual_cols.items():
        col_mask = ~(df[actual_col].isna() | (df[actual_col].astype(str).str.strip() == ""))
        legit_mask = legit_mask & col_mask

    if not legit_mask.any():
        raise PipelineFatalError(f"Sheet '{sheet_name}': no records with all required fields found")

    first_idx = legit_mask.idxmax()
    last_idx = legit_mask[::-1].idxmax()

    # Slice to boundary range [first_idx : last_idx]
    df_bounded = df.loc[first_idx:last_idx].copy()
    n_tail = len(df) - (last_idx - first_idx + 1)

    # Within the bounded range, keep only rows with ALL required fields (exclude tail/partial rows)
    legit_in_range = pd.Series(True, index=df_bounded.index)
    for req_col, actual_col in actual_cols.items():
        col_mask = ~(df_bounded[actual_col].isna() | (df_bounded[actual_col].astype(str).str.strip() == ""))
        legit_in_range = legit_in_range & col_mask

    df_trimmed = df_bounded[legit_in_range].reset_index(drop=True)
    n_non_legit = len(df_bounded) - len(df_trimmed)

    pipeline_logger.info(
        f"Sheet '{sheet_name}': boundary rows [{first_idx}–{last_idx}], "
        f"dropped {n_tail} tail rows + {n_non_legit} incomplete rows within range"
    )

    return df_trimmed


def _drop_brochure_records(
    working_df: pd.DataFrame,
    config: dict,
    pipeline_logger: PipelineLogger,
    sheet_name: str,
) -> pd.DataFrame:
    """
    Remove brochure records: rows where Part Number matches YYYY*BROE/BROF pattern,
    Description contains 'BROCHURE' and language keyword, and pricing (MSRP/DNP) is null or N/A.
    """
    df = working_df.copy()
    col_lower = {c.lower(): c for c in df.columns}

    # Find required columns for brochure detection
    part_col = next(
        (orig for lower, orig in col_lower.items() if "part" in lower and "number" in lower), None
    )
    desc_col = next(
        (orig for lower, orig in col_lower.items() if "description" in lower and "english" in lower), None
    )
    msrp_col = next((orig for lower, orig in col_lower.items() if "msrp" in lower), None)
    dnp_col = next((orig for lower, orig in col_lower.items() if "dnp" in lower), None)

    # If any key column missing, skip brochure check
    if part_col is None or desc_col is None or msrp_col is None or dnp_col is None:
        pipeline_logger.debug(
            f"Sheet '{sheet_name}': brochure detection skipped (missing required columns)"
        )
        return df

    def is_null_or_na(val) -> bool:
        return pd.isna(val) or str(val).strip().upper() in ("N/A", "N\\A", "")

    def is_brochure(row) -> bool:
        # Condition 1: Part number matches YYYY*BROE or YYYY*BROF (case-insensitive)
        part = str(row[part_col]).strip()
        if not re.match(r"^\d{4}.*bro[ef]$", part, re.IGNORECASE):
            return False

        # Condition 2: Description contains "BROCHURE" and ("English" or "French")
        desc = str(row[desc_col]).strip().upper()
        if "BROCHURE" not in desc or not ("ENGLISH" in desc or "FRENCH" in desc):
            return False

        # Condition 3: Both MSRP and DNP are null or "N/A"
        if not (is_null_or_na(row[msrp_col]) and is_null_or_na(row[dnp_col])):
            return False

        return True

    brochure_mask = df.apply(is_brochure, axis=1)
    n_brochures = brochure_mask.sum()

    if n_brochures > 0:
        pipeline_logger.info(f"Sheet '{sheet_name}': dropped {n_brochures} brochure record(s)")

    return df[~brochure_mask].reset_index(drop=True)
