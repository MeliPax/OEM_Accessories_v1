"""Orphaned record validator — safety net for rows with missing model numbers at output stage."""

import pandas as pd


def flag_orphaned_records(df, dq_logger, sheet_name, model_number_column="Model"):
    """
    Flag any row with null/empty model number as orphaned.

    Called at output stage after column mapping, as independent checkpoint:
    catches any record whose failure wasn't logged upstream (code gap, edge case, etc.).

    Args:
        df: DataFrame with output columns
        dq_logger: DQLogger instance to log warnings
        sheet_name: Sheet/language variant name for logging
        model_number_column: Column name to check (usually "Model")

    Returns:
        df unchanged (logging is side-effect only)
    """
    if dq_logger is None:
        return df

    for idx, row in df.iterrows():
        model_num = row.get(model_number_column)
        # Check for .isna() (null) AND empty strings/literal "nan" (matters for Mazda's derived short_model_number)
        if pd.isna(model_num) or (isinstance(model_num, str) and model_num.strip() in ("", "nan")):
            dq_logger.log_warning(
                sheet_name=sheet_name,
                model_name=row.get("ModelName"),
                record_index=idx,
                record_snapshot={col: row.get(col) for col in ["ModelName", "TrimName", "Description", model_number_column]},
                rule_violated="orphaned_record_rule",
                issue_description=f"Row reached output stage with null/empty {model_number_column} (indicates upstream model lookup or enrichment failure)",
            )

    return df
