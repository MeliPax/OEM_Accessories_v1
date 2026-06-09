from db_queries.manufacturer import GET_BY_NAME

import pandas as pd
from sqlalchemy import text

"""

    Helpers

"""


import json
from typing import Union, Any
import os
from datetime import datetime

MANUFACTURER_SEARCH_CONFIG = {
    "default": {
        "year_field": "ModelYear",
        "model_field": "ModelNumber",
        "trim_fields": ["Description"],
        "style_field": "Style_ID",
        "package_field": "Package",
    },
    "Hyundai": {
        "trim_fields": ["Description"],
    },
}


def get_manufacturer_config(make: str) -> dict:
    """
    Get the search config for a manufacturer.
    Merges default config with manufacturer-specific overrides.
    """
    config = MANUFACTURER_SEARCH_CONFIG.get("default", {}).copy()
    if make in MANUFACTURER_SEARCH_CONFIG:
        config.update(MANUFACTURER_SEARCH_CONFIG[make])
    return config


def is_valid_year(value: Any) -> bool:
    """
    Validate if a value is a valid year (1900-current year + 5).
    """
    if value is None or value == "":
        return False
    try:
        year = int(value)
        current_year = datetime.now().year
        return 1900 <= year <= current_year + 5
    except (ValueError, TypeError):
        return False


def strip_row_values(row: dict) -> dict:
    """
    Strip whitespace from all values and remove None/empty strings.
    Returns a cleaned dictionary.
    """
    cleaned = {}
    for key, value in row.items():
        if isinstance(value, str):
            value = value.strip()
        cleaned[key] = value if value not in (None, "") else None
    return cleaned


def validate_row_not_null(row: dict, required_fields: list[str] = None) -> bool:
    """
    Check if all required fields are not null.
    If required_fields not specified, checks all fields.
    """
    if required_fields is None:
        required_fields = list(row.keys())

    for field in required_fields:
        if field not in row or row[field] is None or row[field] == "":
            return False
    return True


def load_existing_csv(csv_path: str) -> pd.DataFrame:
    """
    Load existing CSV file. Returns empty DataFrame if file doesn't exist.
    """
    if os.path.exists(csv_path):
        try:
            return pd.read_csv(csv_path)
        except Exception as e:
            print(f"Warning: Could not read existing CSV: {e}")
            return pd.DataFrame()
    return pd.DataFrame()


def check_duplicate_record(
    df_new: pd.DataFrame, df_existing: pd.DataFrame
) -> pd.DataFrame:
    """
    Filter out records that already exist in the database.
    Uses Manufacturer, ModelYear, and ModelNumber as the unique key.
    """
    if df_existing.empty:
        return df_new

    required_cols = ["Manufacturer", "ModelYear", "ModelNumber"]
    existing_cols = [col for col in required_cols if col in df_existing.columns]

    if not existing_cols:
        return df_new

    merge = df_new.merge(
        df_existing[existing_cols],
        on=existing_cols,
        how="left",
        indicator=True,
    )
    return df_new[merge["_merge"] == "left_only"].drop(
        columns=["_merge"], errors="ignore"
    )


def save_vehicle_models_to_csv(df: pd.DataFrame, csv_path: str = None) -> dict:
    """
    Save vehicle models to CSV with validation and deduplication.

    Args:
        df: DataFrame with vehicle model data
        csv_path: Path to CSV file (defaults to db/db_vehicle_models.csv)

    Returns:
        dict with save status, records saved, duplicates skipped, etc.
    """
    if csv_path is None:
        csv_path = "db/db_vehicle_models.csv"

    result = {
        "success": False,
        "total_records": len(df),
        "records_saved": 0,
        "records_skipped": 0,
        "duplicates": 0,
        "invalid_records": 0,
        "file_path": csv_path,
        "file_created": False,
    }

    if df.empty:
        result["message"] = "No data to save"
        return result

    os.makedirs(os.path.dirname(csv_path) or ".", exist_ok=True)

    df_filtered = df.copy()

    required_fields = ["ModelYear", "ModelNumber", "Description"]

    valid_records = []
    for _, row in df_filtered.iterrows():
        cleaned_row = strip_row_values(row.to_dict())

        if not is_valid_year(cleaned_row.get("ModelYear")):
            result["invalid_records"] += 1
            continue

        if not validate_row_not_null(cleaned_row, required_fields):
            result["invalid_records"] += 1
            continue

        valid_records.append(cleaned_row)

    if not valid_records:
        result["message"] = "No valid records to save"
        return result

    df_valid = pd.DataFrame(valid_records)

    df_existing = load_existing_csv(csv_path)

    if not df_existing.empty:
        df_valid = check_duplicate_record(df_valid, df_existing)
        result["duplicates"] = (
            result["total_records"] - result["invalid_records"] - len(df_valid)
        )

    if df_valid.empty:
        result["success"] = True
        result["message"] = "No new data to load — all records already exist"
        return result

    mode = "w" if df_existing.empty else "a"
    header = df_existing.empty

    try:
        df_valid.to_csv(csv_path, mode=mode, header=header, index=False)
        result["records_saved"] = len(df_valid)
        result["records_skipped"] = result["total_records"] - len(df_valid)
        result["success"] = True
        result["file_created"] = not os.path.exists(csv_path) or mode == "w"
        result["message"] = f"Successfully saved {len(df_valid)} records"
    except Exception as e:
        result["message"] = f"Error saving to CSV: {str(e)}"

    return result


