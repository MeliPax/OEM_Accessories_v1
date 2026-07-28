"""
Transform ADS trim JSON responses into pipeline 10-column schema.

Maps ADS vehicleDescription.style[] array to rows compatible with
db_vehicle_models.csv and the pipeline's search/classification system.

Includes engine_type extraction from ModelName and Description using
configuration-driven ENGINE_TYPE keywords and translator rules.
"""

import logging
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from .config import get_make_name_map

logger = logging.getLogger(__name__)


def extract_model_name_from_model_number(model_number: str, manufacturer: str) -> str:
	"""
	Extract human-readable model name from OEM model code.
	This is a fallback; primary extraction should use model.value field.

	Args:
		model_number: OEM model code (e.g., "ELCS4V2BES00" for Hyundai Elantra)
		manufacturer: Normalized manufacturer name (e.g., "HYUNDAI")

	Returns:
		Model name (e.g., "Elantra") or empty string if not recognized
	"""
	if not model_number:
		return ""

	manufacturer = manufacturer.upper()
	prefix = model_number[:2].upper()

	# OEM-specific model code mappings (fallback only; prefer model.value from ADS)
	if manufacturer == "HYUNDAI":
		codes = {
			"EL": "Elantra", "IO": "Ioniq", "SO": "Sonata",
			"TU": "Tucson", "KO": "Kona", "VE": "Venue",
			"SA": "Santa Fe", "EX": "Excel"
		}
		return codes.get(prefix, "")

	elif manufacturer == "GENESIS":
		codes = {
			"I5": "Ioniq5", "G7": "G70", "G8": "G80",
			"GV": "GV70"
		}
		return codes.get(prefix, "")

	elif manufacturer == "MAZDA":
		# Mazda model codes: HV = CX-5, etc.
		codes = {
			"HV": "CX-5",
		}
		return codes.get(prefix, "")

	elif manufacturer == "MITSUBISHI":
		# Mitsubishi codes: CE = Outlander, etc.
		codes = {
			"CE": "Outlander",
		}
		return codes.get(prefix, "")

	elif manufacturer == "HONDA":
		# Honda codes: CV = Civic, HV = HR-V, etc.
		codes = {
			"CV": "Civic",
			"HV": "HR-V",
		}
		return codes.get(prefix, "")

	return ""


def extract_body_type(body_type_array: Optional[List[Dict[str, Any]]]) -> str:
    """
    Extract primary body type from ADS bodyType array.

    Args:
        body_type_array: ADS bodyType array, typically [{"value": "4dr Car", "primary": true}]

    Returns:
        Body type value string (e.g., "4dr Car") or empty string if not found
    """
    if not body_type_array:
        return ""

    for bt in body_type_array:
        if isinstance(bt, dict) and bt.get("primary"):
            return bt.get("value", "")

    # Fallback: use first if no primary marked
    if body_type_array and isinstance(body_type_array[0], dict):
        return body_type_array[0].get("value", "")

    return ""


def load_engine_type_keywords(classification: Dict[str, Any], manufacturer: str) -> List[str]:
    """
    Dynamically load ENGINE_TYPE keywords from classification.json.

    Reads the fuel_type_category metadata to identify which keywords
    represent engine/fuel types (e.g., "ev", "hybrid", "phev").

    Args:
        classification: Loaded classification.json dict
        manufacturer: OEM name (e.g., "HYUNDAI") for logging

    Returns:
        List of keywords marked as ENGINE_TYPE, or empty list if none found

    Logs:
        - INFO: Keywords loaded successfully
        - WARNING: Missing fuel_type_category metadata
        - ERROR: Failed to process classification
    """
    try:
        # Get fuel category name from metadata
        fuel_category = classification.get("fuel_type_category", "ENGINE_TYPE")

        if fuel_category != "ENGINE_TYPE":
            logger.warning(
                f"mapper | {manufacturer} | Unexpected fuel_type_category: '{fuel_category}' "
                f"(expected 'ENGINE_TYPE'). Using 'ENGINE_TYPE' anyway."
            )
            fuel_category = "ENGINE_TYPE"

        # Extract all keywords with ENGINE_TYPE category
        token_map = classification.get("token_map", {})
        engine_keywords = [
            keyword
            for keyword, category in token_map.items()
            if category == fuel_category
        ]

        logger.info(
            f"mapper | {manufacturer} | Loaded {len(engine_keywords)} ENGINE_TYPE keywords: "
            f"{engine_keywords}"
        )

        return engine_keywords

    except Exception as e:
        logger.error(
            f"mapper | {manufacturer} | FAILED to load engine keywords | Error: {str(e)}"
        )
        return []


