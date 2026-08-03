"""Weighted scoring and confidence calculation for classified keywords."""

from typing import Dict, List

# Weights for each semantic category
CATEGORY_WEIGHTS = {
    "MODEL": 10,
    "ENGINE_TYPE": 8,
    "POWERTRAIN_TYPE": 10,  # Fuel type (HEV, PHEV, EV) — increased to 10 (critical for accessory compatibility)
    "ENGINE_SPEC": 7,  # Specific engine specs (2.5T, 3.3T, etc.)
    "DRIVETRAIN": 6,
    "TRIM": 5,
    "TRIM_VARIANT": 6,  # Trim variants (N, N-Line) — increased to 6 (important for specificity)
    "BODY_STYLE": 4,  # Body type (sedan, suv, hatchback)
    "TRANSMISSION": 3,
    "SEATING": 2,  # Passenger count
    "INTERIOR": 1,  # Interior cosmetics (filtered in search)
    "EXTERIOR_COLOR": 1,  # Exterior cosmetics (filtered in search)
    "PACKAGE": 1,
    "UNCLASSIFIED": 0,  # Unclassified tokens contribute zero to score
}

# Minimum passing score: requires MODEL alone (10)
# Previously required MODEL + TRIM/ENGINE_SPEC, but engine specs are now ignored by design
MINIMUM_SCORE = 10


def compute_score(classified: Dict[str, List[str]], weights: Dict[str, int] = None) -> int:
    """
    Compute weighted score for classified tokens.

    Score = sum of weights for each non-empty category bucket.
    Each category contributes its weight at most once (not per token).

    Args:
        classified: Dictionary mapping category name to list of tokens.
                   Example: {"MODEL": ["outlander"], "DRIVETRAIN": ["awd"]}
        weights: Override category weights. Defaults to CATEGORY_WEIGHTS.

    Returns:
        Integer score (non-negative).

    Example:
        >>> classified = {"MODEL": ["outlander"], "TRIM": ["gt"], "DRIVETRAIN": ["awd"]}
        >>> compute_score(classified)
        21  # MODEL(10) + TRIM(5) + DRIVETRAIN(6)
    """
    if weights is None:
        weights = CATEGORY_WEIGHTS

    score = 0
    for category, tokens in classified.items():
        if tokens:  # Non-empty category
            category_weight = weights.get(category, 0)
            score += category_weight

    return score


def compute_confidence(
    score: int, min_score: int = MINIMUM_SCORE, candidate_count: int = 1
) -> float:
    """
    Compute confidence score (0.0 to 1.0) based on matching score and result uniqueness.

    Confidence is 0.0 if:
    - Candidate count is not exactly 1 (ambiguous or no match)
    - Score is below minimum threshold

    Otherwise:
    - Confidence = min(score / max_possible_score, 1.0)
    - Max possible score = sum of all category weights

    Args:
        score: Raw weighted score from compute_score()
        min_score: Minimum required score (default MINIMUM_SCORE=12)
        candidate_count: Number of matching rows from database (must be exactly 1)

    Returns:
        Float between 0.0 and 1.0 representing confidence in the match.

    Example:
        >>> compute_confidence(score=29, candidate_count=1)  # MODEL+ENGINE_TYPE+DRIVETRAIN+TRIM
        0.85  # Approximately (29 / 34)
        >>> compute_confidence(score=29, candidate_count=2)  # Ambiguous
        0.0
        >>> compute_confidence(score=8, candidate_count=1)   # Below minimum
        0.0
    """
    # Ambiguous match or no match — confidence is 0
    if candidate_count != 1:
        return 0.0

    # Score below minimum threshold — confidence is 0
    if score < min_score:
        return 0.0

    # Compute confidence as score / max_possible_score
    max_possible = sum(CATEGORY_WEIGHTS.values())
    if max_possible == 0:
        return 0.0

    return min(score / max_possible, 1.0)
