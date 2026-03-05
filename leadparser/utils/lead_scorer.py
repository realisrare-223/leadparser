"""
Lead Scorer — calculates a numeric priority score for each lead.

Higher score = higher priority for outreach.

Scoring philosophy (review count is the primary signal):
  ├─ Review count bracket         (0–15 pts)  ← primary driver
  │    Sweet spot is 26–100 reviews: active business, not too big to approach.
  │    0–5 reviews = unestablished / possibly dead = low score.
  ├─ Star rating                  (0–5  pts)  ← secondary
  ├─ High-value niche             (+5 pts bonus)
  ├─ No website found             (+4 pts bonus)  ← strongest need signal
  ├─ Complete contact info        (+2 pts bonus)
  └─ Low rating (business struggling online) ← baked into rating bracket

More reviews = more established = real business worth calling.
Very few reviews = unproven / possibly fake / too small to pay.
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
        # More reviews = more established = better cold-call target.
        # Very few reviews = unproven, possibly closed, too small.
        # Sweet spot: 26–100 (active business, not a regional giant).
        reviews = self._int(raw.get("review_count", 0))

        if reviews == 0:
            total += sc.get("no_reviews_score",         0)   # probably fake/dead
        elif reviews <= 5:
            total += sc.get("very_few_reviews_score",   3)   # too new/small
        elif reviews <= 25:
            total += sc.get("few_reviews_score",        8)   # emerging
        elif reviews <= 100:
            total += sc.get("sweet_spot_reviews_score", 15)  # ← prime targets
        elif reviews <= 300:
            total += sc.get("many_reviews_score",       10)  # well-established
        elif reviews <= 600:
            total += sc.get("lots_reviews_score",        5)  # large business
        else:
            total += sc.get("huge_reviews_score",        1)  # too big to care

        # ── Star rating (secondary: 0–5 pts) ─────────────────────────
        # Low rating = struggling online = open to help.
        # High rating = already doing well; lower priority.
        rating = self._float(raw.get("rating", 0.0))

        if 0 < rating <= 3.0:
            total += sc.get("very_low_rating_bonus",    5)
        elif 3.0 < rating <= 3.8:
            total += sc.get("low_rating_bonus",         3)
        elif 3.8 < rating <= 4.5:
            total += sc.get("medium_rating_bonus",      1)
        # 4.5+ = doing great online; 0 extra pts

        # ── High-value niche ─────────────────────────────────────────
        if niche.lower() in self.high_val_niches:
            total += sc.get("high_value_niche_bonus",   5)

        # ── No website (clearest pitch opportunity) ───────────────────
        if not raw.get("website", "").strip():
            total += sc.get("no_website_bonus",         4)

        # ── Complete contact information ──────────────────────────────
        has_phone   = bool(raw.get("phone",   "").strip())
        has_address = bool(raw.get("address", "").strip())
        if has_phone and has_address:
            total += sc.get("complete_contact_bonus",   2)

        logger.debug(
            f"Score for '{raw.get('name', '?')}' ({niche}): {total} "
            f"[reviews={reviews}, rating={rating}]"
        )
        return total

    def label(self, score: int) -> str:
        """
        Return a human-readable priority label for a given score.
        Shown in the 'Lead Score' column alongside the number.
        """
        if score >= 22:
            return f"{score} ★★★ HOT"
        if score >= 15:
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
