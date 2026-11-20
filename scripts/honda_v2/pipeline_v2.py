"""
Honda Pipeline v2 - Following notebook structure
Phase 1: Load Excel files and extract sections
Phase 2: Process sections and validate data
Phase 3: Create ready-to-load and output Excel
"""

import pandas as pd
import os
import sys
import re
from glob import glob
from typing import Dict, Any, Tuple
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# ============================================================================
# PHASE 1: LOAD & EXTRACT SECTIONS
# ============================================================================

def load_excel_files_with_sanitization(directory_path: str) -> Dict[str, Dict[str, pd.DataFrame]]:
    """
    Load all Excel files and sanitize NaN values.
    CRITICAL: Convert NaN floats to empty strings IMMEDIATELY after loading
    to prevent "float is not iterable" errors later.
    """
    print(f"\n[PHASE 1] Loading Excel files from {directory_path}")

    if not os.path.exists(directory_path):
        raise FileNotFoundError(f"Directory not found: {directory_path}")

    excel_files = glob(os.path.join(directory_path, "*.xlsx")) + glob(os.path.join(directory_path, "*.xlsm"))
    if not excel_files:
        raise FileNotFoundError(f"No Excel files found in {directory_path}")

    print(f"  Found {len(excel_files)} Excel files\n")

    result = {}

    for file_path in sorted(excel_files):
        file_name = os.path.basename(file_path)
        model_key = os.path.splitext(file_name)[0].lower()

        print(f"  Loading: {file_name}")

        try:
            xls = pd.ExcelFile(file_path, engine="openpyxl")
            workbook = {}

            for sheet_name in xls.sheet_names:
                try:
                    df = pd.read_excel(xls, sheet_name=sheet_name)

                    # SANITIZE IMMEDIATELY: NaN -> empty string
                    df = df.astype(str)
                    df = df.replace('nan', '')

                    workbook[sheet_name] = df
                except Exception as e:
                    print(f"    SKIP {sheet_name}: {e}")

            if workbook:
                result[model_key] = workbook
                print(f"    OK: {len(workbook)} sheets")
            else:
                print(f"    SKIP: No readable sheets")

        except Exception as e:
            print(f"    FAIL: {e}")

    print(f"\n[LOAD] Loaded {len(result)} models\n")
    return result


def load_vehicle_database(db_path: str) -> pd.DataFrame:
    """Load and filter Honda vehicle database"""
    print(f"[DATABASE] Loading: {db_path}")

    db = pd.read_csv(db_path)
    db_valid = db[db['ModelName'].notna()].copy()

    print(f"  Original: {len(db)} rows")
    print(f"  Valid: {len(db_valid)} rows\n")

    return db_valid


def find_english_sheet(model_dict: Dict[str, pd.DataFrame]) -> str:
    """Find the English application sheet (matches _APP_EN pattern)"""
    for sheet_name in model_dict.keys():
        if '_APP_EN' in sheet_name:
            return sheet_name
    return None


