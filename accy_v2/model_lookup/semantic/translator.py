"""Keyword translation layer — normalizes OEM-specific abbreviations and variations."""

import yaml
from pathlib import Path
from typing import Dict, List


def load_oem_translator(make: str, configs_dir: str = None) -> Dict[str, str]:
    """
    Load OEM-specific translator config.

    Args:
        make: Manufacturer name (e.g., "Mitsubishi", "Mazda", "Hyundai")
        configs_dir: Directory containing translator YAML files. Defaults to model_lookup/configs/

    Returns:
        Dictionary mapping tokens to normalized forms (e.g., {"s-awc": "awd"}).
        Supports both flat "translations" key (Mitsubishi/Mazda style) and
        "categories" key with nested groups (Hyundai/Genesis style), flattening the latter.
        Returns empty dict if config file is missing (graceful degradation).
    """
    if configs_dir is None:
        configs_dir = str(Path(__file__).parent.parent / "configs")

    # New path: configs/{make}/translator.yaml instead of {make}_translator.json
    translator_path = Path(configs_dir) / make.lower() / "translator.yaml"

    try:
        with open(translator_path, "r") as f:
            config = yaml.safe_load(f)
            # Support categorized structure (new style: nested groups) with fallback to flat (old style)
            if "categories" in config:
                flat = {}
                for group in config["categories"].values():
                    flat.update(group)
                return flat
            return config.get("translations", {})
    except FileNotFoundError:
        # No config for this make — return empty dict (no translations applied)
        return {}
    except Exception as e:
        # YAML parsing error or other issue — log and return empty dict
        print(f"Warning: Failed to load translator for {make}: {e}")
        return {}


def translate_keywords(keywords: List[str], oem_translations: Dict[str, str]) -> List[str]:
    """
    Apply OEM-specific keyword translations.

    Each keyword is looked up in the translation map. If found, the value replaces it.
    Preserves order, deduplicates (first occurrence wins), keeps untranslatable tokens.

    Args:
        keywords: List of keywords (already tokenized and lowercased by caller)
        oem_translations: Dictionary from load_oem_translator()

    Returns:
        Translated keyword list with duplicates removed.

    Example:
        >>> translate_keywords(["outlander", "s-awc", "gt"], {"s-awc": "awd", "gt": "gt"})
        ["outlander", "awd", "gt"]
    """
    if not oem_translations:
        return keywords  # No translations configured — return as-is

    seen = set()
    result = []

    for kw in keywords:
        # Apply translation if available, otherwise keep original
        translated = oem_translations.get(kw, kw)

        # Deduplicate: first occurrence wins
        if translated not in seen:
            seen.add(translated)
            result.append(translated)

    return result
