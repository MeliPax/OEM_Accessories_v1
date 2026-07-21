from typing import Any, Dict, List, Tuple
from pathlib import Path

import pandas as pd

from core.helpers.dq_logger import DQLogger
from core.helpers.keyword_extractor import KeywordExtractor
from core.helpers.pipeline_logger import PipelineLogger
from accy_v2.model_lookup.search_engine import VehicleSearchEngine


def run(
    transformed: Dict[str, pd.DataFrame],
    meta_data: Dict[str, Any],
    config: dict,
    dq_logger: DQLogger,
    pipeline_logger: PipelineLogger,
) -> Dict[str, pd.DataFrame]:
    """
    Enrich transformed data with model numbers via batch lookup.

    Process:
    1. Get unique trims from melted data
    2. For EACH unique trim, do ONE lookup (batch lookup, not per-row)
    3. Store mapping: {trim: model_number}
    4. For each language, add model_number and model_number_status columns
    5. Exclude rows where trim lookup failed
    6. Return enriched DataFrames with model_number and model_number_status

    Hyundai-specific:
    - Manufacturer is routed from meta_data (Hyundai or Genesis)
    - Trim keywords are space-separated in the data (e.g., "Ult HEV"), not underscore-joined
      Pre-process by replacing spaces with underscores before extracting via KeywordExtractor
    - Model keywords are split from the model name (e.g., "Santa Fe" -> ["santa", "fe"])
    """
    group_key = meta_data.get("group_key", "unknown")
    model_name = meta_data.get("model_name", "unknown")
    vehicle_year = meta_data.get("vehicle_year")
    vehicle_make = meta_data.get("manufacturer", "Hyundai")

    if not vehicle_year:
        raise ValueError(f"vehicle_year not found in meta_data for group '{group_key}'")

    oem_config = config.get("model_lookup_rules", {}).get(vehicle_make)

    if not oem_config:
        raise ValueError(
            f"No model_lookup_rules configured for make: {vehicle_make}. "
            f"Available: {list(config.get('model_lookup_rules', {}).keys())}"
        )

    extractor = KeywordExtractor(oem_config, pipeline_logger)

    # Get unique trims from any language version (same trims in both EN/FR)
    first_lang_df = next(iter(transformed.values()))
    trim_col = oem_config.get("trim_column", "trim_level")
    unique_trims = sorted(first_lang_df[trim_col].unique().tolist())

    pipeline_logger.debug(
        f"Group '{group_key}': Unique trims identified: {unique_trims}"
    )

    # Extract model keywords from model_name (group key is f"{year}_{model_slug}")
    # Model slug is already lower/underscore-joined (e.g., "santa_fe" for "Santa Fe")
    model_keywords_from_data = model_name.replace("-", "_").split("_")
    model_keywords_from_data = [kw.strip() for kw in model_keywords_from_data if kw.strip()]

    # Hyundai has no sheet-name fuel_type extraction (fuel comes from trim strings)
    fuel_type = None

    pipeline_logger.debug(
        f"Group '{group_key}': model_keywords from data={model_keywords_from_data}, fuel_type={fuel_type}"
    )

    # Batch lookup: one per unique trim
    model_mapping, duplicate_trims, missing_trims = _batch_lookup_model_numbers(
        year=vehicle_year,
        model_name=model_name,
        group_key=group_key,
        trims=unique_trims,
        model_keywords=model_keywords_from_data,
        fuel_type=fuel_type,
        extractor=extractor,
        vehicle_make=vehicle_make,
        oem_config=oem_config,
        dq_logger=dq_logger,
        pipeline_logger=pipeline_logger,
    )

    # Enrich each language version
    enriched_dict = {}
    for lang, df in transformed.items():
        enriched_df = _add_model_number_columns(
            df=df,
            model_mapping=model_mapping,
            duplicate_trims=duplicate_trims,
            missing_trims=missing_trims,
            vehicle_year=vehicle_year,
            trim_col=trim_col,
            group_key=group_key,
            model_name=model_name,
            dq_logger=dq_logger,
            pipeline_logger=pipeline_logger,
        )
        enriched_dict[lang] = enriched_df

    return enriched_dict


