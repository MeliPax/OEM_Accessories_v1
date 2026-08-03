"""Semantic token classification and configuration management."""

import yaml
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Seed rules: used only at build-time to classify tokens from the vocabulary
_SEED_RULES = {
    "TRIM": {
        "es", "se", "sel", "gt", "le", "limited", "touring", "premium", "noir", "plus", "ta",
        "lx", "sx", "ex", "ex-l", "glx", "comfortline", "highline", "execline", "gli",
        "jetta", "sport", "l", "s", "sport_touring",
    },
    "DRIVETRAIN": {
        "awd", "fwd", "rwd", "4wd", "s-awc", "awc", "4motion", "wd",
    },
    "ENGINE_TYPE": {
        "phev", "ev", "hybrid", "mhev", "hev", "bev", "fcev",
    },
    "PACKAGE": {
        "package", "w/tech", "*ltd", "avail*", "pkg", "edition", "carbon", "black",
    },
    "TRANSMISSION": {
        "cvt", "manual", "auto", "dsg", "ivt", "dct", "at", "mt", "6at", "6mt",
    },
}


def load_classification_config(make: str, configs_dir: str = None) -> Dict:
    """
    Load semantic classification config for a manufacturer.

    Args:
        make: Manufacturer name (e.g., "Mitsubishi")
        configs_dir: Directory containing classification YAML files. Defaults to model_lookup/configs/

    Returns:
        Dictionary with keys "make", "generated_at", "token_map", "unclassified".
        Returns empty dict structure if file missing (graceful degradation).
    """
    if configs_dir is None:
        configs_dir = str(Path(__file__).parent.parent / "configs")

    # New path: configs/{make}/classification.yaml instead of {make}_classification.json
    config_path = Path(configs_dir) / make.lower() / "classification.yaml"

    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {"make": make, "token_map": {}, "unclassified": []}
    except Exception as e:
        print(f"Warning: Failed to load classification for {make}: {e}")
        return {"make": make, "token_map": {}, "unclassified": []}


def classify_tokens(
    tokens: List[str],
    classification_config: Dict,
    logger=None,
) -> Dict[str, List[str]]:
    """
    Classify tokens using a pre-built classification config.

    Tokens not found in the config's token_map land in "UNCLASSIFIED" with a warning.
    Empty category lists are omitted from the result.

    Args:
        tokens: List of keywords to classify
        classification_config: Output from load_classification_config()
        logger: Optional logger for warnings

    Returns:
        Dictionary mapping category names to lists of tokens.
        Example: {"MODEL": ["outlander"], "TRIM": ["gt"], "DRIVETRAIN": ["awd"]}
    """
    token_map = classification_config.get("token_map", {})
    result = {}
    unclassified_tokens = []

    for token in tokens:
        category = token_map.get(token, "UNCLASSIFIED")

        if category == "UNCLASSIFIED":
            unclassified_tokens.append(token)

        if category not in result:
            result[category] = []

        result[category].append(token)

    # Log unclassified tokens (non-fatal warning)
    if unclassified_tokens and logger:
        logger.warning(f"Unclassified tokens: {unclassified_tokens}")

    # Remove UNCLASSIFIED from result (don't pass it to scoring)
    result.pop("UNCLASSIFIED", None)

    return result


def _extract_description_tokens(description: str) -> Set[str]:
    """Split description into lowercase tokens, preserving hyphenated terms."""
    if not description or not isinstance(description, str):
        return set()
    return {t.lower() for t in description.split() if t}


def _heuristic_model_tokens(df: pd.DataFrame) -> Set[str]:
    """
    Identify MODEL tokens heuristically: tokens appearing before the first TRIM discriminator.

    For each Description, walk left-to-right, collect tokens until hitting a known TRIM.
    Aggregate across all rows and return the set of candidate model tokens.

    Args:
        df: DataFrame with "Description" column

    Returns:
        Set of tokens that appear to be model names (e.g., {"outlander", "eclipse", "rvr"})
    """
    model_candidates = set()
    trim_tokens = _SEED_RULES.get("TRIM", set())

    for description in df.get("Description", []):
        if not description or not isinstance(description, str):
            continue

        tokens = description.lower().split()
        for token in tokens:
            token_clean = token.strip("*")  # Remove wildcards from package tokens
            if token_clean in trim_tokens:
                # Stop at first trim token — don't include it
                break
            # Accumulate tokens before trim
            model_candidates.add(token_clean)

    return model_candidates


