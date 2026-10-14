#!/usr/bin/env python3
"""
Unit tests for Phase 2: Header Normalization + Parent/Child Detection

Tests cover:
- Header extraction & normalization
- Parent/child classification (non-package and package sections)
- Parent index building with first-parent rule
- Integration test on real data (CVIC5D.xlsx)
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "accy_v2"))

from accy_v2.oems.honda.pipeline import step2_header_normalization
from accy_v2.core.helpers.dq_logger import DQLogger
from accy_v2.core.helpers.pipeline_logger import PipelineLogger
from accy_v2.core.config_loader_v2 import ModularConfigLoader


class TestHeaderExtraction:
    """Tests for header extraction and normalization"""

    def test_extract_header_row_basic(self):
        """Test basic header row extraction"""
        df = pd.DataFrame({
            0: ["data1", "data2"],
            1: ["data3", "data4"],
        })
        section_bounds = {"header_row": 0}

        header = step2_header_normalization._extract_header_row(df, section_bounds)

        assert header.iloc[0] == "data1"
        assert header.iloc[1] == "data3"

    def test_extract_column_names_en(self):
        """Test column name extraction with EN headers"""
        header_row = pd.Series({
            0: "Part Number",
            1: "Description",
            2: "List Price",
            3: np.nan,
        })

        names = step2_header_normalization._extract_column_names(header_row, language="EN")

        assert names[0] == "part number"
        assert names[1] == "description"
        assert names[2] == "list price"
        assert names[3] == "unnamed_3"

    def test_extract_column_names_fr(self):
        """Test column name extraction with FR headers"""
        header_row = pd.Series({
            0: "Numéro de pièce",
            1: "Description",
            2: "Prix de détail",
            3: np.nan,
        })

        names = step2_header_normalization._extract_column_names(header_row, language="FR")

        assert names[0] == "numéro de pièce"
        assert names[1] == "description"
        assert names[2] == "prix de détail"

    def test_normalize_header_names(self):
        """Test header name normalization using config"""
        raw_names = ["part number", "desc", "list", "dealer net", "frt"]
        detection_config = {
            "column_normalizations": {
                "part_number": ["part number", "part#", "part num"],
                "description": ["description", "desc", "product"],
                "list_price": ["list price", "list", "msrp"],
                "dealer_net": ["dealer net", "dealer cost"],
                "frt": ["frt", "f.r.t."],
            }
        }

        dq_logger = DQLogger(run_id="test", source_file="test.xlsx")
        norm_mapping = step2_header_normalization._normalize_header_names(
            raw_names, detection_config, "EN", dq_logger
        )

        assert norm_mapping[0] == "part_number"
        assert norm_mapping[1] == "description"
        assert norm_mapping[2] == "list_price"
        assert norm_mapping[3] == "dealer_net"
        assert norm_mapping[4] == "frt"


class TestNonPackageClassification:
    """Tests for non-package section classification"""

    def setup_method(self):
        """Setup common test data"""
        self.dq_logger = DQLogger(run_id="test", source_file="test.xlsx")
        self.norm_names = {
            0: "part_number",
            1: "description",
            2: "dealer_net",
            3: "list_price",
            4: "frt",
            5: "installed_price",
        }

    def test_classify_non_package_parent(self):
        """Test parent classification: BOTH product + ALL prices"""
        row = pd.Series({
            0: "ABC123",
            1: "Widget",
            2: 100.0,
            3: 150.0,
            4: 20.0,
            5: 170.0,
        })

        rtype = step2_header_normalization._classify_record_type(
            row, "Wheels", is_package=False, norm_names=self.norm_names, dq_logger=self.dq_logger
        )

        assert rtype == "parent"

    def test_classify_non_package_child(self):
        """Test child classification: BOTH product + NO prices"""
        row = pd.Series({
            0: "ABC123",
            1: "Widget",
            2: np.nan,
            3: np.nan,
            4: np.nan,
            5: np.nan,
        })

        rtype = step2_header_normalization._classify_record_type(
            row, "Wheels", is_package=False, norm_names=self.norm_names, dq_logger=self.dq_logger
        )

        assert rtype == "child"

    def test_classify_non_package_defect_no_product(self):
        """Test defect: missing product data"""
        row = pd.Series({
            0: np.nan,
            1: np.nan,
            2: 100.0,
            3: 150.0,
            4: 20.0,
            5: 170.0,
        })

        rtype = step2_header_normalization._classify_record_type(
            row, "Wheels", is_package=False, norm_names=self.norm_names, dq_logger=self.dq_logger
        )

        assert rtype is None

    def test_classify_non_package_defect_partial_prices(self):
        """Test defect: partial prices"""
        row = pd.Series({
            0: "ABC123",
            1: "Widget",
            2: 100.0,      # dealer_net filled
            3: np.nan,     # list_price empty
            4: np.nan,     # frt empty
            5: np.nan,     # installed_price empty
        })

        rtype = step2_header_normalization._classify_record_type(
            row, "Wheels", is_package=False, norm_names=self.norm_names, dq_logger=self.dq_logger
        )

        assert rtype is None  # Defect: partial prices


class TestPackageClassification:
    """Tests for package section classification"""

    def setup_method(self):
        """Setup common test data"""
        self.dq_logger = DQLogger(run_id="test", source_file="test.xlsx")
        self.norm_names = {
            0: "part_number",
            1: "description",
            2: "dealer_net",
            3: "list_price",
            4: "frt",
            5: "installed_price",
        }

    def test_classify_package_parent(self):
        """Test package parent: (product OR product) + ALL prices"""
        row = pd.Series({
            0: "PKG123",     # part_number filled
            1: np.nan,       # description empty (but part_number exists, so OK)
            2: 200.0,
            3: 250.0,
            4: 30.0,
            5: 280.0,
        })

        rtype = step2_header_normalization._classify_record_type(
            row, "Packages and Kits", is_package=True, norm_names=self.norm_names, dq_logger=self.dq_logger
        )

        assert rtype == "package_parent"

    def test_classify_package_child(self):
        """Test package child: product + NO prices"""
        row = pd.Series({
            0: np.nan,
            1: "Package Variant",
            2: np.nan,
            3: np.nan,
            4: np.nan,
            5: np.nan,
        })

        rtype = step2_header_normalization._classify_record_type(
            row, "Packages and Kits", is_package=True, norm_names=self.norm_names, dq_logger=self.dq_logger
        )

        assert rtype == "package_child"

    def test_classify_package_defect_no_product(self):
        """Test package defect: no product data"""
        row = pd.Series({
            0: np.nan,
            1: np.nan,
            2: 200.0,
            3: 250.0,
            4: 30.0,
            5: 280.0,
        })

        rtype = step2_header_normalization._classify_record_type(
            row, "Packages and Kits", is_package=True, norm_names=self.norm_names, dq_logger=self.dq_logger
        )

        assert rtype is None

    def test_classify_package_defect_partial_prices(self):
        """Test package defect: partial prices"""
        row = pd.Series({
            0: "PKG123",
            1: "Package Name",
            2: 200.0,      # dealer_net filled
            3: np.nan,     # list_price empty
            4: np.nan,     # frt empty
            5: np.nan,     # installed_price empty
        })

        rtype = step2_header_normalization._classify_record_type(
            row, "Packages and Kits", is_package=True, norm_names=self.norm_names, dq_logger=self.dq_logger
        )

        assert rtype is None  # Defect


class TestParentIndexBuilding:
    """Tests for parent index building (first-parent rule)"""

    def setup_method(self):
        """Setup common test data"""
        self.dq_logger = DQLogger(run_id="test", source_file="test.xlsx")

    def test_parent_index_first_parent_rule(self):
        """Test first-parent rule: child inherits from most recent parent"""
        record_types = {
            10: "parent",
            11: "child",
            12: "child",
            13: "parent",
            14: "child",
        }

        parent_index = step2_header_normalization._build_parent_index(
            10, 14, record_types, self.dq_logger
        )

        assert parent_index[10] is None  # First parent
        assert parent_index[11] == 10    # Child inherits from 10
        assert parent_index[12] == 10    # Child inherits from 10
        assert parent_index[13] is None  # New parent
        assert parent_index[14] == 13    # Child inherits from 13 (most recent)

    def test_parent_index_multiple_parents(self):
        """Test consecutive parents: each becomes new parent"""
        record_types = {
            10: "parent",
            11: "parent",
            12: "child",
            13: "child",
        }

        parent_index = step2_header_normalization._build_parent_index(
            10, 13, record_types, self.dq_logger
        )

        assert parent_index[10] is None  # First parent
        assert parent_index[11] is None  # New parent (replaces 10)
        assert parent_index[12] == 11    # Child from 11
        assert parent_index[13] == 11    # Child from 11

    def test_parent_index_orphaned_child(self):
        """Test orphaned child: child before any parent"""
        record_types = {
            10: "child",
            11: "parent",
            12: "child",
        }

        parent_index = step2_header_normalization._build_parent_index(
            10, 12, record_types, self.dq_logger
        )

        # Orphaned child (current_parent is None when encountered)
        assert parent_index[10] is None
        assert parent_index[11] is None
        assert parent_index[12] == 11


class TestIntegration:
    """Integration test on real Honda data"""

    def test_phase2_cvic5d(self):
        """Full Phase 2 run on CVIC5D.xlsx"""
        # Load test data
        file_path = project_root / "accy_v2/data/landing_zone/honda/may_2026/CVIC5D.xlsx"
        config_root = project_root / "accy_v2/oems/honda/config"

        if not file_path.exists():
            pytest.skip(f"Test file not found: {file_path}")

        # Load configs using ModularConfigLoader (structure.yaml via load_all)
        config_loader = ModularConfigLoader("honda", config_root)
        config = config_loader.load_all()

        # Load and process EN sheet
        excel = pd.ExcelFile(file_path)
        en_sheet = "26MY_CIV5D_APP_EN"

        if en_sheet not in excel.sheet_names:
            pytest.skip(f"Sheet not found: {en_sheet}")

        df_en = excel.parse(sheet_name=en_sheet, header=None)

        # Import Phase 1 to get metadata
        from accy_v2.oems.honda.pipeline import step1_validation

        dq_logger = DQLogger(run_id="test_integration", source_file=str(file_path))
        pipeline_logger = PipelineLogger(run_id="test_integration", log_path="accy_v2/output/pipeline_logs/honda")

        meta_data = {"sheet_name": en_sheet}
        df_processed, meta_from_phase1 = step1_validation.run(
            df_en, config, meta_data, dq_logger, pipeline_logger
        )

        # Run Phase 2
        df_phase2, meta_phase2 = step2_header_normalization.run(
            df_processed, config, meta_from_phase1, dq_logger, pipeline_logger
        )

        # Verify Phase 2 outputs
        assert "normalized_headers" in meta_phase2
        assert "column_mapping" in meta_phase2
        assert "price_columns" in meta_phase2
        assert "record_type_per_row" in meta_phase2
        assert "parent_row_index" in meta_phase2
        assert "record_type_counts" in meta_phase2

        # Verify normalized headers for each section
        assert len(meta_phase2["normalized_headers"]) == 6  # 6 sections

        # Verify price_columns is set correctly (Option B)
        assert meta_phase2["price_columns"] == ["dealer_net", "list_price", "frt", "installed_price"]

        # Verify record type counts
        record_type_counts = meta_phase2["record_type_counts"]
        assert sum(record_type_counts.values()) > 0  # At least some rows classified

        # Verify parent index entries
        assert len(meta_phase2["parent_row_index"]) > 0

        print(f"\n✅ Integration test passed!")
        print(f"   Sections: {len(meta_phase2['normalized_headers'])}")
        print(f"   Record types: {record_type_counts}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
