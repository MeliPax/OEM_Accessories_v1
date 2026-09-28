"""
Step 1: Data Loading & Metadata Extraction (CORRECTED v2)

Each FILE = one MODEL with EN and FR sheets (*_APP_EN and *_APP_FR)

Process:
1. Find *_APP_EN and *_APP_FR sheets
2. Extract MODEL NAME from metadata rows (above "1.0 Packages and Kits" marker)
3. Validate both EN and FR sheets have same model name
4. Load data from both sheets
5. Return data organized by model and language
"""

from typing import Tuple, Dict, Any, List, Optional
import pandas as pd
import os
from pathlib import Path


def find_parts_data_sheets(file_path: str) -> Dict[str, Optional[str]]:
    """
    Find *_APP_EN and *_APP_FR sheets in the file.

    Returns:
        {
            "app_en_sheet": sheet_name or None,
            "app_fr_sheet": sheet_name or None,
            "all_sheets": [list of all sheets]
        }
    """
    try:
        xl = pd.ExcelFile(file_path)
        sheet_names = xl.sheet_names

        # Find APP_EN and APP_FR sheets (case-insensitive)
        app_en_sheets = [s for s in sheet_names if "_APP_EN" in s.upper()]
        app_fr_sheets = [s for s in sheet_names if "_APP_FR" in s.upper()]

        return {
            "app_en_sheet": app_en_sheets[0] if app_en_sheets else None,
            "app_fr_sheet": app_fr_sheets[0] if app_fr_sheets else None,
            "all_sheets": sheet_names,
            "found_en": len(app_en_sheets) > 0,
            "found_fr": len(app_fr_sheets) > 0,
        }

    except Exception as e:
        return {
            "app_en_sheet": None,
            "app_fr_sheet": None,
            "all_sheets": [],
            "error": str(e),
            "found_en": False,
            "found_fr": False,
        }