# -----------------------------------------------------------------------
# Private Helpers
# -----------------------------------------------------------------------


def _batch_lookup_model_numbers(
    year: int,
    model_name: str,
    group_key: str,
    trims: List[str],
    model_keywords: List[str],
    fuel_type: str,
    extractor: KeywordExtractor,
    vehicle_make: str,
    oem_config: Dict[str, any],
    dq_logger: DQLogger,
    pipeline_logger: PipelineLogger,
) -> Tuple[Dict[str, List[str]], set, List[str]]:
    """
    Lookup model number for each unique trim (one lookup per trim, not per row).

    Combines:
    - model_keywords: from model_name (e.g., ["santa", "fe"])
    - fuel_type: None for Hyundai (fuel comes from trim keywords)
    - trim_keywords: from trim column (preprocessed: spaces -> underscores)

    Returns:
        - model_mapping: {trim: [model_number, ...]} where model_numbers is a list (len 1 normally, >1 for duplicates)
        - duplicate_trims: set of trims resolved via the duplicate-code path
        - missing_trims: [trim1, trim2] where lookup failed
    """
    model_mapping = {}
    duplicate_trims = set()
    missing_trims = []

    # Initialize search engine once for this batch of lookups
    csv_path = str(Path(__file__).parent.parent.parent.parent / "model_lookup" / "db" / "db_vehicle_models.csv")
    configs_dir = str(Path(__file__).parent.parent.parent.parent / "model_lookup" / "configs")
    engine = VehicleSearchEngine(
        csv_path=csv_path,
        configs_dir=configs_dir,
        oem_config=oem_config,
        ignore_keyword_categories=oem_config.get("ignore_keyword_categories", []),
        pipeline_logger=pipeline_logger,
    )

    for trim in trims:
        # Preprocess trim: spaces -> underscores (Hyundai trims are space-separated like "Ult HEV", "3.5T Sport")
        trim_normalized = trim.replace(" ", "_")

        # Extract trim keywords using the normalized form
        trim_keywords = extractor.extract_from_trim(trim_normalized)
        keywords = extractor.combine_keywords(model_keywords, trim_keywords, fuel_type)

        if not keywords:
            pipeline_logger.warning(
                f"Group '{group_key}' trim '{trim}': No keywords extracted"
            )
            dq_logger.log_warning(
                sheet_name=group_key,
                model_name=model_name,
                record_index=None,
                record_snapshot={"trim": trim},
                rule_violated="model_number_lookup_rule",
                issue_description=(
                    f"[KEYWORD_EXTRACTION_FAILED] {vehicle_make} {year} {trim}: "
                    f"No keywords extracted from trim value. The trim field may be empty, "
                    f"contain only ignored tokens (e.g., interior colors), or have unrecognized abbreviations."
                ),
            )
            missing_trims.append(trim)
            continue

        pipeline_logger.debug(
            f"Group '{group_key}' trim '{trim}': Searching with keywords={keywords}"
        )

        # Search for model number using the search engine
        try:
            result = engine.search(make=vehicle_make, year=int(year), raw_keywords=keywords)

            if result is not None:
                model_mapping[trim] = result.model_numbers
                if result.is_duplicate_group:
                    duplicate_trims.add(trim)
                pipeline_logger.debug(
                    f"  [OK] Found model_number(s)={result.model_numbers} confidence={result.confidence:.2f} "
                    f"for {vehicle_make} {year} {trim}"
                )

            else:
                # No match or ambiguous (confidence = 0)
                missing_trims.append(trim)
                diagnostic = _categorize_search_failure(
                    vehicle_make=vehicle_make,
                    year=year,
                    trim=trim,
                    keywords=keywords,
                )
                dq_logger.log_warning(
                    sheet_name=group_key,
                    model_name=model_name,
                    record_index=None,
                    record_snapshot={"trim": trim, "keywords": keywords},
                    rule_violated="model_number_lookup_rule",
                    issue_description=diagnostic,
                )
                pipeline_logger.warning(
                    f"  [NOT_FOUND] {vehicle_make} {year} {trim} keywords={keywords}"
                )

        except Exception as e:
            missing_trims.append(trim)
            dq_logger.log_warning(
                sheet_name=group_key,
                model_name=model_name,
                record_index=None,
                record_snapshot={"trim": trim, "keywords": keywords},
                rule_violated="model_number_lookup_rule",
                issue_description=(
                    f"[LOOKUP_ERROR] {vehicle_make} {year} {trim}: "
                    f"Unexpected error during model lookup: {str(e)}. "
                    f"Keywords searched: {keywords}. Check logs for full stack trace."
                ),
            )
            pipeline_logger.warning(
                f"  [ERROR] {vehicle_make} {year} {trim}: {str(e)}"
            )

    return model_mapping, duplicate_trims, missing_trims


