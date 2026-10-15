#!/usr/bin/env python3
"""
Phase 2: Header Normalization + Parent/Child Detection

Standardizes column names within each section and identifies parent/child records
for price inheritance in Phase 3.

Input: Raw dataframe + metadata from Phase 1
Output: Same dataframe + enriched metadata with normalized headers, parent/child info
"""

import pandas as pd
import logging
from typing import Dict, List, Tuple, Any, Optional


def run(df: pd.DataFrame, config: Dict, meta_data: Dict, dq_logger, logger) -> Tuple[pd.DataFrame, Dict]:
    """
    Phase 2: Header Normalization + Parent/Child Detection

    Args:
        df: Raw dataframe (unchanged from Phase 1)
        config: Configuration dict with step1_detection settings
        meta_data: Metadata from Phase 1 (model_name, vehicle_year, section_structure, etc.)
        dq_logger: DQ logger for recording data quality issues
        logger: Pipeline logger for debug/info logging

    Returns:
        (df, updated_meta): Same dataframe + enriched metadata
    """

    logger.info("Phase 2: Starting header normalization and parent/child detection")

    updated_meta = meta_data.copy()
    language = meta_data.get("language", "EN")
    section_structure = meta_data.get("section_structure", {})

    # Extract column definitions and categories from upstream.yaml (via config)
    # Config structure: upstream.yaml has 'columns' with language-specific detection
    upstream_schema = config.get("schemas", {}).get("upstream", {})
    column_defs = upstream_schema.get("columns", {})
    column_categories = upstream_schema.get("column_categories", {})
    # Use spaces in column names to match the normalized headers from structure.yaml
    product_columns = column_categories.get("product_columns", ["description", "part number"])
    price_columns = column_categories.get("price_columns", ["dealer net", "list price", "frt", "installed price"])

    # Get section classification from ModularConfigLoader structure
    # Config path: config > schemas > structure > section_classification
    detection_config = config.get("schemas", {}).get("structure", {})

    logger.info(f"Phase 2: Using column definitions from config")
    logger.debug(f"  Product columns: {product_columns}")
    logger.debug(f"  Price columns: {price_columns}")

    # Initialize metadata collections
    normalized_headers = {}
    column_mapping = {}
    record_types = {}
    parent_index = {}
    part_number_fallbacks = {}  # Track rows that use column 1 fallback for part number

    # Process each section
    for section_name, section_bounds in section_structure.items():
        logger.debug(f"Processing section: {section_name}")

        # 1. Extract and normalize headers
        try:
            header_row = _extract_header_row(df, section_bounds)
            raw_names = _extract_column_names(header_row, language)
            norm_names = _normalize_header_names(raw_names, config, language, dq_logger, updated_meta)

            normalized_headers[section_name] = list(norm_names.values())
            column_mapping[section_name] = norm_names

            logger.debug(f"  Headers normalized: {list(norm_names.values())}")

        except Exception as e:
            logger.warning(f"  Error normalizing headers for {section_name}: {e}")
            dq_logger.log_warning(
                sheet_name=meta_data.get("sheet_name", "unknown"),
                model_name=meta_data.get("model_name", "unknown"),
                record_index=section_bounds.get("header_row", -1),
                record_snapshot={"section": section_name},
                rule_violated="header_not_found_rule",
                issue_description=f"Section has no recognizable header row: {section_name}"
            )
            continue

        # 2. Detect parent/child for all data rows in this section
        # Look up section classification from config to support EN/FR section names
        is_package = False
        section_classification = detection_config.get("section_classification", {})
        for section_def in section_classification.get("sections", []):
            # Match against both name and markers (for EN and FR support)
            config_name = section_def.get("name", "").lower()
            markers_en = [m.lower() for m in section_def.get("markers_en", [])]
            markers_fr = [m.lower() for m in section_def.get("markers_fr", [])]
            all_markers = [config_name] + markers_en + markers_fr

            if section_name.lower() in all_markers:
                is_package = section_def.get("is_package", False)
                break
        section_start = section_bounds.get("data_start_row")
        section_end = section_bounds.get("data_end_row")

        logger.debug(f"  Classifying rows {section_start}-{section_end} (is_package={is_package})")

        for row_idx in range(section_start, section_end + 1):
            row = df.iloc[row_idx]
            rtype = _classify_record_type(
                row, section_name, is_package, norm_names, dq_logger, row_idx, updated_meta,
                product_columns, price_columns, part_number_fallbacks
            )
            record_types[row_idx] = rtype

        # 3. Build parent index for this section
        section_parent_index = _build_parent_index(
            section_start, section_end, record_types, dq_logger
        )
        parent_index.update(section_parent_index)

    # 4. Post-process: Fill part numbers from column 1 fallback for parent records
    df_filled, filled_count = _fill_part_numbers_from_fallback(
        df, record_types, section_structure, dq_logger, logger, updated_meta
    )
    df = df_filled

    # 5. Enrich metadata with all Phase 2 outputs
    updated_meta["normalized_headers"] = normalized_headers
    updated_meta["column_mapping"] = column_mapping
    updated_meta["price_columns"] = price_columns  # From config, not hard-coded
    updated_meta["record_type_per_row"] = record_types
    updated_meta["parent_row_index"] = parent_index

    # 6. Compute record type counts for summary
    record_type_counts = {}
    for rtype in record_types.values():
        rtype_key = "defect" if rtype is None else rtype
        record_type_counts[rtype_key] = record_type_counts.get(rtype_key, 0) + 1
    updated_meta["record_type_counts"] = record_type_counts

    logger.info(f"Phase 2: Complete. Record types: {record_type_counts}")
    if filled_count > 0:
        logger.info(f"Phase 2: Recovered {filled_count} part numbers from column 1 fallback")

    return df, updated_meta


