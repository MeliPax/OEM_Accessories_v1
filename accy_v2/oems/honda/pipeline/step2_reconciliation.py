"""Step 2: Header Normalization via Reconciliation DataFrame

Build a single reconciliation dataframe with all sections combined.

For each section:
1. Extract header row (first row of section)
2. Extract data rows (remaining rows in section)
3. Apply headers to data
4. Add section_name column
5. Append to reconciliation dataframe

Result: Single flat dataframe with all sections, proper column names, and traceability.
"""

from typing import Tuple, Dict, Any, List
import pandas as pd
import re


def build_reconciliation_dataframe(
    df: pd.DataFrame,
    metadata: Dict[str, Any],
    config: Dict[str, Any] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Build reconciliation dataframe by iterating through all sections.

    For section-based sheets: Extract headers per section, combine all sections.
    For flat data sheets: Use row 0 as headers.

    Args:
        df: Raw DataFrame from Step 1 (header=None, all rows as data)
        metadata: Metadata from Step 1 (includes section_structure)
        config: Pipeline configuration (optional)

    Returns:
        Tuple of (reconciliation_df, updated_metadata)
        reconciliation_df: Combined dataframe with all sections properly named
    """
    if df is None or df.empty:
        return df, metadata

    section_structure = metadata.get("section_structure", {})

    # =========================================================================
    # CASE 1: Section-based sheet (_APP_EN/_APP_FR with section markers)
    # =========================================================================
    if section_structure and len(section_structure) > 0:
        reconciliation_rows = []

        # Find the first section marker row to exclude pre-section metadata
        first_section_marker_row = min(bounds.get("marker_row", float('inf'))
                                       for bounds in section_structure.values())

        # Iterate through each section (sorted by marker row)
        for section_name, bounds in sorted(section_structure.items(),
                                           key=lambda x: x[1].get("marker_row", 0)):
            data_start = bounds.get("data_start")
            data_end = bounds.get("data_end")

            if data_start is None or data_end is None:
                continue

            # Extract header row (first row of this section)
            header_row_idx = data_start
            if header_row_idx < 0 or header_row_idx >= len(df):
                continue

            header_row = df.iloc[header_row_idx]

            # Build safe header names
            headers = []
            for i, col_val in enumerate(header_row):
                if pd.isna(col_val):
                    headers.append(f"_col_{i}")
                else:
                    header_str = str(col_val).strip().replace('\n', ' ').replace('\r', ' ')
                    header_str = ' '.join(header_str.split())
                    if header_str and header_str.lower() != "nan":
                        headers.append(header_str)
                    else:
                        headers.append(f"_col_{i}")

            # Extract data rows for this section
            # Skip both header row (data_start) and trim sub-header row (data_start + 1)
            section_df = df.iloc[data_start + 2 : data_end + 1].copy()

            if len(section_df) == 0:
                # No data rows in this section
                continue

            # Apply headers
            section_df.columns = headers

            # Add section column for traceability
            section_df.insert(0, "section", section_name)

            # Add to reconciliation rows
            reconciliation_rows.append(section_df)

        # Combine all sections into single reconciliation dataframe
        if reconciliation_rows:
            reconciliation_df = pd.concat(
                reconciliation_rows, ignore_index=True, sort=False
            )

            # Update metadata
            metadata["reconciliation_type"] = "section_based"
            metadata["sections_combined"] = len(reconciliation_rows)
            metadata["headers_extracted"] = True
            metadata["columns"] = list(reconciliation_df.columns)
            metadata["total_reconciliation_rows"] = len(reconciliation_df)

            return reconciliation_df, metadata

    # =========================================================================
    # CASE 2: Flat data sheet (_DATA without section markers)
    # =========================================================================
    if len(df) > 0:
        # Use row 0 as headers
        header_row = df.iloc[0]

        # Build safe header names
        headers = []
        for i, col_val in enumerate(header_row):
            if pd.isna(col_val):
                headers.append(f"_col_{i}")
            else:
                header_str = str(col_val).strip().replace('\n', ' ').replace('\r', ' ')
                header_str = ' '.join(header_str.split())
                if header_str and header_str.lower() != "nan":
                    headers.append(header_str)
                else:
                    headers.append(f"_col_{i}")

        # Extract data rows (skip header row 0)
        reconciliation_df = df.iloc[1:].copy()
        reconciliation_df.columns = headers

        # Add section column for flat data
        reconciliation_df.insert(0, "section", "data")

        # Update metadata
        metadata["reconciliation_type"] = "flat_data"
        metadata["sections_combined"] = 1
        metadata["headers_extracted"] = True
        metadata["columns"] = list(reconciliation_df.columns)
        metadata["header_source"] = "row_0"
        metadata["total_reconciliation_rows"] = len(reconciliation_df)

        return reconciliation_df, metadata

    return df, metadata
