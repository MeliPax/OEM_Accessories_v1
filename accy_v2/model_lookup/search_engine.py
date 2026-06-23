"""OEM Vehicle Model Search Engine — translates, classifies, scores, and searches."""

from dataclasses import dataclass
from typing import Dict, List, Optional
import pandas as pd

from .translator import load_oem_translator, translate_keywords
from .classifier import load_classification_config, classify_tokens
from .scorer import CATEGORY_WEIGHTS, MINIMUM_SCORE, compute_score, compute_confidence
from .models.manufacture_module import search_models_by_description


@dataclass
class SearchResult:
    """Result of a successful model search."""

    match: str  # Human-readable description (e.g., "Outlander PHEV GT S-AWC")
    model_number: str  # OEM model number (e.g., "COEV-X")
    confidence: float  # 0.0 to 1.0
    score: int  # Raw weighted score
    tokens_matched: Dict[str, List[str]]  # Classified tokens used for matching
    candidate_count: int  # Number of DB rows considered (should be 1 for successful match)


class VehicleSearchEngine:
    """
    Semantic vehicle model search engine.

    Wraps search_models_by_description() with:
    - Keyword translation (OEM-specific abbreviations)
    - Semantic classification (MODEL, TRIM, DRIVETRAIN, etc.)
    - Weighted scoring (confidence output)
    - Validation (contradictions, missing requirements)

    Thread-safe: stateless after construction. Each search() call is independent.
    """

    def __init__(
        self,
        csv_path: str,
        configs_dir: str,
        oem_config: Dict = None,
        pipeline_logger=None,
    ):
        """
        Initialize search engine for an OEM.

        Args:
            csv_path: Path to vehicle models CSV (model_lookup/db/db_vehicle_models.csv)
            configs_dir: Directory containing translator and classification JSONs
            oem_config: OEM config dict (optional, used for single-char abbreviations)
            pipeline_logger: Logger for debug messages (optional)
        """
        self.csv_path = csv_path
        self.configs_dir = configs_dir
        self.oem_config = oem_config or {}
        self.logger = pipeline_logger

    def search(
        self,
        make: str,
        year: int,
        raw_keywords: List[str],
        exclude_ev: bool = True,
    ) -> Optional[SearchResult]:
        """
        Search for a vehicle model using keywords.

        Full pipeline:
        1. Translate keywords (OEM-specific abbreviations)
        2. Classify translated keywords into semantic buckets
        3. Validate search profile (require MODEL, reject contradictions)
        4. Compute score
        5. Gate: if score < MINIMUM_SCORE, return None
        6. Call search_models_by_description() with translated keywords
        7. Compute confidence based on candidate count
        8. Return SearchResult or None

        Args:
            make: Manufacturer name (e.g., "Mitsubishi")
            year: Model year (e.g., 2026)
            raw_keywords: Tokenized keywords (already lowercased by KeywordExtractor)
            exclude_ev: If True and no EV keyword in search, exclude EV models from results

        Returns:
            SearchResult if exactly one confident match found, else None.
        """
        # 1. Translate
        oem_translator = load_oem_translator(make, self.configs_dir)
        translated = translate_keywords(raw_keywords, oem_translator)

        if self.logger:
            self.logger.debug(f"Translated keywords: {raw_keywords} → {translated}")

        # 2. Classify
        classification_config = load_classification_config(make, self.configs_dir)
        classified = classify_tokens(translated, classification_config, self.logger)

        if self.logger:
            self.logger.debug(f"Classified tokens: {classified}")

        # 3. Validate search profile
        is_valid, reason = self._validate_search_profile(classified)
        if not is_valid:
            if self.logger:
                self.logger.debug(f"Search validation failed: {reason}")
            return None

        # 4. Compute score
        score = compute_score(classified, CATEGORY_WEIGHTS)

        if self.logger:
            self.logger.debug(f"Score: {score} (minimum: {MINIMUM_SCORE})")

        # 5. Gate
        if score < MINIMUM_SCORE:
            if self.logger:
                self.logger.debug(f"Score {score} below minimum {MINIMUM_SCORE}")
            return None

        # 6. Search database with translated keywords
        results = search_models_by_description(
            make=make,
            year=year,
            keywords=translated,
            csv_path=self.csv_path,
            exclude_ev=exclude_ev,
            configs_dir=self.configs_dir,
        )

        candidate_count = len(results)

        if self.logger:
            self.logger.debug(f"Database search returned {candidate_count} candidates")

        # 7. Compute confidence
        confidence = compute_confidence(score, MINIMUM_SCORE, candidate_count)

        if self.logger:
            self.logger.debug(f"Confidence: {confidence:.2f}")

        # 8. Return result or None
        if candidate_count == 1:
            row = results.iloc[0]
            return SearchResult(
                match=row["Description"],
                model_number=row["ModelNumber"],
                confidence=confidence,
                score=score,
                tokens_matched=classified,
                candidate_count=candidate_count,
            )

        return None

    @staticmethod
    def _validate_search_profile(classified: Dict[str, List[str]]) -> tuple[bool, str]:
        """
        Validate that the search profile is valid.

        Rules:
        - Require at least one MODEL token
        - Reject contradictory DRIVETRAIN tokens (e.g., awd + fwd together)

        Args:
            classified: Output from classify_tokens()

        Returns:
            Tuple (is_valid: bool, reason_if_invalid: str)
        """
        # Require MODEL
        if not classified.get("MODEL"):
            return False, "No MODEL token in search"

        # Check for drivetrain contradictions
        drivetrains = set(classified.get("DRIVETRAIN", []))
        if len(drivetrains) > 1:
            # Multiple drivetrain types present — check for contradiction
            if "awd" in drivetrains and "fwd" in drivetrains:
                return False, "Contradictory drivetrain: awd and fwd both present"
            if "awd" in drivetrains and "rwd" in drivetrains:
                return False, "Contradictory drivetrain: awd and rwd both present"
            if "fwd" in drivetrains and "rwd" in drivetrains:
                return False, "Contradictory drivetrain: fwd and rwd both present"

        return True, ""
