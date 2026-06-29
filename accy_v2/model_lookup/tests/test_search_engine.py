"""Tests for OEM Vehicle Model Search Engine."""

import pytest
from pathlib import Path

from accy_v2.model_lookup.translator import translate_keywords, load_oem_translator
from accy_v2.model_lookup.classifier import classify_tokens, load_classification_config
from accy_v2.model_lookup.scorer import compute_score, compute_confidence, CATEGORY_WEIGHTS, MINIMUM_SCORE
from accy_v2.model_lookup.search_engine import VehicleSearchEngine


class TestTranslator:
    """Test OEM-specific keyword translation."""

    def test_translate_keywords_mitsubishi(self):
        """Test Mitsubishi translation: s-awc -> awd."""
        translations = {"s-awc": "awd", "awc": "awd"}
        result = translate_keywords(["outlander", "s-awc", "phev", "gt"], translations)
        assert result == ["outlander", "awd", "phev", "gt"]

    def test_translate_with_deduplication(self):
        """Test that deduplication preserves first occurrence."""
        translations = {"s-awc": "awd"}
        result = translate_keywords(["awd", "s-awc"], translations)
        assert result == ["awd"]  # s-awc -> awd already present

    def test_translate_preserves_untranslatable(self):
        """Test that tokens without translations are preserved."""
        translations = {"s-awc": "awd"}
        result = translate_keywords(["outlander", "s-awc", "gt"], translations)
        assert "outlander" in result
        assert "gt" in result

    def test_load_oem_translator_mitsubishi(self):
        """Test loading Mitsubishi translator config."""
        translator = load_oem_translator("Mitsubishi")
        assert "s-awc" in translator
        assert translator["s-awc"] == "awd"

    def test_load_oem_translator_mazda(self):
        """Test loading Mazda translator config — has different abbreviations."""
        translator = load_oem_translator("Mazda")
        assert "i-activ" in translator
        assert translator["i-activ"] == "awd"
        # Mazda's single-char differs from Mitsubishi
        assert translator.get("p") == "preferred"


class TestClassifier:
    """Test semantic classification of tokens."""

    def test_classify_tokens_basic(self):
        """Test classification of a standard set of keywords."""
        config = load_classification_config("Mitsubishi")
        classified = classify_tokens(["outlander", "gt", "awd", "phev"], config)

        assert "MODEL" in classified
        assert "outlander" in classified["MODEL"]
        assert "gt" in classified["TRIM"]
        assert "awd" in classified["DRIVETRAIN"]
        assert "phev" in classified["ENGINE_TYPE"]

    def test_classify_handles_unclassified(self):
        """Test that unclassified tokens are handled gracefully (not passed through)."""
        config = load_classification_config("Mitsubishi")
        # "xyz" is not in the classification map
        classified = classify_tokens(["outlander", "xyz", "gt"], config)

        # xyz should not appear in the result
        assert "UNCLASSIFIED" not in classified
        assert all("xyz" not in tokens for tokens in classified.values())


class TestScorer:
    """Test weighted scoring and confidence calculation."""

    def test_compute_score_simple(self):
        """Test score computation with basic categories."""
        classified = {
            "MODEL": ["outlander"],
            "DRIVETRAIN": ["awd"],
            "TRIM": ["gt"],
            "ENGINE_TYPE": ["phev"],
        }
        score = compute_score(classified, CATEGORY_WEIGHTS)
        # MODEL(10) + DRIVETRAIN(6) + TRIM(5) + ENGINE_TYPE(8) = 29
        assert score == 29

    def test_compute_score_empty_categories_ignored(self):
        """Test that empty category lists don't contribute to score."""
        classified = {
            "MODEL": ["outlander"],
            "DRIVETRAIN": ["awd"],
            "PACKAGE": [],  # Empty — should not contribute
        }
        score = compute_score(classified, CATEGORY_WEIGHTS)
        # MODEL(10) + DRIVETRAIN(6) = 16
        assert score == 16

    def test_compute_confidence_single_match_above_minimum(self):
        """Test confidence with a single match and score above minimum."""
        # Score 29, candidate_count 1
        confidence = compute_confidence(score=29, min_score=MINIMUM_SCORE, candidate_count=1)
        # Should be approximately 29 / 34 ≈ 0.85
        assert 0.8 < confidence < 0.9

    def test_compute_confidence_ambiguous(self):
        """Test that ambiguous results (multiple candidates) get 0 confidence."""
        confidence = compute_confidence(score=20, min_score=MINIMUM_SCORE, candidate_count=2)
        assert confidence == 0.0

    def test_compute_confidence_below_minimum(self):
        """Test that scores below minimum get 0 confidence."""
        confidence = compute_confidence(score=8, min_score=MINIMUM_SCORE, candidate_count=1)
        assert confidence == 0.0


