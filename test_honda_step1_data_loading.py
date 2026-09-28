"""
STEP 1: HONDA DATA LOADING & METADATA EXTRACTION TEST SUITE

Objective: Clarify and test the data loading process for Honda Excel files.

Process Flow:
1. Locate Honda files (single or multi-file mode)
2. Validate sheet structure (EN/FR app sheets exist)
3. Load sheets into DataFrames
4. Extract and validate metadata (signature, model, year, publication date)
5. Return validated data + metadata

This test suite prints detailed output at each step to verify the process.
"""

import pandas as pd
import os
from pathlib import Path
from datetime import datetime
import json

class HondaDataLoader:
    """Load and extract metadata from Honda Excel files."""

    def __init__(self, verbose=True):
        self.verbose = verbose
        self.landing_zone = Path(r"C:\Users\paxm\OneDrive - PBS SYSTEMS\Desktop\Office\Projects\OEM Accessory project\OEM_Accessories_v1\landing_zone\2026\Honda")

    def print_section(self, title, char="="):
        """Print a formatted section header."""
        if self.verbose:
            print(f"\n{char * 80}")
            print(f"  {title}")
            print(f"{char * 80}\n")

    def print_info(self, key, value):
        """Print key-value info."""
        if self.verbose:
            print(f"  {key}: {value}")

    def print_success(self, msg):
        """Print success message."""
        if self.verbose:
            print(f"  ✓ {msg}")

    def print_error(self, msg):
        """Print error message."""
        if self.verbose:
            print(f"  ✗ {msg}")

    def print_warning(self, msg):
        """Print warning message."""
        if self.verbose:
            print(f"  ⚠ {msg}")

    # ========================================================================
    # STEP 1: LOCATE HONDA FILES
    # ========================================================================

    def locate_files(self, file_pattern=None, single_file=None):
        """
        Locate Honda Excel files.

        Args:
            file_pattern: Optional pattern to match (e.g., "2026*")
            single_file: Optional single file path

        Returns:
            List of file paths
        """
        self.print_section("STEP 1: LOCATE HONDA FILES")

        if single_file:
            self.print_info("Mode", "SINGLE FILE")
            if os.path.exists(single_file):
                self.print_success(f"Found file: {os.path.basename(single_file)}")
                return [single_file]
            else:
                self.print_error(f"File not found: {single_file}")
                return []

        # Multi-file mode
        self.print_info("Mode", "MULTI-FILE")
        self.print_info("Search location", str(self.landing_zone))

        excel_files = list(self.landing_zone.rglob("*.xlsx"))
        self.print_info("Total Excel files found", len(excel_files))

        if file_pattern:
            filtered = [f for f in excel_files if file_pattern in f.name]
            excel_files = filtered
            self.print_info(f"Files matching '{file_pattern}'", len(excel_files))

        if excel_files:
            self.print_success(f"Found {len(excel_files)} file(s)")
            for i, f in enumerate(excel_files[:5], 1):
                print(f"    {i}. {f.name}")
            if len(excel_files) > 5:
                print(f"    ... and {len(excel_files) - 5} more")
        else:
            self.print_error("No files found")

        return excel_files

    # ========================================================================
    # STEP 2: VALIDATE SHEETS
    # ========================================================================

    def validate_sheets(self, file_path):
        """
        Validate that file has EN and FR application sheets.

        Requirement: Sheets must match pattern *_APP_EN and *_APP_FR

        Returns:
            Dict with sheet info or None if validation fails
        """
        self.print_section(f"STEP 2: VALIDATE SHEETS - {os.path.basename(file_path)}")

        try:
            # Load Excel file
            excel_file = pd.ExcelFile(file_path)
            sheet_names = excel_file.sheet_names

            self.print_info("Total sheets in file", len(sheet_names))
            print(f"    Sheets: {', '.join(sheet_names[:10])}")
            if len(sheet_names) > 10:
                print(f"    ... and {len(sheet_names) - 10} more")

            # Find APP_EN and APP_FR sheets
            app_en_sheets = [s for s in sheet_names if "_APP_EN" in s]
            app_fr_sheets = [s for s in sheet_names if "_APP_FR" in s]

            self.print_info("APP_EN sheets found", len(app_en_sheets))
            for sheet in app_en_sheets:
                print(f"      - {sheet}")

            self.print_info("APP_FR sheets found", len(app_fr_sheets))
            for sheet in app_fr_sheets:
                print(f"      - {sheet}")

            if not app_en_sheets or not app_fr_sheets:
                self.print_error("Missing EN or FR application sheets")
                return None

            # Validate sheets are not empty
            en_sheet = app_en_sheets[0]
            fr_sheet = app_fr_sheets[0]

            df_en = pd.read_excel(file_path, sheet_name=en_sheet)
            df_fr = pd.read_excel(file_path, sheet_name=fr_sheet)

            en_rows = len(df_en)
            fr_rows = len(df_fr)

            self.print_info("EN sheet rows", en_rows)
            self.print_info("FR sheet rows", fr_rows)

            if en_rows == 0 or fr_rows == 0:
                self.print_error("One or both sheets are empty")
                return None

            self.print_success("Sheet validation passed")

            return {
                "file_path": file_path,
                "en_sheet": en_sheet,
                "fr_sheet": fr_sheet,
                "en_rows": en_rows,
                "fr_rows": fr_rows,
                "en_data": df_en,
                "fr_data": df_fr
            }

        except Exception as e:
            self.print_error(f"Exception: {str(e)}")
            return None

    # ========================================================================
    # STEP 3: EXTRACT METADATA
    # ========================================================================

    def extract_metadata(self, sheet_data):
        """
        Extract Honda manufacturer signature, model name, year, and publication date.

        Requirements:
        1. Find "1.0 Packages and Kits" section marker
        2. Look above it for: "Honda Accessories", Model Name, Model Year
        3. Look at last rows for: "publication Date" and date value (YYYY-MM-DD)

        Returns:
            Dict with extracted metadata
        """
        self.print_section("STEP 3: EXTRACT METADATA")

        metadata = {}
        df = sheet_data["en_data"]

        # Display first 20 rows to understand structure
        self.print_info("First 20 rows of data (to locate signature):", "")
        print("\n" + df.head(20).to_string())
        print("\n")

        # ====================================================================
        # 3A: FIND SIGNATURE AND MODEL INFO
        # ====================================================================

        self.print_section("3A: Find 'Packages and Kits' Section", char="-")

        # Search for "1.0 Packages and Kits" or "Packages and Kits"
        packages_row_idx = None
        for idx, row in df.iterrows():
            row_str = " ".join(row.dropna().astype(str))
            if "Packages and Kits" in row_str or "1.0 Packages" in row_str:
                packages_row_idx = idx
                self.print_success(f"Found 'Packages and Kits' at row {idx}")
                print(f"    Row content: {row_str[:100]}")
                break

        if packages_row_idx is None:
            self.print_warning("Could not find 'Packages and Kits' section marker")

        # Search above that row for Honda Accessories header and model info
        search_start = max(0, packages_row_idx - 10) if packages_row_idx else 0
        search_end = packages_row_idx if packages_row_idx else 10

        self.print_section("3B: Search for Signature & Model Info", char="-")
        print(f"    Searching rows {search_start} to {search_end}\n")

        for idx in range(search_start, search_end):
            if idx < len(df):
                row = df.iloc[idx]
                row_str = " ".join(row.dropna().astype(str))
                print(f"    Row {idx}: {row_str[:120]}")

        # Look for specific patterns
        signature_found = False
        model_name = None
        model_year = None

        for idx in range(search_start, search_end):
            if idx >= len(df):
                continue
            row = df.iloc[idx]
            row_str = " ".join(row.dropna().astype(str))

            # Pattern 1: "Honda Accessories" signature
            if "Honda Accessories" in row_str and not signature_found:
                self.print_success("Found Honda Accessories signature")
                signature_found = True
                metadata["manufacture_validated"] = True
                metadata["signature_row"] = idx

            # Pattern 2: Model name (e.g., "Civic", "Accord", "CR-V")
            # Look for row with model-like pattern
            if "Model" in row_str or "2026" in row_str or "2025" in row_str:
                print(f"    >> Potential model row {idx}: {row_str[:100]}")

        # More targeted: look for year pattern (2025, 2026, 2027)
        year_pattern = None
        for idx in range(search_start, search_end):
            if idx >= len(df):
                continue
            row = df.iloc[idx]
            row_list = row.dropna().astype(str).tolist()

            for val in row_list:
                if any(year in val for year in ["2025", "2026", "2027", "2024"]):
                    year_pattern = val
                    self.print_success(f"Found year pattern: {val}")
                    # Extract just the year
                    for year_candidate in ["2025", "2026", "2027", "2024"]:
                        if year_candidate in val:
                            model_year = year_candidate
                            break
                    break

        metadata["model_year"] = model_year
        metadata["manufacture_validated"] = signature_found

        # ====================================================================
        # 3C: EXTRACT PUBLICATION DATE
        # ====================================================================

        self.print_section("3C: Extract Publication Date", char="-")

        # Look at last 10 rows
        print(f"    Last 10 rows of data:\n")
        print(df.tail(10).to_string())
        print("\n")

        publication_date = None
        found_publication_string = False

        # Search from end upward
        for idx in range(len(df) - 1, max(len(df) - 10, -1), -1):
            row = df.iloc[idx]

            # Check if 3rd column (index 2) has "publication" text
            if len(row) > 2:
                col_2_val = str(row.iloc[2]) if pd.notna(row.iloc[2]) else ""

                if "publication" in col_2_val.lower():
                    found_publication_string = True
                    self.print_success(f"Found 'publication' text at row {idx}, column 3")
                    print(f"    Value: {col_2_val}")

                    # Get date from row above (if found_publication_string pattern)
                    if idx > 0:
                        row_above = df.iloc[idx - 1]
                        if len(row_above) > 2:
                            date_val = str(row_above.iloc[2]) if pd.notna(row_above.iloc[2]) else ""
                            print(f"    Date candidate (row {idx-1}, col 3): {date_val}")

                            # Validate YYYY-MM-DD format
                            if len(date_val) == 10 and date_val.count("-") == 2:
                                try:
                                    datetime.strptime(date_val, "%Y-%m-%d")
                                    publication_date = date_val
                                    self.print_success(f"Valid publication date: {publication_date}")
                                except ValueError:
                                    self.print_warning(f"Invalid date format: {date_val}")

        if not found_publication_string:
            self.print_warning("Could not find 'publication' text in last rows")

        metadata["found_publication_date_string"] = found_publication_string
        metadata["publication_date"] = publication_date

        return metadata

    # ========================================================================
    # STEP 4: GENERATE REPORT
    # ========================================================================

    def generate_report(self, file_path):
        """
        Run complete load and extraction for a file.
        """
        self.print_section("HONDA DATA LOADING & METADATA EXTRACTION REPORT")
        self.print_info("File", os.path.basename(file_path))
        self.print_info("Timestamp", datetime.now().isoformat())

        # Step 1: Locate (already have file)
        self.print_section("Step 1: File Located")
        self.print_info("Path", file_path)

        # Step 2: Validate sheets
        sheet_data = self.validate_sheets(file_path)
        if sheet_data is None:
            self.print_error("Sheet validation failed. Stopping.")
            return None

        # Step 3: Extract metadata
        metadata = self.extract_metadata(sheet_data)

        # Step 4: Summary
        self.print_section("EXTRACTION SUMMARY")

        summary = {
            "file": os.path.basename(file_path),
            "timestamp": datetime.now().isoformat(),
            "status": "SUCCESS" if metadata.get("manufacture_validated") else "FAILED",
            "metadata": {
                "manufacture_validated": metadata.get("manufacture_validated", False),
                "model_year": metadata.get("model_year"),
                "publication_date": metadata.get("publication_date"),
                "found_publication_date_string": metadata.get("found_publication_date_string", False),
            },
            "sheet_info": {
                "en_sheet": sheet_data["en_sheet"],
                "fr_sheet": sheet_data["fr_sheet"],
                "en_rows": sheet_data["en_rows"],
                "fr_rows": sheet_data["fr_rows"],
            }
        }

        print(json.dumps(summary, indent=2))

        return summary


