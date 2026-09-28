"""
STEP 1: HONDA DATA LOADING & METADATA EXTRACTION (REVISED FOR ACTUAL STRUCTURE)

Based on inspection of actual Honda files:
- Files have model-specific sheets (LoadFile, Trim, Master)
- No explicit EN/FR sheet split at sheet level
- Multiple data types per file

This test case:
1. Discovers actual sheet types in the file
2. Loads the primary data sheet (Master or LoadFile)
3. Extracts metadata from the actual data
4. Prints detailed outputs for verification
"""

import pandas as pd
import os
from pathlib import Path
from datetime import datetime
import json
import re

class HondaDataLoaderActual:
    """Load and extract from actual Honda file structure."""

    def __init__(self, verbose=True):
        self.verbose = verbose
        self.landing_zone = Path(r"C:\Users\paxm\OneDrive - PBS SYSTEMS\Desktop\Office\Projects\OEM Accessory project\OEM_Accessories_v1\landing_zone\2026\Honda")

    def print_section(self, title, char="=", width=80):
        """Print formatted section header."""
        if self.verbose:
            print(f"\n{char * width}")
            print(f"  {title}")
            print(f"{char * width}\n")

    def print_subsection(self, title, char="-", width=80):
        """Print subsection header."""
        if self.verbose:
            print(f"\n{char * width}")
            print(f"  {title}")
            print(f"{char * width}\n")

    def print_info(self, key, value, indent=2):
        """Print key-value info."""
        if self.verbose:
            prefix = " " * indent
            print(f"{prefix}{key}: {value}")

    def print_success(self, msg, indent=2):
        """Print success."""
        if self.verbose:
            prefix = " " * indent
            print(f"{prefix}✓ {msg}")

    def print_error(self, msg, indent=2):
        """Print error."""
        if self.verbose:
            prefix = " " * indent
            print(f"{prefix}✗ {msg}")

    def print_warning(self, msg, indent=2):
        """Print warning."""
        if self.verbose:
            prefix = " " * indent
            print(f"{prefix}⚠ {msg}")

    # ========================================================================
    # PHASE 1: DISCOVER SHEET STRUCTURE
    # ========================================================================

    def discover_sheets(self, file_path):
        """
        Discover and categorize all sheets in the file.

        Returns:
            Dict with categorized sheets
        """
        self.print_section("PHASE 1: DISCOVER SHEET STRUCTURE")

        try:
            excel_file = pd.ExcelFile(file_path)
            sheet_names = excel_file.sheet_names

            self.print_info("File name", os.path.basename(file_path))
            self.print_info("Total sheets", len(sheet_names))

            # Categorize sheets
            template_sheets = [s for s in sheet_names if s.lower() == "template"]
            loadfile_sheets = [s for s in sheet_names if "loadfile" in s.lower()]
            master_sheets = [s for s in sheet_names if " - master" in s.lower() or "- Master" in s]
            trim_sheets = [s for s in sheet_names if s not in template_sheets + loadfile_sheets + master_sheets]

            self.print_subsection("Sheet Categories")

            self.print_info("Template sheets", len(template_sheets))
            for sheet in template_sheets:
                print(f"      {sheet}")

            self.print_info("LoadFile sheets", len(loadfile_sheets))
            for sheet in loadfile_sheets:
                print(f"      {sheet}")

            self.print_info("Master sheets", len(master_sheets))
            for sheet in master_sheets[:5]:
                print(f"      {sheet}")
            if len(master_sheets) > 5:
                print(f"      ... and {len(master_sheets) - 5} more")

            self.print_info("Trim/Model sheets", len(trim_sheets))
            for sheet in trim_sheets[:5]:
                print(f"      {sheet}")
            if len(trim_sheets) > 5:
                print(f"      ... and {len(trim_sheets) - 5} more")

            return {
                "template_sheets": template_sheets,
                "loadfile_sheets": loadfile_sheets,
                "master_sheets": master_sheets,
                "trim_sheets": trim_sheets,
                "all_sheets": sheet_names
            }

        except Exception as e:
            self.print_error(f"Exception: {str(e)}")
            return None

    # ========================================================================
    # PHASE 2: LOAD PRIMARY DATA SHEET
    # ========================================================================

    def select_primary_sheet(self, sheet_categories):
        """
        Select which sheet to load as primary data source.

        Priority:
        1. Master sheets (consolidated data)
        2. LoadFile sheets (raw data)
        3. First trim sheet
        """
        if sheet_categories["master_sheets"]:
            return sheet_categories["master_sheets"][0]
        elif sheet_categories["loadfile_sheets"]:
            return sheet_categories["loadfile_sheets"][0]
        elif sheet_categories["trim_sheets"]:
            return sheet_categories["trim_sheets"][0]
        else:
            return None

    def load_data_sheet(self, file_path, sheet_name):
        """
        Load the primary data sheet.

        Returns:
            DataFrame
        """
        self.print_subsection(f"Load Sheet: {sheet_name}")

        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name)

            self.print_success(f"Loaded {len(df)} rows × {len(df.columns)} columns")
            self.print_info("Columns", list(df.columns))

            # Show sample data
            self.print_subsection("First 5 rows of data")
            print(df.head(5).to_string())

            return df

        except Exception as e:
            self.print_error(f"Exception loading sheet: {str(e)}")
            return None

    # ========================================================================
    # PHASE 3: EXTRACT METADATA
    # ========================================================================

    def extract_metadata(self, df, file_path):
        """
        Extract metadata from the data:
        - Model year (from data or filename)
        - Publication date (from last rows)
        - Model names (from sheet content)

        Returns:
            Dict with metadata
        """
        self.print_section("PHASE 3: EXTRACT METADATA")

        metadata = {
            "manufacture_validated": False,
            "model_year": None,
            "publication_date": None,
            "found_publication_date_string": False,
            "models_found": [],
            "data_issues": []
        }

        # ====================================================================
        # 3A: Extract model year
        # ====================================================================

        self.print_subsection("3A: Extract Model Year")

        # Strategy 1: From filename
        filename = os.path.basename(file_path)
        year_match = re.search(r'(202[5-9]|203[0-9])', filename)
        if year_match:
            year_from_filename = year_match.group(1)
            self.print_success(f"Year from filename: {year_from_filename}")
            metadata["model_year"] = year_from_filename

        # Strategy 2: From first data row (often has year)
        if "Year" in df.columns:
            first_year = df["Year"].dropna().iloc[0] if len(df["Year"].dropna()) > 0 else None
            if first_year:
                self.print_success(f"Year from 'Year' column: {first_year}")
                if not metadata["model_year"]:
                    metadata["model_year"] = str(first_year)

        # ====================================================================
        # 3B: Extract models found in data
        # ====================================================================

        self.print_subsection("3B: Extract Model Names")

        if "Model" in df.columns:
            unique_models = df["Model"].dropna().unique()[:10]
            self.print_info("Unique model values (first 10)", len(df["Model"].unique()))
            for model in unique_models:
                print(f"      - {model}")
            metadata["models_found"] = list(unique_models)

        # ====================================================================
        # 3C: Extract publication date
        # ====================================================================

        self.print_subsection("3C: Extract Publication Date")

        # Strategy 1: Look in last 10 rows for "publication" text
        self.print_info("Checking last 10 rows for publication date", "")
        print(df.tail(10).to_string())
        print()

        for idx in range(len(df) - 1, max(len(df) - 10, -1), -1):
            row_str = " ".join(df.iloc[idx].dropna().astype(str))

            if "publication" in row_str.lower():
                self.print_success(f"Found 'publication' text at row {idx}")
                print(f"      Row content: {row_str[:100]}")
                metadata["found_publication_date_string"] = True

                # Try to extract date from this row or nearby rows
                # Look for YYYY-MM-DD pattern
                date_pattern = r'(\d{4}-\d{2}-\d{2})'
                date_match = re.search(date_pattern, row_str)
                if date_match:
                    pub_date = date_match.group(1)
                    self.print_success(f"Found publication date: {pub_date}")
                    metadata["publication_date"] = pub_date
                break

        # Strategy 2: Look for date pattern anywhere in last 20 rows
        if not metadata["publication_date"]:
            self.print_info("Publication date not found with 'publication' text", "Searching for date patterns...")
            date_pattern = r'(\d{4}-\d{2}-\d{2})'
            for idx in range(len(df) - 1, max(len(df) - 20, -1), -1):
                row_str = " ".join(df.iloc[idx].dropna().astype(str))
                date_match = re.search(date_pattern, row_str)
                if date_match:
                    pub_date = date_match.group(1)
                    self.print_success(f"Found date pattern at row {idx}: {pub_date}")
                    metadata["publication_date"] = pub_date
                    break

        # ====================================================================
        # 3D: Validate Honda signature
        # ====================================================================

        self.print_subsection("3D: Validate Honda Signature")

        # Look for "Honda" or "Accessories" in first few rows
        first_rows_text = " ".join(df.head(10).values.flatten().astype(str))
        if "Honda" in first_rows_text:
            self.print_success("Found 'Honda' in first rows")
            metadata["manufacture_validated"] = True
        else:
            self.print_warning("Did not find 'Honda' text in first rows")

        return metadata

    # ========================================================================
    # PHASE 4: GENERATE REPORT
    # ========================================================================

    def generate_report(self, file_path):
        """
        Run complete process: discover → load → extract → report
        """
        self.print_section("HONDA DATA LOADING & EXTRACTION REPORT")
        self.print_info("File", os.path.basename(file_path))
        self.print_info("Timestamp", datetime.now().isoformat())

        # Phase 1: Discover
        sheet_categories = self.discover_sheets(file_path)
        if not sheet_categories:
            return None

        # Phase 2: Load
        primary_sheet = self.select_primary_sheet(sheet_categories)
        if not primary_sheet:
            self.print_error("Could not select primary data sheet")
            return None

        self.print_section(f"Selected Primary Sheet: {primary_sheet}")
        df = self.load_data_sheet(file_path, primary_sheet)
        if df is None:
            return None

        # Phase 3: Extract
        metadata = self.extract_metadata(df, file_path)

        # Phase 4: Report
        self.print_section("FINAL REPORT")

        report = {
            "file": os.path.basename(file_path),
            "timestamp": datetime.now().isoformat(),
            "status": "SUCCESS" if metadata["manufacture_validated"] else "PARTIAL",
            "primary_sheet": primary_sheet,
            "sheet_summary": {
                "template_sheets": len(sheet_categories["template_sheets"]),
                "loadfile_sheets": len(sheet_categories["loadfile_sheets"]),
                "master_sheets": len(sheet_categories["master_sheets"]),
                "trim_sheets": len(sheet_categories["trim_sheets"]),
                "total_sheets": len(sheet_categories["all_sheets"])
            },
            "data_shape": {
                "rows": len(df),
                "columns": len(df.columns),
                "column_names": list(df.columns)
            },
            "metadata": {
                "manufacture_validated": metadata["manufacture_validated"],
                "model_year": metadata["model_year"],
                "publication_date": metadata["publication_date"],
                "found_publication_date_string": metadata["found_publication_date_string"],
                "models_found": metadata["models_found"]
            }
        }

        print(json.dumps(report, indent=2))

        return report


