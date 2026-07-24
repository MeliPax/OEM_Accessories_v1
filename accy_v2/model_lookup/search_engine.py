"""OEM Vehicle Model Search Engine — translates, classifies, scores, and searches."""

from dataclasses import dataclass
from typing import Dict, List, Optional
import pandas as pd

from .semantic.translator import load_oem_translator, translate_keywords
from .semantic.classifier import load_classification_config, classify_tokens
from .semantic.scorer import CATEGORY_WEIGHTS, MINIMUM_SCORE, compute_score, compute_confidence

from .models.manufacture_module import search_models_by_description, _extract_description_tokens


@dataclass
class SearchResult:
    """Result of a successful model search."""

    match: str  # Human-readable description (e.g., "Outlander PHEV GT S-AWC")
    model_number: str  # Primary OEM model number (e.g., "COEV-X")
    model_numbers: List[str]  # All model numbers for this match (len 1 normally; >1 for duplicate codes)
    confidence: float  # 0.0 to 1.0
    score: int  # Raw weighted score
    tokens_matched: Dict[str, List[str]]  # Classified tokens used for matching
    candidate_count: int  # Number of DB rows considered (raw count, unaffected by duplicate grouping)
    is_duplicate_group: bool = False  # True when multiple model numbers map to same vehicle


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
        ignore_keyword_categories: List[str] = None,
        pipeline_logger=None,
    ):
        """
        Initialize search engine for an OEM.

        Args:
            csv_path: Path to vehicle models CSV (model_lookup/db/db_vehicle_models.csv)
            configs_dir: Directory containing translator and classification JSONs
            oem_config: OEM config dict (optional, used for single-char abbreviations)
            ignore_keyword_categories: Categories to exclude from search (e.g., INTERIOR, EXTERIOR_COLOR)
            pipeline_logger: Logger for debug messages (optional)
        """
        self.csv_path = csv_path
        self.configs_dir = configs_dir
        self.oem_config = oem_config or {}
        self.ignore_keyword_categories = ignore_keyword_categories or []
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

        # 2.5 Filter ignored categories (INTERIOR, EXTERIOR_COLOR, etc.)
        classified = self._filter_ignored_categories(classified)
        filtered_keywords = [tok for toks in classified.values() for tok in toks if toks]
        if self.logger:
            self.logger.debug(f"After filtering ignored categories {self.ignore_keyword_categories}: {classified}")

        # 2.75 Filter excluded keywords (ICE, combustion, etc. — keywords with no DB presence)
        if "model_lookup_rules" in self.oem_config:
            oem_rules = self.oem_config.get("model_lookup_rules", {}).get(make, {})
        else:
            oem_rules = self.oem_config
        excluded_kws = oem_rules.get("exclude_keywords", [])
        if excluded_kws:
            excluded_set = {kw.lower() for kw in excluded_kws}
            filtered_keywords = [kw for kw in filtered_keywords if kw.lower() not in excluded_set]
            if self.logger:
                self.logger.debug(f"After filtering excluded keywords {excluded_kws}: {filtered_keywords}")

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

        # 5. Search database with filtered keywords (cosmetic keywords removed)
        # Note: We defer the score gate until after we know candidate_count (adaptive threshold)
        results = search_models_by_description(
            make=make,
            year=year,
            keywords=filtered_keywords,
            csv_path=self.csv_path,
            exclude_ev=exclude_ev,
            configs_dir=self.configs_dir,
            oem_config=self.oem_config,
        )

        candidate_count = len(results)

        if self.logger:
            self.logger.debug(f"Database search returned {candidate_count} candidates")

        # 6. Adaptive score gate: requirement depends on candidate count
        # - Unambiguous (1 candidate): always pass (we found THE vehicle)
        # - Low ambiguity (2-3 candidates): require score ≥ 12 (can resolve as duplicates)
        # - High ambiguity (4+ candidates): require stricter score ≥ 14
        min_score_required = self._get_adaptive_minimum_score(candidate_count)
        if score < min_score_required:
            if self.logger:
                self.logger.debug(
                    f"Score {score} below adaptive minimum {min_score_required} "
                    f"for {candidate_count} candidates"
                )
            return None

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
                model_numbers=[row["ModelNumber"]],
                confidence=confidence,
                score=score,
                tokens_matched=classified,
                candidate_count=candidate_count,
            )

        # Same vehicle re-coded under multiple model numbers: not real ambiguity.
        # (Only applied if OEM config explicitly enables this behavior.)
        # Handle both config formats: full config or OEM-specific rules dict
        if "model_lookup_rules" in self.oem_config:
            oem_rules = self.oem_config.get("model_lookup_rules", {}).get(make, {})
        else:
            oem_rules = self.oem_config
        oem_allow_duplicates = oem_rules.get("allow_duplicate_model_numbers", False)
        if candidate_count > 1 and oem_allow_duplicates:
            # Normalize each candidate description by filtering ignored categories
            normalized_keys = [
                self._normalize_description(desc, classification_config)
                for desc in results["Description"]
            ]
            # If all normalized descriptions match, treat as duplicate codes for one vehicle
            if len(set(normalized_keys)) == 1:
                resolved_confidence = compute_confidence(score, MINIMUM_SCORE, candidate_count=1)
                if self.logger:
                    self.logger.debug(
                        f"Resolved {candidate_count} candidates to single vehicle with multiple "
                        f"model numbers (ignoring {self.ignore_keyword_categories}): {results['ModelNumber'].tolist()}"
                    )
                return SearchResult(
                    match=results.iloc[0]["Description"],
                    model_number=results.iloc[0]["ModelNumber"],
                    model_numbers=results["ModelNumber"].tolist(),
                    confidence=resolved_confidence,
                    score=score,
                    tokens_matched=classified,
                    candidate_count=candidate_count,
                    is_duplicate_group=True,
                )

        # Multiple unique variants: not ambiguity, but variant handling (e.g., Manual/DCT, TCR variants).
        # Accept if all model numbers are unique, indicating distinct trim/variant combinations.
        # This handles cases like "Elantra N" returning both N Manual and N DCT with different model numbers.
        if candidate_count > 1:
            model_numbers = results["ModelNumber"].tolist()
            if len(set(model_numbers)) == candidate_count:
                # All model numbers are unique — these are variant combinations, not ambiguous
                if self.logger:
                    self.logger.debug(
                        f"Accepted {candidate_count} candidates with unique model numbers (variant handling): "
                        f"{model_numbers}"
                    )
                return SearchResult(
                    match=results.iloc[0]["Description"],
                    model_number=model_numbers[0],  # Primary model number
                    model_numbers=model_numbers,  # ALL model numbers
                    confidence=confidence,
                    score=score,
                    tokens_matched=classified,
                    candidate_count=candidate_count,
                    is_duplicate_group=False,  # Not duplicate codes, variant handling
                )

        return None

    def _get_adaptive_minimum_score(self, candidate_count: int) -> int:
        """
        Compute adaptive minimum score threshold based on candidate count.

        Rationale: Specificity of score requirement should inverse with result ambiguity:
        - 1 candidate: unambiguous, accept any score (the search found THE vehicle)
        - 2-3 candidates: low ambiguity, can resolve as duplicate codes, require score ≥ 12
        - 4+ candidates: high ambiguity, need higher specificity, require score ≥ 14

        Args:
            candidate_count: Number of candidates returned from database

        Returns:
            Minimum required score for this candidate count
        """
        if candidate_count == 1:
            return 0  # Unambiguous match — accept any score
        elif candidate_count <= 3:
            return 12  # Low ambiguity — standard threshold
        else:
            return 14  # High ambiguity — stricter threshold

    def _filter_ignored_categories(self, classified: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """
        Remove tokens in ignored categories from classified dict.

        Args:
            classified: Output from classify_tokens()

        Returns:
            filtered dict with ignored categories emptied
        """
        return {
            cat: (toks if cat not in self.ignore_keyword_categories else [])
            for cat, toks in classified.items()
        }

    def _normalize_description(self, description: str, classification_config: Dict) -> frozenset:
        """
        Normalize DB description by extracting tokens, classifying, and filtering ignored categories.

        Used for comparing candidate rows when detecting duplicate model codes.

        Args:
            description: DB description string
            classification_config: Classification config for this OEM

        Returns:
            frozenset of remaining tokens after filtering
        """
        tokens = _extract_description_tokens(description)
        classified = classify_tokens(tokens, classification_config, self.logger)
        filtered = self._filter_ignored_categories(classified)
        return frozenset(tok for toks in filtered.values() for tok in toks if toks)

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
