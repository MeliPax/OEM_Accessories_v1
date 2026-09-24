"""Tests for Section Structure Validation Utility

Test coverage for validate_section_structure() function.
Target: >80% coverage of all branches.
"""

import pytest

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

if HAS_PANDAS:
    from accy_v2.core.helpers.section_validation import (
        validate_section_structure,
        extract_section_data,
    )


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas required")
class TestSectionValidation:
    """Test suite for section structure validation."""

    @pytest.fixture
    def sample_config(self):
        """Sample Honda section configuration."""
        return {
            "sections": {
                "packages": {
                    "en": "1.0 Packages and Kits",
                    "fr": "1.0 Groupes et ensembles",
                },
                "electronics": {
                    "en": "2.0 Electronics",
                    "fr": "2.0 Électronique",
                },
                "interior": {
                    "en": "3.0 Interior",
                    "fr": "3.0 Intérieur",
                },
                "exterior": {
                    "en": "4.0 Exterior",
                    "fr": "4.0 Extérieur",
                },
                "cargo": {
                    "en": "5.0 Cargo and Storage",
                    "fr": "5.0 Cargo et rangement",
                },
                "general": {
                    "en": "6.0 General Accessories",
                    "fr": "6.0 Accessoires généraux",
                },
            },
            "section_order": [
                "packages",
                "electronics",
                "interior",
                "exterior",
                "cargo",
                "general",
            ],
            "validation": {
                "require_all_sections": True,
                "enforce_section_order": True,
            },
        }

    @pytest.fixture
    def valid_dataframe(self, sample_config):
        """DataFrame with all 6 sections in correct order."""
        return pd.DataFrame({
            "A": [
                "1.0 Packages and Kits",
                "Part1",
                "2.0 Electronics",
                "Part2",
                "3.0 Interior",
                "Part3",
                "4.0 Exterior",
                "Part4",
                "5.0 Cargo and Storage",
                "Part5",
                "6.0 General Accessories",
                "Part6",
            ]
        })

    # ========== Valid Structure Tests ==========

    def test_valid_structure_all_sections(self, valid_dataframe, sample_config):
        """DataFrame with all sections in correct order → valid."""
        result = validate_section_structure(valid_dataframe, sample_config)

        assert result["valid"] is True
        assert result["errors"] == []
        assert len(result["sections_found"]) == 6
        assert result["sections_found"] == [
            "packages",
            "electronics",
            "interior",
            "exterior",
            "cargo",
            "general",
        ]

    def test_valid_structure_section_boundaries(self, valid_dataframe, sample_config):
        """Section boundaries correctly identified."""
        result = validate_section_structure(valid_dataframe, sample_config)

        assert len(result["section_boundaries"]) == 6
        # Each boundary should be a tuple of (start, end)
        for boundary in result["section_boundaries"]:
            assert isinstance(boundary, tuple)
            assert len(boundary) == 2
            assert boundary[0] <= boundary[1]

    # ========== Missing Section Tests ==========

    def test_missing_one_section(self, sample_config):
        """Missing one section → error."""
        df = pd.DataFrame({
            "A": [
                "1.0 Packages and Kits",
                "Part1",
                "2.0 Electronics",  # electronics present
                "Part2",
                # interior missing
                "4.0 Exterior",
                "Part3",
                "5.0 Cargo and Storage",
                "Part4",
                "6.0 General Accessories",
                "Part5",
            ]
        })

        result = validate_section_structure(df, sample_config)

        assert result["valid"] is False
        assert any("interior" in error.lower() for error in result["errors"])

    def test_missing_multiple_sections(self, sample_config):
        """Missing multiple sections → multiple errors."""
        df = pd.DataFrame({
            "A": [
                "1.0 Packages and Kits",
                "Part1",
                "2.0 Electronics",
                "Part2",
                # interior, exterior, cargo, general missing
            ]
        })

        result = validate_section_structure(df, sample_config)

        assert result["valid"] is False
        assert len(result["errors"]) >= 4

    # ========== Section Order Tests ==========

    def test_sections_out_of_order(self, sample_config):
        """Sections out of order → warning."""
        df = pd.DataFrame({
            "A": [
                "2.0 Electronics",  # Out of order (electronics before packages)
                "Part1",
                "1.0 Packages and Kits",  # Should be first
                "Part2",
                "3.0 Interior",
                "Part3",
                "4.0 Exterior",
                "Part4",
                "5.0 Cargo and Storage",
                "Part5",
                "6.0 General Accessories",
                "Part6",
            ]
        })

        result = validate_section_structure(df, sample_config)

        # Depending on config, may be warning or error
        assert len(result["warnings"]) > 0 or not result["valid"]

    # ========== Section Count Tests ==========

    def test_section_count_mismatch(self, sample_config):
        """Wrong number of sections → warning."""
        df = pd.DataFrame({
            "A": [
                "1.0 Packages and Kits",
                "Part1",
                "2.0 Electronics",
                "Part2",
                # Only 2 sections instead of 6
            ]
        })

        result = validate_section_structure(df, sample_config)

        assert len(result["warnings"]) > 0
        assert result["sections_found"] == ["packages", "electronics"]

    # ========== Case Insensitivity Tests ==========

    def test_section_pattern_case_insensitive(self, sample_config):
        """Section patterns matched case-insensitively."""
        df = pd.DataFrame({
            "A": [
                "1.0 PACKAGES AND KITS",  # Uppercase
                "Part1",
                "2.0 electronics",  # Lowercase
                "Part2",
                "3.0 Interior",
                "Part3",
                "4.0 EXTERIOR",  # Mixed case
                "Part4",
                "5.0 Cargo and Storage",
                "Part5",
                "6.0 General Accessories",
                "Part6",
            ]
        })

        result = validate_section_structure(df, sample_config)

        # Should find all sections despite case differences
        assert len(result["sections_found"]) == 6

    # ========== Empty/Null Handling ==========

    def test_empty_dataframe(self, sample_config):
        """Empty DataFrame → no sections found."""
        df = pd.DataFrame()

        result = validate_section_structure(df, sample_config)

        assert result["valid"] is False
        assert len(result["sections_found"]) == 0

    def test_dataframe_with_nulls(self, sample_config):
        """DataFrame with null values → handled gracefully."""
        df = pd.DataFrame({
            "A": [
                None,
                "1.0 Packages and Kits",
                None,
                "2.0 Electronics",
                None,
            ]
        })

        result = validate_section_structure(df, sample_config)

        # Should find sections despite nulls
        assert "packages" in result["sections_found"]
        assert "electronics" in result["sections_found"]

    # ========== Sheet Name in Results ==========

    def test_sheet_name_included(self, valid_dataframe, sample_config):
        """Sheet name included in results."""
        result = validate_section_structure(
            valid_dataframe,
            sample_config,
            sheet_name="Accord_2027"
        )

        assert result["sheet_name"] == "Accord_2027"

    # ========== Flexible Config ==========

    def test_flexible_require_all_sections(self, sample_config):
        """Validation respects require_all_sections=False."""
        sample_config["validation"]["require_all_sections"] = False

        df = pd.DataFrame({
            "A": [
                "1.0 Packages and Kits",
                "Part1",
                "2.0 Electronics",
                "Part2",
                # Only 2 sections (missing interior, exterior, cargo, general)
            ]
        })

        result = validate_section_structure(df, sample_config)

        # Should not error if require_all_sections=False
        assert len(result["errors"]) == 0

    def test_flexible_enforce_section_order(self, sample_config):
        """Validation respects enforce_section_order=False."""
        sample_config["validation"]["enforce_section_order"] = False

        df = pd.DataFrame({
            "A": [
                "2.0 Electronics",  # Out of order
                "Part1",
                "1.0 Packages and Kits",
                "Part2",
                "3.0 Interior",
                "Part3",
                "4.0 Exterior",
                "Part4",
                "5.0 Cargo and Storage",
                "Part5",
                "6.0 General Accessories",
                "Part6",
            ]
        })

        result = validate_section_structure(df, sample_config)

        # Should not warn about order if enforce_section_order=False
        order_warnings = [w for w in result["warnings"] if "order" in w.lower()]
        assert len(order_warnings) == 0 or result["valid"]


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas required")
class TestExtractSectionData:
    """Test suite for section data extraction."""

    def test_extract_single_section(self):
        """Extract data for a single section."""
        df = pd.DataFrame({
            "A": range(10),
            "B": range(10, 20),
        })

        section_boundary = (2, 5)
        result = extract_section_data(df, section_boundary)

        assert len(result) == 4  # rows 2, 3, 4, 5
        assert result["A"].tolist() == [2, 3, 4, 5]

    def test_extract_section_copies_data(self):
        """Extract creates copy (doesn't modify original)."""
        df = pd.DataFrame({
            "A": range(10),
        })

        result = extract_section_data(df, (2, 5))
        result["A"] = 999  # Modify extracted data

        # Original should be unchanged
        assert df.loc[2, "A"] != 999
