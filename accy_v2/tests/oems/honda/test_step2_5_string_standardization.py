#!/usr/bin/env python3
"""
Unit tests for Phase 2.5: String Standardization

Tests cover:
- normalize_unicode: Smart quotes, unicode dashes -> ASCII
- remove_newlines: Literal \n -> spaces
- split_composite: "part1 or part2" -> keep first, note original
- normalize_trim_markers: Markers (•, ✓, S, T, E) -> canonical states
- Integration test on real data (CVIC5D.xlsx)

Run with: python test_step2_5_string_standardization.py
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from accy_v2.oems.honda.pipeline import step2_string_standardization
from accy_v2.core.helpers.dq_logger import DQLogger
from accy_v2.core.helpers.pipeline_logger import PipelineLogger
from accy_v2.core.config_loader_v2 import ModularConfigLoader


class TestRunner:
    """Simple test runner without pytest"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def run_test(self, test_name, test_func):
        """Run a single test"""
        try:
            test_func()
            self.passed += 1
            print(f"✓ {test_name}")
        except AssertionError as e:
            self.failed += 1
            self.errors.append(f"✗ {test_name}: {e}")
            print(f"✗ {test_name}")
        except Exception as e:
            self.failed += 1
            self.errors.append(f"✗ {test_name}: ERROR: {e}")
            print(f"✗ {test_name} (ERROR)")

    def summary(self):
        """Print summary"""
        total = self.passed + self.failed
        print(f"\n{'='*70}")
        print(f"Test Summary: {self.passed}/{total} passed")
        if self.errors:
            print(f"\nFailures:")
            for error in self.errors:
                print(f"  {error}")
        print(f"{'='*70}")
        return self.failed == 0


# ============================================================================
# Test Functions
# ============================================================================

def test_normalize_unicode_basic():
    """Test basic unicode normalization"""
    df = pd.DataFrame({"description": ["test"]})
    unicode_map = {"'": "'"}
    result = step2_string_standardization._normalize_unicode(df, unicode_map, None)
    assert isinstance(result, pd.DataFrame)
    assert "test" in result["description"].iloc[0]


def test_remove_newlines_single():
    """Test single newline removal"""
    df = pd.DataFrame({"description": ["SPORT\nHybrid"]})
    result = step2_string_standardization._remove_newlines(df, {}, None)
    assert "\n" not in result["description"].iloc[0]
    assert "SPORT" in result["description"].iloc[0]
    assert "Hybrid" in result["description"].iloc[0]


def test_remove_newlines_multiple():
    """Test multiple newline removal"""
    df = pd.DataFrame({"description": ["Racing\nPackage\nPremium"]})
    result = step2_string_standardization._remove_newlines(df, {}, None)
    assert "\n" not in result["description"].iloc[0]


def test_remove_newlines_spaces_collapse():
    """Test space collapsing"""
    df = pd.DataFrame({"description": ["Premium   Package"]})
    result = step2_string_standardization._remove_newlines(df, {}, None)
    assert "   " not in result["description"].iloc[0]


def test_remove_newlines_trim():
    """Test leading/trailing space trimming"""
    df = pd.DataFrame({"description": ["  Racing Kit  "]})
    result = step2_string_standardization._remove_newlines(df, {}, None)
    assert result["description"].iloc[0] == "Racing Kit"


def test_split_composite_english():
    """Test English composite split"""
    df = pd.DataFrame({
        "part_number": ["480-SP or 480-GB"],
        "comments": [np.nan],
    })
    dq_logger = DQLogger(run_id="test", source_file="test.xlsx")
    result = step2_string_standardization._split_composite_part_numbers(df, dq_logger, "sheet", "model")

    assert result["part_number"].iloc[0] == "480-SP"
    assert "[Composite parts:" in str(result["comments"].iloc[0])


def test_split_composite_french():
    """Test French composite split"""
    df = pd.DataFrame({
        "part_number": ["480-SP ou 480-GB"],
        "comments": [np.nan],
    })
    dq_logger = DQLogger(run_id="test", source_file="test.xlsx")
    result = step2_string_standardization._split_composite_part_numbers(df, dq_logger, "sheet", "model")

    assert result["part_number"].iloc[0] == "480-SP"


