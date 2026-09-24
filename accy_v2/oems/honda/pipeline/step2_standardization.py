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
# PART 8: Data Standardization & Packages Rollup
# ============================================================================

def _cleanup_section_data(df: pd.DataFrame, section_name: str, config: Dict[str, Any]) -> pd.DataFrame:
    """Cleanup: trim, type coerce, deduplicate, sort.

    Step 8.1: For each section, standardize data types and remove duplicates.

    Args:
        df: Section DataFrame with canonical column names
        section_name: Section name (for logging)
        config: Pipeline configuration

    Returns:
        Cleaned DataFrame
    """
    if df is None or df.empty:
        return df

    df = df.copy()

    # Drop rows where all values are null
    df = df.dropna(how="all")

    # Type coercion: standardize known column types
    type_mappings = {
        "description": "string",
        "part_number": "string",
        "dealer_net": "float",
        "list_price": "float",
        "frt": "float",
        "installed_price": "float",
    }

    for col, dtype in type_mappings.items():
        if col in df.columns:
            if dtype == "string":
                df[col] = df[col].astype("string", errors="ignore")
            elif dtype == "float":
                try:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                except Exception:
                    pass

    # Title case for descriptions
    if "description" in df.columns:
        df["description"] = df["description"].apply(
            lambda x: x.title() if isinstance(x, str) and x else x
        )

    # Uppercase for part numbers
    if "part_number" in df.columns:
        df["part_number"] = df["part_number"].apply(
            lambda x: x.upper() if isinstance(x, str) and x else x
        )

    # Deduplicate: remove exact duplicates (same values across all columns)
    df = df.drop_duplicates(subset=None, keep="first")

    # Sort by description, then part number
    sort_cols = []
    if "description" in df.columns:
        sort_cols.append("description")
    if "part_number" in df.columns:
        sort_cols.append("part_number")

    if sort_cols:
        df = df.sort_values(by=sort_cols, na_position="last").reset_index(drop=True)

    return df


def _detect_parent_child(df: pd.DataFrame) -> pd.DataFrame:
    """Detect parent-child relationships in packages section.

    Step 8.2: Identify parent rows (main packages with price + trims) and
    child rows (variant packages with no price or minimal price).

    Args:
        df: Section DataFrame (packages section)

    Returns:
        DataFrame with new columns: relationship, parent_idx
    """
    if df is None or df.empty:
        return df

    df = df.copy()

    # Add tracking columns
    df["relationship"] = "standalone"  # default
    df["parent_idx"] = None

    # Determine parent vs child
    for idx, row in df.iterrows():
        has_description = pd.notna(row.get("description"))
        installed_price = row.get("installed_price")
        has_price = pd.notna(installed_price) and installed_price > 0

        # Parent: has description + price + (possibly) trims
        if has_description and has_price:
            df.at[idx, "relationship"] = "parent"
        # Child: has description but no/zero price
        elif has_description and not has_price:
            df.at[idx, "relationship"] = "child"

    # Link children to parents
    # Simple heuristic: each child links to the parent immediately before it
    for idx, row in df.iterrows():
        if row["relationship"] == "child":
            # Find parent (should be immediately above, or last parent)
            for prev_idx in range(idx - 1, -1, -1):
                if df.at[prev_idx, "relationship"] == "parent":
                    df.at[idx, "parent_idx"] = prev_idx
                    break

    return df


