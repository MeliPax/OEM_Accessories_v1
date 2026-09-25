"""Step 4: Transformation & Long-Format Conversion

Melts trim columns from wide to long format and creates trim_level column.

Process:
1. Identify which columns are "trim" columns (contain applicability markers like "Yes", "•")
2. Identify which columns are "product" columns (description, part number, etc.)
3. Melt trim columns to long format
4. Create trim_level column from melted column names
5. Return language-keyed dictionary (for EN/FR in later phases)
"""

from typing import Tuple, Dict, Any, List
import pandas as pd


def transform(
    df: pd.DataFrame,
    metadata: Dict[str, Any],
    config: Dict[str, Any],
) -> Tuple[Dict[str, pd.DataFrame], Dict[str, Any], List[Dict[str, Any]]]:
    """Transform wide-format data to long format with trim_level column.

    Args:
        df: Standardized DataFrame from Step 3 (with proper column names)
        metadata: Metadata from Steps 1-3
        config: Pipeline configuration

    Returns:
        Tuple of (transformed_dict, updated_metadata, dq_warnings)
        transformed_dict: {"EN": df_long, "FR": df_long} (for Phase 4 EN/FR split)
    """
    if df is None or df.empty:
        return {"EN": df, "FR": df}, metadata, []

    dq_warnings = []

    # Identify product columns (metadata/description columns)
    # Include patterns for all Honda product columns: part number, description, pricing, etc.
    product_col_patterns = [
        "part", "number", "description", "item", "name", "frt", "residual",
        "price", "installed", "net", "dealer", "list", "comments", "_col_"
    ]
    product_cols = []
    trim_cols = []

    for col in df.columns:
        col_lower = str(col).lower()

        # Check if this looks like a product column
        is_product = any(pattern in col_lower for pattern in product_col_patterns)

        if is_product:
            product_cols.append(col)
        else:
            # Assume it's a trim column if it's not a product column
            # (trim columns are typically model names like "Civic", "Accord", "CR-V", "SPORT", "Type R")
            trim_cols.append(col)

    # If we found trim columns, melt the data
    if trim_cols and product_cols:
        # Melt: convert trim columns from wide to long format
        df_melted = pd.melt(
            df,
            id_vars=product_cols,
            value_vars=trim_cols,
            var_name="trim_level",
            value_name="applicability"
        )

        # Filter to only rows where applicability is not NaN/empty
        # (applicability markers like "Yes", "•", etc.)
        df_melted = df_melted.dropna(subset=["applicability"])
        df_melted = df_melted[df_melted["applicability"].astype(str).str.strip() != ""]

        # Drop the applicability column (we only need trim_level)
        df_melted = df_melted.drop(columns=["applicability"])

        # Reset index
        df_melted = df_melted.reset_index(drop=True)

        # Update metadata
        metadata["transformation_type"] = "melt"
        metadata["product_columns"] = product_cols
        metadata["trim_columns"] = trim_cols
        metadata["melted_shape"] = df_melted.shape

        # Return as language-keyed dict (both EN and FR get same data for now)
        # In Phase 4, Step 4 will split this into actual EN/FR sheets
        return {"EN": df_melted, "FR": df_melted}, metadata, dq_warnings
    else:
        # No trim columns found, just add a placeholder trim_level
        df["trim_level"] = "All"
        return {"EN": df, "FR": df}, metadata, dq_warnings
