"""Step 3: Data Standardization

Cleans and standardizes the data after header normalization.

Process:
1. Drop empty rows (all NaN)
2. Drop empty columns (all NaN)
3. Strip whitespace from string columns
4. Convert numeric columns to proper types
5. Prepare for transformation (Step 4)
"""

from typing import Tuple, Dict, Any, List
import pandas as pd


def standardize(
    df: pd.DataFrame,
    metadata: Dict[str, Any],
    config: Dict[str, Any],
) -> Tuple[pd.DataFrame, Dict[str, Any], List[Dict[str, Any]]]:
    """Standardize data types and clean values.

    Args:
        df: Normalized DataFrame from Step 2 (with proper column names)
        metadata: Metadata from Steps 1-2
        config: Pipeline configuration

    Returns:
        Tuple of (standardized_df, updated_metadata, dq_warnings)
    """
    if df is None or df.empty:
        return df, metadata, []

    df = df.copy()
    dq_warnings = []

    # Drop completely empty rows (all NaN)
    df = df.dropna(how='all')
    df = df.reset_index(drop=True)

    # Drop columns that are completely empty (all NaN)
    # This is important for Honda files which have NaN column headers as artifacts
    df = df.dropna(axis=1, how='all')

    # Rename NaN columns to avoid reindexing issues
    # Replace any remaining NaN column names with placeholder names
    new_columns = []
    for i, col in enumerate(df.columns):
        if pd.isna(col):
            new_columns.append(f"_unnamed_{i}")
        else:
            new_columns.append(col)
    df.columns = new_columns

    # Clean string columns: strip whitespace
    for col in df.columns:
        try:
            col_str = str(col)
            # Only process columns that aren't just placeholders and are object type
            if not col_str.startswith("_unnamed_") and df[col].dtype == 'object':
                df[col] = df[col].apply(
                    lambda x: str(x).strip() if pd.notna(x) and isinstance(x, str) else x
                )
        except Exception:
            pass  # Skip if error

    # Try to identify and convert numeric columns
    numeric_patterns = ["price", "frt", "residual", "cost", "installed", "dealer", "net"]
    for col in df.columns:
        col_str = str(col)
        if col_str.startswith("_unnamed_"):
            continue

        col_lower = col_str.lower()
        # If column name suggests it's numeric, try to convert
        if any(pattern in col_lower for pattern in numeric_patterns):
            try:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            except Exception:
                pass  # Keep as-is if conversion fails

    # Store column info in metadata
    metadata["standardized_columns"] = df.columns.tolist()
    metadata["standardized_shape"] = df.shape

    return df, metadata, dq_warnings