def _add_model_number_columns(
    df: pd.DataFrame,
    model_mapping: Dict[str, List[str]],
    duplicate_trims: set,
    missing_trims: List[str],
    vehicle_year: int,
    trim_col: str,
    group_key: str,
    model_name: str,
    dq_logger: DQLogger,
    pipeline_logger: PipelineLogger,
) -> pd.DataFrame:
    """
    Add model_number and model_number_status columns to DataFrame.
    For duplicate-code trims, explode rows (one output per model number).
    Exclude rows where trim is in missing_trims.
    """
    df = df.copy()

    # Map trim -> list of model numbers (len 1 normally, >1 for duplicate codes)
    df["model_number"] = df[trim_col].map(model_mapping)

    # Flag rows resolved via the duplicate-model-number path, before exploding
    df["_is_duplicate_match"] = df[trim_col].isin(duplicate_trims)

    # Explode: one output row per model number (no-op for length-1 lists)
    df = df.explode("model_number", ignore_index=True)

    # Add status column
    df["model_number_status"] = df["model_number"].apply(
        lambda x: "yes - Model number found" if pd.notna(x) else "no - missing model number"
    )

    # For duplicate-matched rows, update the status to distinguish them for QA
    df.loc[df["_is_duplicate_match"] & df["model_number"].notna(), "model_number_status"] = (
        "yes - Model number found (duplicate model code)"
    )

    # Remove the internal flag column
    df = df.drop(columns=["_is_duplicate_match"])

    # Count before exclusion
    rows_before = len(df)

    # Exclude rows with missing model numbers (missing_trims)
    rows_to_exclude = df[df[trim_col].isin(missing_trims)]
    excluded_count = len(rows_to_exclude)

    df_filtered = df[~df[trim_col].isin(missing_trims)].copy()

    rows_after = len(df_filtered)

    pipeline_logger.debug(
        f"Group '{group_key}': {rows_before} rows before, {excluded_count} excluded "
        f"(missing trims: {missing_trims}), {rows_after} rows in output"
    )

    return df_filtered


def _categorize_search_failure(
    vehicle_make: str,
    year: int,
    trim: str,
    keywords: list,
) -> str:
    """
    Create diagnostic error message categorizing why model lookup failed.

    Message format: [CATEGORY] Description with actionable info

    Categories:
    - DATABASE_NO_MATCH: Keywords translated/classified correctly, but no database records
    - POSSIBLE_DATA_MISMATCH: Trim requested but not in database for this model/year
    - AMBIGUOUS_SEARCH: Multiple candidates, couldn't resolve to single model

    Args:
        vehicle_make: "Hyundai" or "Genesis"
        year: Model year (2024, 2025, etc.)
        trim: Trim name as requested (e.g., "Ultimate", "Trend")
        keywords: Translated/classified keywords used for search

    Returns:
        Detailed diagnostic message suitable for Excel _Data_Issues sheet
    """
    # Construct message with category prefix
    message = (
        f"[DATABASE_NO_MATCH] {vehicle_make} {year} {trim}: "
        f"No model number found. Keywords searched: {keywords}. "
        f"→ This model/trim combination may not exist in the vehicle database for {year}. "
        f"Verify: (1) trim name is correct, (2) this year/model combo is in DB, "
        f"(3) trim is not listed as a package modifier."
    )
    return message
