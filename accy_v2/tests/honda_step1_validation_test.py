"""Unit tests for Honda Step 1: Validation & Metadata Extraction

Tests each part independently:
- Part 1: Sheet loading and validation
- Part 2: Metadata extraction (Level 1 quick scan, Level 2 regex fallback)
- Part 3: Section detection
- Part 4: Column validation
- Part 5-6: Output formatting
"""

import pytest
import pandas as pd
import tempfile
from pathlib import Path
from openpyxl import Workbook

from accy_v2.oems.honda.pipeline.step1_validation import (
    validate,
    _load_sheets,
    _extract_metadata,
    ValidationError,
)


# ============================================================================
# Fixtures: Create test Excel files
# ============================================================================

@pytest.fixture
def config():
    """Load Honda pipeline config."""
    return {
        "metadata_extraction": {
            "level_1_quick_scan": {
                "enabled": True,
                "rows_to_scan": 5,
                "keywords": {
                    "model_name": {
                        "en": ["Model Name", "Model", "Name"],
                        "fr": ["Nom du modèle", "Modèle", "Nom"],
                    },
                    "model_year": {
                        "en": ["Model Year", "Year", "MY"],
                        "fr": ["Année modèle", "Année", "Year"],
                    },
                },
            },
            "level_2_regex_search": {
                "enabled": True,
                "scan_entire_sheet": True,
                "patterns": {
                    "model_name": {
                        "en": r"(?i)(model\s*name|nom\s*du\s*modèle)\s*:?\s*([A-Za-z0-9\s\-]+)",
                        "fr": r"(?i)(nom\s*du\s*modèle|modèle)\s*:?\s*([A-Za-z0-9\s\-]+)",
                    },
                    "model_year": {
                        "en": r"(?i)(model\s*year|année\s*modèle)\s*:?\s*(\d{4})",
                        "fr": r"(?i)(année\s*modèle|year)\s*:?\s*(\d{4})",
                    },
                },
            },
            "validation": {
                "year_range_min": 2020,
                "year_range_max": 2030,
                "model_name_required": True,
                "model_year_required": True,
            },
            "failure_action": "FATAL",
            "error_message": "Metadata extraction failed. Attempted: Level 1 (top 5 rows), Level 2 (regex search)",
        }
    }


def _create_test_excel_with_metadata(model_name: str, model_year: int, in_top_5: bool = True):
    """Helper: Create test Excel file with EN and FR sheets and metadata."""
    wb = Workbook()
    wb.remove(wb.active)  # Remove default sheet

    # Create EN sheet with metadata in top 5 rows (or buried deeper for fallback test)
    en_ws = wb.create_sheet("26MY_ACCORD_APP_EN")
    if in_top_5:
        en_ws["A1"] = "Model Name"
        en_ws["B1"] = model_name
        en_ws["A2"] = "Model Year"
        en_ws["B2"] = model_year
    else:
        # Bury metadata in row 50
        en_ws["A50"] = "Model Name"
        en_ws["B50"] = model_name
        en_ws["A51"] = "Model Year"
        en_ws["B51"] = model_year

    # Create FR sheet (minimal, just needs to exist)
    fr_ws = wb.create_sheet("26MY_ACCORD_APP_FR")
    fr_ws["A1"] = "Nom du modèle"
    fr_ws["B1"] = model_name

    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        wb.save(tmp.name)
        return tmp.name


def _create_test_excel_missing_sheets():
    """Helper: Create Excel file with missing EN/FR sheets."""
    wb = Workbook()
    # Just keep the default sheet (no *_APP_EN or *_APP_FR)
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        wb.save(tmp.name)
        return tmp.name


# ============================================================================
# Part 1: Sheet Validation Tests
# ============================================================================

