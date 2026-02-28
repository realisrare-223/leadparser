"""
Sentiment Analyzer — scores review text using free offline NLP.

Uses VADER (rule-based, no training required, no API) as the primary
engine and TextBlob as a secondary opinion.  Both work completely
offline after a one-time pip install.

This module is used to:
  1. Analyse any review text that was scraped alongside a listing.
  2. Adjust lead scoring downward for businesses with very happy
     customers (less likely to need outside help).
  3. Flag businesses with lots of negative reviews — those owners
     are often motivated to make changes.

NOTE: Google Maps does not expose individual review text easily.
This module is pre-wired and ready to use if/when review text is
available (e.g. from Yelp scraping or manual input).
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy imports to avoid ImportError at startup if optional packages are missing
_vader_analyzer  = None
_textblob_module = None


def _get_vader():
    global _vader_analyzer
    if _vader_analyzer is None:
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            _vader_analyzer = SentimentIntensityAnalyzer()
        except ImportError:
            logger.warning("vaderSentiment not installed — sentiment analysis disabled")
    return _vader_analyzer


def _get_textblob():
    global _textblob_module
    if _textblob_module is None:
        try:
            import textblob
            _textblob_module = textblob
        except ImportError:
            logger.warning("textblob not installed — secondary sentiment disabled")
    return _textblob_module


class SentimentAnalyzer:
    """
    Analyse a list of review strings and return aggregated sentiment.
    """

    # ── Public API ───────────────────────────────────────────────────

    def analyse_reviews(self, reviews: list[str]) -> dict:
        """
        Analyse a list of review strings.

        Returns a dict:
        {
          "overall":        "positive" | "neutral" | "negative",
          "compound_score": float (-1.0 to 1.0),
          "positive_pct":   float (0.0–100.0),
          "negative_pct":   float (0.0–100.0),
          "review_count":   int,
          "lead_score_adj": int   # adjustment to add to lead score
        }
        """
        if not reviews:
            return self._empty_result()

        vader = _get_vader()
        if vader is None:
            return self._empty_result()

        scores = [vader.polarity_scores(r)["compound"] for r in reviews]
        avg_compound = sum(scores) / len(scores)

        positive_pct = sum(1 for s in scores if s > 0.05)  / len(scores) * 100
        negative_pct = sum(1 for s in scores if s < -0.05) / len(scores) * 100

        overall = self._classify(avg_compound)

        # Lead score adjustment: negative reviews = owner is motivated to fix things
        adj = 0
        if avg_compound < -0.3:
            adj = 4   # Very negative → high priority
        elif avg_compound < 0.0:
            adj = 2   # Slightly negative → moderate priority bonus
        elif avg_compound > 0.5:
            adj = -1  # Very positive → already doing well; slight downgrade

        return {
            "overall":        overall,
            "compound_score": round(avg_compound, 3),
            "positive_pct":   round(positive_pct, 1),
            "negative_pct":   round(negative_pct, 1),
            "review_count":   len(reviews),
            "lead_score_adj": adj,
        }

    def analyse_single(self, text: str) -> dict:
        """Convenience wrapper for a single review string."""
        return self.analyse_reviews([text])

    def sentiment_label(self, compound: float) -> str:
        """Return a human-readable sentiment label."""
        return self._classify(compound)

    # ── Private helpers ───────────────────────────────────────────────

    @staticmethod
    def _classify(compound: float) -> str:
        if compound >= 0.05:
            return "positive"
        if compound <= -0.05:
            return "negative"
        return "neutral"

    @staticmethod
    def _empty_result() -> dict:
        return {
            "overall":        "unknown",
            "compound_score": 0.0,
            "positive_pct":   0.0,
            "negative_pct":   0.0,
            "review_count":   0,
            "lead_score_adj": 0,
        }
