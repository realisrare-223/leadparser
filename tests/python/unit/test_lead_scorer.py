"""
Unit tests for utils/lead_scorer.py

Tests cover all scoring branches:
  - Review count tiers (0, 1-5, 6-25, 26-100, 101-300, 301+)
  - Website presence / no-website bonus
  - Rich no-website bonus (reviews >= 100)
  - Star rating tiers (<=3.0, 3.0-3.8, 3.8-4.5, >4.5)
  - High-value niche bonus
  - Complete contact info bonus
  - label() thresholds
  - Type coercion (_int, _float)

Each test class isolates a single variable by neutralising the others:
  - website="https://x.com" → no website bonus
  - phone="", address="" → no contact bonus
  - niche="other" → no niche bonus
  - rating="4.8" → no rating bonus
  - review_count set explicitly for each tier test
"""

import pytest
from utils.lead_scorer import LeadScorer


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def scorer(sample_config):
    return LeadScorer(sample_config)


def _lead(**overrides):
    """Build a raw lead dict. Defaults produce a score of 0 aside from
    what's explicitly under test (has website, no phone, no address,
    neutral niche, non-scoring rating, 0 reviews)."""
    base = {
        "name":         "Test Business",
        "phone":        "",
        "address":      "",
        "review_count": 0,
        "rating":       "4.8",    # >4.5 → no rating bonus
        "website":      "https://example.com",   # has website → no website bonus
        "niche":        "other",  # not a high-value niche
    }
    base.update(overrides)
    return base


# ── Review count tiers ────────────────────────────────────────────────────────
# To isolate review tiers we keep: has-website, no-phone, no-address,
# neutral niche, and neutral rating.

class TestReviewCountScoring:
    def test_zero_reviews(self, scorer, sample_config):
        # no_reviews_score = 10
        lead = _lead(review_count=0)
        assert scorer.score(lead, "other", sample_config) == 10

    def test_one_review(self, scorer, sample_config):
        # very_few_reviews = 2
        lead = _lead(review_count=1)
        assert scorer.score(lead, "other", sample_config) == 2

    def test_five_reviews_boundary(self, scorer, sample_config):
        # review_count=5 hits very_few (<=5) = 2
        lead = _lead(review_count=5)
        assert scorer.score(lead, "other", sample_config) == 2

    def test_six_reviews(self, scorer, sample_config):
        # few_reviews = 5
        lead = _lead(review_count=6)
        assert scorer.score(lead, "other", sample_config) == 5

    def test_twenty_five_reviews_boundary(self, scorer, sample_config):
        # review_count=25 hits few_reviews (<=25) = 5
        lead = _lead(review_count=25)
        assert scorer.score(lead, "other", sample_config) == 5

    def test_twenty_six_reviews(self, scorer, sample_config):
        # moderate_reviews = 10
        lead = _lead(review_count=26)
        assert scorer.score(lead, "other", sample_config) == 10

    def test_hundred_reviews_boundary(self, scorer, sample_config):
        # review_count=100 hits moderate (<=100) = 10
        lead = _lead(review_count=100)
        assert scorer.score(lead, "other", sample_config) == 10

    def test_hundred_one_reviews(self, scorer, sample_config):
        # many_reviews = 13
        lead = _lead(review_count=101)
        assert scorer.score(lead, "other", sample_config) == 13

    def test_three_hundred_reviews_boundary(self, scorer, sample_config):
        # many_reviews = 13
        lead = _lead(review_count=300)
        assert scorer.score(lead, "other", sample_config) == 13

    def test_three_hundred_one_reviews(self, scorer, sample_config):
        # lots_of_reviews = 15
        lead = _lead(review_count=301)
        assert scorer.score(lead, "other", sample_config) == 15

    def test_five_hundred_reviews(self, scorer, sample_config):
        # lots_of_reviews = 15
        lead = _lead(review_count=500)
        assert scorer.score(lead, "other", sample_config) == 15


# ── No-website bonus ──────────────────────────────────────────────────────────
# Isolate website bonus: use review_count=10 (few_reviews=5),
# neutral rating, neutral niche, no contact.

