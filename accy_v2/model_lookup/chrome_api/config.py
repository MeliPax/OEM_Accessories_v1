"""
Environment and configuration management for ADS API integration.

Loads credentials from .env file and provides fail-fast validation
matching the pattern used in model_lookup/engine.py.
"""

import os
from pathlib import Path
from dotenv import load_dotenv


def load_ads_env() -> dict:
    """
    Load ADS API credentials from .env file.

    Looks for ads_api.env in model_lookup/creds/ relative to this script.
    Fails fast if required variables are missing.

    Returns:
        dict with keys: base_url, api_user, api_password

    Raises:
        RuntimeError if required environment variables are missing
    """
    script_dir = Path(__file__).parent  # chrome_api directory
    env_path = script_dir.parent / "creds" / "ads_api.env"

    if not env_path.exists():
        raise FileNotFoundError(
            f"ADS credentials file not found: {env_path}\n"
            f"Please create {env_path} with ADS_BASE_URL, ADS_API_USER, ADS_API_PASSWORD"
        )

    load_dotenv(dotenv_path=env_path)

    required_vars = ["ADS_BASE_URL", "ADS_API_USER", "ADS_API_PASSWORD"]
    missing = [v for v in required_vars if not os.getenv(v)]

    if missing:
        raise RuntimeError(
            f"Missing ADS environment variables in {env_path}: {missing}\n"
            f"Required: {required_vars}"
        )

    return {
        "base_url": os.getenv("ADS_BASE_URL"),
        "api_user": os.getenv("ADS_API_USER"),
        "api_password": os.getenv("ADS_API_PASSWORD"),
    }


def get_make_name_map() -> dict:
    """
    Map ADS make names (as they come from the API) to internal Manufacturer names.

    Returns:
        dict mapping ADS make spelling to pipeline Manufacturer value
        e.g. {"Hyundai": "HYUNDAI", "Honda": "HONDA"}
    """
    return {
        "Hyundai": "HYUNDAI",
        "Honda": "HONDA",
        "Kia": "KIA",
        "Genesis": "GENESIS",
        "Mazda": "MAZDA",
        "Mitsubishi": "MITSUBISHI",
        "Volkswagen": "VOLKSWAGEN",
    }