def _extract_header_row(df: pd.DataFrame, section_bounds: Dict) -> pd.Series:
    """
    Extract the header row for a section.

    Args:
        df: Dataframe
        section_bounds: Dict with marker_row, header_row, data_start_row, data_end_row

    Returns:
        Header row as Series
    """
    header_row_idx = section_bounds.get("header_row")
    if header_row_idx is None or header_row_idx >= len(df):
        raise ValueError(f"Invalid header row index: {header_row_idx}")
    return df.iloc[header_row_idx]


def _extract_column_names(header_row: pd.Series, language: str = "EN") -> List[str]:
    """
    Extract raw column names from header row.

    Args:
        header_row: Header row Series
        language: Language (EN or FR)

    Returns:
        List of column names (lowercase, whitespace stripped, NaN replaced)
    """
    names = []
    for idx, val in enumerate(header_row):
        if pd.isna(val):
            names.append(f"unnamed_{idx}")
        else:
            # Normalize: lowercase, strip whitespace
            names.append(str(val).strip().lower())
    return names


def _normalize_header_names(
    raw_names: List[str],
    config: Dict,
    language: str,
    dq_logger,
    meta_data: Dict = None
) -> Dict[int, str]:
    """
    Map raw header names to normalized names using language-specific keyword matching.

    Args:
        raw_names: List of raw column names
        config: Full configuration dict from ModularConfigLoader
        language: Language (EN or FR)
        dq_logger: DQ logger
        meta_data: Metadata dict (for logging)

    Returns:
        Dict {column_index: normalized_name}
    """
    upstream_schema = config.get("schemas", {}).get("upstream", {})
    column_defs = upstream_schema.get("columns", {})
    norm_mapping = {}
    matched_columns = set()

    # Map each raw name to normalized name using language-specific rules
    for col_idx, raw_name in enumerate(raw_names):
        best_match = None
        confidence = 0.0

        # Try each column definition's language-specific rules
        # Structure: columns[col_name].detection[LANGUAGE].key_words
        for std_name, spec in column_defs.items():
            detection = spec.get("detection", {})
            lang_rules = detection.get(language)
            if not lang_rules:
                continue  # Skip if language not defined for this column

            keywords = lang_rules.get("key_words", {})

            # Check if raw_name matches this column's keywords
            if _matches_keywords(raw_name, keywords):
                best_match = std_name
                confidence = 0.95
                break  # First match wins

        # Store mapping
        if best_match:
            norm_mapping[col_idx] = best_match
            matched_columns.add(best_match)
        else:
            # No match found; keep raw name (don't warn - this is normal for trim columns)
            norm_mapping[col_idx] = raw_name

    return norm_mapping


def _is_row_completely_empty(row: pd.Series) -> bool:
    """Check if a row is completely empty (all values are NULL or empty strings)."""
    for val in row.values:
        if pd.notna(val):
            val_str = str(val).strip()
            if val_str and val_str.lower() not in ["nan", "none"]:
                return False
    return True