def parse_json_string(json_string: str) -> Union[dict, list]:
    """
    Parse a JSON string into a Python object (dict or list).

    Args:
        json_string (str): A valid JSON string.

    Returns:
        dict or list: Parsed JSON object.

    Raises:
        ValueError: If the input is not valid JSON.
        TypeError: If input is not a string.
    """
    if not isinstance(json_string, str):
        raise TypeError("Input must be a JSON string")

    try:
        return json.loads(json_string)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON string: {exc}") from exc


def get_manufacturer_df(engine, make: str) -> pd.DataFrame:
    query = text("""
        SELECT *
        FROM Manufacturer
        WHERE ManufacturerName = :make
            AND ManufacturerStatus = 0
    """)

    return pd.read_sql(query, engine, params={"make": make})


def get_manufacturer_bulletins_json(engine, make: str) -> pd.DataFrame:

    with engine.begin() as conn:
        result = conn.execute(
            text("""
                    SELECT 
                 top(1)       
                 B.BulletinDetails

                    FROM Bulletin B
                    WHERE B.BulletinManufacturer = (
                        SELECT ManufacturerId
                        FROM Manufacturer
                        WHERE ManufacturerName = :make
                            AND ManufacturerStatus = 0
                    )
                    AND B.BulletinStatus = 1
                    ORDER BY B.BulletinEnd DESC
                """),
            {"make": make},
        )
        return result.mappings().all()


def get_latest_bulletin_by_manufacturer_json(engine, make: str) -> pd.DataFrame:

    with engine.begin() as conn:
        result = conn.execute(
            text("""
                    SELECT 
                        top(1) B.BulletinDetails

                    FROM Bulletin B
                    WHERE B.BulletinManufacturer = (
                        SELECT ManufacturerId
                        FROM Manufacturer
                        WHERE ManufacturerName = :make
                            AND ManufacturerStatus = 0
                    )
                    AND B.BulletinStatus = 1
                    ORDER BY B.BulletinEnd DESC
                """),
            {"make": make},
        )
        return result.mappings().all()


def print_bulletin_details(bull):
    json_ = parse_json_string(bull[0]["BulletinDetails"])

    for idx, values in enumerate(json_):

        ModelYear = json_[idx].get("Year")
        ModelNumber = json_[idx].get("Model")
        Description = json_[idx].get("Description")
        Description2 = json_[idx].get("Description2")
        Package = json_[idx].get("Package")
        Style_ID = json_[idx].get("Style")

        print(
            f"{ModelYear}, {ModelNumber}, { Description}, { Description2}, { Package}, {Style_ID}"
        )


def convert_bulletin_to_df(
    bull: list[dict[str, Any]], make: str = None
) -> pd.DataFrame:
    """
    Convert bulletin JSON to DataFrame with validation.
    Only includes records with valid year and non-null required fields.
    Adds Manufacturer column with the provided make value.
    """
    json_ = parse_json_string(bull[0]["BulletinDetails"])

    records = []
    for item in json_:
        row = {
            "Manufacturer": make,
            "ModelYear": item.get("Year"),
            "ModelNumber": item.get("Model"),
            "Description": item.get("Description"),
            "Description2": item.get("Description2"),
            "Package": item.get("Package"),
            "Style_ID": item.get("Style"),
        }

        cleaned_row = strip_row_values(row)

        if not is_valid_year(cleaned_row.get("ModelYear")):
            continue

        if not validate_row_not_null(
            cleaned_row, ["ModelYear", "ModelNumber", "Description"]
        ):
            continue

        records.append(cleaned_row)

    if not records:
        return pd.DataFrame(
            columns=[
                "Manufacturer",
                "ModelYear",
                "ModelNumber",
                "Description",
                "Description2",
                "Package",
                "Style_ID",
            ]
        )

    return pd.DataFrame(records)


