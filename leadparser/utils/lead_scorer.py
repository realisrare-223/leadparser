"""
Lead Scorer — calculates a numeric priority score for each lead.

Higher score = higher priority for outreach.

Scoring philosophy:
  ├─ Review count (0–15 pts, no upper penalty)
  │    More reviews = more established = richer client = better lead.
  │    0–5 reviews = unproven / possibly dead.
  │    300+ reviews = proven high-revenue business.
  ├─ No website (+3 base, +7 extra if reviews ≥ 100)
  │    A 500-review business with no website is the BEST lead:
  │    they clearly have money, clearly need digital help.
  ├─ Star rating (0–5 pts)  — struggling business = more open to pitch
  ├─ High-value niche (+5 pts bonus)
  └─ Complete contact info (+2 pts bonus)
"""

import logging

logger = logging.getLogger(__name__)


class LeadScorer:
    """Stateless scorer — create once, call score() for every lead."""

    def __init__(self, config: dict):
        self.scoring_cfg     = config.get("scoring", {})
        self.high_val_niches = [
            n.lower() for n in config.get("high_value_niches", [])
        ]

    # ── Public API ───────────────────────────────────────────────────

    def score(self, raw: dict, niche: str, config: dict) -> int:
        total = 0
        sc    = self.scoring_cfg

        # ── Review count (0–15 pts, monotonically increasing) ────────
        # More reviews = proven customer base = richer client.
        # No upper penalty — a 1 000-review restaurant with no website
        # is a far better lead than a 3-review shop.
        reviews = self._int(raw.get("review_count", 0))

        if reviews == 0:
            total += sc.get("no_reviews_score",     0)   # fake/dead/just opened
        elif reviews <= 5:
            total += sc.get("very_few_reviews",     2)   # too small / unproven
        elif reviews <= 25:
            total += sc.get("few_reviews",          5)   # emerging
        elif reviews <= 100:
            total += sc.get("moderate_reviews",    10)   # solid local business
        elif reviews <= 300:
            total += sc.get("many_reviews",        13)   # well-established
        else:
            total += sc.get("lots_of_reviews",     15)   # high-revenue, proven

        # ── No website ────────────────────────────────────────────────
        # Base bonus for any business missing a web presence.
        # Large EXTRA bonus when the business also has many reviews:
        # a 500-review restaurant with no website is wealthy + clearly
        # needs the service = easiest pitch = highest value deal.
        has_website = bool(raw.get("website", "").strip())
        if not has_website:
            total += sc.get("no_website_base_bonus",  3)
            if reviews >= 100:
                total += sc.get("rich_no_website_bonus", 7)  # ← the money shot

        # ── Star rating (0–5 pts) ─────────────────────────────────────
        # Low rating = business is struggling online = receptive to help.
        rating = self._float(raw.get("rating", 0.0))
        if 0 < rating <= 3.0:
            total += sc.get("very_low_rating_bonus",  5)
        elif 3.0 < rating <= 3.8:
            total += sc.get("low_rating_bonus",       3)
        elif 3.8 < rating <= 4.5:
            total += sc.get("medium_rating_bonus",    1)
        # 4.5+ → 0 extra pts (already doing well online)

        # ── High-value niche ─────────────────────────────────────────
        if niche.lower() in self.high_val_niches:
            total += sc.get("high_value_niche_bonus", 5)

        # ── Complete contact info ─────────────────────────────────────
        has_phone   = bool(raw.get("phone",   "").strip())
        has_address = bool(raw.get("address", "").strip())
        if has_phone and has_address:
            total += sc.get("complete_contact_bonus", 2)

        logger.debug(
            f"Score for '{raw.get('name', '?')}' ({niche}): {total} "
            f"[reviews={reviews}, rating={rating}, website={'yes' if has_website else 'no'}]"
        )
        return total

    def label(self, score: int) -> str:
        if score >= 22:
            return f"{score} ★★★ HOT"
        if score >= 15:
            return f"{score} ★★  WARM"
        if score >= 8:
            return f"{score} ★   MEDIUM"
        return f"{score}     LOW"

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