class TestSearchEngine:
    """Integration tests using the full search engine."""

    def test_search_exact_match_mitsubishi(self):
        """Test finding exact match: Outlander PHEV GT."""
        csv_path = Path(__file__).parent.parent / "db" / "db_vehicle_models.csv"
        if not csv_path.exists():
            pytest.skip(f"CSV not found: {csv_path}")

        engine = VehicleSearchEngine(
            csv_path=str(csv_path),
            configs_dir=str(csv_path.parent.parent / "configs"),
            oem_config={},
        )

        result = engine.search(
            make="Mitsubishi",
            year=2026,
            raw_keywords=["outlander", "phev", "gt"],
        )

        assert result is not None, "Should find at least one match"
        assert result.model_number is not None
        assert result.confidence > 0.0
        assert "outlander" in result.match.lower() or "gt" in result.match.lower()

    def test_search_disambiguation_mitsubishi(self):
        """Test disambiguation: adding 'premium' should narrow results."""
        csv_path = Path(__file__).parent.parent / "db" / "db_vehicle_models.csv"
        if not csv_path.exists():
            pytest.skip(f"CSV not found: {csv_path}")

        engine = VehicleSearchEngine(
            csv_path=str(csv_path),
            configs_dir=str(csv_path.parent.parent / "configs"),
            oem_config={},
        )

        result = engine.search(
            make="Mitsubishi",
            year=2026,
            raw_keywords=["outlander", "phev", "gt", "premium"],
        )

        # With "premium" discriminator, should still find a match or return None gracefully
        if result is not None:
            assert result.confidence > 0.0

    def test_search_contradiction_rejected(self):
        """Test that contradictory drivetrain (awd + fwd) is rejected."""
        csv_path = Path(__file__).parent.parent / "db" / "db_vehicle_models.csv"
        if not csv_path.exists():
            pytest.skip(f"CSV not found: {csv_path}")

        engine = VehicleSearchEngine(
            csv_path=str(csv_path),
            configs_dir=str(csv_path.parent.parent / "configs"),
            oem_config={},
        )

        # Inject contradictory drivetrains into the engine's classified dict
        # We do this by calling _validate_search_profile directly
        classified = {
            "MODEL": ["outlander"],
            "DRIVETRAIN": ["awd", "fwd"],  # Contradiction!
        }

        is_valid, reason = engine._validate_search_profile(classified)
        assert not is_valid
        assert "contradict" in reason.lower()

    def test_search_requires_model(self):
        """Test that search requires at least one MODEL token."""
        engine = VehicleSearchEngine(
            csv_path="dummy.csv",  # Not used in this test
            configs_dir="dummy",
        )

        # No MODEL tokens
        classified = {
            "DRIVETRAIN": ["awd"],
            "TRIM": ["gt"],
        }

        is_valid, reason = engine._validate_search_profile(classified)
        assert not is_valid
        assert "model" in reason.lower()


class TestRegressionAgainstExistingLogic:
    """Ensure existing search_models_by_description() behavior is preserved."""

    def test_existing_search_still_works(self):
        """Verify that search_models_by_description() is not broken."""
        from accy_v2.model_lookup.models.manufacture_module import search_models_by_description

        csv_path = Path(__file__).parent.parent / "db" / "db_vehicle_models.csv"
        if not csv_path.exists():
            pytest.skip(f"CSV not found: {csv_path}")

        # Direct call to existing function
        results = search_models_by_description(
            make="Mitsubishi",
            year=2026,
            keywords=["outlander", "phev", "gt"],
            csv_path=str(csv_path),
        )

        # Should return at least one result
        assert len(results) >= 1
        assert "ModelNumber" in results.columns
        assert "Description" in results.columns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