def get_active_unique_manufacturers(engine) -> pd.DataFrame:
    query = text("""
        SELECT DISTINCT *
        FROM Manufacturer
        WHERE ManufacturerStatus = 0
                 AND ManufacturerName IS NOT NULL
                 AND ManufacturerName not like '%test%'
    """)

    return pd.read_sql(query, engine)


def batch_save_manufacturer_models(
    engine,
    manufacturers: list[str],
    csv_path: str = None,
) -> dict:
    """
    Fetch and save vehicle models for multiple manufacturers.

    Args:
        engine: SQLAlchemy engine for database connection
        manufacturers: List of manufacturer names
        csv_path: Path to CSV file (defaults to db/db_vehicle_models.csv)

    Returns:
        dict with results for each manufacturer and summary totals
    """
    if csv_path is None:
        csv_path = "db/db_vehicle_models.csv"

    results = {
        "manufacturers": {},
        "summary": {
            "total_processed": 0,
            "total_saved": 0,
            "total_duplicates": 0,
            "total_invalid": 0,
            "errors": [],
        },
    }

    for make in manufacturers:
        try:
            bull = get_manufacturer_bulletins_json(engine, make)
            if not bull:
                results["manufacturers"][make] = {
                    "status": "no_data",
                    "message": "No bulletin data found",
                }
                continue

            df_models = convert_bulletin_to_df(bull, make=make)
            if df_models.empty:
                results["manufacturers"][make] = {
                    "status": "no_valid_records",
                    "message": "No valid records in bulletin",
                }
                continue

            save_result = save_vehicle_models_to_csv(df_models, csv_path)
            results["manufacturers"][make] = save_result

            results["summary"]["total_processed"] += save_result["total_records"]
            results["summary"]["total_saved"] += save_result["records_saved"]
            results["summary"]["total_duplicates"] += save_result["duplicates"]
            results["summary"]["total_invalid"] += save_result["invalid_records"]

        except Exception as e:
            error_msg = f"Error processing {make}: {str(e)}"
            results["manufacturers"][make] = {
                "status": "error",
                "message": error_msg,
            }
            results["summary"]["errors"].append(error_msg)

    return results


def search_vehicle_models(
    year: int,
    model: str,
    make: str,
    trim: str = None,
    style_id: str = None,
    csv_path: str = None,
) -> pd.DataFrame:
    """
    Search vehicle models in CSV database by manufacturer-specific rules.

    Args:
        year: Model year (required, exact match)
        model: Model number (required, exact match, case-insensitive)
        make: Manufacturer name (required, exact match, case-insensitive)
        trim: Trim level (optional, contains match in configured trim fields)
        style_id: Style ID (optional, exact match, case-insensitive)
        csv_path: Path to CSV file (defaults to db/db_vehicle_models.csv)

    Returns:
        DataFrame with matching records (empty if no matches)
    """
    if csv_path is None:
        csv_path = "db/db_vehicle_models.csv"

    df = load_existing_csv(csv_path)

    if df.empty:
        return pd.DataFrame()

    config = get_manufacturer_config(make)

    df_filtered = df[df["Manufacturer"].str.lower() == make.lower()].copy()

    df_filtered = df_filtered[df_filtered["ModelYear"] == year]

    df_filtered = df_filtered[df_filtered["ModelNumber"].str.lower() == model.lower()]

    if trim:
        trim_fields = config.get("trim_fields", ["Description"])
        trim_lower = trim.lower()

        mask = pd.Series([False] * len(df_filtered), index=df_filtered.index)
        for field in trim_fields:
            if field in df_filtered.columns:
                mask |= (
                    df_filtered[field].str.lower().str.contains(trim_lower, na=False)
                )
        df_filtered = df_filtered[mask]

    if style_id:
        style_field = config.get("style_field", "Style_ID")
        if style_field in df_filtered.columns:
            df_filtered = df_filtered[
                df_filtered[style_field].str.lower() == style_id.lower()
            ]

    return df_filtered
