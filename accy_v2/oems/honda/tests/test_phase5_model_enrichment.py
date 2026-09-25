"""Unit Tests: Phase 5 - Model Lookup & Enrichment

Tests for vehicle year extraction and model number enrichment.
"""

import pytest
import pandas as pd
import numpy as np
from typing import Dict, Any

from accy_v2.oems.honda.pipeline.step3_5_extract_vehicle_year import extract_vehicle_year
from accy_v2.oems.honda.pipeline.step4_5_model_enrichment import (
    enrich_with_model_numbers,
    _add_model_number_columns,
)


# ============================================================================
# Test Data Fixtures
# ============================================================================

@pytest.fixture
def config():
    """Pipeline configuration."""
    return {
        "valid_year_range": {"min": 2020, "max": 2030},
        "model_lookup_rules": {
            "Honda": {
                "trim_column": "trim",
                "translator_config": "honda_translator.yaml",
                "classifier_config": "honda_classification.yaml",
            }
        }
    }


@pytest.fixture
def metadata_sample():
    """Sample metadata from Step 1."""
    return {
        "model_name": "Accord",
        "vehicle_year": 2026,
        "manufacturer": "Honda",
        "file_path": "test_file.xlsx",
    }


@pytest.fixture
def unified_data_sample():
    """Sample unified data from Step 2."""
    en_df = pd.DataFrame({
        "description": ["Floor Mat Set", "Cargo Cover"],
        "part_number": ["MAT001", "COVER001"],
        "installed_price": [60.00, 90.00],
    })

    fr_df = pd.DataFrame({
        "description": ["Tapis De Sol", "Couverture"],
        "part_number": ["MAT001", "COVER001"],
        "installed_price": [60.00, 90.00],
    })

    return {
        "packages": {
            "en_unified": en_df,
            "fr_unified": fr_df,
            "trim_columns": ["Civic", "Accord"],
        },
    }


# ============================================================================
# Test: Extract Vehicle Year
# ============================================================================

def test_extract_vehicle_year_valid(metadata_sample, config):
    """Test extracting valid vehicle year."""
    result = extract_vehicle_year(metadata_sample, config)

    assert result["vehicle_year"] == 2026
    assert isinstance(result["vehicle_year"], int)


def test_extract_vehicle_year_string_conversion(config):
    """Test converting string year to int."""
    metadata = {
        "model_name": "Civic",
        "vehicle_year": "2025",
        "manufacturer": "Honda",
    }

    result = extract_vehicle_year(metadata, config)

    assert result["vehicle_year"] == 2025
    assert isinstance(result["vehicle_year"], int)


def test_extract_vehicle_year_missing():
    """Test missing vehicle year."""
    metadata = {"model_name": "Civic"}
    config = {"valid_year_range": {"min": 2020, "max": 2030}}

    with pytest.raises(ValueError, match="vehicle_year not found"):
        extract_vehicle_year(metadata, config)


def test_extract_vehicle_year_invalid_format(config):
    """Test invalid year format."""
    metadata = {
        "model_name": "Civic",
        "vehicle_year": "not_a_year",
    }

    with pytest.raises(ValueError, match="cannot be converted to int"):
        extract_vehicle_year(metadata, config)


def test_extract_vehicle_year_below_min(config):
    """Test year below minimum range."""
    metadata = {
        "model_name": "Civic",
        "vehicle_year": 2019,
    }

    with pytest.raises(ValueError, match="outside valid range"):
        extract_vehicle_year(metadata, config)


def test_extract_vehicle_year_above_max(config):
    """Test year above maximum range."""
    metadata = {
        "model_name": "Civic",
        "vehicle_year": 2031,
    }

    with pytest.raises(ValueError, match="outside valid range"):
        extract_vehicle_year(metadata, config)