def _rollup_packages(df: pd.DataFrame, config: Dict[str, Any]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Rollup: aggregate children into parents.

    Step 8.3: For each parent, aggregate child variants into the parent row.

    Args:
        df: Packages DataFrame with relationship tracking
        config: Pipeline configuration

    Returns:
        Tuple of:
        - Rolled up DataFrame (parents only, with aggregated info)
        - Metadata dict with rollup stats
    """
    if df is None or df.empty:
        return df, {}

    df = df.copy()

    # Track stats
    parent_count = 0
    child_count = 0
    trim_mismatches = 0

    # Process parents and aggregate children
    parents_to_keep = []
    for idx, row in df.iterrows():
        if row["relationship"] != "parent":
            continue

        parent_count += 1
        parent_row = row.copy()

        # Find children for this parent
        children = df[
            (df["relationship"] == "child") & (df["parent_idx"] == idx)
        ]
        child_count += len(children)

        if len(children) > 0:
            # Aggregate child descriptions
            child_descriptions = children["description"].tolist()
            parent_row["description"] = f"{parent_row['description']} ({', '.join(str(d) for d in child_descriptions)})"

            # Track trim mismatches (warning only, don't change parent)
            # This would be expanded later if we have trim data

            # Mark that this parent has children
            parent_row["has_children"] = True
            parent_row["child_count"] = len(children)
        else:
            parent_row["has_children"] = False
            parent_row["child_count"] = 0

        parents_to_keep.append(parent_row)

    # Also keep any standalone rows (non-package items)
    standalones = df[df["relationship"] == "standalone"]
    for idx, row in standalones.iterrows():
        parent_row = row.copy()
        parent_row["has_children"] = False
        parent_row["child_count"] = 0
        parents_to_keep.append(parent_row)

    # Build rolled-up DataFrame
    if parents_to_keep:
        rolled_up = pd.DataFrame(parents_to_keep).reset_index(drop=True)
    else:
        rolled_up = pd.DataFrame()

    # Metadata
    metadata = {
        "parent_count": parent_count,
        "child_count": child_count,
        "trim_mismatches": trim_mismatches,
    }

    return rolled_up, metadata


def _standardize_data(
    section_data: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Standardize data and detect parent-child relationships.

    Part 8: Clean data, detect parent-child (packages only), aggregate.

    Args:
        section_data: Section data from Part 7 with structure:
            {section_name: {"en_df": ..., "fr_df": ..., "trim_columns": [...]}, ...}
        config: Pipeline configuration

    Returns:
        Dict with standardized data and rollup metadata
    """
    standardized_data = {}
    rollup_metadata = {}
    warnings = []

    # Process each section
    for section_name, section_info in section_data.items():
        en_df = section_info.get("en_df")
        fr_df = section_info.get("fr_df")
        trim_columns = section_info.get("trim_columns", [])

        # Step 8.1: Cleanup EN section
        en_cleaned = _cleanup_section_data(en_df, section_name, config)

        # Step 8.1: Cleanup FR section
        fr_cleaned = _cleanup_section_data(fr_df, section_name, config) if fr_df is not None else None

        # Step 8.2-8.3: Packages-specific rollup (only for "packages" section)
        en_unified = en_cleaned
        fr_unified = fr_cleaned
        section_rollup_metadata = {}

        if section_name == "packages" and en_cleaned is not None and not en_cleaned.empty:
            # Detect parent-child
            en_with_relationships = _detect_parent_child(en_cleaned)

            # Rollup packages
            en_unified, en_rollup_metadata = _rollup_packages(en_with_relationships, config)
            section_rollup_metadata.update(en_rollup_metadata)

            # Same for FR if present
            if fr_cleaned is not None and not fr_cleaned.empty:
                fr_with_relationships = _detect_parent_child(fr_cleaned)
                fr_unified, fr_rollup_metadata = _rollup_packages(fr_with_relationships, config)
                # Merge metadata (for comparison)
                if fr_rollup_metadata.get("child_count", 0) != en_rollup_metadata.get("child_count", 0):
                    warnings.append({
                        "section": section_name,
                        "severity": "WARNING",
                        "message": f"EN/FR child count mismatch: EN={en_rollup_metadata.get('child_count')}, FR={fr_rollup_metadata.get('child_count')}"
                    })

        # Store standardized section
        standardized_data[section_name] = {
            "en_unified": en_unified,
            "fr_unified": fr_unified,
            "trim_columns": trim_columns,
        }

        if section_rollup_metadata:
            rollup_metadata[section_name] = section_rollup_metadata

    return {
        "standardized_data": standardized_data,
        "rollup_metadata": rollup_metadata,
        "warnings": warnings,
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
