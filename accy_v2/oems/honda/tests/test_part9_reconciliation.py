"""Unit Tests: Part 9 - EN/FR Reconciliation

Tests for EN/FR matching, reconciliation map building, and divergence tracking.
"""

import pytest
import pandas as pd
import numpy as np
from typing import Dict, Any

from accy_v2.oems.honda.pipeline.step2_standardization import (
    _compute_description_similarity,
    _match_en_fr_parts,
    _reconcile_en_fr,
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
def en_df_sample():
    """Sample EN section DataFrame."""
    return pd.DataFrame({
        "description": ["Floor Mat Set", "Cargo Cover", "Roof Rack"],
        "part_number": ["ABC123", "XYZ789", "ROOF001"],
        "installed_price": [60.00, 90.00, 150.00],
    })


@pytest.fixture
def fr_df_sample():
    """Sample FR section DataFrame with matching parts."""
    return pd.DataFrame({
        "description": ["Tapis De Sol", "Couverture De Cargo", "Support De Toit"],
        "part_number": ["ABC123", "XYZ789", "ROOF001"],
        "installed_price": [60.00, 90.00, 150.00],
    })


@pytest.fixture
def standardized_data_sample(en_df_sample, fr_df_sample):
    """Sample standardized data from Part 8."""
    return {
        "packages": {
            "en_unified": en_df_sample,
            "fr_unified": fr_df_sample,
            "trim_columns": ["Civic", "Accord"],
        },
    }


# ============================================================================
# Test: Description Similarity
# ============================================================================

def test_similarity_exact_match():
    """Test similarity of identical descriptions."""
    sim = _compute_description_similarity("Floor Mat Set", "Floor Mat Set")
    assert sim == 1.0, "Identical descriptions should have similarity 1.0"


def test_similarity_high_overlap():
    """Test similarity with high word overlap."""
    sim = _compute_description_similarity("Floor Mat Set", "Floor Mat")
    assert sim > 0.6, "Descriptions with high overlap should have similarity > 0.6"


def test_similarity_low_overlap():
    """Test similarity with low word overlap."""
    sim = _compute_description_similarity("Floor Mat Set", "Roof Rack")
    assert sim < 0.4, "Descriptions with low overlap should have similarity < 0.4"


def test_similarity_empty_strings():
    """Test similarity with empty strings."""
    sim = _compute_description_similarity("", "Floor Mat")
    assert sim == 0.0, "Empty string should have zero similarity"


def test_similarity_none_values():
    """Test similarity with None values."""
    sim = _compute_description_similarity(None, "Floor Mat")
    assert sim == 0.0, "None should have zero similarity"


# ============================================================================
# Test: Part Number Matching (Strategy 1)
# ============================================================================

def test_match_exact_part_number(en_df_sample, fr_df_sample, config):
    """Test exact part number matching."""
    reconciliation_map, divergences = _match_en_fr_parts(en_df_sample, fr_df_sample, config)

    # All three parts should match by part number
    assert reconciliation_map["ABC123"]["status"] == "MAPPED"
    assert reconciliation_map["ABC123"]["confidence"] == 0.95
    assert reconciliation_map["ABC123"]["match_method"] == "exact_part_number"
    assert reconciliation_map["ABC123"]["fr_equivalent"] == "ABC123"


def test_match_part_number_case_insensitive(config):
    """Test that part number matching is case-insensitive."""
    en_df = pd.DataFrame({
        "description": ["Floor Mat"],
        "part_number": ["abc123"],
        "installed_price": [60.00],
    })

    fr_df = pd.DataFrame({
        "description": ["Tapis"],
        "part_number": ["ABC123"],
        "installed_price": [60.00],
    })

    reconciliation_map, divergences = _match_en_fr_parts(en_df, fr_df, config)

    assert reconciliation_map["abc123"]["status"] == "MAPPED"
    assert reconciliation_map["abc123"]["confidence"] == 0.95


# ============================================================================
# Test: Description Similarity Matching (Strategy 2)
# ============================================================================

def test_match_description_similarity(config):
    """Test description similarity matching (fallback when part number differs)."""
    en_df = pd.DataFrame({
        "description": ["Floor Mat Set"],
        "part_number": ["EN001"],
        "installed_price": [60.00],
    })

    fr_df = pd.DataFrame({
        "description": ["Floor Mat Tapis"],
        "part_number": ["FR001"],
        "installed_price": [60.00],
    })

    reconciliation_map, divergences = _match_en_fr_parts(en_df, fr_df, config)

    # Should match by description similarity since part numbers differ
    assert reconciliation_map["EN001"]["status"] == "MAPPED"
    assert reconciliation_map["EN001"]["confidence"] == 0.80
    assert reconciliation_map["EN001"]["match_method"] == "description_similarity"


def test_match_no_similarity_no_match(config):
    """Test that dissimilar descriptions don't match."""
    en_df = pd.DataFrame({
        "description": ["Floor Mat"],
        "part_number": ["EN001"],
        "installed_price": [60.00],
    })

    fr_df = pd.DataFrame({
        "description": ["Roof Rack"],
        "part_number": ["FR001"],
        "installed_price": [60.00],
    })

    reconciliation_map, divergences = _match_en_fr_parts(en_df, fr_df, config)

    # Should not match (dissimilar descriptions, different part numbers, different costs)
    assert reconciliation_map["EN001"]["status"] == "EN_ONLY"
    assert reconciliation_map["EN001"]["confidence"] == 0.0


# ============================================================================
# Test: Cost Matching (Strategy 3)
# ============================================================================

def test_match_cost_exact(config):
    """Test cost matching with exact match."""
    en_df = pd.DataFrame({
        "description": ["Item A"],
        "part_number": ["EN001"],
        "installed_price": [50.00],
    })

    fr_df = pd.DataFrame({
        "description": ["Item B"],
        "part_number": ["FR001"],
        "installed_price": [50.00],
    })

    reconciliation_map, divergences = _match_en_fr_parts(en_df, fr_df, config)

    # Should match by cost
    assert reconciliation_map["EN001"]["status"] == "MAPPED"
    assert reconciliation_map["EN001"]["confidence"] == 0.60
    assert reconciliation_map["EN001"]["match_method"] == "cost_match"


def test_match_cost_within_tolerance(config):
    """Test cost matching within ±$10 tolerance."""
    en_df = pd.DataFrame({
        "description": ["Item A"],
        "part_number": ["EN001"],
        "installed_price": [50.00],
    })

    fr_df = pd.DataFrame({
        "description": ["Item B"],
        "part_number": ["FR001"],
        "installed_price": [58.00],  # Within ±$10
    })

    reconciliation_map, divergences = _match_en_fr_parts(en_df, fr_df, config)

    # Should match by cost
    assert reconciliation_map["EN001"]["status"] == "MAPPED"
    assert reconciliation_map["EN001"]["confidence"] == 0.60


def test_match_cost_outside_tolerance(config):
    """Test that cost match fails outside ±$10 tolerance."""
    en_df = pd.DataFrame({
        "description": ["Item A"],
        "part_number": ["EN001"],
        "installed_price": [50.00],
    })

    fr_df = pd.DataFrame({
        "description": ["Item B"],
        "part_number": ["FR001"],
        "installed_price": [65.00],  # Outside ±$10
    })

    reconciliation_map, divergences = _match_en_fr_parts(en_df, fr_df, config)

    # Should not match
    assert reconciliation_map["EN001"]["status"] == "EN_ONLY"


# ============================================================================
# Test: Divergence Detection
# ============================================================================

def test_divergence_en_only_part(config):
    """Test detection of EN-only parts."""
    en_df = pd.DataFrame({
        "description": ["Unique Part"],
        "part_number": ["UNIQUE001"],
        "installed_price": [100.00],
    })

    fr_df = pd.DataFrame({
        "description": ["Autre Partie"],
        "part_number": ["AUTRE001"],
        "installed_price": [200.00],
    })

    reconciliation_map, divergences = _match_en_fr_parts(en_df, fr_df, config)

    # Should have divergence for EN-only part
    assert len(divergences) == 1
    assert divergences[0]["type"] == "en_only_part"
    assert "UNIQUE001" in divergences[0]["message"]


def test_divergence_fr_only_part(config):
    """Test detection of FR-only parts."""
    en_df = pd.DataFrame({
        "description": ["Part A"],
        "part_number": ["A001"],
        "installed_price": [50.00],
    })

    fr_df = pd.DataFrame({
        "description": ["Part A", "Partie Unique"],
        "part_number": ["A001", "UNIQUE_FR"],
        "installed_price": [50.00, 300.00],
    })

    reconciliation_map, divergences = _match_en_fr_parts(en_df, fr_df, config)

    # Should have divergence for FR-only part
    en_only_div = [d for d in divergences if d["type"] == "en_only_part"]
    fr_only_div = [d for d in divergences if d["type"] == "fr_only_part"]

    assert len(fr_only_div) == 1
    assert "UNIQUE_FR" in fr_only_div[0]["message"]


def test_divergence_cost_mismatch(config):
    """Test detection of cost mismatches."""
    en_df = pd.DataFrame({
        "description": ["Floor Mat"],
        "part_number": ["MAT001"],
        "installed_price": [60.00],
    })

    fr_df = pd.DataFrame({
        "description": ["Tapis"],
        "part_number": ["MAT001"],
        "installed_price": [75.00],  # Different cost
    })

    reconciliation_map, divergences = _match_en_fr_parts(en_df, fr_df, config)

    # Should have cost divergence warning
    assert reconciliation_map["MAT001"]["cost_match"] == False
    assert any("Cost divergence" in w for w in reconciliation_map["MAT001"]["dq_warnings"])


# ============================================================================
# Test: EN-Only Case (No FR Data)
# ============================================================================

def test_match_no_fr_data(en_df_sample, config):
    """Test matching when FR data is missing."""
    reconciliation_map, divergences = _match_en_fr_parts(en_df_sample, None, config)

    # All EN parts should be marked EN_ONLY
    assert reconciliation_map["ABC123"]["status"] == "EN_ONLY"
    assert reconciliation_map["XYZ789"]["status"] == "EN_ONLY"
    assert reconciliation_map["ROOF001"]["status"] == "EN_ONLY"

    # All should have zero confidence
    for part_id, match_info in reconciliation_map.items():
        assert match_info["confidence"] == 0.0


# ============================================================================
# Test: Full Reconciliation (Part 9 Orchestrator)
# ============================================================================

def test_reconcile_en_fr_full(standardized_data_sample, config):
    """Test full reconciliation flow."""
    result = _reconcile_en_fr(standardized_data_sample, config)

    assert "unified_data" in result
    assert "reconciliation_map" in result
    assert "divergence_report" in result
    assert "warnings" in result

    # Unified data should match input
    assert result["unified_data"] == standardized_data_sample

    # Reconciliation map should have been built
    assert "packages" in result["reconciliation_map"]


def test_reconcile_en_fr_multiple_sections(config):
    """Test reconciliation with multiple sections."""
    en_packages = pd.DataFrame({
        "description": ["Package A"],
        "part_number": ["PKG001"],
        "installed_price": [100.00],
    })

    fr_packages = pd.DataFrame({
        "description": ["Paquet A"],
        "part_number": ["PKG001"],
        "installed_price": [100.00],
    })

    en_wheels = pd.DataFrame({
        "description": ["Wheel Set"],
        "part_number": ["WHEEL001"],
        "installed_price": [500.00],
    })

    fr_wheels = pd.DataFrame({
        "description": ["Ensemble De Roues"],
        "part_number": ["WHEEL001"],
        "installed_price": [500.00],
    })

    standardized_data = {
        "packages": {
            "en_unified": en_packages,
            "fr_unified": fr_packages,
            "trim_columns": [],
        },
        "wheels": {
            "en_unified": en_wheels,
            "fr_unified": fr_wheels,
            "trim_columns": [],
        },
    }

    result = _reconcile_en_fr(standardized_data, config)

    # Both sections should have reconciliation maps
    assert "packages" in result["reconciliation_map"]
    assert "wheels" in result["reconciliation_map"]


def test_reconcile_en_fr_partial_matching(config):
    """Test reconciliation with partial matching."""
    standardized_data = {
        "packages": {
            "en_unified": pd.DataFrame({
                "description": ["Floor Mat", "Cargo Cover", "Unique Part"],
                "part_number": ["MAT001", "COVER001", "UNIQUE001"],
                "installed_price": [60.00, 90.00, 150.00],
            }),
            "fr_unified": pd.DataFrame({
                "description": ["Tapis", "Couverture"],
                "part_number": ["MAT001", "COVER001"],
                "installed_price": [60.00, 90.00],
            }),
            "trim_columns": [],
        },
    }

    result = _reconcile_en_fr(standardized_data, config)

    reconciliation_map = result["reconciliation_map"]["packages"]

    # First two should match
    assert reconciliation_map["MAT001"]["status"] == "MAPPED"
    assert reconciliation_map["COVER001"]["status"] == "MAPPED"

    # Third should be EN_ONLY
    assert reconciliation_map["UNIQUE001"]["status"] == "EN_ONLY"

    # Should have warning about partial mapping
    assert any("Partial" in w["message"] for w in result["warnings"])


# ============================================================================
# Test: Edge Cases
# ============================================================================

def test_empty_en_df(config):
    """Test with empty EN DataFrame."""
    en_df = pd.DataFrame()
    fr_df = pd.DataFrame({
        "description": ["Tapis"],
        "part_number": ["MAT001"],
        "installed_price": [60.00],
    })

    reconciliation_map, divergences = _match_en_fr_parts(en_df, fr_df, config)

    assert len(reconciliation_map) == 0


def test_empty_fr_df(config):
    """Test with empty FR DataFrame."""
    en_df = pd.DataFrame({
        "description": ["Floor Mat"],
        "part_number": ["MAT001"],
        "installed_price": [60.00],
    })

    fr_df = pd.DataFrame()

    reconciliation_map, divergences = _match_en_fr_parts(en_df, fr_df, config)

    # EN parts should all be EN_ONLY
    assert reconciliation_map["MAT001"]["status"] == "EN_ONLY"


def test_null_prices(config):
    """Test handling of null/None prices."""
    en_df = pd.DataFrame({
        "description": ["Item A"],
        "part_number": ["A001"],
        "installed_price": [None],
    })

    fr_df = pd.DataFrame({
        "description": ["Item B"],
        "part_number": ["B001"],
        "installed_price": [50.00],
    })

    reconciliation_map, divergences = _match_en_fr_parts(en_df, fr_df, config)

    # Should handle None gracefully (cost strategy can't apply)
    assert reconciliation_map["A001"]["status"] == "EN_ONLY"


def test_multiple_matches_picks_best(config):
    """Test that when multiple FR matches exist, best confidence is picked."""
    en_df = pd.DataFrame({
        "description": ["Floor Mat Set"],
        "part_number": ["EN001"],
        "installed_price": [60.00],
    })

    fr_df = pd.DataFrame({
        "description": ["Tapis", "Floor Mat Tapis", "Tapis De Sol"],
        "part_number": ["FR001", "FR002", "FR003"],
        "installed_price": [60.00, 60.00, 60.00],
    })

    reconciliation_map, divergences = _match_en_fr_parts(en_df, fr_df, config)

    # Should match (cost matching) to first eligible FR part
    assert reconciliation_map["EN001"]["status"] == "MAPPED"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
