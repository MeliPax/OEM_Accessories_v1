"""Step 4.5: Model Lookup & Enrichment

Integrates VehicleSearchEngine to add OEM model numbers to accessories.

Process:
1. Extract unique trim values from data
2. Tokenize and normalize each trim using KeywordExtractor
3. Batch lookup: one VehicleSearchEngine.search() per unique trim
4. Build trim→model_number mapping
5. Add model_number and model_status columns to output
6. Handle multiple candidates (packages, drivetrain variants)
7. DQ logging for NOT_FOUND, LOW_CONFIDENCE cases
"""

from typing import Tuple, Dict, Any, Optional, List
import logging

import pandas as pd
import numpy as np

from accy_v2.model_lookup.search_engine import VehicleSearchEngine, SearchResult


logger = logging.getLogger(__name__)


def enrich_with_model_numbers(
    unified_data: Dict[str, Any],
    reconciliation_map: Dict[str, Any],
    metadata: Dict[str, Any],
    config: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
    """Enrich data with model numbers from VehicleSearchEngine.

    Args:
        unified_data: Unified data from Step 2 (section-based structure)
        reconciliation_map: EN/FR reconciliation map from Step 2
        metadata: Metadata from Steps 1-3 (includes vehicle_year, model_name, manufacturer)
        config: Pipeline configuration

    Returns:
        Tuple of (enriched_data, updated_metadata, dq_warnings)
    """
    vehicle_year = metadata.get("vehicle_year")
    model_name = metadata.get("model_name", "unknown")
    manufacturer = metadata.get("manufacturer", "Honda")

    if not vehicle_year:
        raise ValueError(f"vehicle_year not found in metadata")

    enriched_data = {}
    all_warnings = []
    trim_lookup_cache = {}  # Cache: trim → SearchResult

    # Get model lookup config
    oem_rules = config.get("model_lookup_rules", {}).get(manufacturer, {})
    if not oem_rules:
        raise ValueError(f"No model_lookup_rules configured for {manufacturer}")

    engine = VehicleSearchEngine(oem_rules=oem_rules, logger=logger)

    # Process each section
    for section_name, section_info in unified_data.items():
        en_df = section_info.get("en_unified")
        fr_df = section_info.get("fr_unified")
        trim_columns = section_info.get("trim_columns", [])

        if en_df is None or en_df.empty:
            enriched_data[section_name] = section_info
            continue

        # Extract unique trims from EN data (same trims in FR)
        unique_trims = []
        for trim_col in trim_columns:
            if trim_col in en_df.columns:
                col_trims = en_df[trim_col].dropna().unique().tolist()
                unique_trims.extend([str(t).strip() for t in col_trims if t and str(t).strip()])

        unique_trims = sorted(list(set(unique_trims)))
        logger.debug(f"Section '{section_name}': unique trims={unique_trims}")

        # Batch lookup: one search per unique trim
        for trim in unique_trims:
            if trim not in trim_lookup_cache:
                # Search using trim keyword
                search_result = engine.search(
                    make=manufacturer,
                    model_keywords=[model_name.lower()],
                    trim_keywords=[trim.lower()],
                    year=vehicle_year,
                )
                trim_lookup_cache[trim] = search_result

                # Log DQ for missing/low-confidence matches
                if search_result is None:
                    all_warnings.append({
                        "section": section_name,
                        "severity": "WARNING",
                        "type": "model_number_lookup_rule",
                        "trim": trim,
                        "message": f"[DATABASE_NO_MATCH] No model found for trim '{trim}'",
                    })
                elif search_result.confidence < 0.80:
                    all_warnings.append({
                        "section": section_name,
                        "severity": "INFO",
                        "type": "model_number_lookup_rule",
                        "trim": trim,
                        "message": f"[LOW_CONFIDENCE] Model found for trim '{trim}' with confidence {search_result.confidence}",
                    })

        # Enrich EN data
        en_enriched = _add_model_number_columns(
            df=en_df,
            trim_columns=trim_columns,
            trim_lookup_cache=trim_lookup_cache,
            section_name=section_name,
        )

        # Enrich FR data
        fr_enriched = None
        if fr_df is not None and not fr_df.empty:
            fr_enriched = _add_model_number_columns(
                df=fr_df,
                trim_columns=trim_columns,
                trim_lookup_cache=trim_lookup_cache,
                section_name=section_name,
            )

        # Store enriched section
        enriched_data[section_name] = {
            "en_enriched": en_enriched,
            "fr_enriched": fr_enriched,
            "trim_columns": trim_columns,
        }

    return enriched_data, metadata, all_warnings


def _add_model_number_columns(
    df: pd.DataFrame,
    trim_columns: List[str],
    trim_lookup_cache: Dict[str, Optional[Any]],
    section_name: str,
) -> pd.DataFrame:
    """Add model_number and model_status columns to DataFrame.

    For each row, extract trim values from trim_columns, lookup in cache,
    and add model_number and model_status.

    Args:
        df: Section DataFrame
        trim_columns: List of trim column names
        trim_lookup_cache: Cached trim → SearchResult mapping
        section_name: Section name (for logging)

    Returns:
        DataFrame with added model_number and model_status columns
    """
    if df is None or df.empty:
        return df

    df = df.copy()
    df["model_number"] = None
    df["model_status"] = "NOT_FOUND"

    for idx, row in df.iterrows():
        # Extract trim values for this row
        row_trims = []
        for trim_col in trim_columns:
            if trim_col in row.index:
                trim_val = row[trim_col]
                if pd.notna(trim_val):
                    row_trims.append(str(trim_val).strip())

        # Try to find matching model in cache
        best_result = None
        best_confidence = 0.0

        for trim in row_trims:
            if trim in trim_lookup_cache:
                result = trim_lookup_cache[trim]
                if result and result.confidence > best_confidence:
                    best_result = result
                    best_confidence = result.confidence

        # Add model_number and status
        if best_result:
            df.at[idx, "model_number"] = best_result.model_number
            if best_result.confidence >= 0.95:
                df.at[idx, "model_status"] = "EXACT_MATCH"
            elif best_result.confidence >= 0.80:
                df.at[idx, "model_status"] = "HIGH_CONFIDENCE"
            else:
                df.at[idx, "model_status"] = "LOW_CONFIDENCE"
        else:
            df.at[idx, "model_number"] = None
            df.at[idx, "model_status"] = "NOT_FOUND"

    return df