# ============================================================================
# TEST CASES
# ============================================================================

def test_case_1_single_file():
    """Test Case 1: Load and extract metadata from a single file."""
    print("\n" + "="*80)
    print("TEST CASE 1: Single File Loading & Extraction")
    print("="*80)

    loader = HondaDataLoader(verbose=True)

    # Find first available file
    files = loader.locate_files()
    if files:
        report = loader.generate_report(files[0])
        return report
    else:
        print("No files found for testing")
        return None


def test_case_2_multiple_files():
    """Test Case 2: Process multiple files."""
    print("\n" + "="*80)
    print("TEST CASE 2: Multiple Files Processing")
    print("="*80)

    loader = HondaDataLoader(verbose=True)

    files = loader.locate_files()
    reports = []

    for file_path in files[:3]:  # Test first 3 files
        print(f"\n\nProcessing file {len(reports) + 1}/{min(3, len(files))}")
        try:
            report = loader.generate_report(file_path)
            if report:
                reports.append(report)
        except Exception as e:
            print(f"ERROR processing {file_path}: {e}")

    # Summary of all files
    print("\n" + "="*80)
    print("BATCH PROCESSING SUMMARY")
    print("="*80)
    print(f"Total files tested: {len(files)}")
    print(f"Successfully extracted: {len([r for r in reports if r['status'] == 'SUCCESS'])}")
    print(f"Failed: {len([r for r in reports if r['status'] == 'FAILED'])}")

    for report in reports:
        print(f"\n  {report['file']}: {report['status']}")
        if report['status'] == 'SUCCESS':
            print(f"    - Year: {report['metadata']['model_year']}")
            print(f"    - Publication Date: {report['metadata']['publication_date']}")

    return reports


if __name__ == "__main__":
    # Run Test Case 1: Single file
    test_case_1_single_file()

    # Uncomment for Test Case 2: Multiple files
    # test_case_2_multiple_files()
