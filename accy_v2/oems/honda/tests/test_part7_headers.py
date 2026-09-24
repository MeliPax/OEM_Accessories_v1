"""Unit Tests: Part 7 - Header Normalization & Section Extraction

Tests for extracting and normalizing section headers from validated Excel data.
"""

import pytest
import pandas as pd
import numpy as np
from typing import Dict, Any

from accy_v2.oems.honda.pipeline.step2_standardization import (
    _normalize_headers,
    _extract_section,
    _clean_section_data,
)


# ============================================================================
# Test Data Fixtures
# ============================================================================

@pytest.fixture
def config():
    """Pipeline configuration with column mappings."""
    return {
        "en_mappings": {
            "Description": "description",
            "Part Number": "part_number",
            "Dealer Net": "dealer_net",
            "List Price": "list_price",
            "FRT": "frt",
            "Installed Price": "installed_price",
        },
        "fr_mappings": {
            "La description": "description",
            "Numéro de pièce": "part_number",
            "Prix net": "dealer_net",
            "Prix de liste": "list_price",
            "T.F.F.": "frt",
            "Prix installé": "installed_price",
        },
        "strip_whitespace": True,
    }


@pytest.fixture
def en_df_sample():
    """Sample EN DataFrame from Step 1."""
    data = {
        "Description": [
            "Packages",  # Section header (row 0)
            "Floor Mat Set",
            "Cargo Cover",
            None,
            None,
        ],
        "Part Number": [
            "Part Number",
            "ABC123",
            "XYZ789",
            None,
            None,
        ],
        "Dealer Net": [
            "Dealer Net",
            50.00,
            75.00,
            None,
            None,
        ],
        "List Price": [
            "List Price",
            75.00,
            100.00,
            None,
            None,
        ],
        "FRT": [
            "FRT",
            10.00,
            15.00,
            None,
            None,
        ],
        "Installed Price": [
            "Installed Price",
            60.00,
            90.00,
            None,
            None,
        ],
    }
    return pd.DataFrame(data)


@pytest.fixture
def metadata_sample():
    """Sample metadata from Step 1."""
    return {
        "model_name": "Accord",
        "vehicle_year": 2026,
        "section_structure": {
            "packages": {
                "en_row": 0,
                "fr_row": 0,
                "en_header_row": 0,
                "fr_header_row": 0,
            },
            "wheels": {
                "en_row": 10,
                "fr_row": 10,
            },
        },
        "section_order": ["packages", "wheels", "exterior", "interior", "electrical", "paint_pens"],
        "trim_columns_per_section": {
            "packages": ["Civic", "Accord", "CR-V"],
            "wheels": ["LX", "EX"],
        },
    }


# ============================================================================
# Test: Extract Single Section
# ============================================================================

def test_extract_section_normal(en_df_sample, config):
    """Test extracting a section where headers are at section_row."""
    # Section header at row 0, data at row 1+
    result = _extract_section(
        en_df_sample,
        section_row=0,
        section_name="packages",
        column_mappings=config["en_mappings"],
        config=config,
    )

    assert result is not None
    assert list(result.columns) == [
        "description",
        "part_number",
        "dealer_net",
        "list_price",
        "frt",
        "installed_price",
    ]
    assert len(result) > 0


def test_extract_section_headers_normalized(en_df_sample, config):
    """Test that original column names map to canonical names."""
    result = _extract_section(
        en_df_sample,
        section_row=0,
        section_name="packages",
        column_mappings=config["en_mappings"],
        config=config,
    )

    # Check specific mappings
    assert "description" in result.columns
    assert "part_number" in result.columns
    assert "dealer_net" in result.columns
    assert "Description" not in result.columns  # Original name gone


def test_extract_section_data_cleaned(en_df_sample, config):
    """Test that data is cleaned (whitespace, nulls)."""
    result = _extract_section(
        en_df_sample,
        section_row=0,
        section_name="packages",
        column_mappings=config["en_mappings"],
        config=config,
    )

    # NaN values should be None
    assert result["description"].iloc[-1] is None or pd.isna(result["description"].iloc[-1])


def test_extract_section_missing_row():
    """Test handling of section_row out of bounds."""
    df = pd.DataFrame({"A": [1, 2, 3]})
    result = _extract_section(
        df,
        section_row=999,  # Out of bounds
        section_name="test",
        column_mappings={"A": "a"},
        config={},
    )
    assert result is None


# ============================================================================
# Test: Clean Section Data
# ============================================================================

