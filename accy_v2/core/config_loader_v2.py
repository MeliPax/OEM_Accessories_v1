"""
ModularConfigLoader: Load modular YAML config files (6-file structure per OEM)

DECISION [015]: Modular 5-file config structure (pipeline, transformations, enrichment, schemas/*)
Replaces single JSON config file with semantic layers:
  1. pipeline.yaml — Orchestration settings
  2. transformations.yaml — Cleaning rules
  3. enrichment.yaml — Model lookup rules
  4. schemas/upstream.yaml — Input validation
  5. schemas/intermediate.yaml — Post-transform quality gate
  6. schemas/downstream.yaml — Output structure

DECISION [020]: Centralized path registry (paths.yaml) for DRY principle
Loads paths from accy_v2/paths.yaml and resolves ${PATH_*} placeholders.
"""

from pathlib import Path
from typing import Dict, Any
import yaml
import re


class ModularConfigLoader:
    """Load modular config files (6-file structure per OEM)."""

    def __init__(self, oem: str, config_root: Path):
        """
        Initialize loader for an OEM's config files.

        Args:
            oem: OEM name (e.g., "hyundai", "mazda")
            config_root: Path to accy_v2/oems/{oem}/config/
        """
        self.oem = oem
        self.config_root = Path(config_root)
        self._resolve_base_path()
        self._load_path_registry()  # DECISION [020]: Load centralized paths

    def _resolve_base_path(self) -> None:
        """Resolve project root by looking for run_pipeline.py."""
        current = self.config_root
        max_iterations = 20  # Prevent infinite loops

        for _ in range(max_iterations):
            if (current / "run_pipeline.py").exists():
                self.project_root = current
                return
            if current == current.parent:
                break
            current = current.parent

        raise RuntimeError(
            f"Could not find project root starting from {self.config_root}. "
            "run_pipeline.py not found in any parent directory."
        )

    def _resolve_path(self, relative_path: str) -> Path:
        """
        Convert relative path string to absolute Path.

        Args:
            relative_path: Path relative to project root (e.g., "accy_v2/model_lookup/configs/hyundai/translator.yaml")

        Returns:
            Absolute Path object
        """
        if not relative_path:
            return None
        return self.project_root / relative_path

    def _load_path_registry(self) -> None:
        """
        Load centralized path definitions from accy_v2/paths.yaml.

        DECISION [020]: Centralized path registry for DRY principle.
        Enables resolution of ${PATH_*} placeholders in config files.
        """
        registry_path = self.project_root / "accy_v2" / "paths.yaml"
        if not registry_path.exists():
            raise FileNotFoundError(f"Path registry not found: {registry_path}")
        self.path_registry = self._load_yaml(registry_path)

    def _resolve_placeholders(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Replace ${PATH_*} placeholders with actual paths from registry.

        DECISION [020]: Resolve centralized path variables.
        Example: "${MODEL_LOOKUP_CONFIGS}/hyundai/translator.yaml"
                 → "accy_v2/model_lookup/configs/hyundai/translator.yaml"

        Args:
            config: Config dict that may contain ${VAR} placeholders

        Returns:
            Config dict with all placeholders resolved to actual paths
        """
        return self._resolve_placeholders_recursive(config)

    def _resolve_placeholders_recursive(self, obj: Any) -> Any:
        """
        Recursively resolve placeholders in dicts and lists.

        Args:
            obj: Dict, list, string, or other value

        Returns:
            Same object with all ${VAR} strings resolved
        """
        if isinstance(obj, dict):
            return {k: self._resolve_placeholders_recursive(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._resolve_placeholders_recursive(item) for item in obj]
        elif isinstance(obj, str):
            return self._resolve_placeholder_string(obj)
        else:
            return obj

    def _resolve_placeholder_string(self, value: str) -> str:
        """
        Resolve placeholders in a single string.

        Args:
            value: String that may contain ${VAR} or ${VAR}/path

        Returns:
            String with placeholders replaced
        """
        # Pattern: ${VARIABLE_NAME} at start, optionally followed by /path
        pattern = r"\$\{([A-Z_]+)\}"

        def replace_var(match):
            var_name = match.group(1)
            resolved = self._get_path_from_registry(var_name)
            if resolved is None:
                raise ValueError(f"Unknown path variable: {var_name}")
            return resolved

        return re.sub(pattern, replace_var, value)

    def _get_path_from_registry(self, var_name: str) -> str:
        """
        Get path value from registry using variable name.

        DECISION [020]: Support both global and OEM-specific overrides.

        Args:
            var_name: Variable name like "MODEL_LOOKUP_CONFIGS"

        Returns:
            Path string from registry, or None if not found
        """
        # Map variable names to registry keys
        # E.g., MODEL_LOOKUP_CONFIGS → ["model_lookup", "configs_dir"]
        var_to_key = {
            "MODEL_LOOKUP_CONFIGS": ["model_lookup", "configs_dir"],
            "MODEL_LOOKUP_DB": ["model_lookup", "db"],
            "MODEL_LOOKUP_CHROME_API": ["model_lookup", "chrome_api"],
            "OUTPUT_BASE": ["output", "base"],
            "OUTPUT_READY_TO_UPLOAD": ["output", "ready_to_upload"],
            "OUTPUT_DQ_REPORTS": ["output", "dq_reports"],
            "OUTPUT_PIPELINE_LOGS": ["output", "pipeline_logs"],
            "DATA_LANDING_ZONE": ["data", "landing_zone"],
            "CORE_BASE": ["core", "base"],
            "CORE_HELPERS": ["core", "helpers"],
            "CORE_MODELS": ["core", "models"],
            "DOCS_BASE": ["docs", "base"],
        }

        if var_name not in var_to_key:
            return None

        key_path = var_to_key[var_name]

        # Check OEM-specific overrides first
        oem_overrides = (
            self.path_registry.get("oems", {})
            .get(self.oem, {})
            .get("overrides", {})
        )
        if var_name in oem_overrides:
            return oem_overrides[var_name]

        # Fall back to global paths
        global_paths = self.path_registry.get("global", {})
        value = global_paths
        for key in key_path:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value

    def load_pipeline_config(self) -> Dict[str, Any]:
        """
        Load pipeline.yaml (orchestration settings).

        Returns:
            Dict containing: use_model_lookup, non_null_threshold, features
        """
        path = self.config_root / "pipeline.yaml"
        return self._load_yaml(path)

    def load_upstream_schema(self) -> Dict[str, Any]:
        """
        Load schemas/upstream.yaml (input validation rules).

        Returns:
            Dict containing: languages, columns, sheet_validation, validation_gates
        """
        path = self.config_root / "schemas" / "upstream.yaml"
        return self._load_yaml(path)

    def load_intermediate_schema(self) -> Dict[str, Any]:
        """
        Load schemas/intermediate.yaml (post-transform quality gate).

        Returns:
            Dict containing: required_columns, optional_columns, language_requirements, integrity_checks
        """
        path = self.config_root / "schemas" / "intermediate.yaml"
        return self._load_yaml(path)

    def load_downstream_schema(self) -> Dict[str, Any]:
        """
        Load schemas/downstream.yaml (output sheet structure).

        Returns:
            Dict containing: output, output_file, sheets
        """
        path = self.config_root / "schemas" / "downstream.yaml"
        return self._load_yaml(path)

    def load_transformations(self) -> Dict[str, Any]:
        """
        Load transformations.yaml (data cleaning rules).

        Returns:
            Dict containing: columns (per-column operations), global settings
        """
        path = self.config_root / "transformations.yaml"
        config = self._load_yaml(path)
        # DECISION [020]: Resolve path placeholders
        config = self._resolve_placeholders(config)
        return config

    def load_enrichment(self) -> Dict[str, Any]:
        """
        Load enrichment.yaml (model lookup and ADS fallback rules).

        Resolves all path placeholders and converts paths to absolute Paths.

        Returns:
            Dict containing: model_lookup, ads_fallback, database, validation
        """
        path = self.config_root / "enrichment.yaml"
        config = self._load_yaml(path)
        # DECISION [020]: Resolve path placeholders from registry
        config = self._resolve_placeholders(config)
        # Convert resolved paths to absolute Path objects
        self._resolve_enrichment_paths(config)
        return config

    def _resolve_enrichment_paths(self, config: Dict[str, Any]) -> None:
        """
        Convert relative paths in enrichment config to absolute Paths.

        Modifies config in-place, converting:
          - brand config: translator_config, classifier_config, standardization_config
          - database: db_path

        Args:
            config: Enrichment config dict (modified in-place)
        """
        # Resolve brand-specific config paths
        for brand, brand_config in config.get("model_lookup", {}).get("brands", {}).items():
            for key in ["translator_config", "classifier_config", "standardization_config"]:
                if key in brand_config and isinstance(brand_config[key], str):
                    brand_config[key] = self._resolve_path(brand_config[key])

        # Resolve database path
        if "database" in config and "db_path" in config["database"]:
            config["database"]["db_path"] = self._resolve_path(config["database"]["db_path"])

    def load_all(self) -> Dict[str, Any]:
        """
        Load all configs into one combined dict.

        Returns:
            Dict with structure:
                {
                    "pipeline": {...},
                    "schemas": {
                        "upstream": {...},
                        "intermediate": {...},
                        "downstream": {...}
                    },
                    "transformations": {...},
                    "enrichment": {...}
                }
        """
        return {
            "pipeline": self.load_pipeline_config(),
            "schemas": {
                "upstream": self.load_upstream_schema(),
                "intermediate": self.load_intermediate_schema(),
                "downstream": self.load_downstream_schema(),
            },
            "transformations": self.load_transformations(),
            "enrichment": self.load_enrichment(),
        }

    @staticmethod
    def _load_yaml(path: Path) -> Dict[str, Any]:
        """
        Load YAML file with error handling.

        Args:
            path: Path to YAML file

        Returns:
            Parsed YAML dict (or empty dict if file is empty)

        Raises:
            FileNotFoundError: If file doesn't exist
            yaml.YAMLError: If file is not valid YAML
        """
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {path}: {e}")


def get_output_paths(oem: str, base_dir: Path = None) -> Dict[str, Path]:
    """
    Derive output paths from OEM name in code (not configured).

    DECISION [018]: Output paths follow a consistent pattern for all OEMs
    - accy_v2/output/ready_to_upload/{oem}/
    - accy_v2/output/dq_reports/{oem}/
    - accy_v2/output/pipeline_logs/{oem}/

    Args:
        oem: OEM name (e.g., "hyundai", "mazda")
        base_dir: Base directory (defaults to project root / "accy_v2/output")

    Returns:
        Dict with keys: ready_to_upload, dq_reports, pipeline_logs (all Path objects)
    """
    if base_dir is None:
        base_dir = Path(__file__).parent.parent / "output"

    oem_lower = oem.lower()

    return {
        "ready_to_upload": base_dir / "ready_to_upload" / oem_lower,
        "dq_reports": base_dir / "dq_reports" / oem_lower,
        "pipeline_logs": base_dir / "pipeline_logs" / oem_lower,
    }
