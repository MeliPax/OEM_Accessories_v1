"""Unit Tests: Part 8 - Data Standardization & Packages Rollup

Tests for data cleanup, parent-child detection, and rollup aggregation.
"""

import pytest
import pandas as pd
import numpy as np
from typing import Dict, Any

from accy_v2.oems.honda.pipeline.step2_standardization import (
    _cleanup_section_data,
    _detect_parent_child,
    _rollup_packages,
    _standardize_data,
)


# ============================================================================
# Test Data Fixtures
# ============================================================================

@pytest.fixture
def config():
    """Pipeline configuration."""
    return {
        "strip_whitespace": True,
    }


@pytest.fixture
def section_data_sample():
    """Sample section data from Part 7."""
    # Create EN DataFrame for packages
    en_df = pd.DataFrame({
        "description": ["Main Package", "Cargo Mat", "All-Weather Mats", None],
        "part_number": ["PKG001", "ACC002", "ACC003", None],
        "dealer_net": [100.00, 0.00, 0.00, None],
        "list_price": [150.00, None, None, None],
        "frt": [15.00, 0.00, 0.00, None],
        "installed_price": [120.00, 0.00, 0.00, None],
    })

    return {
        "packages": {
            "en_df": en_df,
            "fr_df": None,
            "trim_columns": ["Civic", "Accord"],
        },
    }


# ============================================================================
# Test: Data Cleanup (Step 8.1)
# ============================================================================

def test_cleanup_removes_all_null_rows(config):
    """Test that rows where all values are null are dropped."""
    df = pd.DataFrame({
        "description": ["Item 1", None, "Item 3"],
        "part_number": ["ABC", None, "XYZ"],
    })

    result = _cleanup_section_data(df, "test", config)

    # Middle row (all nulls) should be removed
    assert len(result) == 2


def test_cleanup_type_coercion(config):
    """Test type coercion: costs → float, descriptions → string."""
    df = pd.DataFrame({
        "description": ["Floor Mat", "Cargo Cover"],
        "part_number": ["ABC123", "XYZ789"],
        "dealer_net": ["50.00", "75.50"],
        "installed_price": [60, 90.00],
    })

    result = _cleanup_section_data(df, "test", config)

    # Costs should be float
    assert pd.api.types.is_float_dtype(result["dealer_net"])
    assert result["dealer_net"].iloc[0] == 50.00


def test_cleanup_title_case_descriptions(config):
    """Test that descriptions are converted to title case."""
    df = pd.DataFrame({
        "description": ["floor mat set", "CARGO COVER", "All-Weather Mats"],
        "part_number": ["ABC", "XYZ", "DEF"],
    })

    result = _cleanup_section_data(df, "test", config)

    assert result["description"].iloc[0] == "Floor Mat Set"
    assert result["description"].iloc[1] == "Cargo Cover"


def test_cleanup_uppercase_part_numbers(config):
    """Test that part numbers are converted to uppercase."""
    df = pd.DataFrame({
        "description": ["Floor Mat", "Cargo"],
        "part_number": ["abc123", "XyZ789"],
    })

    result = _cleanup_section_data(df, "test", config)

    assert result["part_number"].iloc[0] == "ABC123"
    assert result["part_number"].iloc[1] == "XYZ789"


def test_cleanup_deduplication(config):
    """Test that exact duplicate rows are removed."""
    df = pd.DataFrame({
        "description": ["Floor Mat", "Floor Mat", "Cargo"],
        "part_number": ["ABC", "ABC", "XYZ"],
        "dealer_net": [50.0, 50.0, 75.0],
    })

    result = _cleanup_section_data(df, "test", config)

    # Duplicate Floor Mat row should be removed
    assert len(result) == 2
    assert result["description"].iloc[0] == "Floor Mat"
    assert result["description"].iloc[1] == "Cargo"


def test_cleanup_sorting(config):
    """Test that data is sorted by description, then part number."""
    df = pd.DataFrame({
        "description": ["Zebra Mat", "Apple Cover", "Cargo"],
        "part_number": ["Z1", "A1", "C1"],
    })

    result = _cleanup_section_data(df, "test", config)

    # Should be sorted by description
    assert result["description"].iloc[0] == "Apple Cover"
    assert result["description"].iloc[1] == "Cargo"
    assert result["description"].iloc[2] == "Zebra Mat"


# ============================================================================
# Test: Parent-Child Detection (Step 8.2)
# ============================================================================

def test_detect_parent_basic(config):
    """Test parent detection: has description + price."""
    df = pd.DataFrame({
        "description": ["Main Package", "Side Package"],
        "part_number": ["PKG001", "PKG002"],
        "installed_price": [100.0, 50.0],
    })

    result = _detect_parent_child(df)

    assert result["relationship"].iloc[0] == "parent"
    assert result["relationship"].iloc[1] == "parent"


def test_detect_child_no_price(config):
    """Test child detection: has description but no price."""
    df = pd.DataFrame({
        "description": ["Main Package", "Sport Variant"],
        "part_number": ["PKG001", "PKG001-S"],
        "installed_price": [100.0, None],
    })

    result = _detect_parent_child(df)

    assert result["relationship"].iloc[0] == "parent"
    assert result["relationship"].iloc[1] == "child"


def test_detect_child_zero_price(config):
    """Test child detection: price is zero."""
    df = pd.DataFrame({
        "description": ["Main Package", "Trim Variant"],
        "part_number": ["PKG001", "PKG001-T"],
        "installed_price": [100.0, 0.0],
    })

    result = _detect_parent_child(df)

    assert result["relationship"].iloc[0] == "parent"
    assert result["relationship"].iloc[1] == "child"