def test_clean_whitespace(config):
    """Test that whitespace is trimmed from strings."""
    df = pd.DataFrame({
        "description": ["  Floor Mat  ", " Cargo   "],
        "part_number": ["ABC123 ", " XYZ789"],
    })

    result = _clean_section_data(df, config)

    assert result["description"].iloc[0] == "Floor Mat"
    assert result["description"].iloc[1] == "Cargo"
    assert result["part_number"].iloc[0] == "ABC123"
    assert result["part_number"].iloc[1] == "XYZ789"


def test_clean_null_handling(config):
    """Test that empty strings and 'nan' are converted to None."""
    df = pd.DataFrame({
        "description": ["Floor Mat", "", "nan", None],
        "part_number": ["ABC123", "XYZ", "DEF", ""],
    })

    result = _clean_section_data(df, config)

    # Empty strings should become None
    assert result["description"].iloc[1] is None
    assert result["description"].iloc[2] is None
    assert result["part_number"].iloc[3] is None


# ============================================================================
# Test: Normalize Headers (Full Flow)
# ============================================================================

def test_normalize_headers_single_section(en_df_sample, metadata_sample, config):
    """Test normalizing headers for a single section."""
    result = _normalize_headers(
        en_df_sample,
        fr_df=None,
        metadata=metadata_sample,
        config=config,
    )

    section_data = result.get("section_data", {})
    warnings = result.get("warnings", [])

    # Should have extracted packages section
    assert "packages" in section_data
    assert section_data["packages"]["en_df"] is not None
    assert section_data["packages"]["trim_columns"] == ["Civic", "Accord", "CR-V"]

    # FR missing should generate warning
    assert any("FR sheet missing" in w.get("message", "") for w in warnings)


def test_normalize_headers_trim_columns_included(en_df_sample, metadata_sample, config):
    """Test that trim columns are included in section output."""
    result = _normalize_headers(
        en_df_sample,
        fr_df=None,
        metadata=metadata_sample,
        config=config,
    )

    section_data = result["section_data"]
    assert "trim_columns" in section_data["packages"]
    assert section_data["packages"]["trim_columns"] == ["Civic", "Accord", "CR-V"]


def test_normalize_headers_both_languages(en_df_sample, metadata_sample, config):
    """Test normalizing headers for both EN and FR."""
    # Create FR DataFrame
    fr_df = pd.DataFrame({
        "La description": ["Packages", "Tapis", "Couverture"],
        "Numéro de pièce": ["Numéro de pièce", "ABC123", "XYZ789"],
        "Prix net": ["Prix net", 50.00, 75.00],
        "Prix de liste": ["Prix de liste", 75.00, 100.00],
        "T.F.F.": ["T.F.F.", 10.00, 15.00],
        "Prix installé": ["Prix installé", 60.00, 90.00],
    })

    result = _normalize_headers(
        en_df_sample,
        fr_df=fr_df,
        metadata=metadata_sample,
        config=config,
    )

    section_data = result["section_data"]
    assert section_data["packages"]["en_df"] is not None
    assert section_data["packages"]["fr_df"] is not None


# ============================================================================
# Test: Edge Cases
# ============================================================================

def test_extract_section_empty_df(config):
    """Test handling of empty DataFrame."""
    df = pd.DataFrame()
    result = _extract_section(
        df,
        section_row=0,
        section_name="test",
        column_mappings=config["en_mappings"],
        config=config,
    )
    assert result is None


def test_extract_section_no_data_after_header(config):
    """Test section with only headers, no data."""
    df = pd.DataFrame({
        "Description": ["Header"],
        "Part Number": ["Header"],
        "Dealer Net": ["Header"],
    })

    result = _extract_section(
        df,
        section_row=0,
        section_name="test",
        column_mappings=config["en_mappings"],
        config=config,
    )

    # Should still extract, but with no data rows
    assert result is not None


def test_extract_section_sparse_excel(config):
    """Test sparse Excel file (NaN values mixed with data)."""
    df = pd.DataFrame({
        "Description": ["Header", "Item 1", None, "Item 2", None],
        "Part Number": ["Header", "ABC", None, "XYZ", None],
        "Dealer Net": ["Header", 50.0, np.nan, 75.0, np.nan],
    })

    result = _extract_section(
        df,
        section_row=0,
        section_name="test",
        column_mappings=config["en_mappings"],
        config=config,
    )

    assert result is not None
    # NaN/None values should be preserved or converted consistently
    assert pd.isna(result["dealer_net"].iloc[2]) or result["dealer_net"].iloc[2] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
