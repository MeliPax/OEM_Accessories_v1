"""Step 2: Header Normalization (Section-Aware)

Extracts proper column names from each section's header row and applies them.
Processes each section independently, then concatenates all sections.

Process:
1. For each section (from metadata.section_structure):
   a. Extract header row at (data_start - 1)
   b. Extract data rows from data_start to data_end
   c. Rename columns using header
   d. Keep only data rows (drop header row)
2. Concatenate all normalized sections
3. Return cleaned DataFrame with proper column names
"""

from typing import Tuple, Dict, Any, List
import pandas as pd


def _extract_headers_from_row(header_row: pd.Series) -> List[str]:
    """Clean header values and convert to safe column names."""
    headers = []
    for col_val in header_row:
        if pd.isna(col_val):
            headers.append(None)
        else:
            header_str = str(col_val).strip().replace('\n', ' ').replace('\r', ' ')
            header_str = ' '.join(header_str.split())
            headers.append(header_str if header_str else None)

    safe_headers = []
    for i, h in enumerate(headers):
        if h is None or h == "nan":
            safe_headers.append(f"_col_{i}")
        else:
            safe_headers.append(h)

    return safe_headers


def normalize_headers(
    df: pd.DataFrame,
    metadata: Dict[str, Any],
    config: Dict[str, Any] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Extract headers for each section and build reconciliation dataframe.

    For section-based sheets (_APP_EN): extract headers per section, collect all data.
    For flat data sheets (_DATA): use row 0 as headers.

    Args:
        df: Raw DataFrame from Step 1
        metadata: Metadata from Step 1 (includes section_structure)
        config: Pipeline configuration (optional)

    Returns:
        Tuple of (reconciliation_df, updated_metadata)
        reconciliation_df: Combined dataframe with all sections, proper headers, _section_name column
    """
    if df is None or df.empty:
        return df, metadata

    section_structure = metadata.get("section_structure", {})

    # Case 1: Section-based sheet (_APP_EN/_APP_FR with "1.0 Packages" markers)
    if section_structure:
        # Process each section independently
        normalized_sections = []

        for section_name, boundaries in section_structure.items():
            data_start = boundaries.get("data_start")
            data_end = boundaries.get("data_end")

            if data_start is None or data_end is None:
                continue

            # Header row IS the first row of the data section (at data_start)
            header_row_idx = data_start

            if header_row_idx < 0 or header_row_idx >= len(df):
                continue

            # Extract header from first row of section
            header_row = df.iloc[header_row_idx]
            safe_headers = _extract_headers_from_row(header_row)

            # Extract data rows for this section (skip header row at data_start)
            section_df = df.iloc[data_start+1:data_end+1].copy()

            # Apply headers
            section_df.columns = safe_headers
            section_df.index = range(len(section_df))

            # Add section name for traceability (will be used in Step 4)
            section_df["_section_name"] = section_name

            normalized_sections.append(section_df)

        # Concatenate all sections
        if normalized_sections:
            df_normalized = pd.concat(normalized_sections, ignore_index=True, sort=False)

            # Update metadata
            metadata["headers_extracted"] = True
            metadata["sections_normalized"] = len(normalized_sections)
            metadata["columns"] = list(df_normalized.columns)

            return df_normalized, metadata

    # Case 2: Flat data sheet (LoadFile sheets without section markers)
    # Use row 0 as headers, skip it from data
    if len(df) > 0:
        header_row = df.iloc[0]
        safe_headers = _extract_headers_from_row(header_row)

        # Extract data rows (skip header row 0)
        df_normalized = df.iloc[1:].copy()
        df_normalized.columns = safe_headers
        df_normalized.index = range(len(df_normalized))

        # Add section name for flat data
        df_normalized["_section_name"] = "flat_data"

        # Update metadata
        metadata["headers_extracted"] = True
        metadata["sections_normalized"] = 1
        metadata["columns"] = list(df_normalized.columns)
        metadata["header_source"] = "row_0"

        return df_normalized, metadata

    return df, metadata
