"""
Unit tests for utils/sentiment_analyzer.py

Tests cover:
  - analyse_reviews() with positive, neutral, negative review lists
  - analyse_reviews() with empty list → _empty_result()
  - analyse_single() convenience wrapper
  - sentiment_label() classification thresholds
  - lead_score_adj values: very negative (+4), slightly negative (+2),
    very positive (-1), neutral (0)
  - Result dict keys always present
"""

import pytest
from unittest.mock import patch, MagicMock
from utils.sentiment_analyzer import SentimentAnalyzer


@pytest.fixture
def analyzer():
    return SentimentAnalyzer()


# ── Helpers ───────────────────────────────────────────────────────────────────

POSITIVE_REVIEWS = [
    "Absolutely fantastic service! Would recommend to everyone.",
    "Best plumber in the city, very professional.",
    "Outstanding work, arrived on time and fixed everything.",
]

NEGATIVE_REVIEWS = [
    "Terrible experience, they broke my pipe and charged extra.",
    "Worst service I have ever had. Never using again.",
    "They left a mess and the repair failed within a week.",
]

NEUTRAL_REVIEWS = [
    "They came and fixed it. OK.",
    "The job was done.",
    "Average service, nothing special.",
]


# ── analyse_reviews() ─────────────────────────────────────────────────────────

class TestAnalyseReviews:
    def test_returns_required_keys(self, analyzer):
        result = analyzer.analyse_reviews(POSITIVE_REVIEWS)
        required = {
            "overall", "compound_score", "positive_pct",
            "negative_pct", "review_count", "lead_score_adj"
        }
        assert required.issubset(result.keys())

    def test_review_count_matches_input(self, analyzer):
        result = analyzer.analyse_reviews(POSITIVE_REVIEWS)
        assert result["review_count"] == len(POSITIVE_REVIEWS)

    def test_positive_reviews_classified(self, analyzer):
        result = analyzer.analyse_reviews(POSITIVE_REVIEWS)
        assert result["overall"] == "positive"
        assert result["compound_score"] > 0.05

    def test_negative_reviews_classified(self, analyzer):
        result = analyzer.analyse_reviews(NEGATIVE_REVIEWS)
        assert result["overall"] == "negative"
        assert result["compound_score"] < -0.05

    def test_empty_list_returns_unknown(self, analyzer):
        result = analyzer.analyse_reviews([])
        assert result["overall"] == "unknown"
        assert result["compound_score"] == 0.0
        assert result["review_count"] == 0
        assert result["lead_score_adj"] == 0

    def test_positive_pct_high_for_positive_reviews(self, analyzer):
        result = analyzer.analyse_reviews(POSITIVE_REVIEWS)
        assert result["positive_pct"] > 50.0

    def test_negative_pct_high_for_negative_reviews(self, analyzer):
        result = analyzer.analyse_reviews(NEGATIVE_REVIEWS)
        assert result["negative_pct"] > 50.0

    def test_compound_score_in_range(self, analyzer):
        for reviews in [POSITIVE_REVIEWS, NEGATIVE_REVIEWS, NEUTRAL_REVIEWS]:
            result = analyzer.analyse_reviews(reviews)
            assert -1.0 <= result["compound_score"] <= 1.0


# ── lead_score_adj values ─────────────────────────────────────────────────────

class TestLeadScoreAdj:
    def test_very_negative_gives_high_adj(self, analyzer):
        """compound < -0.3 → adj = 4"""
        with patch("utils.sentiment_analyzer._get_vader") as mock_vader_fn:
            mock_vader = MagicMock()
            mock_vader.polarity_scores.return_value = {"compound": -0.5}
            mock_vader_fn.return_value = mock_vader

            result = analyzer.analyse_reviews(["bad review"])
            assert result["lead_score_adj"] == 4

    def test_slightly_negative_gives_moderate_adj(self, analyzer):
        """compound in [-0.3, 0) → adj = 2"""
        with patch("utils.sentiment_analyzer._get_vader") as mock_vader_fn:
            mock_vader = MagicMock()
            mock_vader.polarity_scores.return_value = {"compound": -0.15}
            mock_vader_fn.return_value = mock_vader

            result = analyzer.analyse_reviews(["slightly bad"])
            assert result["lead_score_adj"] == 2

    def test_very_positive_gives_negative_adj(self, analyzer):
        """compound > 0.5 → adj = -1"""
        with patch("utils.sentiment_analyzer._get_vader") as mock_vader_fn:
            mock_vader = MagicMock()
            mock_vader.polarity_scores.return_value = {"compound": 0.8}
            mock_vader_fn.return_value = mock_vader

            result = analyzer.analyse_reviews(["amazing!"])
            assert result["lead_score_adj"] == -1

    def test_neutral_adj_zero(self, analyzer):
        """compound in [0, 0.5] → adj = 0"""
        with patch("utils.sentiment_analyzer._get_vader") as mock_vader_fn:
            mock_vader = MagicMock()
            mock_vader.polarity_scores.return_value = {"compound": 0.2}
            mock_vader_fn.return_value = mock_vader

            result = analyzer.analyse_reviews(["ok"])
            assert result["lead_score_adj"] == 0


# ── analyse_single() ──────────────────────────────────────────────────────────

class TestAnalyseSingle:
    def test_returns_dict(self, analyzer):
        result = analyzer.analyse_single("Great service!")
        assert isinstance(result, dict)

    def test_review_count_is_one(self, analyzer):
        result = analyzer.analyse_single("decent")
        assert result["review_count"] == 1

    def test_positive_text(self, analyzer):
        result = analyzer.analyse_single("Absolutely wonderful experience, highly recommend!")
        assert result["overall"] == "positive"

    def test_negative_text(self, analyzer):
        result = analyzer.analyse_single("Terrible service, complete disaster, never again.")
        assert result["overall"] == "negative"


# ── sentiment_label() ─────────────────────────────────────────────────────────

class TestSentimentLabel:
    def test_positive_threshold(self, analyzer):
        assert analyzer.sentiment_label(0.05) == "positive"
        assert analyzer.sentiment_label(0.5)  == "positive"
        assert analyzer.sentiment_label(1.0)  == "positive"

    def test_negative_threshold(self, analyzer):
        assert analyzer.sentiment_label(-0.05) == "negative"
        assert analyzer.sentiment_label(-0.5)  == "negative"
        assert analyzer.sentiment_label(-1.0)  == "negative"

    def test_neutral_range(self, analyzer):
        assert analyzer.sentiment_label(0.0)   == "neutral"
        assert analyzer.sentiment_label(0.04)  == "neutral"
        assert analyzer.sentiment_label(-0.04) == "neutral"


# ── VADER unavailable graceful fallback ──────────────────────────────────────

class TestVaderUnavailable:
    def test_returns_empty_when_vader_missing(self, analyzer):
        with patch("utils.sentiment_analyzer._get_vader", return_value=None):
            result = analyzer.analyse_reviews(["some review"])
            assert result["overall"] == "unknown"
            assert result["review_count"] == 0