class TestWebsiteBonus:
    def test_no_website_gives_base_bonus(self, scorer, sample_config):
        # few_reviews(5) + no_website_base_bonus(3)
        lead = _lead(review_count=10, website="")
        assert scorer.score(lead, "other", sample_config) == 5 + 3

    def test_has_website_no_bonus(self, scorer, sample_config):
        # few_reviews(5) only
        lead = _lead(review_count=10, website="https://example.com")
        assert scorer.score(lead, "other", sample_config) == 5

    def test_rich_no_website_bonus_applied_at_reviews_100(self, scorer, sample_config):
        # reviews=100 → moderate(10) + no_website_base(3) + rich_no_website(7)
        lead = _lead(review_count=100, website="")
        assert scorer.score(lead, "other", sample_config) == 10 + 3 + 7

    def test_rich_no_website_bonus_applied_at_reviews_101(self, scorer, sample_config):
        # reviews=101 → many(13) + no_website_base(3) + rich_no_website(7)
        lead = _lead(review_count=101, website="")
        assert scorer.score(lead, "other", sample_config) == 13 + 3 + 7

    def test_rich_no_website_bonus_not_applied_when_has_website(self, scorer, sample_config):
        # reviews=200 with website → many(13) only
        lead = _lead(review_count=200, website="https://example.com")
        assert scorer.score(lead, "other", sample_config) == 13

    def test_rich_no_website_not_applied_at_reviews_99(self, scorer, sample_config):
        # reviews=99 → moderate(10) + no_website_base(3), NO rich bonus
        lead = _lead(review_count=99, website="")
        assert scorer.score(lead, "other", sample_config) == 10 + 3


# ── Star rating tiers ─────────────────────────────────────────────────────────
# Isolate rating: no_reviews=0 → 10pts, has-website, neutral niche, no contact.
# So base = 10 (no_reviews_score) and rating bonus adds on top.

class TestRatingScoring:
    def test_very_low_rating_le_3(self, scorer, sample_config):
        # no_reviews(10) + very_low_rating(5)
        lead = _lead(review_count=0, rating="2.5")
        assert scorer.score(lead, "other", sample_config) == 10 + 5

    def test_rating_exactly_3(self, scorer, sample_config):
        # <=3.0 → very_low_rating(5)
        lead = _lead(review_count=0, rating="3.0")
        assert scorer.score(lead, "other", sample_config) == 10 + 5

    def test_low_rating_above_3(self, scorer, sample_config):
        # 3.0 < 3.5 <= 3.8 → low_rating(3)
        lead = _lead(review_count=0, rating="3.5")
        assert scorer.score(lead, "other", sample_config) == 10 + 3

    def test_rating_exactly_3_8(self, scorer, sample_config):
        # 3.0 < 3.8 <= 3.8 → low_rating(3)
        lead = _lead(review_count=0, rating="3.8")
        assert scorer.score(lead, "other", sample_config) == 10 + 3

    def test_medium_rating(self, scorer, sample_config):
        # 3.8 < 4.0 <= 4.5 → medium_rating(1)
        lead = _lead(review_count=0, rating="4.0")
        assert scorer.score(lead, "other", sample_config) == 10 + 1

    def test_rating_exactly_4_5(self, scorer, sample_config):
        # 3.8 < 4.5 <= 4.5 → medium_rating(1)
        lead = _lead(review_count=0, rating="4.5")
        assert scorer.score(lead, "other", sample_config) == 10 + 1

    def test_high_rating_no_bonus(self, scorer, sample_config):
        # 4.6 > 4.5 → 0 bonus
        lead = _lead(review_count=0, rating="4.6")
        assert scorer.score(lead, "other", sample_config) == 10

    def test_zero_rating_no_bonus(self, scorer, sample_config):
        # rating=0 → condition `0 < rating` is False → no bonus
        lead = _lead(review_count=0, rating="0")
        assert scorer.score(lead, "other", sample_config) == 10


# ── High-value niche bonus ────────────────────────────────────────────────────
# Isolate niche: has-website, no-phone, no-address, 0 reviews (→10), neutral rating.

