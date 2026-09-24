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
# PART 9: EN/FR Reconciliation
# ============================================================================

def _compute_description_similarity(en_desc: str, fr_desc: str) -> float:
    """Compute similarity between EN and FR descriptions (0.0–1.0).

    Simple approach: check key word overlap (case-insensitive).
    """
    if not en_desc or not fr_desc:
        return 0.0

    en_words = set(str(en_desc).lower().split())
    fr_words = set(str(fr_desc).lower().split())

    if not en_words or not fr_words:
        return 0.0

    intersection = en_words & fr_words
    union = en_words | fr_words

    if not union:
        return 0.0

    # Jaccard similarity
    return len(intersection) / len(union)


def _match_en_fr_parts(
    en_df: pd.DataFrame,
    fr_df: Optional[pd.DataFrame],
    config: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Match EN and FR parts using priority strategy.

    Strategy (in order):
    1. Exact part number match (confidence 0.95)
    2. Description similarity > 0.6 (confidence 0.80)
    3. Cost match (within ±$10, confidence 0.60)

    Args:
        en_df: EN section DataFrame (with canonical columns)
        fr_df: FR section DataFrame (may be None)
        config: Pipeline configuration

    Returns:
        Tuple of:
        - reconciliation_map: {en_part_id: {"fr_equivalent": ..., "status": ..., ...}}
        - divergences: List of divergence warnings
    """
    reconciliation_map = {}
    divergences = []

    if en_df is None or en_df.empty:
        return reconciliation_map, divergences

    if fr_df is None or fr_df.empty:
        # EN-only case: all EN parts are unmapped
        for idx, row in en_df.iterrows():
            part_id = row.get("part_number", f"EN_{idx}")
            reconciliation_map[part_id] = {
                "fr_equivalent": None,
                "status": "EN_ONLY",
                "cost_match": False,
                "part_count_match": False,
                "confidence": 0.0,
                "dq_warnings": ["FR section not available"],
            }
        return reconciliation_map, divergences

    # Build lookup tables
    fr_by_part_number = {}
    fr_by_cost = {}

    for idx, row in fr_df.iterrows():
        part_num = row.get("part_number")
        if pd.notna(part_num):
            fr_by_part_number[str(part_num).upper()] = (idx, row)

        cost = row.get("installed_price")
        if pd.notna(cost):
            cost_key = round(float(cost), 2)
            if cost_key not in fr_by_cost:
                fr_by_cost[cost_key] = []
            fr_by_cost[cost_key].append((idx, row))

    matched_fr_indices = set()

    # Match EN parts
    for en_idx, en_row in en_df.iterrows():
        en_part_id = en_row.get("part_number", f"EN_{en_idx}")
        en_desc = en_row.get("description")
        en_cost = en_row.get("installed_price")

        fr_match = None
        confidence = 0.0
        match_method = None

        # Strategy 1: Exact part number match
        en_part_upper = str(en_part_id).upper() if pd.notna(en_part_id) else None
        if en_part_upper and en_part_upper in fr_by_part_number:
            fr_idx, fr_row = fr_by_part_number[en_part_upper]
            fr_match = fr_row
            confidence = 0.95
            match_method = "exact_part_number"
            matched_fr_indices.add(fr_idx)

        # Strategy 2: Description similarity (if no part number match)
        if fr_match is None:
            best_sim = 0.0
            best_fr_idx = None
            best_fr_row = None

            for fr_idx, fr_row in fr_df.iterrows():
                if fr_idx in matched_fr_indices:
                    continue

                fr_desc = fr_row.get("description")
                sim = _compute_description_similarity(en_desc, fr_desc)

                if sim > best_sim and sim > 0.6:
                    best_sim = sim
                    best_fr_idx = fr_idx
                    best_fr_row = fr_row

            if best_fr_row is not None:
                fr_match = best_fr_row
                confidence = 0.80
                match_method = "description_similarity"
                matched_fr_indices.add(best_fr_idx)

        # Strategy 3: Cost match within ±$10 (if no prior match)
        if fr_match is None and pd.notna(en_cost):
            try:
                en_cost_float = float(en_cost)
                for cost_offset in range(-10, 11):
                    check_cost = round(en_cost_float + cost_offset, 2)
                    if check_cost in fr_by_cost:
                        candidates = [
                            (idx, row) for idx, row in fr_by_cost[check_cost]
                            if idx not in matched_fr_indices
                        ]
                        if candidates:
                            fr_idx, fr_row = candidates[0]
                            fr_match = fr_row
                            confidence = 0.60
                            match_method = "cost_match"
                            matched_fr_indices.add(fr_idx)
                            break
            except (ValueError, TypeError):
                pass

        # Record match
        if fr_match is not None:
            fr_part_id = fr_match.get("part_number", "UNKNOWN_FR")

            # Check for divergences
            dq_warnings = []

            en_cost_float = float(en_cost) if pd.notna(en_cost) else None
            fr_cost_float = float(fr_match.get("installed_price")) if pd.notna(fr_match.get("installed_price")) else None

            cost_match = False
            if en_cost_float is not None and fr_cost_float is not None:
                cost_diff = abs(en_cost_float - fr_cost_float)
                cost_match = cost_diff < 0.01  # Allow tiny float rounding
                if cost_diff > 0.01:
                    dq_warnings.append(f"Cost divergence: EN=${en_cost_float:.2f} vs FR=${fr_cost_float:.2f}")

            reconciliation_map[en_part_id] = {
                "fr_equivalent": fr_part_id,
                "status": "MAPPED",
                "cost_match": cost_match,
                "part_count_match": True,  # Since matched
                "confidence": confidence,
                "match_method": match_method,
                "dq_warnings": dq_warnings,
            }
        else:
            # EN part with no FR match
            reconciliation_map[en_part_id] = {
                "fr_equivalent": None,
                "status": "EN_ONLY",
                "cost_match": False,
                "part_count_match": False,
                "confidence": 0.0,
                "dq_warnings": ["No FR equivalent found"],
            }
            divergences.append({
                "section": "unknown",  # filled by caller
                "severity": "INFO",
                "type": "en_only_part",
                "en_part": en_part_id,
                "message": f"EN part {en_part_id} has no FR equivalent"
            })

    # Find FR-only parts (not matched to any EN part)
    for fr_idx, fr_row in fr_df.iterrows():
        if fr_idx not in matched_fr_indices:
            fr_part_id = fr_row.get("part_number", f"FR_{fr_idx}")
            divergences.append({
                "section": "unknown",
                "severity": "INFO",
                "type": "fr_only_part",
                "fr_part": fr_part_id,
                "message": f"FR part {fr_part_id} has no EN equivalent"
            })

    return reconciliation_map, divergences


def _reconcile_en_fr(
    standardized_data: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Reconcile EN and FR sheets.

    Part 9: Build reconciliation map, match parts, track divergence.

    Args:
        standardized_data: Standardized data from Part 8 with structure:
            {section_name: {"en_unified": ..., "fr_unified": ..., ...}, ...}
        config: Pipeline configuration

    Returns:
        Dict with unified data, reconciliation map, and divergence report
    """
    reconciliation_map = {}
    all_divergences = []
    warnings = []

    # Process each section
    for section_name, section_info in standardized_data.items():
        en_df = section_info.get("en_unified")
        fr_df = section_info.get("fr_unified")

        if en_df is None or en_df.empty:
            continue

        # Match EN and FR parts for this section
        section_map, section_divergences = _match_en_fr_parts(en_df, fr_df, config)

        # Update divergences with section info
        for div in section_divergences:
            div["section"] = section_name

        reconciliation_map[section_name] = section_map
        all_divergences.extend(section_divergences)

        # Summary stats
        total_en = len(en_df) if en_df is not None else 0
        en_only_count = sum(1 for m in section_map.values() if m["status"] == "EN_ONLY")
        mapped_count = sum(1 for m in section_map.values() if m["status"] == "MAPPED")
        low_confidence_count = sum(
            1 for m in section_map.values()
            if m["status"] == "MAPPED" and m["confidence"] < 0.80
        )

        if mapped_count < total_en:
            warnings.append({
                "section": section_name,
                "severity": "WARNING",
                "message": f"Partial EN/FR mapping: {mapped_count}/{total_en} EN parts mapped, {en_only_count} EN-only, {low_confidence_count} low-confidence"
            })

    # Unified data: keep standardized data as-is (transformation happens in Step 4)
    unified_data = standardized_data

    return {
        "unified_data": unified_data,
        "reconciliation_map": reconciliation_map,
        "divergence_report": all_divergences,
        "warnings": warnings,
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