def _is_subsection_label(row: pd.Series, norm_names: Dict[int, str]) -> bool:
    """
    Check if row is a subsection label (marks start of a subsection).

    Subsection labels have:
    - Description column: HAS DATA
    - Part Number column: EMPTY (key differentiator from products)
    - All price columns: EMPTY (dealer net, list price, frt, installed price)
    - All application/trim columns: EMPTY
    - May have placeholder code in column before description

    Examples: "Sedan Models", "Roof Attachments", "Interior Controls"
    """
    # Check if description has data
    has_description = _check_column("description", row, norm_names)
    if not has_description:
        return False

    # Part number MUST be empty (key differentiator from real products)
    has_part_number = _check_column("part number", row, norm_names)
    if has_part_number:
        # Has part number - it's a real product, not a subsection label
        return False

    # All price/application columns must be empty
    columns_to_check = [
        "dealer net", "list price", "frt", "installed price", "application"
    ]

    for col_name in columns_to_check:
        if _check_column(col_name, row, norm_names):
            # Found data in a required column - not a subsection label
            return False

    # Check that all trim columns are empty (typically columns 9-16 and beyond)
    # Only check trim columns that come AFTER the main product/price columns
    for col_idx, norm_name in norm_names.items():
        norm_lower = norm_name.lower()

        # Skip the main product/price/application columns we already checked
        if any(keyword in norm_lower for keyword in
               ["description", "part", "dealer", "list", "frt", "installed", "application"]):
            continue

        # Skip unnamed columns that come before the main data area (cols 0-1)
        if col_idx < 2:
            continue

        # Check if this trim column has data
        val = row.iloc[col_idx] if col_idx < len(row) else None
        if pd.notna(val):
            val_str = str(val).strip()
            if val_str and val_str.lower() not in ["nan", "none"]:
                # Found data in a trim column - not a subsection label
                return False

    return True


def _matches_keywords(col_name: str, keywords: Dict[str, List[str]]) -> bool:
    """
    Check if column name matches keyword rules.
    Language-agnostic: handles accents, case-insensitive, position-independent.

    Args:
        col_name: Raw column name
        keywords: Dict with must_have, must_have_one_of, not_have lists

    Returns:
        True if column matches all keyword criteria
    """
    # Normalize: lowercase, remove accents
    col_lower = (col_name.lower()
                 .replace('é', 'e').replace('è', 'e').replace('ê', 'e')
                 .replace('à', 'a').replace('â', 'a').replace('ä', 'a')
                 .replace('ï', 'i').replace('ô', 'o').replace('ö', 'o')
                 .replace('ù', 'u').replace('û', 'u').replace('ü', 'u')
                 .replace('ç', 'c').replace('ñ', 'n'))

    must_have = [k.lower() for k in keywords.get("must_have", [])]
    must_have_one_of = [k.lower() for k in keywords.get("must_have_one_of", [])]
    not_have = [k.lower() for k in keywords.get("not_have", [])]

    # All must_have keywords must be present as substrings
    if must_have and not all(k in col_lower for k in must_have):
        return False

    # None of not_have keywords should be present
    if not_have and any(k in col_lower for k in not_have):
        return False

    # At least one must_have_one_of should be present (if list is not empty)
    if must_have_one_of and not any(k in col_lower for k in must_have_one_of):
        return False

    return True