class TestNicheBonus:
    def test_plumbers_is_high_value(self, scorer, sample_config):
        lead = _lead(review_count=0)
        assert scorer.score(lead, "plumbers", sample_config) == 10 + 5

    def test_electricians_is_high_value(self, scorer, sample_config):
        lead = _lead(review_count=0)
        assert scorer.score(lead, "electricians", sample_config) == 10 + 5

    def test_hvac_is_high_value(self, scorer, sample_config):
        lead = _lead(review_count=0)
        assert scorer.score(lead, "hvac", sample_config) == 10 + 5

    def test_roofers_is_high_value(self, scorer, sample_config):
        lead = _lead(review_count=0)
        assert scorer.score(lead, "roofers", sample_config) == 10 + 5

    def test_restaurants_not_high_value(self, scorer, sample_config):
        lead = _lead(review_count=0)
        assert scorer.score(lead, "restaurants", sample_config) == 10

    def test_case_insensitive_niche(self, scorer, sample_config):
        lead = _lead(review_count=0)
        assert scorer.score(lead, "PLUMBERS", sample_config) == 10 + 5


# ── Complete contact info bonus ────────────────────────────────────────────────
# Isolate contact: has-website, 0 reviews (→10), neutral rating, neutral niche.

class TestContactBonus:
    def test_phone_and_address_gives_bonus(self, scorer, sample_config):
        lead = _lead(review_count=0, phone="(214) 555-0100", address="123 Main St")
        assert scorer.score(lead, "other", sample_config) == 10 + 2

    def test_missing_phone_no_bonus(self, scorer, sample_config):
        lead = _lead(review_count=0, phone="", address="123 Main St")
        assert scorer.score(lead, "other", sample_config) == 10

    def test_missing_address_no_bonus(self, scorer, sample_config):
        lead = _lead(review_count=0, phone="(214) 555-0100", address="")
        assert scorer.score(lead, "other", sample_config) == 10


# ── Additive scoring (all bonuses combined) ───────────────────────────────────

class TestAdditive:
    def test_hot_lead_all_bonuses(self, scorer, sample_config):
        """A rich business with no website, bad rating, high-value niche, complete contact."""
        lead = {
            "name":         "Busy Plumber",
            "phone":        "(214) 555-0100",
            "address":      "123 Main St",
            "review_count": 200,   # many_reviews = 13
            "rating":       "2.5", # very_low_rating = 5
            "website":      "",    # base_bonus=3 + rich_bonus=7
        }
        score = scorer.score(lead, "plumbers", sample_config)
        expected = 13 + 3 + 7 + 5 + 5 + 2  # many + no_web_base + rich + rating + niche + contact
        assert score == expected


# ── Type coercion edge cases ──────────────────────────────────────────────────

class TestTypeCoercion:
    def test_string_review_count(self, scorer, sample_config):
        lead = _lead(review_count="50")
        # "50" → 50 → moderate_reviews = 10
        assert scorer.score(lead, "other", sample_config) == 10

    def test_none_review_count_defaults_to_zero(self, scorer, sample_config):
        lead = _lead(review_count=None)
        # None → 0 → no_reviews_score = 10
        assert scorer.score(lead, "other", sample_config) == 10

    def test_invalid_rating_defaults_to_zero(self, scorer, sample_config):
        lead = _lead(review_count=0, rating="N/A")
        # N/A → 0.0 → 0 < 0.0 is False → no rating bonus; 0 reviews = 10
        assert scorer.score(lead, "other", sample_config) == 10

    def test_none_rating_defaults_to_zero(self, scorer, sample_config):
        lead = _lead(review_count=0, rating=None)
        # None → 0.0 → no bonus; 0 reviews = 10
        assert scorer.score(lead, "other", sample_config) == 10


# ── label() ──────────────────────────────────────────────────────────────────

class TestLabel:
    def test_hot_label_at_threshold(self, scorer):
        assert "HOT" in scorer.label(22)

    def test_hot_label_above_threshold(self, scorer):
        assert "HOT" in scorer.label(35)

    def test_warm_label_at_threshold(self, scorer):
        assert "WARM" in scorer.label(15)

    def test_warm_label_at_upper_bound(self, scorer):
        assert "WARM" in scorer.label(21)

    def test_medium_label_at_threshold(self, scorer):
        assert "MEDIUM" in scorer.label(8)

    def test_medium_label_at_upper_bound(self, scorer):
        assert "MEDIUM" in scorer.label(14)

    def test_low_label_at_zero(self, scorer):
        assert "LOW" in scorer.label(0)

    def test_low_label_just_below_medium(self, scorer):
        assert "LOW" in scorer.label(7)

    def test_label_includes_numeric_score(self, scorer):
        assert "25" in scorer.label(25)
