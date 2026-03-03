"""
Lead Scorer — calculates a numeric priority score for each lead.

Higher score = higher priority for outreach.

Scoring rules (all weights configurable in config.yaml → scoring):
  ├─ Review count bracket         (0–15 pts)  ← primary driver
  ├─ Star rating                  (0–7  pts)  ← secondary driver
  ├─ High-value niche             (+7 pts bonus)
  ├─ Complete contact info        (+2 pts bonus)
  ├─ No website found             (+3 pts bonus)  ← strong need signal
  └─ Active on Facebook           (+1 pt  bonus)

Review count is weighted the most: fewer reviews = easier cold-call win,
because the business clearly isn't active online.
Rating is secondary: low rating = business struggling online = better lead.
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

        # ── Review count (primary: 0–15 pts) ─────────────────────────
        # Fewer reviews → higher score (cold-call sweet spot).
        reviews = self._int(raw.get("review_count", 0))

        if reviews == 0:
            total += sc.get("no_reviews_score",       15)   # completely invisible online
        elif reviews <= 5:
            total += sc.get("very_few_reviews_score",  12)
        elif reviews <= 15:
            total += sc.get("few_reviews_score",        9)
        elif reviews <= 40:
            total += sc.get("some_reviews_score",       5)
        elif reviews <= 100:
            total += sc.get("many_reviews_score",       1)
        # 100+ reviews → 0 pts (too established; hard to pitch)

        # ── Star rating (secondary: 0–7 pts) ─────────────────────────
        # Lower rating → higher score (business clearly struggling online).
        rating = self._float(raw.get("rating", 0.0))

        if 0 < rating <= 3.5:
            total += sc.get("low_rating_bonus",        7)
        elif 3.5 < rating <= 4.0:
            total += sc.get("medium_rating_bonus",     3)
        # 4.0+ star businesses already have a good online rep; lower priority

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
        if score >= 20:
            return f"{score} ★★★ HOT"
        if score >= 14:
            return f"{score} ★★  WARM"
        if score >= 8:
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
