from typing import Any, Dict, List, Tuple
from pathlib import Path

import pandas as pd

from core.helpers.dq_logger import DQLogger
from core.helpers.keyword_extractor import KeywordExtractor
from core.helpers.pipeline_logger import PipelineLogger
from accy_v2.model_lookup.search_engine import VehicleSearchEngine, diagnose_search_failure
from accy_v2.model_lookup.models.manufacture_module import find_model_line, load_existing_csv, save_vehicle_models_to_csv
from accy_v2.model_lookup.chrome_api.service import ADSService


def run(
    transformed: Dict[str, pd.DataFrame],
    meta_data: Dict[str, Any],
    config: dict,
    dq_logger: DQLogger,
    pipeline_logger: PipelineLogger,
    ads_attempted: set = None,
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

    Args:
        transformed: Dict of {language: DataFrame} from Step 4 (melted)
        meta_data: Metadata including vehicle_year, model_name, sheet_name
        config: Configuration including model_lookup_rules
        dq_logger: Data quality logger
        pipeline_logger: Pipeline logger

    Returns:
        Dict of {language: enriched_DataFrame} with model_number and model_number_status columns
    """
    sheet_name = meta_data.get("sheet_name", "unknown")
    model_name = meta_data.get("model_name", "unknown")
    vehicle_year = meta_data.get("vehicle_year")

    if not vehicle_year:
        raise ValueError(f"vehicle_year not found in meta_data for sheet '{sheet_name}'")

    vehicle_make = _extract_make_from_model_name(model_name)
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
        f"Sheet '{sheet_name}': Unique trims identified: {unique_trims}"
    )

    # Extract keywords from sheet_name to get fuel_type (if applicable)
    try:
        sheet_info = extractor.extract_from_sheet_name(sheet_name)
        fuel_type = sheet_info.get("fuel_type")
    except Exception as e:
        fuel_type = None
        pipeline_logger.debug(f"Could not extract fuel_type from sheet_name: {str(e)}")

    # Get model_name from meta_data (extracted in Step 1 from cell (0,0))
    # This is the actual model name from the data
    model_keywords_from_data = []
    if model_name:
        # Split model_name which is already normalized (e.g., "outlander_phev" or "outlander_es")
        # Remove the year (first part if it's all digits) as it's used for filtering only
        parts = [kw.strip() for kw in model_name.lower().replace("-", "_").split("_") if kw.strip()]

        # Filter out year keywords (4-digit numbers)
        model_keywords_from_data = [kw for kw in parts if not (len(kw) == 4 and kw.isdigit())]

    pipeline_logger.debug(
        f"Sheet '{sheet_name}': model_keywords from data={model_keywords_from_data}, fuel_type={fuel_type}"
    )

    # ===== MODEL-LINE GATE: Check if model line exists locally, or refresh from ADS =====
    csv_path = str(Path(__file__).parent.parent.parent.parent / "model_lookup" / "db" / "db_vehicle_models.csv")
    configs_dir = str(Path(__file__).parent.parent.parent.parent / "model_lookup" / "configs")

    local_df = load_existing_csv(csv_path)
    model_line_df = find_model_line(local_df, vehicle_make, vehicle_year, model_name)

    if model_line_df.empty:
        cache_key = (vehicle_make, model_name, vehicle_year)
        if ads_attempted is None:
            ads_attempted = set()

        if cache_key not in ads_attempted:
            ads_attempted.add(cache_key)
            pipeline_logger.info(f"  Model line '{model_name}' not in local db; attempting ADS refresh...")

            try:
                ads_service = ADSService(pipeline_logger=pipeline_logger, dq_logger=dq_logger)
                ads_result = ads_service.fetch_vehicle(vehicle_make, model_name, vehicle_year)

                if not ads_result.empty:
                    pipeline_logger.info(f"  ADS returned {len(ads_result)} rows for {vehicle_make} {vehicle_year} {model_name}; saving to db...")
                    save_vehicle_models_to_csv(ads_result, csv_path=csv_path, configs_dir=configs_dir, dq_logger=dq_logger)
                    local_df = load_existing_csv(csv_path)
                    model_line_df = find_model_line(local_df, vehicle_make, vehicle_year, model_name)
                else:
                    pipeline_logger.warning(f"  ADS returned no results for {vehicle_make} {vehicle_year} {model_name}")
            except Exception as e:
                dq_logger.log_warning(
                    sheet_name=sheet_name, model_name=model_name, record_index=None,
                    record_snapshot={}, rule_violated="model_number_lookup_rule",
                    issue_description=f"[ADS_FETCH_ERROR] Failed to fetch from ADS: {str(e)}"
                )
                pipeline_logger.warning(f"  ADS fetch failed: {str(e)}")
    # ===== END MODEL-LINE GATE =====

    # Batch lookup: one per unique trim
    model_mapping, missing_trims = _batch_lookup_model_numbers(
        year=vehicle_year,
        model_name=model_name,
        sheet_name=sheet_name,
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
            missing_trims=missing_trims,
            vehicle_year=vehicle_year,
            trim_col=trim_col,
            sheet_name=sheet_name,
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
    sheet_name: str,
    trims: List[str],
    model_keywords: List[str],
    fuel_type: str,
    extractor: KeywordExtractor,
    vehicle_make: str,
    oem_config: Dict[str, Any],
    dq_logger: DQLogger,
    pipeline_logger: PipelineLogger,
) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """
    Lookup model number for each unique trim (one lookup per trim, not per row).

    Combines:
    - model_keywords: from meta_data["model_name"] (extracted in Step 1)
    - fuel_type: from sheet_name (if applicable)
    - trim_keywords: from trim column

    Returns:
        - model_mapping: {trim: {model_number, drivetrain, fuel_type, color, package}}
        - missing_trims: [trim1, trim2] where lookup failed
    """
    model_mapping = {}
    missing_trims = []

    # Initialize search engine once for this batch of lookups
    csv_path = str(Path(__file__).parent.parent.parent.parent / "model_lookup" / "db" / "db_vehicle_models.csv")
    configs_dir = str(Path(__file__).parent.parent.parent.parent / "model_lookup" / "configs")
    engine = VehicleSearchEngine(csv_path=csv_path, configs_dir=configs_dir, oem_config=oem_config, pipeline_logger=pipeline_logger)

    # Get color_keywords from config (if available)
    color_keywords = []
    if isinstance(oem_config, dict):
        # Try nested path first (brands -> Mitsubishi -> color_keywords)
        if "brands" in oem_config and vehicle_make in oem_config.get("brands", {}):
            color_keywords = oem_config["brands"][vehicle_make].get("color_keywords", [])
        # Also try flat path (color_keywords at top level)
        elif "color_keywords" in oem_config:
            color_keywords = oem_config.get("color_keywords", [])

    for trim in trims:
        # Extract trim keywords and combine with model + fuel_type keywords
        trim_keywords = extractor.extract_from_trim(trim)
        keywords = extractor.combine_keywords(model_keywords, trim_keywords, fuel_type)

        if not keywords:
            pipeline_logger.warning(
                f"Sheet '{sheet_name}' trim '{trim}': No keywords extracted"
            )
            dq_logger.log_warning(
                sheet_name=sheet_name,
                model_name=model_name,
                record_index=None,
                record_snapshot={"trim": trim},
                rule_violated="model_number_lookup_rule",
                issue_description=f"No keywords extracted for trim '{trim}'",
            )
            missing_trims.append(trim)
            continue

        pipeline_logger.debug(
            f"Sheet '{sheet_name}' trim '{trim}': Searching with keywords={keywords}"
        )

        # Search for model number using new search engine
        try:
            result = engine.search(make=vehicle_make, year=int(year), raw_keywords=keywords)

            if result is not None:
                model_number = result.model_number
                # Store richer metadata from SearchResult (not just model_number)
                model_mapping[trim] = {
                    "model_number": model_number,
                    "drivetrain": result.drivetrain,
                    "fuel_type": result.fuel_type,
                    "color": result.color,
                    "package": result.package,
                }
                pipeline_logger.debug(
                    f"  [OK] Found model_number='{model_number}' confidence={result.confidence:.2f} "
                    f"drivetrain={result.drivetrain} fuel_type={result.fuel_type} "
                    f"for {vehicle_make} {year} {trim}"
                )

            else:
                # No match or ambiguous (confidence = 0)
                missing_trims.append(trim)

                # Diagnose the failure reason (why search returned None)
                csv_path = str(Path(__file__).parent.parent.parent.parent / "model_lookup" / "db" / "db_vehicle_models.csv")

                # Classify keywords to pass to diagnostic function
                from accy_v2.model_lookup.semantic.classifier import load_classification_config, classify_tokens
                from accy_v2.model_lookup.semantic.translator import load_oem_translator, translate_keywords

                configs_dir = str(Path(__file__).parent.parent.parent.parent / "model_lookup" / "configs")
                oem_translator = load_oem_translator(vehicle_make, configs_dir)
                translated = translate_keywords(keywords, oem_translator)
                classification_config = load_classification_config(vehicle_make, configs_dir)
                classified = classify_tokens(translated, classification_config, pipeline_logger)

                diagnostic = diagnose_search_failure(vehicle_make, year, classified, csv_path)
                failure_reason = diagnostic.get("reason", "UNKNOWN")
                failure_details = diagnostic.get("details", "No details available")

                dq_logger.log_warning(
                    sheet_name=sheet_name,
                    model_name=model_name,
                    record_index=None,
                    record_snapshot={"trim": trim, "keywords": keywords},
                    rule_violated="model_number_lookup_rule",
                    issue_description=(
                        f"[{failure_reason}] {vehicle_make} {year} {trim}: {failure_details}"
                    ),
                )
                pipeline_logger.warning(
                    f"  [NOT_FOUND] {vehicle_make} {year} {trim} | Reason: {failure_reason} | {failure_details}"
                )

        except Exception as e:
            missing_trims.append(trim)
            dq_logger.log_warning(
                sheet_name=sheet_name,
                model_name=model_name,
                record_index=None,
                record_snapshot={"trim": trim, "keywords": keywords},
                rule_violated="model_number_lookup_rule",
                issue_description=f"Error during model number lookup for trim '{trim}': {str(e)}",
            )
            pipeline_logger.warning(
                f"  [ERROR] {vehicle_make} {year} {trim}: {str(e)}"
            )

    return model_mapping, missing_trims


def _add_model_number_columns(
    df: pd.DataFrame,
    model_mapping: Dict[str, Dict[str, Any]],
    missing_trims: List[str],
    vehicle_year: int,
    trim_col: str,
    sheet_name: str,
    model_name: str,
    dq_logger: DQLogger,
    pipeline_logger: PipelineLogger,
) -> pd.DataFrame:
    """
    Add model_number, drivetrain, fuel_type, color, and package columns to DataFrame.
    Extract each field from the model_mapping dict entries.
    """
    df = df.copy()

    # Map each field from the metadata dict stored in model_mapping
    def extract_field(trim_val, field_name):
        if trim_val in model_mapping and isinstance(model_mapping[trim_val], dict):
            return model_mapping[trim_val].get(field_name)
        return None

    # Extract model_number (and others) based on trim
    df["model_number"] = df[trim_col].apply(lambda trim: extract_field(trim, "model_number"))
    df["drivetrain"] = df[trim_col].apply(lambda trim: extract_field(trim, "drivetrain"))
    df["fuel_type"] = df[trim_col].apply(lambda trim: extract_field(trim, "fuel_type"))
    df["color"] = df[trim_col].apply(lambda trim: extract_field(trim, "color"))
    df["package"] = df[trim_col].apply(lambda trim: extract_field(trim, "package"))

    # Add status column
    df["model_number_status"] = df["model_number"].apply(
        lambda x: "yes - Model number found" if pd.notna(x) else "no - missing model number"
    )

    # Count rows with and without model numbers
    rows_total = len(df)
    rows_with_model = len(df[df["model_number"].notna()])
    rows_without_model = len(df[df["model_number"].isna()])

    pipeline_logger.debug(
        f"Sheet '{sheet_name}': {rows_total} total rows. {rows_with_model} rows with model numbers, "
        f"{rows_without_model} rows with missing model numbers. "
        f"Drivetrain: {df['drivetrain'].notna().sum()} rows, Fuel Type: {df['fuel_type'].notna().sum()} rows"
    )

    # Return ALL rows, including those with missing model_number
    # Rows with missing model_number will have empty ModelNumber column in output for manual correction
    return df


def _extract_make_from_model_name(model_name: str) -> str:
    return "Mitsubishi"
