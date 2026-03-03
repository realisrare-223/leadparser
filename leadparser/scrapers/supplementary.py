"""
Supplementary Scraper — orchestrates all secondary data-source lookups.

When a lead is missing a phone number (or social profiles), this
module runs each enabled supplementary scraper in sequence until the
data is found, then returns the enriched lead dict.

Sources tried in order (all FREE, no API keys):
  1. Yelp               — phone + social profiles
  2. Yellow Pages       — phone
  3. White Pages        — phone
  4. BBB                — phone
  5. 411.com            — phone

Social media discovery (Facebook, Instagram) via:
  • Yelp business pages
  • Google search (site:facebook.com "business name" "city")
  • Direct Facebook search URL

NOTE: Facebook and LinkedIn scraping is disabled by default because
their bot-detection is aggressive.  Enable under supplementary_scrapers
in config.yaml only if you can accept occasional blocks.
"""

import logging
import re
import time
import random

import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

from .yelp_scraper import YelpScraper
from .yellow_pages import YellowPagesScraper

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_PHONE_RE = re.compile(r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}")
_FB_URL_RE = re.compile(r"https?://(?:www\.)?facebook\.com/[^\s\"'<>]+")
_IG_URL_RE = re.compile(r"https?://(?:www\.)?instagram\.com/[^\s\"'<>]+")


