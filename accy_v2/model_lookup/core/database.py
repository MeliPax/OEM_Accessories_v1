"""Database (CSV) operations for vehicle models."""

import os
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Any, Dict
from .vocabulary import build_vocabulary


def is_valid_year(value: Any) -> bool:
    """Validate if a value is a valid year (1900-current year + 5)."""
    if value is None or value == "":
        return False
    try:
        year = int(value)
        current_year = datetime.now().year
        return 1900 <= year <= current_year + 5
    except (ValueError, TypeError):
        return False


def strip_row_values(row: dict) -> dict:
    """Strip whitespace from all values and remove None/empty strings."""
    cleaned = {}
    for key, value in row.items():
        if isinstance(value, str):
            value = value.strip()
        cleaned[key] = value if value not in (None, "") else None
    return cleaned


def validate_row_not_null(row: dict, required_fields: list = None) -> bool:
    """Check if all required fields are not null."""
    if required_fields is None:
        required_fields = list(row.keys())

    for field in required_fields:
        if field not in row or row[field] is None or row[field] == "":
            return False
    return True


def load_models(csv_path: str = None) -> pd.DataFrame:
    """
    Load vehicle models from CSV.

    Args:
        csv_path: Path to CSV file. Defaults to db/db_vehicle_models.csv

    Returns:
        DataFrame with vehicle models. Empty DataFrame if file doesn't exist.
    """
    if csv_path is None:
        csv_path = str(Path(__file__).parent.parent / "db" / "db_vehicle_models.csv")

    if os.path.exists(csv_path):
        try:
            return pd.read_csv(csv_path)
        except Exception as e:
            print(f"Warning: Could not read CSV: {e}")
            return pd.DataFrame()
    return pd.DataFrame()


def _check_duplicates(df_new: pd.DataFrame, df_existing: pd.DataFrame) -> pd.DataFrame:
    """Filter out records that already exist in database."""
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
    return df_new[merge["_merge"] == "left_only"].drop(columns=["_merge"], errors="ignore")


def save_models(df: pd.DataFrame, csv_path: str = None, configs_dir: str = None) -> Dict:
    """
    Save vehicle models to CSV with validation and deduplication.

    Args:
        df: DataFrame with vehicle model data
        csv_path: Path to CSV file. Defaults to db/db_vehicle_models.csv
        configs_dir: Directory for configs. Defaults to configs/

    Returns:
        Dictionary with save status and metadata
    """
    if csv_path is None:
        csv_path = str(Path(__file__).parent.parent / "db" / "db_vehicle_models.csv")

    if configs_dir is None:
        configs_dir = str(Path(__file__).parent.parent / "configs")

    result = {
        "success": False,
        "total_records": len(df),
        "records_saved": 0,
        "duplicates": 0,
        "invalid_records": 0,
        "file_path": csv_path,
        "vocabulary_rebuilt": [],
    }

    if df.empty:
        result["message"] = "No data to save"
        return result

    os.makedirs(os.path.dirname(csv_path) or ".", exist_ok=True)

    # Validate records
    required_fields = ["ModelYear", "ModelNumber", "Description"]
    valid_records = []

    for _, row in df.iterrows():
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
    df_existing = load_models(csv_path)

    # Check duplicates
    if not df_existing.empty:
        df_valid = _check_duplicates(df_valid, df_existing)
        result["duplicates"] = result["total_records"] - result["invalid_records"] - len(df_valid)

    if df_valid.empty:
        result["success"] = True
        result["message"] = "No new data to load — all records already exist"
        return result

    # Write to CSV
    mode = "w" if df_existing.empty else "a"
    header = df_existing.empty

    try:
        df_valid.to_csv(csv_path, mode=mode, header=header, index=False)
        result["records_saved"] = len(df_valid)
        result["success"] = True
        result["message"] = f"Successfully saved {len(df_valid)} records"

        # Rebuild vocabulary for all manufacturers in saved data
        unique_makes = df_valid["Manufacturer"].unique().tolist()
        for make in unique_makes:
            try:
                vocab_result = build_vocabulary(make, csv_path, configs_dir)
                if vocab_result.get("saved", False):
                    result["vocabulary_rebuilt"].append(make)
            except Exception:
                pass  # Non-fatal

    except Exception as e:
        result["message"] = f"Error saving to CSV: {str(e)}"

    return result