def extract_sections_from_df(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """
    Extract sections from the English sheet.
    Sections are delimited by section headers in column 0.
    """
    sections = {}
    current_section = None
    section_rows = []

    for idx, row in df.iterrows():
        cell_0 = str(row.iloc[0]) if len(row) > 0 else ""

        # Check if this is a section header (matches format "X.X ...")
        if re.match(r'^\d+\.\d+\s+', cell_0):
            # Save previous section
            if current_section and section_rows:
                sections[current_section] = pd.DataFrame(section_rows)

            # Start new section
            current_section = cell_0
            section_rows = []
        elif current_section:
            section_rows.append(dict(row))

    # Save last section
    if current_section and section_rows:
        sections[current_section] = pd.DataFrame(section_rows)

    return sections


def extract_one_model(model_key: str, model_sheets: Dict[str, pd.DataFrame], vehicle_db: pd.DataFrame) -> Dict[str, Any]:
    """
    Extract one complete model.
    Returns: {
        'model_key': model_key,
        'english_sheet': sheet_name,
        'sections': {section_key: DataFrame},
        'vehicle_db_match': model_number
    }
    """
    print(f"\n  [EXTRACT] {model_key}")

    # Find English sheet
    en_sheet = find_english_sheet(model_sheets)
    if not en_sheet:
        raise ValueError(f"No _APP_EN sheet found")

    en_df = model_sheets[en_sheet].copy()
    print(f"    Sheet: {en_sheet} ({en_df.shape[0]} rows x {en_df.shape[1]} cols)")

    # Extract sections
    sections = extract_sections_from_df(en_df)
    print(f"    Sections: {len(sections)} found")

    # Map model_key to vehicle DB
    model_map = {
        '27crv': 'CR-V',
        '27civichatch5': 'Civic',
        '27civicsedan4': 'Civic',
        '27hrv': 'HR-V',
        '27odyssey': 'Odyssey',
        '27passport': 'Passport',
        '27prelude': 'Prelude',
    }

    honda_model = model_map.get(model_key, '')
    matching = vehicle_db[vehicle_db['ModelName'].str.contains(honda_model, case=False, na=False)]

    if len(matching) > 0:
        matching_sorted = matching.sort_values('ModelYear', ascending=False)
        model_number = matching_sorted.iloc[0]['ModelNumber']
        print(f"    Vehicle: {matching_sorted.iloc[0]['ModelName']} -> {model_number}")
    else:
        model_number = ''
        print(f"    Vehicle: Not found")

    return {
        'model_key': model_key,
        'english_sheet': en_sheet,
        'sections': sections,
        'model_number': model_number,
        'english_df': en_df,
    }


# ============================================================================
# PHASE 2: PROCESS & BUILD FINAL DATASET
# ============================================================================

def build_final_dataframe(extraction: Dict[str, Any]) -> pd.DataFrame:
    """
    Build final DataFrame for one model.
    Takes all sections and combines into single DataFrame with model_number column.
    """
    model_key = extraction['model_key']
    model_number = extraction['model_number']

    # Combine all sections
    dfs_to_concat = []
    for section_key, sec_df in extraction['sections'].items():
        if not sec_df.empty:
            dfs_to_concat.append(sec_df)

    if dfs_to_concat:
        combined_df = pd.concat(dfs_to_concat, ignore_index=True)
    else:
        combined_df = extraction['english_df'].copy()

    # Add model_number column
    combined_df['model_number'] = model_number

    print(f"    Built: {combined_df.shape[0]} rows x {combined_df.shape[1]} cols")

    return combined_df


# ============================================================================
# PHASE 3: OUTPUT TO EXCEL
# ============================================================================

def save_to_excel(extracted_models: Dict[str, pd.DataFrame], output_dir: str) -> str:
    """
    Save all models to single Excel file with one sheet per model.
    """
    print(f"\n[PHASE 3] Saving to Excel")

    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_file = os.path.join(output_dir, f"Honda_Accessories-Upload_file-{timestamp}.xlsx")

    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        for model_key in sorted(extracted_models.keys()):
            df = extracted_models[model_key]
            df.to_excel(writer, sheet_name=model_key, index=False)
            print(f"  Sheet: {model_key} ({len(df)} rows)")

    file_size_kb = os.path.getsize(output_file) / 1024
    print(f"\n  File: {output_file}")
    print(f"  Size: {file_size_kb:.1f} KB\n")

    return output_file


# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================

def main():
    print("=" * 80)
    print("HONDA PIPELINE V2 - Following Notebook Structure")
    print("=" * 80)

    HONDA_DATA_PATH = "landing_zone/2026/Honda/2026-11"
    DB_PATH = "scripts/models_catalogue/honda_models.csv"
    OUTPUT_DIR = "ready_to_upload/2026/Honda"

    # Load data
    try:
        excel_dict = load_excel_files_with_sanitization(HONDA_DATA_PATH)
        vehicle_db = load_vehicle_database(DB_PATH)
    except Exception as e:
        print(f"\n[FAIL] Loading phase failed: {e}")
        import traceback
        traceback.print_exc()
        return None

    # Extract all models
    print("\n" + "=" * 80)
    print("PHASE 2: EXTRACT & BUILD DATASETS")
    print("=" * 80)

    extracted_models = {}
    failures = {}

    for model_key in sorted(excel_dict.keys()):
        try:
            # Extract one model
            extraction = extract_one_model(model_key, excel_dict[model_key], vehicle_db)

            # Build final DataFrame
            final_df = build_final_dataframe(extraction)

            extracted_models[model_key] = final_df
            print(f"    SUCCESS: {model_key}")

        except Exception as e:
            failures[model_key] = str(e)
            print(f"    FAIL: {model_key}: {e}")

    if failures:
        print(f"\n[WARNING] {len(failures)} models failed:")
        for model_key, error in failures.items():
            print(f"  {model_key}: {error}")

    if not extracted_models:
        print(f"\n[FAIL] No models were extracted. Aborting.")
        return None

    # Output to Excel
    print("\n" + "=" * 80)
    print("PHASE 3: SAVE EXCEL OUTPUT")
    print("=" * 80)

    try:
        output_file = save_to_excel(extracted_models, OUTPUT_DIR)

        print("=" * 80)
        print("SUCCESS - All phases complete")
        print("=" * 80)
        print(f"Models extracted: {len(extracted_models)}")
        print(f"Models failed: {len(failures)}")
        print(f"Output file ready")

        return output_file

    except Exception as e:
        print(f"\n[FAIL] Output phase failed: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == '__main__':
    output_file = main()