def test_split_composite_preserves_comments():
    """Test that existing comments are preserved"""
    df = pd.DataFrame({
        "part_number": ["480-SP or 480-GB"],
        "comments": ["Standard"],
    })
    dq_logger = DQLogger(run_id="test", source_file="test.xlsx")
    result = step2_string_standardization._split_composite_part_numbers(df, dq_logger, "sheet", "model")

    assert "Standard" in str(result["comments"].iloc[0])
    assert "[Composite parts:" in str(result["comments"].iloc[0])


def test_split_composite_non_composite():
    """Test that non-composite parts are unchanged"""
    df = pd.DataFrame({
        "part_number": ["480-SP"],
        "comments": [np.nan],
    })
    dq_logger = DQLogger(run_id="test", source_file="test.xlsx")
    result = step2_string_standardization._split_composite_part_numbers(df, dq_logger, "sheet", "model")

    assert result["part_number"].iloc[0] == "480-SP"


def test_normalize_trim_markers_bullet():
    """Test bullet normalization"""
    df = pd.DataFrame({"trim_col": ["•"]})
    marker_mapping = {"•": "applicable"}
    result = step2_string_standardization._normalize_trim_markers(df, marker_mapping, None)

    assert result["trim_col"].iloc[0] == "applicable"


def test_normalize_trim_markers_checkmark():
    """Test checkmark normalization"""
    df = pd.DataFrame({"trim_col": ["✓"]})
    marker_mapping = {"✓": "applicable"}
    result = step2_string_standardization._normalize_trim_markers(df, marker_mapping, None)

    assert result["trim_col"].iloc[0] == "applicable"


def test_normalize_trim_markers_s():
    """Test S normalization"""
    df = pd.DataFrame({"trim_col": ["S"]})
    marker_mapping = {"S": "standard"}
    result = step2_string_standardization._normalize_trim_markers(df, marker_mapping, None)

    assert result["trim_col"].iloc[0] == "standard"


def test_normalize_trim_markers_t():
    """Test T normalization"""
    df = pd.DataFrame({"trim_col": ["T"]})
    marker_mapping = {"T": "tire_change"}
    result = step2_string_standardization._normalize_trim_markers(df, marker_mapping, None)

    assert result["trim_col"].iloc[0] == "tire_change"


def test_normalize_trim_markers_e():
    """Test E normalization"""
    df = pd.DataFrame({"trim_col": ["E"]})
    marker_mapping = {"E": "exchange"}
    result = step2_string_standardization._normalize_trim_markers(df, marker_mapping, None)

    assert result["trim_col"].iloc[0] == "exchange"


def test_normalize_trim_markers_zeros():
    """Test zero placeholder normalization"""
    df = pd.DataFrame({
        "col1": ["0"],
        "col2": ["0.0"],
        "col3": [""],
        "col4": ["N/A"],
    })
    marker_mapping = {
        "0": None,
        "0.0": None,
        "": None,
        "N/A": None,
    }
    result = step2_string_standardization._normalize_trim_markers(df, marker_mapping, None)

    assert pd.isna(result["col1"].iloc[0])
    assert pd.isna(result["col2"].iloc[0])
    assert pd.isna(result["col3"].iloc[0])
    assert pd.isna(result["col4"].iloc[0])


def test_extract_operation_params_unicode():
    """Test unicode parameter extraction"""
    trans_config = {
        "columns": {
            "description": {
                "operations": [
                    {
                        "name": "normalize_unicode",
                        "from_chars": ["'", "'"],
                        "to_chars": ["'", "'"],
                    }
                ]
            }
        }
    }

    params = step2_string_standardization._extract_operation_params(
        trans_config, "normalize_unicode"
    )

    assert isinstance(params, dict)
    assert len(params) == 2


def test_extract_operation_params_trim_mapping():
    """Test trim marker mapping extraction"""
    trans_config = {
        "columns": {
            "trim_columns": {
                "operations": [
                    {
                        "name": "normalize_trim_markers",
                        "mapping": {
                            "•": "applicable",
                            "S": "standard",
                            "0": None,
                        }
                    }
                ]
            }
        }
    }

    params = step2_string_standardization._extract_operation_params(
        trans_config, "normalize_trim_markers", "mapping"
    )

    assert params["•"] == "applicable"
    assert params["S"] == "standard"