def build_classification_config(
    make: str, csv_path: str = None, configs_dir: str = None
) -> Dict:
    """
    Build and save semantic classification config for a manufacturer.

    Algorithm:
    1. Load {make}_keywords.json (already exists from vocab build)
    2. For each token, check against _SEED_RULES
    3. MODEL tokens: identified heuristically from DB descriptions
    4. Remaining tokens → "unclassified" list
    5. Write {make}_classification.json
    6. Return result dict

    Args:
        make: Manufacturer name
        csv_path: Path to vehicle models CSV. Defaults to model_lookup/db/db_vehicle_models.csv
        configs_dir: Directory for config files. Defaults to model_lookup/configs/

    Returns:
        Dictionary with keys: saved (bool), make (str), token_count (int), unclassified (list)
    """
    if csv_path is None:
        csv_path = str(Path(__file__).parent / "db" / "db_vehicle_models.csv")

    if configs_dir is None:
        configs_dir = str(Path(__file__).parent / "configs")

    configs_dir = Path(configs_dir)
    configs_dir.mkdir(parents=True, exist_ok=True)

    # Load vocabulary for this make
    vocab_path = configs_dir / f"{make.lower()}_keywords.json"
    try:
        with open(vocab_path, "r") as f:
            vocab_config = json.load(f)
            vocab_tokens = set(vocab_config.get("keywords", []))
    except FileNotFoundError:
        print(f"Warning: No vocabulary found for {make} — building from CSV")
        vocab_tokens = set()

    # If no vocab, build it from CSV
    if not vocab_tokens:
        try:
            df = pd.read_csv(csv_path)
            df_make = df[df["Manufacturer"] == make]
            for desc in df_make.get("Description", []):
                vocab_tokens.update(_extract_description_tokens(desc))
        except Exception as e:
            print(f"Error reading CSV for {make}: {e}")
            return {"saved": False, "make": make, "token_count": 0, "unclassified": list(vocab_tokens)}

    # Classify each token using seed rules
    token_map = {}
    unclassified = []

    for token in sorted(vocab_tokens):
        classified = False
        for category, seed_set in _SEED_RULES.items():
            if token in seed_set:
                token_map[token] = category
                classified = True
                break

        if not classified:
            unclassified.append(token)

    # Add MODEL tokens identified heuristically
    if not unclassified or True:  # Always try heuristic
        try:
            df = pd.read_csv(csv_path)
            df_make = df[df["Manufacturer"] == make]
            model_tokens = _heuristic_model_tokens(df_make)
            # Add model tokens to classification, but don't override existing classifications
            for token in model_tokens:
                if token not in token_map and token not in unclassified:
                    token_map[token] = "MODEL"
                elif token in unclassified:
                    unclassified.remove(token)
                    token_map[token] = "MODEL"
        except Exception as e:
            print(f"Warning: Heuristic MODEL detection failed for {make}: {e}")

    # Build config structure
    config = {
        "make": make,
        "generated_at": datetime.now().isoformat(),
        "schema_version": "1.0",
        "token_map": token_map,
        "unclassified": unclassified,
    }

    # Write to file
    output_path = configs_dir / f"{make.lower()}_classification.json"
    try:
        with open(output_path, "w") as f:
            json.dump(config, f, indent=2)
        print(f"Saved classification config for {make} to {output_path}")
        return {
            "saved": True,
            "make": make,
            "token_count": len(token_map),
            "unclassified": unclassified,
        }
    except Exception as e:
        print(f"Error writing classification config for {make}: {e}")
        return {
            "saved": False,
            "make": make,
            "token_count": len(token_map),
            "unclassified": unclassified,
        }


def bootstrap_all_classification_configs(csv_path: str = None, configs_dir: str = None) -> Dict:
    """
    Build classification configs for all manufacturers in the CSV.

    Args:
        csv_path: Path to vehicle models CSV
        configs_dir: Directory for config files

    Returns:
        Dictionary with results per manufacturer
    """
    if csv_path is None:
        csv_path = str(Path(__file__).parent / "db" / "db_vehicle_models.csv")

    try:
        df = pd.read_csv(csv_path)
        makes = df["Manufacturer"].unique()
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return {}

    results = {}
    for make in makes:
        result = build_classification_config(make, csv_path, configs_dir)
        results[make] = result
        if result.get("unclassified"):
            print(f"  [WARNING] {make}: {len(result['unclassified'])} unclassified tokens: {result['unclassified']}")

    return results
