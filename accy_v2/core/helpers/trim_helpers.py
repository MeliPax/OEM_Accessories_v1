from typing import Dict, List, Tuple

import pandas as pd


def identify_trim_candidates(df: pd.DataFrame, trim_bounds_config: dict) -> List[str]:
    """
    Return columns strictly between the left and right boundary columns.
    Matching against column names is case-insensitive.
    Raises ValueError if either boundary cannot be located.
    """
    cols_lower = [str(c).lower() for c in df.columns]
    cols_original = list(df.columns)

    def find_bound_index(bound_cfg: dict, side: str) -> int:
        must_contain = [k.lower() for k in bound_cfg.get("must_contain", [])]
        must_contain_one_of = [k.lower() for k in bound_cfg.get("must_contain_one_of", [])]

        for i, col in enumerate(cols_lower):
            mc_ok = all(k in col for k in must_contain)
            mco_ok = (not must_contain_one_of) or any(k in col for k in must_contain_one_of)
            if mc_ok and mco_ok:
                return i

        raise ValueError(f"Trim {side} boundary column not found. Config: {bound_cfg}")

    left_idx = find_bound_index(trim_bounds_config["left_bound"], "left")
    right_idx = find_bound_index(trim_bounds_config["right_bound"], "right")

    if left_idx >= right_idx:
        raise ValueError(
            f"Trim boundaries invalid: left_idx ({left_idx}) >= right_idx ({right_idx})"
        )

    return cols_original[left_idx + 1: right_idx]


def validate_trim_by_datatype(
    df: pd.DataFrame,
    candidates: List[str],
    trim_validation_config: dict,
) -> Tuple[List[str], Dict]:
    """
    Validate each candidate column against the trim_validation_config rules.
    "__na__" in expected_value_types resolves to pd.isna(). All string comparisons are case-insensitive.
    Returns (passed_cols_list, full_results_dict).
    """
    expected_data = trim_validation_config["expected_data"]["data"].lower()
    perc_thresh = trim_validation_config["expected_data"]["perc_thresh"]
    allowed_types = trim_validation_config["must_have_only"]["expected_value_types"]
    allowed_lower = [t.lower() for t in allowed_types if t != "__na__"]
    na_allowed = "__na__" in allowed_types

    passed = []
    results = {}

    for col in candidates:
        series = df[col]
        unique_vals = [str(v) for v in series.unique().tolist()]

        def is_allowed(val) -> bool:
            if pd.isna(val):
                return na_allowed
            return str(val).lower() in allowed_lower

        all_allowed = series.apply(is_allowed).all()

        total = len(series)
        match_count = series.apply(
            lambda v: not pd.isna(v) and str(v).lower() == expected_data
        ).sum()
        rate = round(match_count / total * 100, 2) if total > 0 else 0.0

        passed_check = all_allowed and rate >= perc_thresh
        results[col] = {
            "result": "pass" if passed_check else "fail",
            "expected_data_rate": rate,
            "unique_col_data": unique_vals,
        }

        if passed_check:
            passed.append(col)

    return passed, results
