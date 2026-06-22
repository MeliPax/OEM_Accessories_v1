from typing import Any, Dict, List, Tuple
from pathlib import Path

import pandas as pd

from core.helpers.dq_logger import DQLogger
from core.helpers.keyword_extractor import KeywordExtractor
from core.helpers.pipeline_logger import PipelineLogger
from model_lookup.models.manufacture_module import search_models_by_description


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
    dq_logger: DQLogger,
    pipeline_logger: PipelineLogger,
) -> Tuple[Dict[str, str], List[str]]:
    """
    Lookup model number for each unique trim (one lookup per trim, not per row).

    Combines:
    - model_keywords: from meta_data["model_name"] (extracted in Step 1)
    - fuel_type: from sheet_name (if applicable)
    - trim_keywords: from trim column

    Returns:
        - model_mapping: {trim: model_number} where model_number is string or None
        - missing_trims: [trim1, trim2] where lookup failed
    """
    model_mapping = {}
    missing_trims = []

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

        # Search for model number
        try:
            # Path: accy_v2/oems/mitsubishi/pipeline/step4_5_model_enrichment.py
            # Up 4 levels to accy_v2, then up 1 more to project root
            csv_path = str(Path(__file__).parent.parent.parent.parent.parent / "model_lookup" / "db" / "db_vehicle_models.csv")
            results = search_models_by_description(
                make=vehicle_make, year=int(year), keywords=keywords, csv_path=csv_path
            )

            if len(results) == 1:
                model_number = results.iloc[0]["ModelNumber"]
                model_mapping[trim] = model_number
                pipeline_logger.debug(
                    f"  ✓ Found model_number='{model_number}' for {vehicle_make} {year} {trim}"
                )

            elif len(results) == 0:
                missing_trims.append(trim)
                dq_logger.log_warning(
                    sheet_name=sheet_name,
                    model_name=model_name,
                    record_index=None,
                    record_snapshot={"trim": trim, "keywords": keywords},
                    rule_violated="model_number_lookup_rule",
                    issue_description=(
                        f"No model number found for {vehicle_make} {year} {trim} "
                        f"with keywords: {keywords}"
                    ),
                )
                pipeline_logger.warning(
                    f"  ✗ Not found: {vehicle_make} {year} {trim} keywords={keywords}"
                )

            else:
                missing_trims.append(trim)
                matching_models = results["ModelNumber"].tolist()
                dq_logger.log_warning(
                    sheet_name=sheet_name,
                    model_name=model_name,
                    record_index=None,
                    record_snapshot={"trim": trim, "keywords": keywords},
                    rule_violated="model_number_lookup_rule",
                    issue_description=(
                        f"Ambiguous match: {len(results)} model numbers found for "
                        f"{vehicle_make} {year} {trim} with keywords {keywords}: {matching_models}"
                    ),
                )
                pipeline_logger.warning(
                    f"  ✗ Ambiguous ({len(results)} matches): {vehicle_make} {year} {trim}"
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
                f"  ✗ Error: {vehicle_make} {year} {trim}: {str(e)}"
            )

    return model_mapping, missing_trims


def _add_model_number_columns(
    df: pd.DataFrame,
    model_mapping: Dict[str, str],
    missing_trims: List[str],
    vehicle_year: int,
    trim_col: str,
    sheet_name: str,
    model_name: str,
    dq_logger: DQLogger,
    pipeline_logger: PipelineLogger,
) -> pd.DataFrame:
    """
    Add model_number and model_number_status columns to DataFrame.
    Exclude rows where trim is in missing_trims.
    """
    df = df.copy()

    # Map model_number based on trim
    df["model_number"] = df[trim_col].map(model_mapping)

    # Add status column
    df["model_number_status"] = df["model_number"].apply(
        lambda x: "yes - Model number found" if pd.notna(x) else "no - missing model number"
    )

    # Count before exclusion
    rows_before = len(df)

    # Exclude rows with missing model numbers (missing_trims)
    rows_to_exclude = df[df[trim_col].isin(missing_trims)]
    excluded_count = len(rows_to_exclude)

    df_filtered = df[~df[trim_col].isin(missing_trims)].copy()

    rows_after = len(df_filtered)

    pipeline_logger.debug(
        f"Sheet '{sheet_name}': {rows_before} rows before, {excluded_count} excluded "
        f"(missing trims: {missing_trims}), {rows_after} rows in output"
    )

    return df_filtered


def _extract_make_from_model_name(model_name: str) -> str:
    return "Mitsubishi"
