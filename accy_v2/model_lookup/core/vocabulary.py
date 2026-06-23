"""Vocabulary building and management."""

import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, Set


def _extract_description_tokens(description: str) -> Set[str]:
    """Split description into lowercase tokens, preserving hyphenated terms."""
    if not description or not isinstance(description, str):
        return set()
    return {t.lower() for t in description.split() if t}


def build_vocabulary(make: str, csv_path: str = None, configs_dir: str = None) -> Dict:
    """
    Build vocabulary (unique tokens) for a manufacturer from CSV.

    Args:
        make: Manufacturer name
        csv_path: Path to vehicle models CSV
        configs_dir: Directory for vocabulary files

    Returns:
        Dictionary with saved status and metadata
    """
    if csv_path is None:
        csv_path = str(Path(__file__).parent.parent / "db" / "db_vehicle_models.csv")

    if configs_dir is None:
        configs_dir = str(Path(__file__).parent.parent / "configs")

    configs_dir = Path(configs_dir)
    configs_dir.mkdir(parents=True, exist_ok=True)

    try:
        df = pd.read_csv(csv_path)
        df_make = df[df["Manufacturer"] == make]
    except Exception as e:
        print(f"Error reading CSV for {make}: {e}")
        return {"saved": False, "make": make, "keyword_count": 0}

    # Extract unique tokens from Description column
    vocab = set()
    for desc in df_make.get("Description", []):
        vocab.update(_extract_description_tokens(desc))

    # Write to file
    vocab_config = {
        "make": make,
        "generated_at": datetime.now().isoformat(),
        "keyword_count": len(vocab),
        "keywords": sorted(list(vocab)),
    }

    vocab_path = configs_dir / f"{make.lower()}_keywords.json"
    try:
        with open(vocab_path, "w") as f:
            json.dump(vocab_config, f, indent=2)
        print(f"Saved vocabulary for {make} to {vocab_path}")
        return {
            "saved": True,
            "make": make,
            "keyword_count": len(vocab),
            "file_path": str(vocab_path),
        }
    except Exception as e:
        print(f"Error writing vocabulary for {make}: {e}")
        return {"saved": False, "make": make, "keyword_count": len(vocab)}


def load_vocabulary(make: str, configs_dir: str = None) -> Set[str]:
    """
    Load vocabulary tokens for a manufacturer.

    Args:
        make: Manufacturer name
        configs_dir: Directory containing vocabulary files

    Returns:
        Set of vocabulary tokens. Empty set if file not found.
    """
    if configs_dir is None:
        configs_dir = str(Path(__file__).parent.parent / "configs")

    vocab_path = Path(configs_dir) / f"{make.lower()}_keywords.json"

    try:
        with open(vocab_path, "r") as f:
            config = json.load(f)
            return set(config.get("keywords", []))
    except FileNotFoundError:
        return set()
    except Exception as e:
        print(f"Warning: Failed to load vocabulary for {make}: {e}")
        return set()
