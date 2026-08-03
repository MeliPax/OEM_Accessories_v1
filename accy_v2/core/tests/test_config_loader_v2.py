"""
Unit tests for ModularConfigLoader (6-file YAML config structure)

DECISION [015]: Modular config structure (6-file YAML replacing single JSON)
Tests verify:
  - All 6 YAML files load successfully
  - Relative paths are resolved to absolute Paths
  - Schema validation (required keys present)
  - Output path derivation works correctly
"""

import pytest
from pathlib import Path
from accy_v2.core.config_loader_v2 import ModularConfigLoader, get_output_paths


class TestModularConfigLoader:
    """Test suite for ModularConfigLoader class."""

    @pytest.fixture
    def hyundai_config_root(self) -> Path:
        """Get path to Hyundai config directory."""
        return Path(__file__).parent.parent.parent / "oems" / "hyundai" / "config"

    @pytest.fixture
    def loader(self, hyundai_config_root) -> ModularConfigLoader:
        """Create loader instance for Hyundai."""
        return ModularConfigLoader("hyundai", hyundai_config_root)

    def test_loader_finds_project_root(self, loader):
        """Verify loader correctly identifies project root."""
        assert loader.project_root.exists()
        assert (loader.project_root / "run_pipeline.py").exists()

    def test_load_pipeline_config(self, loader):
        """Verify pipeline.yaml loads with expected structure."""
        config = loader.load_pipeline_config()
        assert isinstance(config, dict)
        assert "use_model_lookup" in config
        assert "non_null_threshold" in config
        assert config["use_model_lookup"] is True
        assert config["non_null_threshold"] == 0.5

    def test_load_upstream_schema(self, loader):
        """Verify upstream.yaml loads with expected structure."""
        schema = loader.load_upstream_schema()
        assert isinstance(schema, dict)
        assert "languages" in schema
        assert "columns" in schema
        assert schema["languages"] == ["EN", "FR"]
        assert "model" in schema["columns"]
        assert "part_number" in schema["columns"]

    def test_load_intermediate_schema(self, loader):
        """Verify intermediate.yaml loads with expected structure."""
        schema = loader.load_intermediate_schema()
        assert isinstance(schema, dict)
        assert "required_columns" in schema
        assert "optional_columns" in schema
        assert "language_requirements" in schema
        assert "ModelYear" in schema["required_columns"]
        assert "Description" in schema["required_columns"]

    def test_load_downstream_schema(self, loader):
        """Verify downstream.yaml loads with expected structure."""
        schema = loader.load_downstream_schema()
        assert isinstance(schema, dict)
        assert "output" in schema
        assert "sheets" in schema
        # DECISION [019]: Check for renamed output_column_* fields
        assert "column_mapping" in schema["output"]
        assert "required_columns" in schema["output"]
        assert "Accessories" in schema["sheets"]
        assert "_Data_Issues" in schema["sheets"]
        assert "_Report" in schema["sheets"]

    def test_load_transformations(self, loader):
        """Verify transformations.yaml loads with expected structure."""
        config = loader.load_transformations()
        assert isinstance(config, dict)
        assert "columns" in config
        assert "ModelYear" in config["columns"]
        assert "Description" in config["columns"]
        # Check that columns have operations
        assert "operations" in config["columns"]["Description"]

    def test_load_enrichment(self, loader):
        """Verify enrichment.yaml loads with expected structure."""
        config = loader.load_enrichment()
        assert isinstance(config, dict)
        assert "model_lookup" in config
        assert "ads_fallback" in config
        assert "database" in config
        # DECISION [016]: Check use_model_lookup flag
        assert config["model_lookup"]["enabled"] is True
        # Check brands
        assert "Hyundai" in config["model_lookup"]["brands"]
        assert "Genesis" in config["model_lookup"]["brands"]

    def test_enrichment_paths_resolved_to_absolute(self, loader):
        """Verify relative paths in enrichment are resolved to absolute Paths."""
        config = loader.load_enrichment()

        # Check Hyundai paths are Path objects (not strings)
        hyundai = config["model_lookup"]["brands"]["Hyundai"]
        assert isinstance(hyundai["translator_config"], Path)
        assert isinstance(hyundai["classifier_config"], Path)
        assert isinstance(hyundai["standardization_config"], Path)

        # Check Genesis paths are Path objects
        genesis = config["model_lookup"]["brands"]["Genesis"]
        assert isinstance(genesis["translator_config"], Path)

        # Check database path is Path object
        assert isinstance(config["database"]["db_path"], Path)

    def test_load_all_configs(self, loader):
        """Verify all 6 configs load simultaneously."""
        all_configs = loader.load_all()

        # Verify structure
        assert "pipeline" in all_configs
        assert "schemas" in all_configs
        assert "transformations" in all_configs
        assert "enrichment" in all_configs

        # Verify schemas substructure
        assert "upstream" in all_configs["schemas"]
        assert "intermediate" in all_configs["schemas"]
        assert "downstream" in all_configs["schemas"]

        # Verify each is a dict
        assert isinstance(all_configs["pipeline"], dict)
        assert isinstance(all_configs["schemas"]["upstream"], dict)
        assert isinstance(all_configs["transformations"], dict)

    def test_detect_by_keyword_naming(self, loader):
        """Verify column detection uses 'detect_by_keyword' (new naming)."""
        schema = loader.load_upstream_schema()

        # Check at least one column has detect_by_keyword
        model_col = schema["columns"]["model"]
        assert "detect_by_keyword" in model_col
        assert "must_have" in model_col["detect_by_keyword"]

    def test_rename_to_canonical_naming(self, loader):
        """Verify column renaming uses 'rename_to_canonical' (new naming)."""
        schema = loader.load_upstream_schema()

        # Check that columns have rename_to_canonical
        model_col = schema["columns"]["model"]
        assert "rename_to_canonical" in model_col
        assert model_col["rename_to_canonical"] == "ModelName"

    def test_output_column_mapping_renamed(self, loader):
        """DECISION [019]: Verify rate_import_* renamed to output_column_*"""
        schema = loader.load_downstream_schema()

        # Should NOT have old names
        assert "rate_import_column_mapping" not in schema.get("output", {})
        assert "rate_import_required_columns" not in schema.get("output", {})

        # Should have new names
        assert "column_mapping" in schema["output"]
        assert "required_columns" in schema["output"]

    def test_file_not_found_error(self, hyundai_config_root, loader):
        """Verify error handling for missing config files."""
        # Create a loader with project root set, but point to non-existent file
        fake_config_root = Path(__file__).parent.parent.parent.parent / "nonexistent" / "config"

        fake_loader = ModularConfigLoader("fake", hyundai_config_root)
        fake_loader.config_root = fake_config_root

        # Should raise FileNotFoundError when trying to load
        with pytest.raises(FileNotFoundError):
            fake_loader.load_pipeline_config()


