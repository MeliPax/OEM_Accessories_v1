"""Step 4.5: Model Lookup & Enrichment

Integrates VehicleSearchEngine to add OEM model numbers to accessories.

Process:
1. Extract unique trim values from data
2. For each unique trim, do one VehicleSearchEngine.search()
3. Build trim→model_number mapping (cache)
4. Add model_number and model_status columns to output
5. DQ logging for NOT_FOUND, LOW_CONFIDENCE cases
"""

from typing import Tuple, Dict, Any, Optional, List
from pathlib import Path
import logging

import pandas as pd
import numpy as np

from accy_v2.model_lookup.search_engine import VehicleSearchEngine, SearchResult


logger = logging.getLogger(__name__)


def enrich_with_model_numbers(
    transformed: Dict[str, pd.DataFrame],
    reconciliation_map: Dict[str, Any],
    metadata: Dict[str, Any],
    config: Dict[str, Any],
) -> Tuple[Dict[str, pd.DataFrame], Dict[str, Any], List[Dict[str, Any]]]:
    """Enrich language-keyed data with model numbers via VehicleSearchEngine.

    Args:
        transformed: Dict mapping language -> DataFrame (e.g., {"EN": df_en, "FR": df_fr})
        reconciliation_map: EN/FR reconciliation map (unused in Honda context)
        metadata: Metadata including vehicle_year, model_name, manufacturer
        config: Pipeline configuration with model_lookup_rules

    Returns:
        Tuple of (enriched_dict, metadata, dq_warnings)
    """
    vehicle_year = metadata.get("vehicle_year")
    model_name = metadata.get("model_name", "unknown")
    manufacturer = metadata.get("manufacturer", "Honda")

    if not vehicle_year:
        raise ValueError(f"vehicle_year not found in metadata for model '{model_name}'")

    # Get OEM model lookup configuration
    oem_config = config.get("model_lookup_rules", {}).get(manufacturer, {})
    if not oem_config:
        raise ValueError(
            f"No model_lookup_rules configured for OEM '{manufacturer}'. "
            f"Available: {list(config.get('model_lookup_rules', {}).keys())}"
        )

    enriched_dict = {}
    all_warnings = []
    trim_lookup_cache = {}  # Cache: trim → SearchResult

    # Initialize search engine
    csv_path = str(Path(__file__).parent.parent.parent.parent / "model_lookup" / "db" / "db_vehicle_models.csv")
    configs_dir = str(Path(__file__).parent.parent.parent.parent / "model_lookup" / "configs")

    engine = VehicleSearchEngine(
        csv_path=csv_path,
        configs_dir=configs_dir,
        oem_config=oem_config,
        ignore_keyword_categories=oem_config.get("ignore_keyword_categories", []),
        pipeline_logger=logger
    )

    # Get first language DataFrame to extract unique trims (same trims in all languages)
    if not transformed:
        return transformed, metadata, all_warnings

    first_lang_df = next(iter(transformed.values()))
    if first_lang_df.empty:
        return transformed, metadata, all_warnings

    # Extract unique trims (assume "trim_level" column from Step 4 transformation)
    trim_col = oem_config.get("trim_column_name", "trim_level")
    if trim_col not in first_lang_df.columns:
        # Fallback: use any column that might contain trims
        logger.warning(f"trim_column '{trim_col}' not found; available: {first_lang_df.columns.tolist()}")
        return transformed, metadata, all_warnings

    unique_trims = sorted(first_lang_df[trim_col].dropna().unique().tolist())
    logger.debug(f"Model '{model_name}' {vehicle_year}: unique trims={unique_trims}")

    # Batch lookup: one search per unique trim
    for trim in unique_trims:
        if trim not in trim_lookup_cache:
            # Build keyword list: model name + trim
            keywords = [str(model_name).lower().replace(" ", "_"), str(trim).lower()]

            try:
                search_result = engine.search(
                    make=manufacturer,
                    year=vehicle_year,
                    raw_keywords=keywords,
                    exclude_ev=True,
                )
                trim_lookup_cache[trim] = search_result

                # Log DQ for missing/low-confidence matches
                if search_result is None:
                    all_warnings.append({
                        "severity": "WARNING",
                        "type": "model_number_lookup_rule",
                        "trim": trim,
                        "message": f"[DATABASE_NO_MATCH] No model found for {manufacturer} {vehicle_year} {model_name} trim '{trim}'",
                    })
                elif search_result.confidence < 0.80:
                    all_warnings.append({
                        "severity": "INFO",
                        "type": "model_number_lookup_rule",
                        "trim": trim,
                        "message": f"[LOW_CONFIDENCE] Found model with confidence {search_result.confidence:.2f} for trim '{trim}'",
                    })
            except Exception as e:
                logger.warning(f"Model lookup failed for trim '{trim}': {e}")
                trim_lookup_cache[trim] = None
                all_warnings.append({
                    "severity": "WARNING",
                    "type": "model_number_lookup_rule",
                    "trim": trim,
                    "message": f"[LOOKUP_ERROR] {str(e)}",
                })

    # Enrich each language version
    for lang, df in transformed.items():
        if df is None or df.empty:
            enriched_dict[lang] = df
            continue

        enriched_dict[lang] = _add_model_number_columns(df, trim_col, trim_lookup_cache)

    return enriched_dict, metadata, all_warnings


def _add_model_number_columns(
    df: pd.DataFrame,
    trim_column: str,
    trim_lookup_cache: Dict[str, Optional[SearchResult]],
) -> pd.DataFrame:
    """Add model_number and model_status columns to DataFrame.

    Args:
        df: Input DataFrame from Step 4 transformation
        trim_column: Name of the trim column (e.g., "trim_level")
        trim_lookup_cache: Cached trim → SearchResult mapping

    Returns:
        DataFrame with added model_number and model_status columns
    """
    if df is None or df.empty:
        return df

    df = df.copy()
    df["model_number"] = None
    df["model_status"] = "NOT_FOUND"

    for idx, row in df.iterrows():
        # Get trim value for this row
        if trim_column not in row.index:
            continue

        trim_val = row[trim_column]
        if pd.isna(trim_val):
            continue

        trim_str = str(trim_val).strip()

        # Look up in cache
        if trim_str in trim_lookup_cache:
            result = trim_lookup_cache[trim_str]
            if result:
                df.at[idx, "model_number"] = result.model_number
                # Map confidence to status
                if result.confidence >= 0.95:
                    df.at[idx, "model_status"] = "EXACT_MATCH"
                elif result.confidence >= 0.80:
                    df.at[idx, "model_status"] = "HIGH_CONFIDENCE"
                elif result.confidence > 0:
                    df.at[idx, "model_status"] = "LOW_CONFIDENCE"
                else:
                    df.at[idx, "model_status"] = "NOT_FOUND"

    return df
