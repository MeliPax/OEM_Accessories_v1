"""
Step 1: Data Loading & Metadata Extraction

Handles actual Honda file structure:
- Master sheets: wide format with trims as columns
- LoadFile sheets: raw load data
- Template sheet: structure template + metadata
"""

from typing import Tuple, Dict, Any, List, Optional
import pandas as pd
import os
import re


def extract_model_from_sheet_name(sheet_name: str) -> Optional[str]:
    """Extract model name from sheet name."""
    model = sheet_name.replace(" - Master", "").replace("LoadFile - ", "")
    
    trim_prefixes = [
        "Si ", "Sport ", "Sport Hybrid ", "Sport Touring ", "Type R ",
        "Ex-L ", "EX-L ", "Lx ", "LX ", "Touring ", "Hybrid ",
        "Black Edition ", "TrailSport ", "Sport L "
    ]
    
    for prefix in trim_prefixes:
        if model.startswith(prefix):
            model = model[len(prefix):]
    
    return model.strip() if model.strip() else None


def identify_section_boundaries(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """
    Detect all 6 sections using regex pattern: ^\d+\.\d+\s+(.+)$
    Returns: {"packages": {"marker_row": 9, "data_start": 10, "data_end": 55, ...}, ...}
    """
    section_structure = {}

    # Pattern for section markers: "1.0 Packages", "2.0 Wheels", etc.
    pattern = r'^\d+\.\d+\s+(.+)$'

    section_rows = []
    for idx, row in df.iterrows():
        for val in row.values:
            val_str = str(val).strip() if pd.notna(val) else ""
            if re.match(pattern, val_str):
                section_name = val_str.split(maxsplit=1)[1].lower().replace(" and ", "_").replace(" ", "_")
                section_rows.append((idx, section_name, val_str))
                break

    # For each section marker, determine data boundaries
    # Section structure: marker_row, then header_row and data_rows follow
    for i, (marker_row, section_name, section_text) in enumerate(section_rows):
        data_start = marker_row + 1  # Data starts right after marker (includes header)

        # Data ends at the next section marker (or end of df)
        if i < len(section_rows) - 1:
            data_end = section_rows[i + 1][0] - 1
        else:
            # Last section: find last non-empty row
            data_end = len(df) - 1
            for j in range(len(df) - 1, marker_row, -1):
                if df.iloc[j].notna().any():
                    data_end = j
                    break

        total_rows = max(0, data_end - data_start + 1)

        section_structure[section_name] = {
            "marker_row": marker_row,
            "data_start": data_start,
            "data_end": data_end,
            "total_rows": total_rows,
            "marker_text": section_text
        }

    return section_structure


def extract_trim_columns(df: pd.DataFrame, section_structure: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Extract trim columns per section.
    For each section, find "Installed Price" column, all columns after it are trims.
    """
    trim_columns_per_section = {}

    # Product columns that come before trim columns
    product_col_markers = ["Description", "Part Number", "Dealer Net", "List Price", "FRT", "Installed Price"]

    for section_name, boundaries in section_structure.items():
        data_start = boundaries.get("data_start")
        data_end = boundaries.get("data_end")

        if data_start is None or data_end is None:
            trim_columns_per_section[section_name] = []
            continue

        # Get header row (one row before data_start)
        header_row_idx = data_start - 1
        if header_row_idx >= 0 and header_row_idx < len(df):
            header_row = df.iloc[header_row_idx]

            # Find "Installed Price" column (last product column)
            installed_price_col = None
            for col_idx, col_name in enumerate(header_row):
                col_str = str(col_name).strip()
                if "Installed" in col_str and "Price" in col_str:
                    installed_price_col = col_idx
                    break

            # All columns after Installed Price are trim columns
            if installed_price_col is not None:
                trim_cols = []
                for col_idx in range(installed_price_col + 1, len(header_row)):
                    col_name = str(header_row.iloc[col_idx]).strip()
                    # Skip empty columns, notes, application columns
                    if col_name and col_name.lower() not in ["nan", "notes", "application", "comments"]:
                        trim_cols.append(col_name)

                trim_columns_per_section[section_name] = trim_cols
            else:
                trim_columns_per_section[section_name] = []
        else:
            trim_columns_per_section[section_name] = []

    return trim_columns_per_section


def extract_metadata_from_data_sheet(df: pd.DataFrame) -> Dict[str, Any]:
    """Extract metadata from header rows (before section marker) and footer rows."""
    meta = {
        "honda_accessories_found": False,
        "model_name": None,
        "section_marker_row": None,
        "publication_date": None,
    }

    try:
        # Convert to string for searching
        df_str = df.astype(str)

        # Find section marker (Packages and Kits / Groupes et ensembles)
        section_marker_row = None
        for idx, row in df_str.iterrows():
            row_text = " ".join(str(val) for val in row.values)
            if "Packages and Kits" in row_text or "1.0 Packages" in row_text or \
               "Groupes et ensembles" in row_text or "1.0 Groupes" in row_text:
                section_marker_row = idx
                break

        meta["section_marker_row"] = section_marker_row

        # Extract from header rows (before section marker)
        if section_marker_row is not None:
            header_rows = df.iloc[0:section_marker_row]
            header_text = " ".join(header_rows.values.flatten().astype(str))

            # Look for Honda Accessories signature
            if "Honda Accessories" in header_text or "Honda" in header_text:
                meta["honda_accessories_found"] = True

        # Extract publication date from footer rows (last 3 rows)
        footer_rows = df.tail(3)
        footer_text = " ".join(footer_rows.values.flatten().astype(str))

        if "Publication Date" in footer_text or "Date de publication" in footer_text:
            # Look for date in format YYYY-MM-DD
            date_pattern = r'(\d{4}-\d{2}-\d{2})'
            date_match = re.search(date_pattern, footer_text)
            if date_match:
                meta["publication_date"] = date_match.group(1)

        return meta

    except Exception as e:
        meta["error"] = str(e)
        return meta


def extract_metadata_from_file(file_path: str) -> Dict[str, Any]:
    """Extract Honda file metadata: year, models, publication date."""
    metadata = {
        "file_path": file_path,
        "file_name": os.path.basename(file_path),
        "model_year": None,
        "publication_date": None,
        "found_publication_date_string": False,
        "manufacture_validated": False,
        "models_in_file": [],
        "primary_sheet": None,
        "sheet_summary": {},
    }

    try:
        excel_file = pd.ExcelFile(file_path)
        sheet_names = excel_file.sheet_names

        # Extract year from filename
        year_match = re.search(r'(202[5-9]|203[0-9])', os.path.basename(file_path))
        if year_match:
            metadata["model_year"] = year_match.group(1)

        # Categorize sheets
        template_sheets = [s for s in sheet_names if s.lower() == "template"]
        loadfile_sheets = [s for s in sheet_names if "loadfile" in s.lower()]
        master_sheets = [s for s in sheet_names if " - master" in s.lower() or "- Master" in s]
        trim_sheets = [s for s in sheet_names if s not in template_sheets + loadfile_sheets + master_sheets]

        metadata["sheet_summary"] = {
            "template_sheets": len(template_sheets),
            "loadfile_sheets": len(loadfile_sheets),
            "master_sheets": len(master_sheets),
            "trim_sheets": len(trim_sheets),
            "total_sheets": len(sheet_names)
        }

        # Extract models from sheet names
        models_found = set()
        for sheet in master_sheets:
            model = extract_model_from_sheet_name(sheet)
            if model:
                models_found.add(model)

        metadata["models_in_file"] = sorted(list(models_found))

        # Select primary data sheet
        if master_sheets:
            metadata["primary_sheet"] = master_sheets[0]
        elif loadfile_sheets:
            metadata["primary_sheet"] = loadfile_sheets[0]
        elif trim_sheets:
            metadata["primary_sheet"] = trim_sheets[0]

        # Extract metadata from primary sheet (header + footer)
        if metadata["primary_sheet"]:
            primary_df = pd.read_excel(file_path, sheet_name=metadata["primary_sheet"])
            sheet_meta = extract_metadata_from_data_sheet(primary_df)

            if sheet_meta.get("honda_accessories_found"):
                metadata["manufacture_validated"] = True

            if sheet_meta.get("publication_date"):
                metadata["publication_date"] = sheet_meta["publication_date"]
                metadata["found_publication_date_string"] = True

        if metadata["model_year"]:
            metadata["manufacture_validated"] = True

        return metadata

    except Exception as e:
        metadata["error"] = str(e)
        return metadata


def load_honda_file(file_path: str, metadata: Dict[str, Any]) -> Tuple[Optional[pd.DataFrame], Dict[str, Any]]:
    """Load primary data sheet from Honda file."""
    try:
        primary_sheet = metadata.get("primary_sheet")
        if not primary_sheet:
            metadata["error"] = "No primary sheet identified"
            return None, metadata
        
        df = pd.read_excel(file_path, sheet_name=primary_sheet)
        
        metadata["loaded_sheet"] = primary_sheet
        metadata["data_shape"] = {
            "rows": len(df),
            "columns": len(df.columns),
            "column_names": list(df.columns)
        }
        
        trim_indicators = ["LX", "SPORT", "Si", "Type R", "Touring", "EX-L", "Sport", "Hybrid", "Sport L"]
        trim_columns = [col for col in df.columns if any(trim in col for trim in trim_indicators)]
        
        metadata["wide_format_detected"] = len(trim_columns) > 0
        metadata["trim_columns"] = trim_columns
        
        return df, metadata
    
    except Exception as e:
        metadata["error"] = str(e)
        return None, metadata


def validate_and_extract(file_path: str, config: Optional[Dict[str, Any]] = None) -> Tuple[Optional[Dict[str, pd.DataFrame]], Dict[str, Any], List[Dict[str, Any]]]:
    """Main entry point: Validate Honda file and extract data + metadata."""
    dq_warnings = []

    metadata = extract_metadata_from_file(file_path)

    if not metadata.get("manufacture_validated"):
        dq_warnings.append({
            "rule_type": "file_validation_rule",
            "severity": "WARNING",
            "message": "Could not validate Honda manufacturer signature"
        })

    if not metadata.get("model_year"):
        dq_warnings.append({
            "rule_type": "file_validation_rule",
            "severity": "ERROR",
            "message": "Could not extract model year from filename"
        })
        return None, metadata, dq_warnings

    df, metadata = load_honda_file(file_path, metadata)

    if df is None:
        dq_warnings.append({
            "rule_type": "data_load_rule",
            "severity": "ERROR",
            "message": f"Failed to load primary data sheet: {metadata.get('error', 'Unknown error')}"
        })
        return None, metadata, dq_warnings

    if len(df) == 0:
        dq_warnings.append({
            "rule_type": "data_load_rule",
            "severity": "ERROR",
            "message": "Loaded data sheet is empty"
        })
        return None, metadata, dq_warnings

    # STEP 1A: Detect section boundaries
    section_structure = identify_section_boundaries(df)

    if not section_structure:
        dq_warnings.append({
            "rule_type": "section_detection_rule",
            "severity": "ERROR",
            "message": "No sections detected in data sheet"
        })
        return None, metadata, dq_warnings

    if len(section_structure) < 6:
        dq_warnings.append({
            "rule_type": "section_detection_rule",
            "severity": "WARNING",
            "message": f"Expected 6 sections, found {len(section_structure)}: {list(section_structure.keys())}"
        })

    # STEP 1B: Extract trim columns per section
    trim_columns_per_section = extract_trim_columns(df, section_structure)

    # Add section structure to metadata
    metadata["section_structure"] = section_structure
    metadata["trim_columns_per_section"] = trim_columns_per_section

    data_dict = {
        "EN": df,
        "FR": None
    }

    metadata["status"] = "SUCCESS"

    return data_dict, metadata, dq_warnings