class SupplementaryScraper:
    """
    Enriches a lead dict by finding missing phone numbers and social
    media profiles using multiple free public data sources.
    """

    def __init__(self, config: dict, rate_limiter):
        self.config       = config
        self.rate_limiter = rate_limiter
        self.ss_config    = config.get("supplementary_scrapers", {})
        self.session      = requests.Session()
        self.session.headers.update(_HEADERS)

        # Lazy-initialised sub-scrapers
        self._yelp = None
        self._yp   = None

    # ── Public API ────────────────────────────────────────────────────

    def enrich(self, lead: dict) -> dict:
        """
        Attempt to fill in missing phone number and social profiles for *lead*.
        Modifies *lead* in place and returns it.
        """
        name  = lead.get("name", "")
        city  = lead.get("city",  "") or self.config["location"].get("city",  "")
        state = lead.get("state", "") or self.config["location"].get("state", "")

        if not name:
            return lead

        # ── Phone number enrichment ────────────────────────────────────
        if not lead.get("phone"):
            lead["phone"] = self._find_phone(name, city, state)
            if lead.get("phone"):
                # Note which source found the number
                lead["source"] = lead.get("source", "Google Maps") + " + Supplementary"
                # Clear the "Phone Needed" note if we found one
                notes = lead.get("notes", "")
                lead["notes"] = notes.replace(
                    "Phone Number Needed - Manual Research Required", ""
                ).strip(" |")
            else:
                # Ensure the flag is set for manual follow-up
                if "Phone Number Needed" not in lead.get("notes", ""):
                    lead["notes"] = (
                        (lead.get("notes", "") + " | Phone Number Needed - Manual Research Required")
                        .strip(" |")
                    )

        # ── Social media discovery ──────────────────────────────────────
        if not lead.get("facebook") or not lead.get("instagram"):
            socials = self._find_social_profiles(name, city, state)
            if not lead.get("facebook") and socials.get("facebook"):
                lead["facebook"] = socials["facebook"]
            if not lead.get("instagram") and socials.get("instagram"):
                lead["instagram"] = socials["instagram"]

        return lead

    def enrich_batch(self, leads: list[dict]) -> list[dict]:
        """Enrich an entire list of leads. Logs progress."""
        missing_phone = [l for l in leads if not l.get("phone")]
        logger.info(
            f"Enriching {len(missing_phone)} leads missing phone numbers "
            f"(out of {len(leads)} total)"
        )
        for i, lead in enumerate(missing_phone, start=1):
            logger.info(f"  Enriching [{i}/{len(missing_phone)}]: {lead.get('name', '?')}")
            self.enrich(lead)
        return leads

    # ── Phone lookup waterfall ────────────────────────────────────────

    def _find_phone(self, name: str, city: str, state: str) -> str:
        """Try each enabled source in order until a phone is found."""

        # 1. Yelp
        if self.ss_config.get("yelp", True):
            phone = self._yelp_scraper().find_phone(name, city, state)
            if phone:
                logger.debug(f"Phone found on Yelp for '{name}': {phone}")
                return phone

        # 2. Yellow Pages
        if self.ss_config.get("yellow_pages", True):
            phone = self._yp_scraper().find_phone(name, city, state)
            if phone:
                logger.debug(f"Phone found on Yellow Pages for '{name}': {phone}")
                return phone

        # 3. BBB
        if self.ss_config.get("bbb", True):
            phone = self._yp_scraper().find_phone_bbb(name, city, state)
            if phone:
                logger.debug(f"Phone found on BBB for '{name}': {phone}")
                return phone

        # 4. 411.com
        phone = self._search_411(name, city, state)
        if phone:
            logger.debug(f"Phone found on 411.com for '{name}': {phone}")
            return phone

        logger.info(f"No phone found through any source for '{name}'")
        return ""

    def _search_411(self, name: str, city: str, state: str) -> str:
        """Search 411.com (free public directory)."""
        url = (
            f"https://www.411.com/business/{quote_plus(name.replace(' ', '-'))}/"
            f"{quote_plus(city.replace(' ', '-'))}-{state.upper()}/"
        )
        try:
            self.rate_limiter.wait()
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            for sel in ('[class*="phone"]', 'a[href^="tel:"]', '[itemprop="telephone"]'):
                elems = soup.select(sel)
                for elem in elems:
                    href  = elem.get("href", "")
                    if href.startswith("tel:"):
                        return href.replace("tel:", "").strip()
                    match = _PHONE_RE.search(elem.get_text())
                    if match:
                        return match.group(0).strip()
        except Exception as exc:
            logger.debug(f"411.com lookup failed for '{name}': {exc}")
        return ""

    # ── Social media discovery ────────────────────────────────────────

    def _find_social_profiles(self, name: str, city: str, state: str) -> dict:
        """
        Attempt to find Facebook and Instagram profiles.
        Uses Yelp (which often links to social profiles) and a
        DuckDuckGo HTML search as fallback.
        """
        profiles = {"facebook": "", "instagram": ""}

        # Try Yelp first
        if self.ss_config.get("yelp", True):
            yelp_profiles = self._yelp_scraper().find_social_profiles(name, city, state)
            profiles["facebook"]  = yelp_profiles.get("facebook",  "")
            profiles["instagram"] = yelp_profiles.get("instagram", "")

        if profiles["facebook"] and profiles["instagram"]:
            return profiles

        # Fallback: DuckDuckGo HTML search (free, no API)
        ddg_profiles = self._ddg_social_search(name, city, state)
        if not profiles["facebook"]:
            profiles["facebook"]  = ddg_profiles.get("facebook",  "")
        if not profiles["instagram"]:
            profiles["instagram"] = ddg_profiles.get("instagram", "")

        return profiles

    def _ddg_social_search(self, name: str, city: str, state: str) -> dict:
        """
        Run a DuckDuckGo HTML search to find Facebook/Instagram profiles.
        DuckDuckGo does not require an API key and works without JavaScript.
        """
        profiles = {"facebook": "", "instagram": ""}
        query    = f'"{name}" "{city}" site:facebook.com OR site:instagram.com'
        url      = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

        try:
            time.sleep(random.uniform(2, 4))
            resp = self.session.get(url, timeout=12)
            if resp.status_code != 200:
                return profiles

            # Look for facebook/instagram links in the results
            fb_matches = _FB_URL_RE.findall(resp.text)
            ig_matches = _IG_URL_RE.findall(resp.text)

            if fb_matches:
                # Filter out generic facebook.com links
                for fb in fb_matches:
                    if "/pg/" not in fb and "/search/" not in fb and len(fb) > 25:
                        profiles["facebook"] = fb.rstrip("/")
                        break

            if ig_matches:
                for ig in ig_matches:
                    if "/explore/" not in ig and len(ig) > 25:
                        profiles["instagram"] = ig.rstrip("/")
                        break

        except Exception as exc:
            logger.debug(f"DuckDuckGo social search failed for '{name}': {exc}")

        return profiles

    # ── Lazy sub-scraper initialisation ──────────────────────────────

    def _yelp_scraper(self) -> YelpScraper:
        if self._yelp is None:
            self._yelp = YelpScraper(self.config, self.rate_limiter)
        return self._yelp

    def _yp_scraper(self) -> YellowPagesScraper:
        if self._yp is None:
            self._yp = YellowPagesScraper(self.config, self.rate_limiter)
        return self._yp
