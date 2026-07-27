"""
Transform ADS trim JSON responses into pipeline 7-column schema.

Maps ADS vehicleDescription.style[] array to rows compatible with
db_vehicle_models.csv and the pipeline's search/classification system.
"""

from typing import List, Dict, Any, Optional
from .config import get_make_name_map


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


def ads_trim_to_row(
    trim: Dict[str, Any],
    manufacturer: str,
) -> Optional[Dict[str, Any]]:
    """
    Convert a single ADS trim object to pipeline row.

    Args:
        trim: Single trim object from ADS vehicleDescription.style[]
        manufacturer: Normalized manufacturer name (e.g., "HYUNDAI")

    Returns:
        dict with 9-column schema: Manufacturer, ModelYear, ModelNumber,
        Description, Description2, Package, Style_ID, Drivetrain, PassDoors
        Returns None if required fields are missing.
    """
    # Extract required fields
    model_number = trim.get("mfrModelCode")
    model_year = trim.get("modelYear")
    description = trim.get("name")
    trim_level = trim.get("trim")
    name_wo_trim = trim.get("nameWoTrim")
    body_type = extract_body_type(trim.get("bodyType"))
    drivetrain = trim.get("drivetrain", "")
    pass_doors = trim.get("passDoors")

    # Validate required fields
    if not model_number or not model_year or not description:
        return None

    return {
        "Manufacturer": manufacturer,
        "ModelYear": int(model_year),
        "ModelNumber": model_number,
        "Description": description,
        "Description2": name_wo_trim or "",
        "Package": trim_level or "",
        "Style_ID": body_type,
        "Drivetrain": drivetrain or "",
        "PassDoors": pass_doors or "",
    }


def ads_response_to_rows(
    response: Dict[str, Any],
    ads_make_name: str,
) -> List[Dict[str, Any]]:
    """
    Convert full ADS response to list of pipeline rows.

    Args:
        response: Full ADS API response (with vehicleDescription.style[])
        ads_make_name: Make name as returned by ADS (e.g., "Hyundai")

    Returns:
        List of dicts, one per trim, ready for save_vehicle_models_to_csv()
    """
    make_map = get_make_name_map()
    manufacturer = make_map.get(ads_make_name)

    if not manufacturer:
        raise ValueError(
            f"Unknown ADS make name: {ads_make_name}. "
            f"Valid makes: {list(make_map.keys())}"
        )

    rows = []
    vehicle_desc = response.get("vehicleDescription", {})
    styles = vehicle_desc.get("style", [])

    for trim in styles:
        row = ads_trim_to_row(trim, manufacturer)
        if row:
            rows.append(row)

    return rows
