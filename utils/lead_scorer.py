"""
Lead Scorer — calculates a numeric priority score for each lead.

Higher score = higher priority for outreach.

Scoring rules (all weights configurable in config.yaml → scoring):
  ├─ Review count bracket         (0–10 pts)
  ├─ Star rating                  (0–9 pts bonus)
  ├─ High-value niche             (+7 pts bonus)
  ├─ Complete contact info        (+2 pts bonus)
  ├─ No website found             (+3 pts bonus)  ← big need signal
  └─ Active on Facebook           (+1 pt  bonus)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class LeadScorer:
    """
    Stateless scorer — create once, call score() for every lead.
    """

    def __init__(self, config: dict):
        self.scoring_cfg     = config.get("scoring", {})
        self.high_val_niches = [
            n.lower() for n in config.get("high_value_niches", [])
        ]

    # ── Public API ───────────────────────────────────────────────────

    def score(self, raw: dict, niche: str, config: dict) -> int:
        """
        Compute and return the integer lead score for *raw*.

        Parameters
        ----------
        raw    : dict of scraped fields (name, review_count, rating,
                 phone, address, website, facebook, …)
        niche  : the search niche string (e.g. "plumbers")
        config : full config dict (same object used everywhere)
        """
        total = 0
        sc    = self.scoring_cfg

        # ── Review count ─────────────────────────────────────────────
        reviews = self._int(raw.get("review_count", 0))

        if reviews == 0:
            total += sc.get("no_reviews_score",       10)
        elif reviews <= 10:
            total += sc.get("very_few_reviews_score",  8)
        elif reviews <= 25:
            total += sc.get("few_reviews_score",       5)
        elif reviews <= 50:
            total += sc.get("some_reviews_score",      3)
        else:
            total += sc.get("many_reviews_score",      1)

        # ── Star rating ──────────────────────────────────────────────
        rating = self._float(raw.get("rating", 0.0))

        if 0 < rating <= 3.5:
            total += sc.get("low_rating_bonus",        9)
        elif 3.5 < rating <= 4.0:
            total += sc.get("medium_rating_bonus",     4)
        # Businesses with 4.5+ already have good reviews; lower priority

        # ── High-value niche ─────────────────────────────────────────
        if niche.lower() in self.high_val_niches:
            total += sc.get("high_value_niche_bonus",  7)

        # ── Complete contact information ──────────────────────────────
        has_phone   = bool(raw.get("phone", "").strip())
        has_address = bool(raw.get("address", "").strip())
        if has_phone and has_address:
            total += sc.get("complete_contact_bonus",  2)

        # ── No website (highest need for digital services) ────────────
        if not raw.get("website", "").strip():
            total += sc.get("no_website_bonus",        3)

        # ── Social media present ──────────────────────────────────────
        if raw.get("facebook", "").strip():
            total += sc.get("has_facebook_bonus",      1)

        logger.debug(
            f"Score for '{raw.get('name', '?')}' ({niche}): {total}"
        )
        return total

    def label(self, score: int) -> str:
        """
        Return a human-readable priority label for a given score.
        Shown in the 'Lead Score' column alongside the number.
        """
        if score >= 18:
            return f"{score} ★★★ HOT"
        if score >= 12:
            return f"{score} ★★  WARM"
        if score >= 7:
            return f"{score} ★   MEDIUM"
        return f"{score}     LOW"

    # ── Private helpers ───────────────────────────────────────────────

    @staticmethod
    def _int(val) -> int:
        try:
            return int(val)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _float(val) -> float:
        try:
            return float(val)
        except (TypeError, ValueError):
            return 0.0
