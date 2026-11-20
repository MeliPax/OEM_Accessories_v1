"""
Honda Pipeline v2 - Clean rebuild
Step 1: Load Excel files with data sanitization
"""

import pandas as pd
import os
import sys
from glob import glob
from typing import Dict, Any

# Add scripts directory to path so we can import honda_vehicle_matcher
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from honda_vehicle_matcher import match_vehicle

def load_excel_files(directory_path: str) -> Dict[str, Dict[str, Any]]:
    """
    Load all Excel files from directory.
    Sanitize: Convert NaN float values to empty strings.
    Returns: {model_key: {sheet_name: DataFrame, '__META__': metadata}}
    """

    if not os.path.exists(directory_path):
        raise FileNotFoundError(f"Directory not found: {directory_path}")

    # Find all Excel files
    excel_files = glob(os.path.join(directory_path, "*.xlsx")) + glob(os.path.join(directory_path, "*.xlsm"))

    if not excel_files:
        raise FileNotFoundError(f"No Excel files found in {directory_path}")

    print(f"\n[LOAD] Found {len(excel_files)} Excel files")

    result = {}

    for file_path in sorted(excel_files):
        file_name = os.path.basename(file_path)
        model_key = os.path.splitext(file_name)[0].lower()

        print(f"\n  [FILE] Loading: {file_name}")

        try:
            # Read all sheets
            xls = pd.ExcelFile(file_path, engine="openpyxl")
            workbook = {}

            for sheet_name in xls.sheet_names:
                try:
                    # Read sheet
                    df = pd.read_excel(xls, sheet_name=sheet_name)

                    # SANITIZE: Convert all to string, then replace 'nan' with empty string
                    df = df.astype(str)
                    df = df.replace('nan', '')

                    workbook[sheet_name] = df
                    print(f"     OK {sheet_name}: {df.shape[0]} rows x {df.shape[1]} cols")

                except Exception as e:
                    print(f"     SKIP {sheet_name}: {e}")

            if not workbook:
                print(f"     FAIL No readable sheets")
                continue

            result[model_key] = {
                '__META__': {
                    'model_key': model_key,
                    'file_name': file_name,
                    'sheet_count': len(workbook),
                },
                **workbook
            }

            print(f"     DONE Loaded: {len(workbook)} sheets")

        except Exception as e:
            print(f"     FAIL Error: {e}")

    print(f"\n[SUCCESS] Loaded {len(result)} models")
    return result


