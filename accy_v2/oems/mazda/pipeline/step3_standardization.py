import re
from typing import Any, Dict

import pandas as pd

from core.helpers.dq_logger import DQLogger
from core.helpers.pipeline_logger import PipelineLogger


def run(
    working_df: pd.DataFrame,
    step2_result: Dict,
    config: dict,
    meta_data: Dict[str, Any],
    dq_logger: DQLogger,
    pipeline_logger: PipelineLogger,
) -> pd.DataFrame:
    """
    Apply column mapping, enforce data types, extract package and short_model_number from model_number.
    Mazda-specific: TrimLevel (10 chars) = 6-char short code + 4-char package code (e.g., SVSL86 + AA00).
    Validates package format (2 letters + 2 digits) and logs DQ warnings for failures.
    """
    df = working_df.copy()
    sheet_name = meta_data["sheet_name"]
    model_name = meta_data.get("model_name", "unknown")
    col_mapping = step2_result["col_mapping"]

    # 1. Rename columns using col_mapping
    rename_map = {orig: std for orig, std in col_mapping.items() if std is not None}
    df = df.rename(columns=rename_map)

    # 2. Enforce data types
    for col in config["col_data_type_dict"].get("to_float", []):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        for col in config["col_data_type_dict"].get("to_string", []):
            if col in df.columns:
                df[col] = df[col].astype(str)

    # 3. Extract package and short_model_number from model_number (TrimLevel)
    df["package"] = df["model_number"].astype(str).str[-4:]
    df["short_model_number"] = df["model_number"].astype(str).str[:-4]

    # 4. Validate package format and exclude invalid rows
    pattern = config.get("package_validation", {}).get("pattern", r"^[A-Za-z]{2}[0-9]{2}$")
    df["_package_valid"] = df["package"].apply(
        lambda p: bool(re.match(pattern, p, re.IGNORECASE))
    )

    for idx, row in df[~df["_package_valid"]].iterrows():
        dq_logger.log_warning(
            sheet_name=sheet_name,
            model_name=model_name,
            record_index=int(idx),
            record_snapshot=row.to_dict(),
            rule_violated="invalid_package_format",
            issue_description=f"Package '{row['package']}' does not match expected format (2 letters + 2 digits) — record excluded",
        )

    df = df[df["_package_valid"]].reset_index(drop=True)
    df = df.drop(columns=["_package_valid"])

    return df