def extract_model_name_from_sheet(df: pd.DataFrame, sheet_name: str, language: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract model name and year from metadata rows.

    Process:
    1. Find row with "1.0 Packages and Kits" marker
    2. Look in rows ABOVE it for Model Name and Year
    3. Extract the model name

    Returns:
        (model_name, model_year) or (None, None) if not found
    """
    try:
        # Convert all cells to string for searching
        df_str = df.astype(str)

        # Find row with "1.0 Packages and Kits" marker
        packages_marker_row = None
        for idx, row in df_str.iterrows():
            row_text = " ".join(row.values)
            if "1.0 Packages and Kits" in row_text or "Packages and Kits" in row_text:
                packages_marker_row = idx
                break

        if packages_marker_row is None:
            return None, None

        # Look in rows ABOVE the marker (from top to marker)
        model_name = None
        model_year = None

        # Search from top down to marker for metadata
        for idx in range(0, packages_marker_row):
            row = df_str.iloc[idx]
            row_text = " ".join(row.values)

            # Look for model keywords (e.g., "Civic", "Accord", "CR-V", etc.)
            # Check if row contains common Honda model patterns
            honda_models = ["Civic", "Accord", "CR-V", "HR-V", "Pilot", "Passport", "Ridgeline", "Odyssey"]
            for model in honda_models:
                if model in row_text:
                    model_name = model
                    break

            # Look for year pattern (2025, 2026, 2027, etc.)
            for year_candidate in ["2025", "2026", "2027", "2024", "2028"]:
                if year_candidate in row_text:
                    model_year = year_candidate

        return model_name, model_year

    except Exception as e:
        return None, None


def load_parts_data_sheets(
    file_path: str,
    en_sheet: str,
    fr_sheet: str
) -> Tuple[Optional[Dict[str, pd.DataFrame]], Dict[str, Any], List[Dict[str, Any]]]:
    """
    Load EN and FR parts data sheets and extract metadata.

    Returns:
        (data_dict, metadata, dq_warnings)
    """
    dq_warnings = []
    metadata = {
        "file_path": file_path,
        "file_name": os.path.basename(file_path),
        "en_sheet": en_sheet,
        "fr_sheet": fr_sheet,
        "status": "PENDING",
        "model_name_en": None,
        "model_year_en": None,
        "model_name_fr": None,
        "model_year_fr": None,
        "model_name_match": False,
    }

    try:
        # Load EN sheet
        df_en = pd.read_excel(file_path, sheet_name=en_sheet)
        if len(df_en) == 0:
            dq_warnings.append({
                "rule_type": "sheet_validation_rule",
                "severity": "ERROR",
                "message": f"EN sheet '{en_sheet}' is empty"
            })
            return None, metadata, dq_warnings

        # Load FR sheet
        df_fr = pd.read_excel(file_path, sheet_name=fr_sheet)
        if len(df_fr) == 0:
            dq_warnings.append({
                "rule_type": "sheet_validation_rule",
                "severity": "ERROR",
                "message": f"FR sheet '{fr_sheet}' is empty"
            })
            return None, metadata, dq_warnings

        # Extract model name from EN sheet
        model_name_en, model_year_en = extract_model_name_from_sheet(df_en, en_sheet, "EN")
        metadata["model_name_en"] = model_name_en
        metadata["model_year_en"] = model_year_en

        # Extract model name from FR sheet
        model_name_fr, model_year_fr = extract_model_name_from_sheet(df_fr, fr_sheet, "FR")
        metadata["model_name_fr"] = model_name_fr
        metadata["model_year_fr"] = model_year_fr

        # Validate model names match
        if model_name_en and model_name_fr:
            if model_name_en == model_name_fr:
                metadata["model_name_match"] = True
            else:
                dq_warnings.append({
                    "rule_type": "model_mismatch_rule",
                    "severity": "WARNING",
                    "message": f"Model name mismatch: EN='{model_name_en}' vs FR='{model_name_fr}'"
                })

        if not model_name_en:
            dq_warnings.append({
                "rule_type": "model_extraction_rule",
                "severity": "WARNING",
                "message": "Could not extract model name from EN sheet"
            })

        if not model_name_fr:
            dq_warnings.append({
                "rule_type": "model_extraction_rule",
                "severity": "WARNING",
                "message": "Could not extract model name from FR sheet"
            })

        # Store data shape info
        metadata["en_shape"] = df_en.shape
        metadata["fr_shape"] = df_fr.shape
        metadata["en_columns"] = list(df_en.columns)
        metadata["fr_columns"] = list(df_fr.columns)
        metadata["status"] = "SUCCESS"

        data_dict = {
            "EN": df_en,
            "FR": df_fr
        }

        return data_dict, metadata, dq_warnings

    except Exception as e:
        dq_warnings.append({
            "rule_type": "data_load_rule",
            "severity": "ERROR",
            "message": f"Failed to load sheets: {str(e)}"
        })
        return None, metadata, dq_warnings


def validate_and_extract(
    file_path: str,
    config: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[Dict[str, pd.DataFrame]], Dict[str, Any], List[Dict[str, Any]]]:
    """
    Main entry point: Load and validate Honda file.

    Process:
    1. Find *_APP_EN and *_APP_FR sheets
    2. Load both sheets
    3. Extract model name from metadata rows (above "1.0 Packages and Kits")
    4. Validate both sheets have same model
    5. Return data and metadata
    """
    dq_warnings = []

    # Find parts data sheets
    sheet_info = find_parts_data_sheets(file_path)

    if "error" in sheet_info:
        return None, {"file_path": file_path, "error": sheet_info["error"]}, [
            {
                "rule_type": "file_read_rule",
                "severity": "ERROR",
                "message": f"Could not read file: {sheet_info['error']}"
            }
        ]

    # Validate EN sheet exists
    if not sheet_info["found_en"]:
        dq_warnings.append({
            "rule_type": "sheet_discovery_rule",
            "severity": "ERROR",
            "message": "No *_APP_EN sheet found in file. Skipping."
        })
        return None, {"file_path": file_path, "all_sheets": sheet_info["all_sheets"]}, dq_warnings

    # Validate FR sheet exists
    if not sheet_info["found_fr"]:
        dq_warnings.append({
            "rule_type": "sheet_discovery_rule",
            "severity": "ERROR",
            "message": "No *_APP_FR sheet found in file. Skipping."
        })
        return None, {"file_path": file_path, "all_sheets": sheet_info["all_sheets"]}, dq_warnings

    en_sheet = sheet_info["app_en_sheet"]
    fr_sheet = sheet_info["app_fr_sheet"]

    # Load sheets and extract metadata
    data_dict, metadata, load_warnings = load_parts_data_sheets(file_path, en_sheet, fr_sheet)

    dq_warnings.extend(load_warnings)

    if data_dict is None:
        return None, metadata, dq_warnings

    return data_dict, metadata, dq_warnings