# ============================================================================
# TEST CASES
# ============================================================================

def test_case_1():
    """Test Case 1: Single file - full extraction."""
    print("\n" + "="*80)
    print("TEST CASE 1: Load & Extract from Single Honda File")
    print("="*80)

    loader = HondaDataLoaderActual(verbose=True)

    # Get first file
    landing_zone = Path(r"C:\Users\paxm\OneDrive - PBS SYSTEMS\Desktop\Office\Projects\OEM Accessory project\OEM_Accessories_v1\landing_zone\2026\Honda")
    files = list(landing_zone.rglob("*.xlsx"))

    if files:
        report = loader.generate_report(str(files[0]))
        return report
    else:
        print("No files found")
        return None


def test_case_2():
    """Test Case 2: Multiple files - quick comparison."""
    print("\n" + "="*80)
    print("TEST CASE 2: Multiple Files - Quick Scan")
    print("="*80)

    loader = HondaDataLoaderActual(verbose=False)  # Less verbose for multiple files

    landing_zone = Path(r"C:\Users\paxm\OneDrive - PBS SYSTEMS\Desktop\Office\Projects\OEM Accessory project\OEM_Accessories_v1\landing_zone\2026\Honda")
    files = list(landing_zone.rglob("*.xlsx"))

    print(f"\nProcessing {min(5, len(files))} files...\n")

    reports = []
    for file_path in files[:5]:
        try:
            loader_instance = HondaDataLoaderActual(verbose=False)
            report = loader_instance.generate_report(str(file_path))
            if report:
                reports.append(report)
                print(f"✓ {report['file']}")
                print(f"    Year: {report['metadata']['model_year']}")
                print(f"    Sheets: {report['sheet_summary']['total_sheets']}")
                print(f"    Data: {report['data_shape']['rows']} rows")
        except Exception as e:
            print(f"✗ {os.path.basename(str(file_path))}: {str(e)}")

    print(f"\n\nSuccessfully processed: {len(reports)}/{min(5, len(files))}")
    return reports


if __name__ == "__main__":
    # Run both test cases
    report1 = test_case_1()
    # test_case_2()  # Uncomment for multiple files