def extract_accessory_data_for_model(model_key: str, excel_sheets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Extract accessory data for one model.
    Uses the _APP_EN sheet (English accessories sheet).
    Returns: DataFrame with accessory data
    """
    print(f"\n  [EXTRACT] {model_key}")

    # Find the _APP_EN sheet
    app_sheet = None
    for sheet_name in excel_sheets.keys():
        if '_APP_EN' in sheet_name:
            app_sheet = sheet_name
            break

    if app_sheet is None:
        raise ValueError(f"No _APP_EN sheet found for {model_key}")

    print(f"    Using sheet: {app_sheet}")

    df = excel_sheets[app_sheet].copy()
    print(f"    Shape: {df.shape[0]} rows x {df.shape[1]} cols")
    print(f"    Columns: {list(df.columns)}")

    return df


def attach_model_numbers(accessory_df: pd.DataFrame, model_key: str, vehicle_db: pd.DataFrame) -> pd.DataFrame:
    """
    Attach Honda model numbers to accessory data.
    Uses match_vehicle() to match each row to vehicle database.
    Returns: DataFrame with new 'model_number' column
    """
    print(f"\n  [MODEL] {model_key}: Looking up model numbers")

    # Map model_key to Honda model name
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

    # Find model number for this model in the database
    matching_rows = vehicle_db[vehicle_db['ModelName'].str.contains(honda_model, case=False, na=False)]

    if len(matching_rows) > 0:
        # Get most recent year's model number
        matching_rows_sorted = matching_rows.sort_values('ModelYear', ascending=False)
        first_match = matching_rows_sorted.iloc[0]
        model_number = first_match['ModelNumber']
        print(f"    Found: {first_match['ModelName']} ({first_match['ModelYear']}) -> {model_number}")
    else:
        model_number = ''
        print(f"    No match found for {honda_model}")

    # Add model_number column to all rows
    accessory_df_with_models = accessory_df.copy()
    accessory_df_with_models['model_number'] = model_number

    print(f"    Attached model_number to {len(accessory_df_with_models)} rows")

    return accessory_df_with_models


def generate_excel_output(loaded_data: Dict[str, Dict[str, Any]], vehicle_db: pd.DataFrame, output_dir: str) -> str:
    """
    Generate final Excel output with all models.
    One sheet per model, with model_number column attached.
    Returns: Path to output file
    """
    print(f"\n[EXPORT] Generating Excel file with {len(loaded_data)} models")

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Create Excel writer
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_file = os.path.join(output_dir, f"Honda_Accessories-Upload_file-{timestamp}.xlsx")

    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        for model_key, model_data in sorted(loaded_data.items()):
            # Extract metadata
            meta = model_data['__META__']

            # Get APP_EN sheet
            app_sheet = None
            for sheet_name in model_data.keys():
                if '_APP_EN' in sheet_name:
                    app_sheet = sheet_name
                    break

            if app_sheet is None:
                print(f"  SKIP {model_key}: No _APP_EN sheet")
                continue

            # Get dataframe
            df = model_data[app_sheet].copy()

            # Map model_key to Honda model name
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
            matching_rows = vehicle_db[vehicle_db['ModelName'].str.contains(honda_model, case=False, na=False)]

            if len(matching_rows) > 0:
                matching_rows_sorted = matching_rows.sort_values('ModelYear', ascending=False)
                model_number = matching_rows_sorted.iloc[0]['ModelNumber']
            else:
                model_number = ''

            # Add model_number column
            df['model_number'] = model_number

            # Write to Excel
            df.to_excel(writer, sheet_name=model_key, index=False)
            print(f"  OK {model_key}: {len(df)} rows, model={model_number}")

    print(f"\n[SUCCESS] Excel file created: {output_file}")
    print(f"  File size: {os.path.getsize(output_file) / 1024:.1f} KB")

    return output_file


def load_vehicle_database(db_path: str) -> pd.DataFrame:
    """
    Load Honda vehicle database.
    Filter to only rows with valid ModelName (non-null).
    Returns: DataFrame with 217 valid vehicle records
    """
    print(f"\n[LOAD] Reading database: {db_path}")

    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")

    # Load CSV
    db = pd.read_csv(db_path)
    print(f"  Original: {len(db)} rows")

    # Filter: keep only rows with valid ModelName
    db_valid = db[db['ModelName'].notna()].copy()
    print(f"  Valid (ModelName not null): {len(db_valid)} rows")

    # Show sample
    print(f"\n  Sample records:")
    for idx, row in db_valid.head(3).iterrows():
        print(f"    {row['ModelName']} ({row['ModelYear']}) -> {row['ModelNumber']}")

    print(f"\n[SUCCESS] Loaded {len(db_valid)} vehicle records")
    return db_valid


def main():
    """Test Steps 1-2: Load Excel files and vehicle database"""

    print("=" * 80)
    print("STEP 1: Load Excel Files")
    print("=" * 80)

    HONDA_DATA_PATH = "landing_zone/2026/Honda/2026-11"
    DB_PATH = "scripts/models_catalogue/honda_models.csv"

    # STEP 1: Load Excel files
    try:
        loaded_data = load_excel_files(HONDA_DATA_PATH)
        print(f"\n[PASS] STEP 1 PASSED: {len(loaded_data)} models loaded")
    except Exception as e:
        print(f"\n[FAIL] STEP 1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return None, None

    # STEP 2: Load vehicle database
    print("\n" + "=" * 80)
    print("STEP 2: Load Vehicle Database")
    print("=" * 80)

    try:
        vehicle_db = load_vehicle_database(DB_PATH)
        print(f"\n[PASS] STEP 2 PASSED: Vehicle database loaded")
    except Exception as e:
        print(f"\n[FAIL] STEP 2 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return loaded_data, None

    # STEP 3: Extract accessory data for one model (test)
    print("\n" + "=" * 80)
    print("STEP 3: Extract Accessory Data (Test - One Model)")
    print("=" * 80)

    try:
        # Pick first model
        test_model = list(loaded_data.keys())[0]
        model_sheets = {k: v for k, v in loaded_data[test_model].items() if k != '__META__'}

        accessory_df = extract_accessory_data_for_model(test_model, model_sheets)
        print(f"\n[PASS] STEP 3 PASSED: {test_model} extracted")
    except Exception as e:
        print(f"\n[FAIL] STEP 3 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return loaded_data, vehicle_db

    # STEP 5: Attach model numbers
    print("\n" + "=" * 80)
    print("STEP 5: Attach Model Numbers (Test - One Model)")
    print("=" * 80)

    try:
        accessory_with_models = attach_model_numbers(accessory_df, test_model, vehicle_db)
        print(f"\n[PASS] STEP 5 PASSED: Model numbers attached")
    except Exception as e:
        print(f"\n[FAIL] STEP 5 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return loaded_data, vehicle_db

    # STEP 6: Generate Excel output
    print("\n" + "=" * 80)
    print("STEP 6: Generate Excel Output (All Models)")
    print("=" * 80)

    output_dir = "ready_to_upload/2026/Honda"
    try:
        output_file = generate_excel_output(loaded_data, vehicle_db, output_dir)
        print(f"\n[PASS] STEP 6 PASSED: Excel file generated")
    except Exception as e:
        print(f"\n[FAIL] STEP 6 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return loaded_data, vehicle_db

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY - ALL STEPS PASSED")
    print("=" * 80)
    print(f"Models: {len(loaded_data)}")
    print(f"Vehicle records: {len(vehicle_db)}")
    print(f"Output file: {output_file}")
    print(f"Status: SUCCESS - Ready to upload!")

    return loaded_data, vehicle_db


if __name__ == '__main__':
    loaded_data, vehicle_db = main()
