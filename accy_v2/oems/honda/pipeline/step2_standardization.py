"""Step 2: Data Standardization & Reconciliation

Standardizes validated Honda data and reconciles EN/FR sheets.

Part 7: Header Normalization & Section Extraction
  - Extract clean data from each section using boundaries from Step 1
  - Normalize headers to canonical names
  - Handle sparse Excel (headers in data rows)
  - Build per-section DataFrames

Part 8: Data Standardization & Packages Rollup
  - Clean data (trim, type coerce, deduplicate)
  - Detect parent-child relationships (packages only)
  - Aggregate children into parents
  - Track rollup metadata

Part 9: EN/FR Reconciliation
  - Build reconciliation map (EN ↔ FR matching)
  - Matching strategy: part number → description → cost
  - Track divergence (cost, part count, trims)
  - Confidence scoring
"""

from pathlib import Path
from typing import Tuple, Dict, Any, Optional, List
import re
import logging

import pandas as pd
import numpy as np
import yaml


logger = logging.getLogger(__name__)


class StandardizationError(Exception):
    """Raised when standardization errors occur."""
    pass


# ============================================================================
# PART 7: Header Normalization & Section Extraction
# ============================================================================

def _normalize_headers(
    en_df: pd.DataFrame,
    fr_df: Optional[pd.DataFrame],
    metadata: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Extract and normalize section headers.

    Part 7: For each section, extract clean data using boundaries from Step 1,
    normalize column headers to canonical names, and handle sparse Excel.

    Args:
        en_df: English DataFrame from Step 1
        fr_df: French DataFrame from Step 1 (may be None or empty)
        metadata: Step 1 metadata (contains section_structure, column_mappings)
        config: Pipeline configuration (for column mappings)

    Returns:
        Dict with structure:
        {
            "packages": {"en_df": ..., "fr_df": ..., "trim_columns": [...]},
            "wheels": {...},
            # ... (6 sections total)
            "warnings": [...]
        }

    Raises:
        StandardizationError: If critical section data is missing
    """
    section_data = {}
    warnings = []

    # Get section structure from metadata (output from Step 1)
    section_structure = metadata.get("section_structure", {})
    trim_columns_per_section = metadata.get("trim_columns_per_section", {})

    # Get column mappings
    en_mappings = config.get("en_mappings", {})
    fr_mappings = config.get("fr_mappings", {})

    # Expected sections (from Step 1)
    expected_sections = metadata.get("section_order", [
        "packages", "wheels", "exterior", "interior", "electrical", "paint_pens"
    ])

    for section_name in expected_sections:
        section_info = section_structure.get(section_name, {})

        # Get section boundaries
        en_row = section_info.get("en_row")
        fr_row = section_info.get("fr_row")

        # Part 7.1: Extract EN section
        en_section_df = None
        if en_row is not None:
            en_section_df = _extract_section(
                en_df,
                en_row,
                section_name,
                en_mappings,
                config
            )

        # Part 7.2: Extract FR section
        fr_section_df = None
        if fr_df is not None and not fr_df.empty and fr_row is not None:
            fr_section_df = _extract_section(
                fr_df,
                fr_row,
                section_name,
                fr_mappings,
                config
            )
        else:
            if en_section_df is not None:
                warnings.append({
                    "section": section_name,
                    "severity": "WARNING",
                    "message": f"FR sheet missing or section not found; proceeding with EN only"
                })

        # Part 7.3: Get trim columns for this section
        section_trim_columns = trim_columns_per_section.get(section_name, [])

        # Part 7.4: Build section output
        if en_section_df is not None:
            section_data[section_name] = {
                "en_df": en_section_df,
                "fr_df": fr_section_df,
                "trim_columns": section_trim_columns,
            }
        else:
            warnings.append({
                "section": section_name,
                "severity": "ERROR",
                "message": f"EN sheet missing section; skipping"
            })

    return {
        "section_data": section_data,
        "warnings": warnings,
    }


def _extract_section(
    df: pd.DataFrame,
    section_row: int,
    section_name: str,
    column_mappings: Dict[str, str],
    config: Dict[str, Any],
) -> Optional[pd.DataFrame]:
    """Extract and normalize a single section from raw DataFrame.

    Handles edge cases:
    - section_row == 0: Headers are in df.columns, use df.iloc[0] as first data row
    - section_row > 0: Headers are in df.iloc[section_row], data starts below
    - Sparse Excel: Handle NaN, empty strings, "nan" strings

    Args:
        df: Raw DataFrame (EN or FR)
        section_row: Row index where section header/data begins
        section_name: Name of section (for logging)
        column_mappings: {original_name: canonical_name} mappings
        config: Pipeline config (for type coercion, cleaning rules)

    Returns:
        Cleaned DataFrame with canonical column names, or None if extraction fails
    """
    if df is None or df.empty:
        return None

    if section_row < 0 or section_row >= len(df):
        logger.warning(f"Section {section_name}: row {section_row} out of bounds")
        return None

    try:
        # Part 7.1: Extract section rows
        if section_row == 0:
            # Headers are in df.columns; use entire df
            section_df = df.copy()
            # First row (iloc[0]) becomes our explicit header row
            # We'll use it to validate/normalize column names
            header_row = section_df.iloc[0]
            data_start = 1
        else:
            # Headers are at section_row; data starts at section_row + 1
            header_row = df.iloc[section_row]
            data_start = section_row + 1

            # Extract from data_start to end (or next section)
            # For now, assume data goes to end of df; step1_validation.py handles sections
            section_df = df.iloc[data_start:].copy()

        # Part 7.2: Normalize headers to canonical names
        # Build mapping: current column name → canonical name
        normalized_headers = {}

        for orig_col in section_df.columns:
            # Look up mapping
            canonical = column_mappings.get(orig_col)
            if canonical:
                normalized_headers[orig_col] = canonical
            else:
                # Keep original if no mapping found (shouldn't happen if config is good)
                normalized_headers[orig_col] = orig_col.lower().replace(" ", "_")

        section_df = section_df.rename(columns=normalized_headers)

        # Part 7.3: Clean data
        section_df = _clean_section_data(section_df, config)

        return section_df

    except Exception as e:
        logger.error(f"Section {section_name}: extraction failed: {e}")
        return None


def _clean_section_data(df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
    """Clean section data: trim whitespace, handle nulls, type coerce.

    Args:
        df: Section DataFrame with canonical column names
        config: Pipeline configuration

    Returns:
        Cleaned DataFrame
    """
    df = df.copy()

    # Get cleaning config
    strip_whitespace = config.get("strip_whitespace", True)

    # Trim whitespace and handle nulls from all string columns
    if strip_whitespace:
        for col in df.columns:
            col_dtype = str(df[col].dtype)
            # Check for object, str, string, or StringDtype
            if col_dtype in ("object", "str", "string") or col_dtype.startswith("string"):
                # Strip, convert empty/nan to None
                df[col] = df[col].apply(
                    lambda x: (
                        None if x is None or pd.isna(x) or x == "" or x == "nan"
                        else (x.strip() if isinstance(x, str) else x)
                    )
                )

    # Handle numeric columns - replace NaN with None
    for col in df.columns:
        if df[col].dtype in ("float64", "float32", "float"):
            df[col] = df[col].where(pd.notna(df[col]), None)

    return df


# ============================================================================
# PART 8: Data Standardization & Packages Rollup (Stub)
# ============================================================================

def _standardize_data(
    section_data: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Standardize data and detect parent-child relationships.

    Part 8: Clean data, detect parent-child (packages only), aggregate.

    This is a stub for Part 8 implementation.

    Args:
        section_data: Section data from Part 7
        config: Pipeline configuration

    Returns:
        Dict with standardized data and rollup metadata
    """
    # TODO: Implement Part 8
    # - Data cleanup (type coercion, deduplication, sorting)
    # - Parent-child detection (packages section only)
    # - Rollup aggregation (children → parent)
    # - Rollup metadata tracking
    return {
        "standardized_data": section_data,
        "rollup_metadata": {},
        "warnings": [],
    }


# ============================================================================
# PART 9: EN/FR Reconciliation (Stub)
# ============================================================================

def _reconcile_en_fr(
    standardized_data: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Reconcile EN and FR sheets.

    Part 9: Build reconciliation map, match parts, track divergence.

    This is a stub for Part 9 implementation.

    Args:
        standardized_data: Standardized data from Part 8
        config: Pipeline configuration

    Returns:
        Dict with unified data, reconciliation map, and divergence report
    """
    # TODO: Implement Part 9
    # - Build reconciliation map (EN ↔ FR matching)
    # - Matching strategy: part number → description → cost
    # - Divergence tracking (cost, part count, trims)
    # - Confidence scoring
    return {
        "unified_data": standardized_data,
        "reconciliation_map": {},
        "divergence_report": [],
        "warnings": [],
    }


# ============================================================================
# Main Orchestrator
# ============================================================================

def standardize_and_reconcile(
    en_df: pd.DataFrame,
    fr_df: Optional[pd.DataFrame],
    metadata: Dict[str, Any],
    config: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
    """Orchestrate Steps 2.1-2.3: standardization and reconciliation.

    Args:
        en_df: English DataFrame from Step 1
        fr_df: French DataFrame from Step 1
        metadata: Step 1 metadata
        config: Pipeline configuration (must include column_mappings)

    Returns:
        Tuple of:
        - unified_data: Clean, reconciled data ready for model lookup
        - reconciliation_map: EN/FR matching details
        - warnings: List of DQ warnings

    Raises:
        StandardizationError: If critical processing fails
    """
    all_warnings = []

    # Part 7: Header Normalization & Section Extraction
    logger.info("Step 2: Part 7 - Header normalization & section extraction")
    part7_result = _normalize_headers(en_df, fr_df, metadata, config)
    section_data = part7_result.get("section_data", {})
    all_warnings.extend(part7_result.get("warnings", []))

    if not section_data:
        raise StandardizationError("Part 7: No section data extracted")

    # Part 8: Data Standardization & Rollup
    logger.info("Step 2: Part 8 - Data standardization & packages rollup")
    part8_result = _standardize_data(section_data, config)
    standardized_data = part8_result.get("standardized_data", {})
    all_warnings.extend(part8_result.get("warnings", []))

    # Part 9: EN/FR Reconciliation
    logger.info("Step 2: Part 9 - EN/FR reconciliation")
    part9_result = _reconcile_en_fr(standardized_data, config)
    unified_data = part9_result.get("unified_data", {})
    reconciliation_map = part9_result.get("reconciliation_map", {})
    all_warnings.extend(part9_result.get("warnings", []))

    return unified_data, reconciliation_map, all_warnings