def test_extract_vehicle_year_custom_range():
    """Test extraction with custom year range."""
    metadata = {
        "model_name": "Civic",
        "vehicle_year": 2022,
    }
    config = {"valid_year_range": {"min": 2020, "max": 2025}}

    result = extract_vehicle_year(metadata, config)
    assert result["vehicle_year"] == 2022


def test_extract_vehicle_year_boundary_min(config):
    """Test year at minimum boundary."""
    metadata = {
        "model_name": "Civic",
        "vehicle_year": 2020,
    }

    result = extract_vehicle_year(metadata, config)
    assert result["vehicle_year"] == 2020


def test_extract_vehicle_year_boundary_max(config):
    """Test year at maximum boundary."""
    metadata = {
        "model_name": "Civic",
        "vehicle_year": 2030,
    }

    result = extract_vehicle_year(metadata, config)
    assert result["vehicle_year"] == 2030


# ============================================================================
# Test: Add Model Number Columns
# ============================================================================

def test_add_model_number_columns_no_match():
    """Test adding model number columns when no match found."""
    df = pd.DataFrame({
        "description": ["Item 1", "Item 2"],
        "trim": ["Civic", "Accord"],
    })

    trim_lookup_cache = {
        "Civic": None,
        "Accord": None,
    }

    result = _add_model_number_columns(df, ["trim"], trim_lookup_cache, "test")

    assert "model_number" in result.columns
    assert "model_status" in result.columns
    assert all(result["model_status"] == "NOT_FOUND")
    assert all(result["model_number"].isna())


def test_add_model_number_columns_with_match():
    """Test adding model number columns with matches."""
    from accy_v2.model_lookup.search_engine import SearchResult

    df = pd.DataFrame({
        "description": ["Item 1"],
        "trim": ["Civic"],
    })

    # Create mock SearchResult
    class MockSearchResult:
        def __init__(self, model_number, confidence):
            self.model_number = model_number
            self.confidence = confidence
            self.packages = None

    trim_lookup_cache = {
        "Civic": MockSearchResult("12345", 0.95),
    }

    result = _add_model_number_columns(df, ["trim"], trim_lookup_cache, "test")

    assert result["model_number"].iloc[0] == "12345"
    assert result["model_status"].iloc[0] == "EXACT_MATCH"


def test_add_model_number_columns_high_confidence():
    """Test high confidence match."""
    class MockSearchResult:
        def __init__(self, model_number, confidence):
            self.model_number = model_number
            self.confidence = confidence

    df = pd.DataFrame({
        "description": ["Item 1"],
        "trim": ["Civic"],
    })

    trim_lookup_cache = {
        "Civic": MockSearchResult("12345", 0.85),
    }

    result = _add_model_number_columns(df, ["trim"], trim_lookup_cache, "test")

    assert result["model_status"].iloc[0] == "HIGH_CONFIDENCE"


def test_add_model_number_columns_low_confidence():
    """Test low confidence match."""
    class MockSearchResult:
        def __init__(self, model_number, confidence):
            self.model_number = model_number
            self.confidence = confidence

    df = pd.DataFrame({
        "description": ["Item 1"],
        "trim": ["Civic"],
    })

    trim_lookup_cache = {
        "Civic": MockSearchResult("12345", 0.70),
    }

    result = _add_model_number_columns(df, ["trim"], trim_lookup_cache, "test")

    assert result["model_status"].iloc[0] == "LOW_CONFIDENCE"


def test_add_model_number_columns_multiple_trims():
    """Test with multiple trim columns."""
    class MockSearchResult:
        def __init__(self, model_number, confidence):
            self.model_number = model_number
            self.confidence = confidence

    df = pd.DataFrame({
        "description": ["Item 1"],
        "trim1": ["Civic"],
        "trim2": ["Base"],
    })

    trim_lookup_cache = {
        "Civic": MockSearchResult("12345", 0.95),
        "Base": MockSearchResult("12346", 0.90),
    }

    result = _add_model_number_columns(
        df, ["trim1", "trim2"], trim_lookup_cache, "test"
    )

    # Should pick the best match (highest confidence)
    assert result["model_number"].iloc[0] == "12345"
    assert result["model_status"].iloc[0] == "EXACT_MATCH"


