"""Step 2: Header Normalization

Extracts proper column names from the header row and applies them to the DataFrame.
Handles Honda's complex multi-level header structure with metadata rows.

Process:
1. Identify the header row (stored in metadata from Step 1)
2. Extract headers from that row
3. Rename all columns to those headers
4. Drop all rows before the header (metadata rows)
5. Return cleaned DataFrame with proper column names
"""

from typing import Tuple, Dict, Any
import pandas as pd


def normalize_headers(
    df: pd.DataFrame,
    metadata: Dict[str, Any],
    config: Dict[str, Any],
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Extract and apply proper column headers.

    Args:
        df: Raw DataFrame from Step 1 with numeric column indices and metadata rows
        metadata: Metadata from Step 1 (includes header_row_index)
        config: Pipeline configuration

    Returns:
        Tuple of (normalized_df, updated_metadata)
    """
    if df is None or df.empty:
        return df, metadata

    sheet_name = metadata.get("sheet_name", "unknown")
    header_row_idx = metadata.get("header_row_index")

    # If no header row was identified, try to infer it
    if header_row_idx is None:
        if "DATA" in sheet_name.upper():
            header_row_idx = 6  # Default for DATA sheets
        elif "APP" in sheet_name.upper():
            # For APP sheets, look for first row with many non-null values
            for idx in range(8, min(15, len(df))):
                row = df.iloc[idx]
                non_null_count = sum(1 for v in row if pd.notna(v))
                if non_null_count > 3:
                    header_row_idx = idx
                    break
        else:
            # Fallback: assume first row with data
            header_row_idx = 0

    # Extract headers from the identified row
    if header_row_idx is not None and header_row_idx < len(df):
        header_row = df.iloc[header_row_idx]

        # Convert headers to strings and clean them
        headers = []
        for col_val in header_row:
            if pd.isna(col_val):
                headers.append(None)
            else:
                # Clean header: strip whitespace, replace newlines
                header_str = str(col_val).strip().replace('\n', ' ').replace('\r', ' ')
                header_str = ' '.join(header_str.split())  # Normalize whitespace
                headers.append(header_str if header_str else None)

        # Create safe column names (replace None/NaN with placeholders)
        safe_headers = []
        for i, h in enumerate(headers):
            if h is None:
                safe_headers.append(f"_col_{i}")
            else:
                safe_headers.append(h)

        # Assign headers to DataFrame
        df.columns = safe_headers

        # Drop all rows up to and including the header row (metadata rows)
        df = df.iloc[header_row_idx + 1:].copy()

        # Reset index carefully to avoid duplicate column issues
        df.index = range(len(df))

        # Update metadata
        metadata["headers_extracted"] = True
        metadata["header_row_original_index"] = header_row_idx
        metadata["columns"] = safe_headers

        return df, metadata

    # If we couldn't find or extract headers, return as-is
    return df, metadata
