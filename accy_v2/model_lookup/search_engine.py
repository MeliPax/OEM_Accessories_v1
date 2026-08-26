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
    drivetrain: Optional[str] = None  # Drivetrain from DB (e.g., "ALL_WHEEL_DRIVE")
    fuel_type: Optional[str] = None  # Fuel type (e.g., "phev", "electric", or gasoline if None)
    color: Optional[str] = None  # Color keyword from config (e.g., "noir", "carbon")
    package: Optional[str] = None  # ADS numeric style ID from DB (e.g., "481877")


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

        # 5.5. Exact TRIM token-set matching (narrowing layer)
        # Apply ONLY when we have multiple candidates to disambiguate.
        # Extracts TRIM tokens from both search and DB rows, keeps only exact matches.
        # This fixes collisions like "GT" vs "GT Premium" vs "GT NOIR" where substring
        # matching returns all three, but exact TRIM set matching narrows to one.
        if len(results) > 1:
            searched_trim_set = set(classified.get("TRIM", []))
            if searched_trim_set:  # Only apply if search includes TRIM tokens
                narrowed_results = []
                for idx, row in results.iterrows():
                    candidate_trim_set = self._extract_trim_token_set(
                        row["Description"], classification_config
                    )
                    if candidate_trim_set == searched_trim_set:
                        narrowed_results.append(row)

                if narrowed_results:
                    results = pd.DataFrame(narrowed_results).reset_index(drop=True)
                    if self.logger:
                        self.logger.debug(
                            f"Exact TRIM matching narrowed {len(results) + len(narrowed_results) - len(results)} "
                            f"candidates to {len(results)} (searched TRIM: {searched_trim_set})"
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
            drivetrain, fuel_type, color, package = self._extract_row_metadata(row, classification_config)
            return SearchResult(
                match=row["Description"],
                model_number=row["ModelNumber"],
                model_numbers=[row["ModelNumber"]],
                confidence=confidence,
                score=score,
                tokens_matched=classified,
                candidate_count=candidate_count,
                drivetrain=drivetrain,
                fuel_type=fuel_type,
                color=color,
                package=package,
            )

        # Same vehicle re-coded under multiple model numbers: not real ambiguity.
        # (Only applied if OEM config explicitly enables this behavior.)
        # Duplicate model-number handling (unconditional): if multiple candidates normalize to
        # the same (ModelYear, ModelName, Description), they are legitimate multiple model codes
        # for the same vehicle config (e.g., old/new mfr part numbers), not ambiguity.
        if candidate_count > 1:
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
                row = results.iloc[0]
                drivetrain, fuel_type, color, package = self._extract_row_metadata(row, classification_config)
                return SearchResult(
                    match=row["Description"],
                    model_number=row["ModelNumber"],
                    model_numbers=results["ModelNumber"].tolist(),
                    confidence=resolved_confidence,
                    score=score,
                    tokens_matched=classified,
                    candidate_count=candidate_count,
                    is_duplicate_group=True,
                    drivetrain=drivetrain,
                    fuel_type=fuel_type,
                    color=color,
                    package=package,
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
                row = results.iloc[0]
                drivetrain, fuel_type, color, package = self._extract_row_metadata(row, classification_config)
                return SearchResult(
                    match=row["Description"],
                    model_number=model_numbers[0],  # Primary model number
                    model_numbers=model_numbers,  # ALL model numbers
                    confidence=confidence,
                    score=score,
                    tokens_matched=classified,
                    candidate_count=candidate_count,
                    is_duplicate_group=False,  # Not duplicate codes, variant handling
                    drivetrain=drivetrain,
                    fuel_type=fuel_type,
                    color=color,
                    package=package,
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

    def _extract_trim_token_set(self, description: str, classification_config: Dict) -> set:
        """
        Extract TRIM token set from a DB description for exact-match disambiguation.

        Used to narrow candidates when multiple rows match substring search but differ in TRIM modifiers.
        Example: "GT" vs "GT Premium" vs "GT NOIR" — all contain "gt", but only exact TRIM match
        narrows to the intended row.

        Args:
            description: DB description string
            classification_config: Classification config for this OEM

        Returns:
            set of TRIM tokens found in description
        """
        tokens = _extract_description_tokens(description)
        classified = classify_tokens(tokens, classification_config, self.logger)
        return set(classified.get("TRIM", []))

    def _extract_row_metadata(self, row, classification_config: Dict, color_keywords: List[str] = None) -> tuple:
        """
        Extract drivetrain, fuel_type, color, and package from a database row.

        Args:
            row: pandas Series representing a database row
            classification_config: Classification config for this OEM
            color_keywords: List of color keywords to check for (optional)

        Returns:
            Tuple of (drivetrain, fuel_type, color, package)
        """
        import pandas as pd

        # Drivetrain: direct column, 0 empty values in DB
        drivetrain = row.get("Drivetrain") if pd.notna(row.get("Drivetrain")) else None

        # Fuel type: 3-tier fallback
        fuel_type = None
        # Tier 1: Use engine_type column if populated
        if pd.notna(row.get("engine_type")) and row.get("engine_type"):
            fuel_type = str(row.get("engine_type")).lower()
        else:
            # Tier 2: Check if search included ENGINE_TYPE tokens
            # (This would come from the classified dict passed during search)
            # For now, leave as None — will be filled by caller if needed
            pass
        # Note: Tier 3 (ModelName/Description classification) would require passing classified dict

        # Color: config-driven lookup
        color = None
        if color_keywords:
            row_description = str(row.get("Description", "")).lower()
            for color_kw in color_keywords:
                if color_kw.lower() in row_description:
                    color = color_kw.lower()
                    break

        # Package: direct column (ADS numeric style ID), 0 empty values in Mitsubishi rows
        package = row.get("Package") if pd.notna(row.get("Package")) else None

        return drivetrain, fuel_type, color, package

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


def diagnose_search_failure(
    make: str,
    year: int,
    classified: Dict[str, List[str]],
    csv_path: str,
) -> Dict[str, str]:
    """
    Diagnose why a search failed by walking the Year → Model → Trim → Drivetrain hierarchy.

    Returns a dict with structured diagnostic info instead of generic "NOT_FOUND".

    Args:
        make: Manufacturer name (e.g., "Mitsubishi")
        year: Model year (e.g., 2026)
        classified: Classified tokens dict from failed search
        csv_path: Path to vehicle models CSV

    Returns:
        Dict with keys:
        - reason: One of MANUFACTURER_NOT_IN_DB, MODEL_YEAR_NOT_IN_DB, MODEL_NAME_NOT_FOUND_FOR_YEAR,
                  TRIM_VARIANT_NOT_FOUND, AMBIGUOUS_TRIM_MULTIPLE_MODEL_NUMBERS, SCORE_BELOW_THRESHOLD
        - available_years: List of years in DB for this manufacturer (if applicable)
        - available_models: List of models in DB for this year (if applicable)
        - available_trims: List of trims in DB for matching model (if applicable)
        - requested_trim: The trim tokens that were searched for
        - details: Human-readable explanation
    """
    try:
        db = pd.read_csv(csv_path)
    except Exception as e:
        return {
            "reason": "DATABASE_ERROR",
            "details": f"Failed to load database: {str(e)}"
        }

    # Layer 1: Is manufacturer in DB?
    mfr_rows = db[db["Manufacturer"].str.lower() == make.lower()]
    if mfr_rows.empty:
        return {
            "reason": "MANUFACTURER_NOT_IN_DB",
            "details": f"Manufacturer '{make}' not found in database"
        }

    # Layer 2: Is this year available for this manufacturer?
    year_rows = mfr_rows[mfr_rows["ModelYear"] == year]
    if year_rows.empty:
        available_years = sorted(mfr_rows["ModelYear"].unique().tolist())
        return {
            "reason": "MODEL_YEAR_NOT_IN_DB",
            "available_years": available_years,
            "details": f"Model year {year} not in database for {make}. Available years: {available_years}"
        }

    # Layer 3: Does the MODEL match?
    model_tokens = set(classified.get("MODEL", []))
    if not model_tokens:
        return {
            "reason": "NO_MODEL_TOKEN",
            "details": "No MODEL token in search (search validation should have caught this)"
        }

    matching_model_rows = []
    for model_kw in model_tokens:
        # Word-boundary match for model
        pattern = rf"(?<![-])\b{model_kw}\b(?![-])"
        model_matches = year_rows[
            (year_rows["ModelName"].str.lower().str.contains(pattern, regex=True, na=False)) |
            (year_rows["Description"].str.lower().str.contains(pattern, regex=True, na=False))
        ]
        matching_model_rows.extend(model_matches.index.tolist())

    if not matching_model_rows:
        available_models = sorted(year_rows["ModelName"].unique().tolist())
        return {
            "reason": "MODEL_NAME_NOT_FOUND_FOR_YEAR",
            "available_models": available_models,
            "requested_model": list(model_tokens),
            "details": f"Model {model_tokens} not found for {make} {year}. Available models: {available_models}"
        }

    model_rows = year_rows.loc[matching_model_rows]

    # Layer 4: Does the TRIM match exactly?
    trim_tokens = set(classified.get("TRIM", []))
    requested_trim = list(trim_tokens) if trim_tokens else ["(none)"]

    if trim_tokens:
        # Exact TRIM match (from plan Step 1)
        exact_trim_matches = []
        for idx, row in model_rows.iterrows():
            row_tokens = _extract_description_tokens(row["Description"])
            row_classified = classify_tokens(row_tokens, {"token_map": {}})
            row_trim_set = set(row_classified.get("TRIM", []))
            if row_trim_set == trim_tokens:
                exact_trim_matches.append(idx)

        if exact_trim_matches:
            # Found exact match(es)
            candidates = model_rows.loc[exact_trim_matches]
            if len(candidates) == 1:
                # Unambiguous
                return {
                    "reason": "MATCH_FOUND_BUT_FAILED_CONFIDENCE",
                    "details": "Match found but failed confidence gate (internal error)"
                }
            else:
                # Ambiguous (multiple model numbers)
                model_nums = candidates["ModelNumber"].tolist()
                return {
                    "reason": "AMBIGUOUS_TRIM_MULTIPLE_MODEL_NUMBERS",
                    "model_numbers": model_nums,
                    "details": f"Multiple model numbers for this exact TRIM: {model_nums}"
                }
        else:
            # No exact TRIM match
            available_trims = sorted(model_rows["TrimName"].unique().tolist())
            return {
                "reason": "TRIM_VARIANT_NOT_FOUND",
                "requested_trim": requested_trim,
                "available_trims": available_trims,
                "details": f"Trim variant {requested_trim} not found. Available trims: {available_trims}"
            }
    else:
        # No TRIM tokens in search
        available_trims = sorted(model_rows["TrimName"].unique().tolist())
        return {
            "reason": "NO_TRIM_TOKEN",
            "available_trims": available_trims,
            "details": f"No TRIM token in search. Available trims: {available_trims}"
        }


def _extract_description_tokens(description: str) -> List[str]:
    """Extract tokens from a description string (simple split + cleanup)."""
    if not description or not isinstance(description, str):
        return []
    tokens = description.lower().replace("_", " ").split()
    return [t.strip() for t in tokens if t.strip()]