def test_integration_phase2_5_cvic5d():
    """Integration test: Full Phase 2.5 on real Honda data"""
    # Load test data
    file_path = project_root / "accy_v2/data/landing_zone/honda/may_2026/CVIC5D.xlsx"
    config_root = project_root / "accy_v2/oems/honda/config"

    if not file_path.exists():
        print(f"⊘ Skipping integration test: {file_path} not found")
        return

    # Load configs
    config_loader = ModularConfigLoader("honda", config_root)
    config = config_loader.load_all()

    # Load EN sheet
    excel = pd.ExcelFile(file_path)
    en_sheet = "26MY_CIV5D_APP_EN"

    if en_sheet not in excel.sheet_names:
        print(f"⊘ Skipping integration test: Sheet {en_sheet} not found")
        return

    df_en = excel.parse(sheet_name=en_sheet, header=None)

    # Import pipeline steps
    from accy_v2.oems.honda.pipeline import step1_validation, step2_header_normalization

    dq_logger = DQLogger(run_id="test_phase2_5", source_file=str(file_path))
    pipeline_logger = PipelineLogger(
        run_id="test_phase2_5", log_path="accy_v2/output/pipeline_logs/honda"
    )

    # Run Phase 1
    meta_data = {"sheet_name": en_sheet}
    df_phase1, meta_phase1 = step1_validation.run(
        df_en, config, meta_data, dq_logger, pipeline_logger
    )

    # Run Phase 2
    df_phase2, meta_phase2 = step2_header_normalization.run(
        df_phase1, config, meta_phase1, dq_logger, pipeline_logger
    )

    # Run Phase 2.5
    df_phase2_5 = step2_string_standardization.run(
        df_phase2, config, meta_phase2, dq_logger, pipeline_logger
    )

    # Verify output
    assert df_phase2_5.shape == df_phase2.shape
    assert isinstance(df_phase2_5, pd.DataFrame)
    print(f"   -> Input: {df_phase2.shape}, Output: {df_phase2_5.shape}")


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    runner = TestRunner()

    print("="*70)
    print("Phase 2.5: String Standardization Unit Tests")
    print("="*70 + "\n")

    # Normalize Unicode Tests
    print("normalize_unicode() tests:")
    runner.run_test("test_normalize_unicode_basic", test_normalize_unicode_basic)

    # Remove Newlines Tests
    print("\nremove_newlines() tests:")
    runner.run_test("test_remove_newlines_single", test_remove_newlines_single)
    runner.run_test("test_remove_newlines_multiple", test_remove_newlines_multiple)
    runner.run_test("test_remove_newlines_spaces_collapse", test_remove_newlines_spaces_collapse)
    runner.run_test("test_remove_newlines_trim", test_remove_newlines_trim)

    # Split Composite Tests
    print("\nsplit_composite_part_numbers() tests:")
    runner.run_test("test_split_composite_english", test_split_composite_english)
    runner.run_test("test_split_composite_french", test_split_composite_french)
    runner.run_test("test_split_composite_preserves_comments", test_split_composite_preserves_comments)
    runner.run_test("test_split_composite_non_composite", test_split_composite_non_composite)

    # Normalize Trim Markers Tests
    print("\nnormalize_trim_markers() tests:")
    runner.run_test("test_normalize_trim_markers_bullet", test_normalize_trim_markers_bullet)
    runner.run_test("test_normalize_trim_markers_checkmark", test_normalize_trim_markers_checkmark)
    runner.run_test("test_normalize_trim_markers_s", test_normalize_trim_markers_s)
    runner.run_test("test_normalize_trim_markers_t", test_normalize_trim_markers_t)
    runner.run_test("test_normalize_trim_markers_e", test_normalize_trim_markers_e)
    runner.run_test("test_normalize_trim_markers_zeros", test_normalize_trim_markers_zeros)

    # Config Extraction Tests
    print("\n_extract_operation_params() tests:")
    runner.run_test("test_extract_operation_params_unicode", test_extract_operation_params_unicode)
    runner.run_test("test_extract_operation_params_trim_mapping", test_extract_operation_params_trim_mapping)

    # Integration Tests
    print("\nIntegration tests:")
    runner.run_test("test_integration_phase2_5_cvic5d", test_integration_phase2_5_cvic5d)

    # Summary
    success = runner.summary()
    sys.exit(0 if success else 1)
