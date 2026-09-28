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
    """Transform or preserve data based on reconciliation mode.

    For flat data (reconciliation dataframes): Return as-is with section column
    For wide-format data (legacy): Transform to long format with melt

    Args:
        df: Standardized DataFrame from Step 3 (with proper column names)
        metadata: Metadata from Steps 1-3 (includes reconciliation_type)
        config: Pipeline configuration

    Returns:
        Tuple of (transformed_dict, updated_metadata, dq_warnings)
        transformed_dict: {"EN": df_flat_or_long, "FR": df_flat_or_long}
    """
    if df is None or df.empty:
        return {"EN": df, "FR": df}, metadata, []

    dq_warnings = []
    df = df.copy()

    # =========================================================================
    # CASE 1: Flat data from reconciliation (section-based sheets)
    # =========================================================================
    reconciliation_type = metadata.get("reconciliation_type", None)
    if reconciliation_type == "section_based":
        # Already has proper structure from reconciliation DF
        # No melt needed - output as-is for flat file
        metadata["transformation_type"] = "flat_preserve"
        metadata["flat_rows"] = len(df)

        return {"EN": df, "FR": df}, metadata, dq_warnings

    # Rename _section_name to section if present
    if "_section_name" in df.columns:
        df = df.rename(columns={"_section_name": "section"})

    # Try to use trim columns from metadata (Step 1), fallback to pattern matching
    trim_columns_per_section = metadata.get("trim_columns_per_section", {})

    # If we have section-based trim columns, use them
    if trim_columns_per_section:
        # Flatten all trim columns from all sections
        trim_cols = []
        for section_name, trims in trim_columns_per_section.items():
            trim_cols.extend(trims)
        trim_cols = list(set(trim_cols))  # Remove duplicates
    else:
        # Fallback: pattern-based detection
        product_col_patterns = [
            "part", "number", "description", "item", "name", "frt", "residual",
            "price", "installed", "net", "dealer", "list", "comments", "_col_",
            "sitecore", "overlay", "display", "order", "dependanc", "exclusion",
            "publication", "application", "_section_name", "section"
        ]
        product_cols = []
        trim_cols = []

        for col in df.columns:
            col_lower = str(col).lower()
            is_product = any(pattern in col_lower for pattern in product_col_patterns)
            if is_product:
                product_cols.append(col)
            else:
                trim_cols.append(col)

    # Define product columns (always include these)
    product_col_patterns = [
        "part", "number", "description", "item", "name", "frt", "residual",
        "price", "installed", "net", "dealer", "list", "comments", "_col_",
        "sitecore", "overlay", "display", "order", "dependanc", "exclusion",
        "publication", "application", "_section_name", "section"
    ]
    product_cols = []
    for col in df.columns:
        col_lower = str(col).lower()
        if any(pattern in col_lower for pattern in product_col_patterns) or col not in trim_cols:
            product_cols.append(col)

    # Filter product_cols to only those that exist in df
    product_cols = [c for c in product_cols if c in df.columns]
    trim_cols = [c for c in trim_cols if c in df.columns]

    # If we found trim columns, melt the data
    if trim_cols and product_cols:
        # Ensure section is in product_cols if it exists
        if "section" in df.columns and "section" not in product_cols:
            product_cols.append("section")

        # Melt: convert trim columns from wide to long format
        df_melted = pd.melt(
            df,
            id_vars=product_cols,
            value_vars=trim_cols,
            var_name="trim_level",
            value_name="applicability"
        )

        # Filter to only rows where applicability is not NaN/empty
        df_melted = df_melted.dropna(subset=["applicability"])
        df_melted = df_melted[df_melted["applicability"].astype(str).str.strip() != ""]

        # Drop the applicability column (we only need trim_level)
        df_melted = df_melted.drop(columns=["applicability"])

        # Filter out garbage rows
        if "Part Number" in df_melted.columns:
            part_nums = df_melted["Part Number"].astype(str)
            is_valid = (
                (part_nums.str.len() >= 2) &
                (part_nums.str.lower() != "part number") &
                (part_nums != "nan") &
                ~part_nums.str.match(r"^\d+$")
            )
            df_melted = df_melted[is_valid]

        # Reset index
        df_melted = df_melted.reset_index(drop=True)

        # Update metadata
        metadata["transformation_type"] = "melt"
        metadata["product_columns"] = product_cols
        metadata["trim_columns"] = trim_cols
        metadata["melted_shape"] = df_melted.shape

        # Reorder columns for flat output: section, part number, description, Cost, Hours, MSRP, comments, trim_level
        cols_ordered = []

        # 1. section (always first)
        if "section" in df_melted.columns:
            cols_ordered.append("section")

        # 2-7. Required product columns in order (case-insensitive match)
        col_map = {col.lower(): col for col in df_melted.columns}
        required_order = ["part number", "description", "cost", "hours", "msrp", "comments"]
        for req_col in required_order:
            if req_col in col_map:
                cols_ordered.append(col_map[req_col])

        # 8. trim_level (always last before remaining)
        if "trim_level" in df_melted.columns:
            cols_ordered.append("trim_level")

        # Add any remaining columns (except those already ordered)
        for col in df_melted.columns:
            if col not in cols_ordered:
                cols_ordered.append(col)

        # Select only columns that exist
        cols_ordered = [c for c in cols_ordered if c in df_melted.columns]
        df_melted = df_melted[cols_ordered]

        return {"EN": df_melted, "FR": df_melted}, metadata, dq_warnings
    else:
        # No trim columns found, just add a placeholder trim_level
        df["trim_level"] = "All"
        return {"EN": df, "FR": df}, metadata, dq_warnings