class TestGetOutputPaths:
    """Test suite for output path derivation."""

    def test_derive_output_paths_hyundai(self):
        """Verify output paths derived correctly for Hyundai."""
        paths = get_output_paths("hyundai")

        assert "ready_to_upload" in paths
        assert "dq_reports" in paths
        assert "pipeline_logs" in paths

        # Check path pattern
        assert "hyundai" in str(paths["ready_to_upload"]).lower()
        assert "hyundai" in str(paths["dq_reports"]).lower()
        assert "hyundai" in str(paths["pipeline_logs"]).lower()

    def test_derive_output_paths_mazda(self):
        """Verify output paths derived correctly for Mazda."""
        paths = get_output_paths("mazda")

        # Check all paths have mazda in them
        assert "mazda" in str(paths["ready_to_upload"]).lower()
        assert "mazda" in str(paths["dq_reports"]).lower()

    def test_output_paths_are_path_objects(self):
        """Verify output paths are Path objects."""
        paths = get_output_paths("hyundai")

        for key, path in paths.items():
            assert isinstance(path, Path), f"{key} should be Path object, got {type(path)}"

    def test_output_paths_consistent_pattern(self):
        """Verify all output path types follow consistent pattern."""
        paths = get_output_paths("hyundai")

        # All paths should contain "accy_v2/output/{oem}"
        for path in paths.values():
            path_str = str(path)
            assert "accy_v2" in path_str
            assert "output" in path_str
            assert "hyundai" in path_str


class TestConfigValidation:
    """Test suite for config validation and structure."""

    @pytest.fixture
    def loader(self) -> ModularConfigLoader:
        """Create loader instance for Hyundai."""
        config_root = Path(__file__).parent.parent.parent / "oems" / "hyundai" / "config"
        return ModularConfigLoader("hyundai", config_root)

    def test_pipeline_config_has_flags(self, loader):
        """Verify pipeline.yaml has all required flags."""
        config = loader.load_pipeline_config()

        # DECISION [016]: use_model_lookup flag
        assert "use_model_lookup" in config

        # DECISION [017]: non_null_threshold flag
        assert "non_null_threshold" in config

    def test_enrichment_has_model_lookup_brands(self, loader):
        """Verify enrichment.yaml defines model lookup brands."""
        config = loader.load_enrichment()
        brands = config["model_lookup"]["brands"]

        # Should have at least Hyundai and Genesis
        assert "Hyundai" in brands
        assert "Genesis" in brands

        # Each brand should have required fields
        for brand_name, brand_config in brands.items():
            assert "valid_year_range" in brand_config
            assert "fuel_type_keywords" in brand_config

    def test_downstream_schema_has_all_sheets(self, loader):
        """Verify downstream.yaml defines all output sheets."""
        schema = loader.load_downstream_schema()
        sheets = schema["sheets"]

        # Check standard sheets exist
        assert "Accessories" in sheets
        assert "_Data_Issues" in sheets
        assert "_Report" in sheets
        assert "_Audit" in sheets


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
