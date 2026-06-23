"""Main search interface for vehicle models."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd

from .database import load_models
from .vocabulary import load_vocabulary


@dataclass
class SearchResult:
    """Result of a successful model search."""

    match: str  # Human-readable description
    model_number: str  # OEM model number
    confidence: float  # 0.0 to 1.0 (0.0 = no match or ambiguous)
    score: int  # Raw score (used internally)
    tokens_matched: Dict[str, List[str]]  # Classified tokens used for matching


def _extract_description_tokens(description: str) -> set:
    """Split description into lowercase tokens."""
    if not description or not isinstance(description, str):
        return set()
    return {t.lower() for t in description.split() if t}


def _build_word_boundary_pattern(keyword: str) -> str:
    """Build regex pattern for whole-word matching."""
    return rf"\b{keyword}\b"


def _get_trim_discriminator_keywords(make: str = None, configs_dir: str = None) -> set:
    """
    Get trim discriminator keywords.

    Prefers to load from classification config if available,
    falls back to hardcoded set for backward compatibility.

    Args:
        make: Manufacturer name (optional)
        configs_dir: Directory with classification configs (optional)

    Returns:
        Set of trim discriminator keywords
    """
    # Try to load from classification config
    if make:
        try:
            from model_lookup.semantic.classifier import load_classification_config

            config = load_classification_config(make, configs_dir)
            trim_tokens = {
                token
                for token, category in config.get("token_map", {}).items()
                if category == "TRIM"
            }
            if trim_tokens:
                return trim_tokens
        except Exception:
            pass  # Fall through to hardcoded set

    # Fallback to hardcoded set
    return {
        "premium", "noir", "se", "es", "gt", "le", "limited", "touring", "sel",
        "ex", "ex-l", "lx", "sx", "sport", "l", "s", "plus", "ta",
        "glx", "high line", "highline", "execline", "comfortline", "trendline", "gli", "jetta",
    }


def search(
    make: str,
    year: int,
    keywords: List[str],
    csv_path: str = None,
    exclude_ev: bool = True,
    configs_dir: str = None,
    use_semantic: bool = True,
) -> Optional[SearchResult]:
    """
    Search for vehicle models by manufacturer, year, and keywords.

    Optionally applies semantic processing (translation, classification, scoring)
    for improved matching accuracy and confidence scoring.

    Args:
        make: Manufacturer name (e.g., "Mitsubishi")
        year: Model year (e.g., 2026)
        keywords: List of keywords to match (already tokenized, lowercased)
        csv_path: Path to vehicle models CSV (optional)
        exclude_ev: If True and no EV keyword in search, exclude EV models (optional)
        configs_dir: Directory for configs (optional)
        use_semantic: If True, apply semantic translation/classification/scoring (default: True)

    Returns:
        SearchResult if exactly one confident match found, else None
    """
    if csv_path is None:
        csv_path = str(Path(__file__).parent.parent / "db" / "db_vehicle_models.csv")

    if configs_dir is None:
        configs_dir = str(Path(__file__).parent.parent / "configs")

    # If semantic processing requested, use it
    if use_semantic:
        from model_lookup.semantic import search as semantic_search

        return semantic_search(make, year, keywords, csv_path, exclude_ev, configs_dir)

    # Otherwise, use direct database search
    df = load_models(csv_path)
    if df.empty:
        return None

    # Filter by make and year
    df_filtered = df[(df["Manufacturer"] == make) & (df["ModelYear"] == year)]

    if df_filtered.empty:
        return None

    # Apply keyword filters (AND logic - all keywords must be present)
    for keyword in keywords:
        pattern = _build_word_boundary_pattern(keyword)
        df_filtered = df_filtered[
            df_filtered["Description"].str.contains(pattern, case=False, na=False, regex=True)
        ]

    if df_filtered.empty:
        return None

    # Post-filter: exclude results with TRIM DISCRIMINATOR keywords not in search
    vocab = load_vocabulary(make, configs_dir)
    if vocab:
        trim_discriminators = _get_trim_discriminator_keywords(make, configs_dir)
        search_kw_set = {kw.lower() for kw in keywords}

        def _has_extra_discriminator_keywords(desc: str) -> bool:
            tokens = set(_extract_description_tokens(desc))
            discriminator_tokens = tokens & trim_discriminators
            extra_discriminators = discriminator_tokens - search_kw_set
            return bool(extra_discriminators)

        df_filtered = df_filtered[~df_filtered["Description"].apply(_has_extra_discriminator_keywords)]

    if df_filtered.empty:
        return None

    if len(df_filtered) == 1:
        row = df_filtered.iloc[0]
        return SearchResult(
            match=row["Description"],
            model_number=row["ModelNumber"],
            confidence=0.7,  # Default confidence when semantic processing not used
            score=0,  # No score computed without semantic processing
            tokens_matched={"keywords": keywords},
        )

    # Multiple results (ambiguous)
    return None