def extract_engine_type(
    model_name: str,
    description: str,
    engine_keywords: List[str],
    translator: Dict[str, Any],
    manufacturer: str,
    model_number: str,
) -> Optional[str]:
    """
    Search for engine type keywords in ModelName and Description.
    Translate the found keyword and return the result.

    Priority: ModelName first (more likely to have model-specific fuel type),
    then Description.

    Args:
        model_name: e.g., "Elantra EV"
        description: e.g., "Essential Ivt"
        engine_keywords: List of keywords to search for
        translator: Translator dict (may be empty if no translator file)
        manufacturer: OEM name for logging
        model_number: OEM model code for logging context

    Returns:
        Translated engine type (e.g., "Electric") or None if not found

    Logs:
        - DEBUG: Searching text, keywords checked
        - DEBUG: Found keyword location
        - INFO: Translation result
        - ERROR: Translation failed
    """
    if not engine_keywords:
        logger.debug(
            f"mapper | {manufacturer} | {model_number} | No engine keywords to search"
        )
        return None

    # Combine text for searching
    full_text = f"{model_name} {description}".lower()

    logger.debug(
        f"mapper | {manufacturer} | {model_number} | Searching text: '{full_text}'"
    )

    # Check each keyword
    found_keyword = None
    for keyword in engine_keywords:
        if keyword.lower() in full_text:
            found_keyword = keyword
            logger.debug(
                f"mapper | {manufacturer} | {model_number} | "
                f"Found keyword '{keyword}' in '{model_name} {description}'"
            )
            break

    if not found_keyword:
        logger.debug(
            f"mapper | {manufacturer} | {model_number} | "
            f"No ENGINE_TYPE keyword found"
        )
        return None

    # Try to translate the found keyword
    try:
        # Search through translator's nested structure
        translated = None

        # First check top-level translations
        if found_keyword.lower() in translator:
            translated = translator[found_keyword.lower()]
        else:
            # Check in categories (some translators have nested structure)
            for category_dict in translator.values():
                if isinstance(category_dict, dict) and found_keyword.lower() in category_dict:
                    translated = category_dict[found_keyword.lower()]
                    break

        if translated:
            logger.info(
                f"mapper | {manufacturer} | {model_number} | "
                f"Translated '{found_keyword}' → '{translated}'"
            )
            return translated
        else:
            logger.warning(
                f"mapper | {manufacturer} | {model_number} | "
                f"Keyword '{found_keyword}' found but NOT in translator. "
                f"Returning keyword as-is."
            )
            return found_keyword

    except Exception as e:
        logger.error(
            f"mapper | {manufacturer} | {model_number} | "
            f"Translation failed for '{found_keyword}' | Error: {str(e)}"
        )
        return None


