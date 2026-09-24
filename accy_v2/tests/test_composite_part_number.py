"""Tests for Composite Part Number Normalization Utility

Test coverage for normalize_composite_part_number() function.
Target: >80% coverage of all branches.
"""

import pytest
from accy_v2.core.helpers.composite_part_number import normalize_composite_part_number


class TestCompositePartNumberNormalization:
    """Test suite for composite part number normalization."""

    # ========== Basic Cases ==========

    def test_single_part_number_no_separator(self):
        """No separator → return unchanged."""
        assert normalize_composite_part_number("50977-565-45BH", "EN") == "50977-565-45BH"

    def test_with_or_separator_en(self):
        """EN "or" separator → left side."""
        result = normalize_composite_part_number("50977-565-45BH or 50977-565-45SH", "EN")
        assert result == "50977-565-45BH"

    def test_with_ou_separator_fr(self):
        """FR "ou" separator → left side."""
        result = normalize_composite_part_number("50977-565-45BH ou 50977-565-45SH", "FR")
        assert result == "50977-565-45BH"

    # ========== Edge Cases ==========

    def test_null_input(self):
        """None input → None output."""
        assert normalize_composite_part_number(None, "EN") is None

    def test_empty_string(self):
        """Empty string → empty string."""
        assert normalize_composite_part_number("", "EN") == ""

    def test_left_side_empty(self):
        """Left side empty → use right."""
        result = normalize_composite_part_number(" or 50977-565-45SH", "EN")
        assert result == "50977-565-45SH"

    def test_right_side_empty(self):
        """Right side empty → use left."""
        result = normalize_composite_part_number("50977-565-45BH or ", "EN")
        assert result == "50977-565-45BH"

    def test_both_sides_empty(self):
        """Both sides empty → None."""
        result = normalize_composite_part_number(" or ", "EN")
        assert result is None

    # ========== Whitespace Handling ==========

    def test_extra_whitespace_left(self):
        """Left side with leading/trailing whitespace → stripped."""
        result = normalize_composite_part_number("  50977-565-45BH  or 50977-565-45SH", "EN")
        assert result == "50977-565-45BH"

    def test_extra_whitespace_right(self):
        """Right side with extra whitespace."""
        result = normalize_composite_part_number("50977-565-45BH or  50977-565-45SH  ", "EN")
        assert result == "50977-565-45BH"

    def test_multiple_spaces_around_separator(self):
        """Multiple spaces around separator."""
        result = normalize_composite_part_number("50977-565-45BH   or   50977-565-45SH", "EN")
        assert result == "50977-565-45BH"

    # ========== Multiple Separators ==========

    def test_multiple_or_separators(self):
        """Multiple separators → split on first only."""
        result = normalize_composite_part_number("A or B or C", "EN")
        assert result == "A"

    def test_multiple_ou_separators(self):
        """Multiple "ou" separators → split on first only."""
        result = normalize_composite_part_number("A ou B ou C", "FR")
        assert result == "A"

    # ========== Case Insensitivity ==========

    def test_uppercase_separator_en(self):
        """Uppercase "OR" → treated as separator (case-insensitive)."""
        result = normalize_composite_part_number("A OR B", "EN")
        assert result == "A"

    def test_mixed_case_separator_en(self):
        """Mixed case "Or" → treated as separator."""
        result = normalize_composite_part_number("A Or B", "EN")
        assert result == "A"

    def test_uppercase_ou_fr(self):
        """Uppercase "OU" for FR → treated as separator."""
        result = normalize_composite_part_number("A OU B", "FR")
        assert result == "A"

    # ========== Language Parameter ==========

    def test_invalid_language_uppercase(self):
        """Invalid language → ValueError."""
        with pytest.raises(ValueError) as excinfo:
            normalize_composite_part_number("A or B", "INVALID")
        assert "Invalid language" in str(excinfo.value)

    def test_language_case_insensitive_lowercase(self):
        """Language parameter is case-insensitive (lowercase accepted)."""
        result = normalize_composite_part_number("A or B", "en")
        assert result == "A"

    def test_language_case_insensitive_mixed(self):
        """Language parameter is case-insensitive (mixed case)."""
        result = normalize_composite_part_number("A ou B", "fr")
        assert result == "A"

    # ========== Real-World Examples ==========

    def test_real_world_en_example(self):
        """Real Honda part number example (EN)."""
        result = normalize_composite_part_number(
            "50977-565-45BH or 50977-565-45SH",
            "EN"
        )
        assert result == "50977-565-45BH"

    def test_real_world_fr_example(self):
        """Real Honda part number example (FR)."""
        result = normalize_composite_part_number(
            "50977-565-45BH ou 50977-565-45SH",
            "FR"
        )
        assert result == "50977-565-45BH"

    def test_part_number_with_hyphens_and_dashes(self):
        """Part number with hyphens (no conflict with separator)."""
        result = normalize_composite_part_number(
            "50977-565-45BH or 50977-565-45SH",
            "EN"
        )
        assert result == "50977-565-45BH"
        # Hyphens within part number don't interfere

    # ========== Separator in Content (Edge) ==========

    def test_separator_in_part_number_ignored(self):
        """Separator word appears only once (in part, not as separator)."""
        # "Order" contains "or" but not as standalone word
        result = normalize_composite_part_number("ORDERNUM123", "EN")
        assert result == "ORDERNUM123"  # Not treated as separator

    def test_word_boundary_matching(self):
        """Separator must be word boundary (space-delimited)."""
        # "morning" contains "or" but not as standalone word
        result = normalize_composite_part_number("morning123", "EN")
        assert result == "morning123"

    # ========== Parametrized Tests ==========

    @pytest.mark.parametrize("input_val,expected", [
        ("A or B", "A"),
        ("A OR B", "A"),
        ("A Or B", "A"),
        ("A oR B", "A"),
    ])
    def test_or_case_variations(self, input_val, expected):
        """Test various casings of "or" separator."""
        assert normalize_composite_part_number(input_val, "EN") == expected

    @pytest.mark.parametrize("input_val,expected", [
        ("A ou B", "A"),
        ("A OU B", "A"),
        ("A Ou B", "A"),
        ("A oU B", "A"),
    ])
    def test_ou_case_variations(self, input_val, expected):
        """Test various casings of "ou" separator (FR)."""
        assert normalize_composite_part_number(input_val, "FR") == expected

    @pytest.mark.parametrize("language", ["EN", "en", "En", "eN"])
    def test_language_case_variations_en(self, language):
        """Test all case variations of 'EN' language."""
        result = normalize_composite_part_number("A or B", language)
        assert result == "A"

    @pytest.mark.parametrize("language", ["FR", "fr", "Fr", "fR"])
    def test_language_case_variations_fr(self, language):
        """Test all case variations of 'FR' language."""
        result = normalize_composite_part_number("A ou B", language)
        assert result == "A"

    # ========== Boundary Conditions ==========

    def test_very_long_part_number(self):
        """Very long part number."""
        long_num = "A" * 100
        result = normalize_composite_part_number(f"{long_num} or B", "EN")
        assert result == long_num

    def test_special_characters_in_part_number(self):
        """Part numbers with special characters."""
        result = normalize_composite_part_number(
            "ABC-123.45/XYZ or DEF-456.78/XYZ",
            "EN"
        )
        assert result == "ABC-123.45/XYZ"

    def test_numeric_only_part_numbers(self):
        """Numeric-only part numbers."""
        result = normalize_composite_part_number("50977565 or 50977566", "EN")
        assert result == "50977565"