def _classify_record_type(
    row: pd.Series,
    section_name: str,
    is_package: bool,
    norm_names: Dict[int, str],
    dq_logger,
    row_idx: int = -1,
    meta_data: Dict = None,
    product_columns: List[str] = None,
    price_columns: List[str] = None,
    part_number_fallbacks: Dict[int, str] = None
) -> Optional[str]:
    """
    Determine record type for a single row.

    Args:
        product_columns: List of product column names (from config)
        price_columns: List of price column names (from config)

    Returns:
        "subsection_label" | "package_parent" | "package_child" | "parent" | "child" | None (defect)

    Subsection labels: Rows with description only, all other columns empty (marks start of subsection)
    Parent (complete): ALL product columns filled + ALL price columns filled
    Child (incomplete): ALL product columns filled + ALL price columns EMPTY
    Defects: Missing product data, partial prices
    """
    # Use config defaults if not provided
    if product_columns is None:
        product_columns = ["part_number", "description"]
    if price_columns is None:
        price_columns = ["dealer_net", "list_price", "frt", "installed_price"]

    # Check if row is completely empty first - skip as data cleanup, not a defect
    if _is_row_completely_empty(row):
        return None

    # Check which columns have data (use config column names)
    # For part number, use fallback to column 1 if official part number column is empty
    has_description = _check_column("description", row, norm_names)
    has_part_number, part_number_fallback_value = _check_part_number_with_fallback(row, norm_names)

    # If row has NO product identification (no description AND no part number),
    # skip it as data cleanup - not a defect. These are empty/padding rows in Excel.
    if not has_description and not has_part_number:
        return None

    # Check if row is a subsection label (marks start of subsection)
    # These are dropped from processing but logged for audit trail
    if _is_subsection_label(row, norm_names):
        return "subsection_label"

    has_product_data = has_description or has_part_number
    has_all_products = has_description and has_part_number  # Both required for parent
    has_all_prices = _check_all_columns(price_columns, row, norm_names)
    has_any_price = _check_any_columns(price_columns, row, norm_names)

    # Track rows that used fallback part number (for later data hydration)
    if part_number_fallback_value and part_number_fallbacks is not None:
        part_number_fallbacks[row_idx] = part_number_fallback_value

    # For non-package sections, need ALL product columns filled
    # For package sections, need ANY product column filled
    has_complete_product_np = has_all_products  # Non-packages: ALL product columns
    has_product_pkg = has_product_data  # Packages: ANY product column

    if is_package:
        # Package section logic
        if not has_product_pkg:
            if meta_data and dq_logger:
                dq_logger.log_warning(
                    sheet_name=meta_data.get("sheet_name", "unknown"),
                    model_name=meta_data.get("model_name", "unknown"),
                    record_index=row_idx,
                    record_snapshot=row.to_dict(),
                    rule_violated="record_type_defect_partial_data",
                    issue_description=f"Missing required product data (description or part number) in {section_name}"
                )
            return None

        if has_any_price and not has_all_prices:
            if meta_data and dq_logger:
                dq_logger.log_warning(
                    sheet_name=meta_data.get("sheet_name", "unknown"),
                    model_name=meta_data.get("model_name", "unknown"),
                    record_index=row_idx,
                    record_snapshot=row.to_dict(),
                    rule_violated="record_type_defect_partial_prices",
                    issue_description=f"Partial pricing data in {section_name} - missing one or more price columns"
                )
            return None

        if has_all_prices:
            return "package_parent"
        elif not has_any_price:
            return "package_child"

    else:
        # Non-package section logic
        if not has_complete_product_np:
            if meta_data and dq_logger:
                dq_logger.log_warning(
                    sheet_name=meta_data.get("sheet_name", "unknown"),
                    model_name=meta_data.get("model_name", "unknown"),
                    record_index=row_idx,
                    record_snapshot=row.to_dict(),
                    rule_violated="record_type_defect_partial_data",
                    issue_description=f"Missing required product data (description and part number) in {section_name}"
                )
            return None

        if has_any_price and not has_all_prices:
            if meta_data and dq_logger:
                dq_logger.log_warning(
                    sheet_name=meta_data.get("sheet_name", "unknown"),
                    model_name=meta_data.get("model_name", "unknown"),
                    record_index=row_idx,
                    record_snapshot=row.to_dict(),
                    rule_violated="record_type_defect_partial_prices",
                    issue_description=f"Partial pricing data in {section_name} - missing one or more price columns"
                )
            return None

        if has_all_prices:
            return "parent"
        elif not has_any_price:
            return "child"

    return None


def _check_part_number_with_fallback(row: pd.Series, norm_names: Dict[int, str]) -> Tuple[bool, Optional[str]]:
    """
    Check if row has a part number, with fallback to column 1.

    Returns:
        (has_part_number: bool, fallback_value: str or None)
        - If column 3 (part number) has data: return (True, None)
        - If column 3 is empty but column 1 has data: return (True, column_1_value)
        - Otherwise: return (False, None)
    """
    # First check official part number column (column 3)
    has_official = _check_column("part number", row, norm_names)
    if has_official:
        return (True, None)

    # Fallback: check column 1 (unnamed_1, contains placeholder codes)
    if len(row) > 1:
        fallback_val = row.iloc[1]
        if pd.notna(fallback_val):
            fallback_str = str(fallback_val).strip()
            if fallback_str and fallback_str.lower() not in ["nan", "none"]:
                return (True, fallback_str)

    return (False, None)


def _check_column(col_name: str, row: pd.Series, norm_names: Dict[int, str]) -> bool:
    """Check if a specific normalized column has data in this row.

    Supports both English and French column names.
    """
    # EN/FR column name mappings
    col_aliases = {
        "description": ["description", "la description"],
        "part number": ["part number", "numéro de pièce"],
        "dealer net": ["dealer net", "prix net"],
        "list price": ["list price", "prix de liste"],
        "frt": ["frt", "t.f.f."],
        "installed price": ["installed price", "prix installé"]
    }

    col_name_lower = col_name.lower()
    aliases = col_aliases.get(col_name_lower, [col_name_lower])

    for col_idx, norm_name in norm_names.items():
        norm_lower = norm_name.lower()
        # Check if norm_name matches any of the aliases
        if any(alias in norm_lower for alias in aliases):
            val = row.iloc[col_idx]
            has_data = pd.notna(val) and str(val).strip() != ""
            if has_data:
                return True
    return False


