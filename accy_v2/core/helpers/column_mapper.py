from typing import Dict, List, Optional

import pandas as pd


def column_type_finder(
    col_name: str, column_definition: dict
) -> Dict[str, Optional[str]]:
    """
    Match col_name against column_definition rules using word-token matching.
    Column name is split by "_" into tokens; keywords must match whole tokens, not substrings.
    Rules applied in sequence: not_have -> must_have -> must_have_one_of.
    All matching is case-insensitive.
    Returns {"original": "mapped_name"} or {"original": None}.
    """
    tokens = set(col_name.lower().split("_"))

    for mapped_name, spec in column_definition.items():
        kw = spec["key_words"]
        not_have = [k.lower() for k in kw.get("not_have", [])]
        must_have = [k.lower() for k in kw.get("must_have", [])]
        must_have_one_of = [k.lower() for k in kw.get("must_have_one_of", [])]

        if any(k in tokens for k in not_have):
            continue
        if not all(k in tokens for k in must_have):
            continue
        if must_have_one_of and not any(k in tokens for k in must_have_one_of):
            continue

        return {col_name: mapped_name}

    return {col_name: None}


def map_all_columns(
    df: pd.DataFrame, column_definition: dict
) -> Dict[str, Optional[str]]:
    """Map every column in df against the column_definition. Returns {original: mapped | None}."""
    result = {}
    for col in df.columns:
        result.update(column_type_finder(str(col), column_definition))
    return result


def assert_required_columns(
    col_mapping: Dict[str, Optional[str]], required_cols: List[str]
) -> None:
    """Raise ValueError if any required standard column has no match in col_mapping."""
    mapped_values = {v for v in col_mapping.values() if v is not None}
    missing = [col for col in required_cols if col not in mapped_values]
    if missing:
        unmapped_originals = [
            orig for orig, mapped in col_mapping.items() if mapped is None
        ]
        raise ValueError(
            f"Required columns not found after mapping: {missing}. "
            f"Unrecognized source columns: {unmapped_originals}"
        )
