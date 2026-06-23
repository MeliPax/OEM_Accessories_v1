"""Semantic search: combines translation, classification, and scoring."""

from typing import Dict, List, Optional
from pathlib import Path

from model_lookup.core.search import SearchResult, _extract_description_tokens, _build_word_boundary_pattern
from model_lookup.core.database import load_models
from model_lookup.core.vocabulary import load_vocabulary
from .translator import load_oem_translator, translate_keywords
from .classifier import load_classification_config, classify_tokens
from .scorer import compute_score, compute_confidence, CATEGORY_WEIGHTS, MINIMUM_SCORE


def search(
    make: str,
    year: int,
    keywords: List[str],
    csv_path: str = None,
    exclude_ev: bool = True,
    configs_dir: str = None,
) -> Optional[SearchResult]:
    """
    Semantic vehicle model search with translation, classification, and confidence.

    Pipeline:
    1. Translate keywords (OEM-specific abbreviations)
    2. Classify translated keywords (semantic buckets)
    3. Validate search profile (require MODEL, reject contradictions)
    4. Compute score
    5. Database search with translated keywords
    6. Compute confidence
    7. Return SearchResult or None

    Args:
        make: Manufacturer name
        year: Model year
        keywords: Tokenized keywords (lowercased)
        csv_path: Path to vehicle models CSV (optional)
        exclude_ev: If True, exclude EV models unless EV keyword present (optional)
        configs_dir: Directory for configs (optional)

    Returns:
        SearchResult if exactly one confident match found, else None
    """
    if csv_path is None:
        csv_path = str(Path(__file__).parent.parent / "db" / "db_vehicle_models.csv")

    if configs_dir is None:
        configs_dir = str(Path(__file__).parent.parent / "configs")

    # 1. Translate
    oem_translator = load_oem_translator(make, configs_dir)
    translated = translate_keywords(keywords, oem_translator)

    # 2. Classify
    classification_config = load_classification_config(make, configs_dir)
    classified = classify_tokens(translated, classification_config)

    # 3. Validate
    is_valid, _ = _validate_search_profile(classified)
    if not is_valid:
        return None

    # 4. Score
    score = compute_score(classified, CATEGORY_WEIGHTS)

    # 5. Gate
    if score < MINIMUM_SCORE:
        return None

    # 6. Database search with translated keywords
    df = load_models(csv_path)
    if df.empty:
        return None

    # Filter by make and year
    df_filtered = df[(df["Manufacturer"] == make) & (df["ModelYear"] == year)]

    if df_filtered.empty:
        return None

    # Apply keyword filters (all translated keywords must be present)
    for keyword in translated:
        pattern = _build_word_boundary_pattern(keyword)
        df_filtered = df_filtered[
            df_filtered["Description"].str.contains(pattern, case=False, na=False, regex=True)
        ]

    if df_filtered.empty:
        return None

    # Post-filter using trim discriminators from classification
    vocab = load_vocabulary(make, configs_dir)
    if vocab:
        trim_tokens = {
            token
            for token, category in classification_config.get("token_map", {}).items()
            if category == "TRIM"
        }

        if trim_tokens:
            search_kw_set = {kw.lower() for kw in translated}

            def _has_extra_discriminator_keywords(desc: str) -> bool:
                tokens = set(_extract_description_tokens(desc))
                discriminator_tokens = tokens & trim_tokens
                extra_discriminators = discriminator_tokens - search_kw_set
                return bool(extra_discriminators)

            df_filtered = df_filtered[
                ~df_filtered["Description"].apply(_has_extra_discriminator_keywords)
            ]

    if df_filtered.empty:
        return None

    candidate_count = len(df_filtered)

    # 7. Compute confidence
    confidence = compute_confidence(score, MINIMUM_SCORE, candidate_count)

    # 8. Return result
    if candidate_count == 1:
        row = df_filtered.iloc[0]
        return SearchResult(
            match=row["Description"],
            model_number=row["ModelNumber"],
            confidence=confidence,
            score=score,
            tokens_matched=classified,
        )

    return None


def _validate_search_profile(classified: Dict[str, List[str]]) -> tuple:
    """
    Validate that search profile is valid.

    Rules:
    - Require at least one MODEL token
    - Reject contradictory DRIVETRAIN tokens

    Returns:
        Tuple (is_valid, reason_if_invalid)
    """
    # Require MODEL
    if not classified.get("MODEL"):
        return False, "No MODEL token in search"

    # Check for drivetrain contradictions
    drivetrains = set(classified.get("DRIVETRAIN", []))
    if len(drivetrains) > 1:
        if "awd" in drivetrains and "fwd" in drivetrains:
            return False, "Contradictory drivetrain: awd and fwd"
        if "awd" in drivetrains and "rwd" in drivetrains:
            return False, "Contradictory drivetrain: awd and rwd"
        if "fwd" in drivetrains and "rwd" in drivetrains:
            return False, "Contradictory drivetrain: fwd and rwd"

    return True, ""