class TestPartSheetValidation:
    """Tests for Part 1: Sheet loading and validation."""

    def test_load_sheets_success(self, config):
        """Test Case 1: Valid file with EN and FR sheets."""
        excel_file = _create_test_excel_with_metadata("Accord", 2026)
        try:
            en_df, fr_df, sheet_names = _load_sheets(excel_file, config)

            assert en_df is not None
            assert fr_df is not None
            assert sheet_names["en_sheet_name"] == "26MY_ACCORD_APP_EN"
            assert sheet_names["fr_sheet_name"] == "26MY_ACCORD_APP_FR"
            assert "Model Name" in en_df.iloc[:, 0].values or "Model Name" in en_df.columns
        finally:
            Path(excel_file).unlink()

    def test_load_sheets_missing_en(self, config):
        """Test Case 2: Missing EN sheet should raise ValidationError."""
        excel_file = _create_test_excel_missing_sheets()
        try:
            with pytest.raises(ValidationError, match="Missing required sheets"):
                _load_sheets(excel_file, config)
        finally:
            Path(excel_file).unlink()


# ============================================================================
# Part 2: Metadata Extraction Tests
# ============================================================================

class TestPartMetadataExtraction:
    """Tests for Part 2: Metadata extraction (Level 1 and Level 2)."""

    def test_metadata_level_1_success(self, config):
        """Test Case 3: Level 1 finds metadata in top 5 rows."""
        excel_file = _create_test_excel_with_metadata("Accord", 2026, in_top_5=True)
        try:
            en_df, fr_df, _ = _load_sheets(excel_file, config)
            metadata = _extract_metadata(en_df, fr_df, config)

            assert metadata["model_name"] == "Accord"
            assert metadata["vehicle_year"] == 2026
        finally:
            Path(excel_file).unlink()

    def test_metadata_level_2_fallback(self, config):
        """Test Case 4: Level 2 fallback finds metadata buried in sheet."""
        excel_file = _create_test_excel_with_metadata("Civic", 2025, in_top_5=False)
        try:
            en_df, fr_df, _ = _load_sheets(excel_file, config)
            metadata = _extract_metadata(en_df, fr_df, config)

            assert metadata["model_name"] == "Civic"
            assert metadata["vehicle_year"] == 2025
        finally:
            Path(excel_file).unlink()

    def test_metadata_both_levels_fail(self, config):
        """Test Case 5: Both levels fail should raise ValidationError."""
        # Create Excel with NO metadata anywhere
        wb = Workbook()
        wb.remove(wb.active)
        en_ws = wb.create_sheet("26MY_TEST_APP_EN")
        en_ws["A1"] = "Description"
        en_ws["B1"] = "Some Part"
        fr_ws = wb.create_sheet("26MY_TEST_APP_FR")
        fr_ws["A1"] = "Description"

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            wb.save(tmp.name)
            excel_file = tmp.name

        try:
            en_df, fr_df, _ = _load_sheets(excel_file, config)
            with pytest.raises(ValidationError, match="Model name extraction failed"):
                _extract_metadata(en_df, fr_df, config)
        finally:
            Path(excel_file).unlink()

    def test_metadata_year_out_of_range(self, config):
        """Test Case 9: Year outside [2020, 2030] should raise ValidationError."""
        excel_file = _create_test_excel_with_metadata("Accord", 2019)  # Before 2020
        try:
            en_df, fr_df, _ = _load_sheets(excel_file, config)
            with pytest.raises(ValidationError, match="out of range"):
                _extract_metadata(en_df, fr_df, config)
        finally:
            Path(excel_file).unlink()


# ============================================================================
# Integration Test: Full validate() function
# ============================================================================

class TestIntegration:
    """End-to-end tests of validate() function."""

    def test_validate_full_success(self, config):
        """Integration Test 1: Full validation on valid file."""
        excel_file = _create_test_excel_with_metadata("Accord", 2026)
        try:
            (en_df, fr_df), metadata, dq_warnings = validate(excel_file, config)

            assert metadata["model_name"] == "Accord"
            assert metadata["vehicle_year"] == 2026
            assert metadata["en_sheet_name"] == "26MY_ACCORD_APP_EN"
            assert metadata["fr_sheet_name"] == "26MY_ACCORD_APP_FR"
            # Parts 3-6 not yet implemented, so warnings may be incomplete
        finally:
            Path(excel_file).unlink()

    def test_validate_missing_sheets(self, config):
        """Integration Test 2: validate() raises on missing sheets."""
        excel_file = _create_test_excel_missing_sheets()
        try:
            with pytest.raises(ValidationError):
                validate(excel_file, config)
        finally:
            Path(excel_file).unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
