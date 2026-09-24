"""Section Structure Validation Utility

Validates Honda section structure (boundaries, headers, order) for data quality.

Example:
  Honda files have 6 mandatory sections in order. This utility verifies structure.
"""

from typing import Dict, List, Tuple, Any, Optional

import pandas as pd


def validate_section_structure(
    df: pd.DataFrame,
    section_config: Dict[str, Any],
    sheet_name: str = "Sheet1"
) -> Dict[str, Any]:
    """Validate section structure (boundaries, headers, count, order).

    Args:
        df: DataFrame with raw sheet data (may have merged cells, headers, etc.)
        section_config: Config dict with section_patterns and validation rules
                       Expected keys: 'sections', 'section_order', 'validation'
        sheet_name: Sheet name (for error reporting)

    Returns:
        Dict with:
          - 'valid' (bool): Whether structure is valid
          - 'errors' (list): List of validation error messages
          - 'warnings' (list): List of validation warning messages
          - 'section_boundaries' (list): List of (start_row, end_row) tuples
          - 'sections_found' (list): List of section names found (in order)

    Examples:
        >>> result = validate_section_structure(df, config)
        >>> if result['valid']:
        ...     boundaries = result['section_boundaries']
        ...     # Use boundaries to extract sections
        ... else:
        ...     print(f"Validation errors: {result['errors']}")
    """
    errors = []
    warnings = []
    section_boundaries = []
    sections_found = []

    # Extract config
    sections_config = section_config.get("sections", {})
    section_order = section_config.get("section_order", [])
    validation_rules = section_config.get("validation", {})

    require_all_sections = validation_rules.get("require_all_sections", True)
    enforce_section_order = validation_rules.get("enforce_section_order", True)

    # Scan DataFrame rows for section headers
    found_sections = {}  # section_name -> row_index

    for idx, row in df.iterrows():
        # Convert row to string for searching
        row_str = " ".join(
            str(val).strip()
            for val in row.values
            if pd.notna(val)
        ).lower()

        # Check each section pattern
        for section_name, section_pattern in sections_config.items():
            if "en" in section_pattern:
                pattern_text = section_pattern["en"].lower()
                if pattern_text in row_str:
                    found_sections[section_name] = idx
                    sections_found.append(section_name)

    # Validation 1: Check if all required sections found
    if require_all_sections:
        missing_sections = set(section_order) - set(sections_found)
        if missing_sections:
            for section in missing_sections:
                errors.append(
                    f"Required section '{section}' not found in {sheet_name}"
                )

    # Validation 2: Check section order
    if enforce_section_order and sections_found:
        expected_order = [s for s in section_order if s in sections_found]
        if sections_found != expected_order:
            warnings.append(
                f"Sections out of order in {sheet_name}: "
                f"found {sections_found}, expected {expected_order}"
            )

    # Validation 3: Check section count
    expected_count = len(section_order)
    actual_count = len(sections_found)
    if actual_count != expected_count and require_all_sections:
        warnings.append(
            f"Expected {expected_count} sections in {sheet_name}, found {actual_count}"
        )

    # Calculate section boundaries (row ranges)
    if sections_found:
        section_rows = [found_sections.get(s) for s in sections_found
                       if s in found_sections]
        section_rows.sort()

        for i, start_row in enumerate(section_rows):
            if i + 1 < len(section_rows):
                end_row = section_rows[i + 1] - 1
            else:
                end_row = len(df) - 1
            section_boundaries.append((start_row, end_row))

    # Determine overall validity
    valid = len(errors) == 0

    return {
        "valid": valid,
        "errors": errors,
        "warnings": warnings,
        "section_boundaries": section_boundaries,
        "sections_found": sections_found,
        "sheet_name": sheet_name,
    }


def extract_section_data(
    df: pd.DataFrame,
    section_boundary: Tuple[int, int]
) -> pd.DataFrame:
    """Extract data for a single section using row boundaries.

    Args:
        df: Full DataFrame
        section_boundary: Tuple of (start_row, end_row)

    Returns:
        DataFrame containing only rows in section boundary
    """
    start_row, end_row = section_boundary
    return df.iloc[start_row:end_row + 1].copy()
