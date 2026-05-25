import re
from typing import List

import pandas as pd


def promote_header_row(df: pd.DataFrame) -> pd.DataFrame:
    """Drop row 0, promote row 1 as column headers. Returns a copy — never mutates input."""
    if df.shape[0] < 2:
        raise ValueError("DataFrame needs at least 2 rows for header promotion")
    new_header = df.iloc[1].astype(str).str.strip()
    result = df.iloc[2:].reset_index(drop=True).copy()
    result.columns = new_header
    return result


def clean_column_name(name: str) -> str:
    """Normalize a column name: collapse hyphen spacing, collapse spaces, replace spaces with underscores."""
    if not isinstance(name, str):
        return str(name)
    cleaned = re.sub(r"\s*-\s*", "-", name)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip().replace(" ", "_")


def lowercase_columns(col_list: List[str]) -> List[str]:
    """Return a new list with each string lowercased, preserving order."""
    return [c.lower() for c in col_list]


def strip_df_string_values(df: pd.DataFrame) -> pd.DataFrame:
    """Strip leading/trailing whitespace from all string cells. Returns a copy."""
    df = df.copy()
    for col in df.select_dtypes(include=["object", "string"]):
        df[col] = df[col].apply(lambda v: v.strip() if isinstance(v, str) else v)
    return df