def test_add_model_number_columns_empty_df():
    """Test with empty DataFrame."""
    df = pd.DataFrame()
    trim_lookup_cache = {}

    result = _add_model_number_columns(df, [], trim_lookup_cache, "test")

    assert result.empty


# ============================================================================
# Test: Enrich with Model Numbers (Full Integration)
# ============================================================================

def test_enrich_with_model_numbers_basic(unified_data_sample, metadata_sample, config):
    """Test full enrichment flow."""
    reconciliation_map = {}

    enriched_data, updated_metadata, warnings = enrich_with_model_numbers(
        unified_data_sample, reconciliation_map, metadata_sample, config
    )

    assert "packages" in enriched_data
    assert "en_enriched" in enriched_data["packages"]
    assert "model_number" in enriched_data["packages"]["en_enriched"].columns
    assert "model_status" in enriched_data["packages"]["en_enriched"].columns


def test_enrich_with_model_numbers_no_sections(metadata_sample, config):
    """Test enrichment with empty sections."""
    unified_data = {}
    reconciliation_map = {}

    enriched_data, updated_metadata, warnings = enrich_with_model_numbers(
        unified_data, reconciliation_map, metadata_sample, config
    )

    assert enriched_data == {}
    assert len(warnings) == 0


def test_enrich_with_model_numbers_empty_section(metadata_sample, config):
    """Test enrichment with empty section DataFrame."""
    unified_data = {
        "packages": {
            "en_unified": pd.DataFrame(),
            "fr_unified": None,
            "trim_columns": [],
        },
    }
    reconciliation_map = {}

    enriched_data, updated_metadata, warnings = enrich_with_model_numbers(
        unified_data, reconciliation_map, metadata_sample, config
    )

    # Should return section unchanged
    assert "packages" in enriched_data
    assert enriched_data["packages"]["en_unified"].empty


def test_enrich_with_model_numbers_missing_year():
    """Test enrichment with missing vehicle year."""
    metadata = {"model_name": "Civic", "manufacturer": "Honda"}
    unified_data = {"packages": {"en_unified": pd.DataFrame()}}
    config = {"model_lookup_rules": {"Honda": {}}}

    with pytest.raises(ValueError, match="vehicle_year"):
        enrich_with_model_numbers(unified_data, {}, metadata, config)


def test_enrich_with_model_numbers_missing_config(unified_data_sample, metadata_sample):
    """Test enrichment with missing model lookup config."""
    config = {"model_lookup_rules": {}}  # No Honda config

    with pytest.raises(ValueError, match="No model_lookup_rules"):
        enrich_with_model_numbers(unified_data_sample, {}, metadata_sample, config)


# ============================================================================
# Test: Edge Cases
# ============================================================================

def test_extract_year_none_value(config):
    """Test with None vehicle_year."""
    metadata = {"model_name": "Civic", "vehicle_year": None}

    with pytest.raises(ValueError):
        extract_vehicle_year(metadata, config)


def test_add_model_number_null_trim():
    """Test with null/NaN trim values."""
    df = pd.DataFrame({
        "description": ["Item 1"],
        "trim": [None],
    })

    trim_lookup_cache = {}
    result = _add_model_number_columns(df, ["trim"], trim_lookup_cache, "test")

    assert result["model_status"].iloc[0] == "NOT_FOUND"


def test_add_model_number_missing_trim_column():
    """Test when trim column doesn't exist in DataFrame."""
    df = pd.DataFrame({
        "description": ["Item 1"],
    })

    trim_lookup_cache = {}
    result = _add_model_number_columns(df, ["nonexistent_trim"], trim_lookup_cache, "test")

    assert result["model_status"].iloc[0] == "NOT_FOUND"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