def _check_all_columns(col_names: List[str], row: pd.Series, norm_names: Dict[int, str]) -> bool:
    """Check if ALL specified columns have data in this row."""
    for col_name in col_names:
        if not _check_column(col_name, row, norm_names):
            return False
    return True


def _check_any_columns(col_names: List[str], row: pd.Series, norm_names: Dict[int, str]) -> bool:
    """Check if ANY of the specified columns have data in this row."""
    for col_name in col_names:
        if _check_column(col_name, row, norm_names):
            return True
    return False


def _fill_part_numbers_from_fallback(
    df: pd.DataFrame,
    record_types: Dict[int, Optional[str]],
    section_structure: Dict[str, Dict],
    dq_logger,
    logger,
    meta_data: Dict = None
) -> Tuple[pd.DataFrame, int]:
    """
    Fill in missing part numbers from column 1 fallback for parent records.

    For parent/package_parent records that used the column 1 fallback,
    populate the actual part number column with the fallback value.

    Args:
        df: Dataframe
        record_types: Dict of row_idx -> record type
        section_structure: Section boundaries from metadata
        dq_logger: DQ logger
        logger: Pipeline logger
        meta_data: Metadata dict

    Returns:
        (modified_df, filled_count)
    """
    df_copy = df.copy()
    filled_count = 0
    sheet_name = meta_data.get("sheet_name", "unknown") if meta_data else "unknown"
    model_name = meta_data.get("model_name", "unknown") if meta_data else "unknown"

    # Find part number column index across all sections
    column_mapping = meta_data.get("column_mapping", {}) if meta_data else {}

    for row_idx, record_type in record_types.items():
        # Only process parent records
        if record_type not in ("parent", "package_parent"):
            continue

        row = df_copy.iloc[row_idx]

        # Check if this row used fallback (column 1 has data, column 3 doesn't)
        col_1_val = None
        if len(row) > 1:
            col_1_raw = row.iloc[1]
            if pd.notna(col_1_raw):
                col_1_str = str(col_1_raw).strip()
                if col_1_str and col_1_str.lower() not in ["nan", "none"]:
                    col_1_val = col_1_str

        if not col_1_val:
            continue  # No fallback data to fill

        # Check if part number column (column 3) is actually empty
        part_num_empty = False
        if len(row) > 3:
            part_num_raw = row.iloc[3]
            if pd.isna(part_num_raw) or str(part_num_raw).strip() == "":
                part_num_empty = True

        if not part_num_empty:
            continue  # Part number already filled

        # Fill part number column with fallback value
        df_copy.iloc[row_idx, 3] = col_1_val
        filled_count += 1

        # Log as cleaning activity (not a warning)
        logger.debug(
            f"Row {row_idx}: Filled missing part number from column 1: '{col_1_val}' ({record_type})"
        )

    return df_copy, filled_count


def _build_parent_index(
    section_start: int,
    section_end: int,
    record_types: Dict[int, Optional[str]],
    dq_logger
) -> Dict[int, Optional[int]]:
    """
    Build parent index using first-parent-rule (most recent parent).

    For each child row, find its parent (most recent preceding parent in same section).

    Returns:
        {row_idx: parent_row_idx or None}
        - If parent_index[row] = None → row is a parent (or defect/orphan)
        - If parent_index[row] = some_idx → row inherits from row some_idx
    """

    parent_index = {}
    current_parent = None

    for row_idx in range(section_start, section_end + 1):
        record_type = record_types.get(row_idx)

        # Parent types: set as current parent source
        if record_type in ("parent", "package_parent"):
            current_parent = row_idx
            parent_index[row_idx] = None

        # Child types: inherit from current parent
        elif record_type in ("child", "package_child"):
            if current_parent is None:
                # Defect: orphaned child (no parent to inherit from)
                dq_logger.log_warning(
                    sheet_name="unknown",
                    model_name="unknown",
                    record_index=row_idx,
                    record_snapshot={"record_type": record_type},
                    rule_violated="orphaned_child_rule",
                    issue_description=f"Child record has no preceding parent"
                )
                parent_index[row_idx] = None
            else:
                parent_index[row_idx] = current_parent

        # Defect rows (None) and others: no parent relationship
        else:
            parent_index[row_idx] = None

    return parent_index