class TestCompositePartNumberIntegration:
    """Integration tests for composite part number normalization."""

    def test_normalize_list_of_part_numbers(self):
        """Apply normalization to list of part numbers."""
        part_numbers = [
            "50977-565-45BH or 50977-565-45SH",
            "ABC-123",
            None,
            "XYZ or",
        ]
        expected = [
            "50977-565-45BH",
            "ABC-123",
            None,
            "XYZ",
        ]

        result = [
            normalize_composite_part_number(pn, "EN")
            for pn in part_numbers
        ]
        assert result == expected

    def test_en_fr_consistency(self):
        """Ensure EN and FR normalize to same value."""
        en_part = "50977-565-45BH or 50977-565-45SH"
        fr_part = "50977-565-45BH ou 50977-565-45SH"

        en_result = normalize_composite_part_number(en_part, "EN")
        fr_result = normalize_composite_part_number(fr_part, "FR")

        assert en_result == fr_result == "50977-565-45BH"


class TestCompositePartNumberDataFrameIntegration:
    """Test integration with pandas (if available)."""

    def test_apply_to_dataframe_column(self):
        """Apply normalization to DataFrame column."""
        try:
            import pandas as pd

            df = pd.DataFrame({
                "part_number": [
                    "50977-565-45BH or 50977-565-45SH",
                    "ABC-123",
                    "XYZ ou",
                ],
            })

            df["normalized"] = df["part_number"].apply(
                lambda x: normalize_composite_part_number(x, "EN")
            )

            expected = [
                "50977-565-45BH",
                "ABC-123",
                "XYZ",
            ]

            assert df["normalized"].tolist() == expected

        except ImportError:
            pytest.skip("pandas not available")