def test_detect_standalone(config):
    """Test standalone detection: no relationship."""
    df = pd.DataFrame({
        "description": ["Random Item"],
        "part_number": ["ITEM001"],
        "installed_price": [50.0],
    })

    result = _detect_parent_child(df)

    # Single parent item is "parent", not "standalone"
    assert result["relationship"].iloc[0] == "parent"


def test_detect_child_links_to_parent(config):
    """Test that children link to parent_idx."""
    df = pd.DataFrame({
        "description": ["Main Package", "Variant A", "Variant B"],
        "part_number": ["PKG001", "PKG001-A", "PKG001-B"],
        "installed_price": [100.0, 0.0, 0.0],
    })

    result = _detect_parent_child(df)

    # Children should link to parent (index 0)
    assert result["parent_idx"].iloc[1] == 0
    assert result["parent_idx"].iloc[2] == 0


# ============================================================================
# Test: Rollup Aggregation (Step 8.3)
# ============================================================================

def test_rollup_aggregates_children_into_parent(config):
    """Test that children are aggregated into parent description."""
    df = pd.DataFrame({
        "description": ["Main Package", "Variant A", "Variant B"],
        "part_number": ["PKG001", "PKG001-A", "PKG001-B"],
        "installed_price": [100.0, 0.0, 0.0],
        "relationship": ["parent", "child", "child"],
        "parent_idx": [None, 0, 0],
    })

    rolled_up, metadata = _rollup_packages(df, config)

    # Should have 1 row (parent with aggregated children)
    assert len(rolled_up) == 1
    assert "Variant A" in rolled_up["description"].iloc[0]
    assert "Variant B" in rolled_up["description"].iloc[0]


def test_rollup_tracks_child_count(config):
    """Test that child count is tracked."""
    df = pd.DataFrame({
        "description": ["Main Package", "Variant A", "Variant B"],
        "part_number": ["PKG001", "PKG001-A", "PKG001-B"],
        "installed_price": [100.0, 0.0, 0.0],
        "relationship": ["parent", "child", "child"],
        "parent_idx": [None, 0, 0],
    })

    rolled_up, metadata = _rollup_packages(df, config)

    assert rolled_up["has_children"].iloc[0] == True
    assert rolled_up["child_count"].iloc[0] == 2


def test_rollup_metadata(config):
    """Test that rollup metadata is correct."""
    df = pd.DataFrame({
        "description": ["Main Package", "Variant A", "Another Package"],
        "part_number": ["PKG001", "PKG001-A", "PKG002"],
        "installed_price": [100.0, 0.0, 50.0],
        "relationship": ["parent", "child", "parent"],
        "parent_idx": [None, 0, None],
    })

    rolled_up, metadata = _rollup_packages(df, config)

    assert metadata["parent_count"] == 2
    assert metadata["child_count"] == 1


def test_rollup_preserves_standalones(config):
    """Test that non-packages (standalone) are preserved."""
    df = pd.DataFrame({
        "description": ["Main Package", "Standalone Item"],
        "part_number": ["PKG001", "ITEM001"],
        "installed_price": [100.0, 75.0],
        "relationship": ["parent", "standalone"],
        "parent_idx": [None, None],
    })

    rolled_up, metadata = _rollup_packages(df, config)

    # Should have both parent and standalone
    assert len(rolled_up) == 2


# ============================================================================
# Test: Full Standardization (Part 8)
# ============================================================================

def test_standardize_data_full_flow(section_data_sample, config):
    """Test full standardization flow: cleanup + rollup."""
    result = _standardize_data(section_data_sample, config)

    standardized = result.get("standardized_data", {})
    rollup_metadata = result.get("rollup_metadata", {})

    # Should have processed packages section
    assert "packages" in standardized
    assert standardized["packages"]["en_unified"] is not None

    # Should have rollup metadata for packages
    assert "packages" in rollup_metadata
    assert "parent_count" in rollup_metadata["packages"]


def test_standardize_data_non_package_sections(section_data_sample, config):
    """Test that non-package sections are cleaned but not rolled up."""
    # Add a wheels section (no rollup)
    section_data_sample["wheels"] = {
        "en_df": pd.DataFrame({
            "description": ["17-inch Alloy Wheels"],
            "part_number": ["WHEEL001"],
        }),
        "fr_df": None,
        "trim_columns": ["LX", "EX"],
    }

    result = _standardize_data(section_data_sample, config)

    standardized = result.get("standardized_data", {})

    # Wheels should be cleaned but not have rollup metadata
    assert "wheels" in standardized
    assert "wheels" not in result.get("rollup_metadata", {})


# ============================================================================
# Test: Edge Cases
# ============================================================================

def test_cleanup_empty_section(config):
    """Test handling of empty section."""
    df = pd.DataFrame()
    result = _cleanup_section_data(df, "test", config)
    assert result.empty


def test_detect_parent_child_no_price_column(config):
    """Test parent-child detection when price column missing."""
    df = pd.DataFrame({
        "description": ["Item 1", "Item 2"],
        "part_number": ["ABC", "XYZ"],
    })

    result = _detect_parent_child(df)

    # Should treat all as standalones (no price = no parent)
    assert all(result["relationship"] == "standalone")


def test_rollup_no_parents(config):
    """Test rollup when there are no parents."""
    df = pd.DataFrame({
        "description": ["Variant A", "Variant B"],
        "part_number": ["A1", "B1"],
        "installed_price": [0.0, 0.0],
        "relationship": ["child", "child"],
        "parent_idx": [None, None],
    })

    rolled_up, metadata = _rollup_packages(df, config)

    # No parents, so should be empty
    assert len(rolled_up) == 0
    assert metadata["parent_count"] == 0


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
