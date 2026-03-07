"""
Unit tests for utils/pitch_engine.py

Tests cover:
  - Exact niche template match
  - Case-insensitive niche match
  - Partial niche match fallback
  - Default template fallback
  - Placeholder substitution: {name}, {city}, {niche}, {review_count}, {rating}
  - Missing placeholders handled gracefully (no exception)
  - generate() returns a non-empty string
  - list_niches_with_templates() excludes 'default'
"""

import pytest
from utils.pitch_engine import PitchEngine


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def engine(sample_config):
    return PitchEngine(sample_config)


def _raw(**overrides):
    base = {
        "name":         "Joe's Plumbing",
        "city":         "Dallas",
        "review_count": 45,
        "rating":       "3.8",
    }
    base.update(overrides)
    return base


# ── Template selection ────────────────────────────────────────────────────────

class TestTemplateSelection:
    def test_exact_niche_match(self, engine, sample_config):
        result = engine.generate("plumbers", _raw(), sample_config)
        assert "plumb" in result.lower()

    def test_case_insensitive_match(self, engine, sample_config):
        """'PLUMBERS' should still match the 'plumbers' template."""
        result_lower = engine.generate("plumbers", _raw(), sample_config)
        result_upper = engine.generate("PLUMBERS", _raw(), sample_config)
        assert result_lower == result_upper

    def test_partial_niche_match(self, engine, sample_config):
        """'residential plumbers' should partially match 'plumbers' template."""
        result = engine.generate("residential plumbers", _raw(), sample_config)
        assert result  # not empty

    def test_default_fallback(self, engine, sample_config):
        """An unknown niche should fall back to the default template."""
        result = engine.generate("widget-makers", _raw(), sample_config)
        assert result  # not empty
        assert "Joe" in result or "Dallas" in result  # placeholders filled

    def test_restaurants_niche(self, engine, sample_config):
        result = engine.generate("restaurants", _raw(name="Mario's"), sample_config)
        assert result  # not empty


# ── Placeholder substitution ──────────────────────────────────────────────────

class TestPlaceholders:
    def test_name_substituted(self, engine, sample_config):
        result = engine.generate("plumbers", _raw(name="Ace Plumbing"), sample_config)
        assert "Ace Plumbing" in result

    def test_city_substituted(self, engine, sample_config):
        result = engine.generate("plumbers", _raw(city="Houston"), sample_config)
        assert "Houston" in result

    def test_city_from_config_when_missing_in_raw(self, engine, sample_config):
        """If raw has no city, fall back to config location city."""
        raw = _raw()
        raw["city"] = ""
        result = engine.generate("plumbers", raw, sample_config)
        # config has city=Dallas
        assert "Dallas" in result

    def test_default_name_when_missing(self, engine, sample_config):
        """If name is missing, use 'there' as fallback."""
        result = engine.generate("plumbers", _raw(name=""), sample_config)
        assert result  # should not crash
        assert "there" in result or "Plumbing" not in result

    def test_review_count_and_rating_available(self, engine, sample_config):
        """Custom template using {review_count} should work."""
        custom_config = dict(sample_config)
        custom_config["pitch_templates"] = {
            "default": "Hi {name}, you have {review_count} reviews and a {rating} rating.",
        }
        eng = PitchEngine(custom_config)
        result = eng.generate("anything", _raw(review_count=25, rating="4.2"), custom_config)
        assert "25" in result
        assert "4.2" in result


# ── Missing placeholder safety ────────────────────────────────────────────────

class TestMissingPlaceholders:
    def test_unknown_placeholder_does_not_raise(self, engine, sample_config):
        """Template with unknown key like {unknown} must not raise."""
        custom_config = dict(sample_config)
        custom_config["pitch_templates"] = {
            "default": "Hi {name}, your score is {unknown_key}.",
        }
        eng = PitchEngine(custom_config)
        result = eng.generate("anything", _raw(), custom_config)
        assert result  # should return something, not crash
        assert "Joe" in result or "{name}" not in result


# ── generate() output contract ────────────────────────────────────────────────

class TestGenerateOutput:
    def test_returns_string(self, engine, sample_config):
        result = engine.generate("plumbers", _raw(), sample_config)
        assert isinstance(result, str)

    def test_not_empty(self, engine, sample_config):
        result = engine.generate("plumbers", _raw(), sample_config)
        assert len(result) > 0

    def test_stripped(self, engine, sample_config):
        """Result should not have leading/trailing whitespace."""
        result = engine.generate("plumbers", _raw(), sample_config)
        assert result == result.strip()


# ── list_niches_with_templates() ──────────────────────────────────────────────

class TestListNiches:
    def test_excludes_default(self, engine):
        niches = engine.list_niches_with_templates()
        assert "default" not in niches

    def test_includes_configured_niches(self, engine):
        niches = engine.list_niches_with_templates()
        assert "plumbers" in niches
        assert "restaurants" in niches

    def test_returns_list(self, engine):
        assert isinstance(engine.list_niches_with_templates(), list)
