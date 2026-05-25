import json
from pathlib import Path

_REQUIRED_KEYS = [
    "column_definition",
    "required_columns",
    "non_null_columns",
    "col_data_type_dict",
    "trim_bounds_config",
    "trim_validation_config",
    "non_acceptable_sheet_names",
    "output",
]

_OUTPUT_REQUIRED_KEYS = ["ready_to_upload_path", "dq_report_path", "pipeline_log_path"]


def load_config(config_path: str) -> dict:
    """Load and structurally validate an OEM config file. Fails fast before any data is touched."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    with open(path, encoding="utf-8") as f:
        config = json.load(f)

    missing = [k for k in _REQUIRED_KEYS if k not in config]

    if missing:
        raise ValueError(f"Config missing required top-level keys: {missing}")

    missing_output = [
        k for k in _OUTPUT_REQUIRED_KEYS if k not in config.get("output", {})
    ]
    if missing_output:
        raise ValueError(f"Config 'output' section missing keys: {missing_output}")

    return config