def ads_trim_to_row(
    trim: Dict[str, Any],
    manufacturer: str,
    classification: Optional[Dict[str, Any]] = None,
    translator: Optional[Dict[str, Any]] = None,
    standardizer: Optional[Any] = None,
) -> Optional[Dict[str, Any]]:
    """
    Convert a single ADS trim object to pipeline row (10 columns).

    Extracts engine_type from ModelName and Description using ENGINE_TYPE
    keywords from classification and translation rules from translator.

    Applies standardization rules to TrimName and Description (e.g., "N Line" → "N-Line").

    Args:
        trim: Single trim object from ADS vehicleDescription.style[]
        manufacturer: Normalized manufacturer name (e.g., "HYUNDAI")
        classification: Loaded classification.json dict (optional, for engine_type extraction)
        translator: Loaded translator dict (optional, for engine_type translation)
        standardizer: DataStandardizer instance (optional, for data standardization)

    Returns:
        dict with 10-column schema: Manufacturer, ModelYear, ModelNumber,
        Description, TrimName, Package, Drivetrain, PassDoors, ModelName, engine_type
        Returns None if required fields are missing.

    Logs:
        - DEBUG: Field extraction progress, standardization applied
        - INFO: Row completion
        - ERROR: Critical processing failures
    """
    try:
        # Extract required fields
        model_number = trim.get("mfrModelCode")
        model_year = trim.get("modelYear")
        description = trim.get("name")
        trim_level = trim.get("trim")
        body_type = extract_body_type(trim.get("bodyType"))
        drivetrain = trim.get("drivetrain", "")
        pass_doors = trim.get("passDoors")
        style_id = trim.get("id")

        logger.debug(
            f"mapper | {manufacturer} | {model_number} | "
            f"Extracted fields: year={model_year}, desc={description}, trim={trim_level}"
        )

        # Validate required fields
        if not model_number or not model_year or not description:
            logger.debug(
                f"mapper | {manufacturer} | {model_number} | "
                f"Skipping row: missing required fields"
            )
            return None

        # Extract model name from ADS model field, fallback to code-based extraction if not available
        model_obj = trim.get("model", {})
        if isinstance(model_obj, dict):
            model_name = model_obj.get("value", "")
        else:
            model_name = ""

        logger.debug(
            f"mapper | {manufacturer} | {model_number} | ModelName from ADS: {model_name}"
        )

        # Fallback: extract from model number using OEM-specific code mappings if model field is empty
        if not model_name:
            model_name = extract_model_name_from_model_number(model_number, manufacturer)
            logger.debug(
                f"mapper | {manufacturer} | {model_number} | "
                f"ModelName fallback from code: {model_name}"
            )

        # Apply standardization rules if standardizer is provided
        if standardizer:
            model_name = standardizer.standardize_model_name(model_name) or model_name
            trim_level = standardizer.standardize_trim_name(trim_level) or trim_level
            description = standardizer.standardize_description(description) or description
            logger.debug(
                f"mapper | {manufacturer} | {model_number} | "
                f"Applied standardization rules"
            )

        # Extract engine_type if classification and translator are provided
        engine_type = None
        if classification and translator:
            engine_keywords = load_engine_type_keywords(classification, manufacturer)
            engine_type = extract_engine_type(
                model_name,
                description,
                engine_keywords,
                translator,
                manufacturer,
                model_number,
            )

        logger.info(
            f"mapper | {manufacturer} | {model_number} | "
            f"Row complete: model={model_name}, trim={description}, engine_type={engine_type}"
        )

        return {
            "Manufacturer": manufacturer,
            "ModelYear": int(model_year),
            "ModelNumber": model_number,
            "Description": description,
            "TrimName": trim_level or "",
            "Package": style_id or "",
            "Drivetrain": drivetrain or "",
            "PassDoors": pass_doors or "",
            "ModelName": model_name,
            "engine_type": engine_type,
        }

    except Exception as e:
        logger.error(
            f"mapper | {manufacturer} | {trim.get('mfrModelCode', 'UNKNOWN')} | "
            f"CRITICAL: Row processing failed | Error: {str(e)}"
        )
        return None


def ads_response_to_rows(
    response: Dict[str, Any],
    ads_make_name: str,
    classification: Optional[Dict[str, Any]] = None,
    translator: Optional[Dict[str, Any]] = None,
    standardizer: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """
    Convert full ADS response to list of pipeline rows (10 columns with engine_type).

    Applies standardization rules (e.g., "N Line" → "N-Line") to all rows.
    Extracts engine_type from keywords.

    Args:
        response: Full ADS API response (with vehicleDescription.style[])
        ads_make_name: Make name as returned by ADS (e.g., "Hyundai")
        classification: Loaded classification.json dict (optional, for engine_type extraction)
        translator: Loaded translator dict (optional, for engine_type translation)
        standardizer: DataStandardizer instance (optional, for data standardization)

    Returns:
        List of dicts (10 columns each), one per trim, ready for save_vehicle_models_to_csv()

    Logs:
        - INFO: Response processing start/progress
        - ERROR: Unknown make name or processing failures
    """
    make_map = get_make_name_map()
    manufacturer = make_map.get(ads_make_name)

    if not manufacturer:
        logger.error(
            f"mapper | ads_response_to_rows | Unknown ADS make: {ads_make_name} | "
            f"Valid makes: {list(make_map.keys())}"
        )
        raise ValueError(
            f"Unknown ADS make name: {ads_make_name}. "
            f"Valid makes: {list(make_map.keys())}"
        )

    rows = []
    vehicle_desc = response.get("vehicleDescription", {})
    styles = vehicle_desc.get("style", [])

    logger.info(
        f"mapper | ads_response_to_rows | {ads_make_name} | "
        f"Processing {len(styles)} trims from ADS response"
    )

    for i, trim in enumerate(styles, 1):
        row = ads_trim_to_row(trim, manufacturer, classification, translator, standardizer)
        if row:
            rows.append(row)

    logger.info(
        f"mapper | ads_response_to_rows | {ads_make_name} | "
        f"Converted {len(rows)}/{len(styles)} trims to rows"
    )

    return rows
