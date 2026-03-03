"""
Yelp Scraper — supplementary phone number lookup.

Used ONLY when a business scraped from Google Maps is missing a
phone number.  Searches Yelp by business name + city and extracts
the phone from the first matching result.

All access is via free public web scraping — no API key required.
Yelp's free API tier only allows 5,000 calls/day and requires
registration, so we use direct HTML scraping to stay 100% free.
"""

import logging
import re
import time
import random

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Realistic headers to avoid simple bot blocks
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/webp,*/*;q=0.8"
    ),
}

_PHONE_RE = re.compile(
    r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}"
)


class YelpScraper:
    """
    Looks up a single business on Yelp and returns its phone number.
    Instantiate once and call find_phone() for each lead that needs it.
    """

    SEARCH_URL = "https://www.yelp.com/search?find_desc={name}&find_loc={loc}"
    SESSION_PAUSE = (1.5, 3.5)   # random delay range between requests

    def __init__(self, config: dict, rate_limiter):
        self.config       = config
        self.rate_limiter = rate_limiter
        self.session      = requests.Session()
        self.session.headers.update(_HEADERS)

    # ── Public API ────────────────────────────────────────────────────

    def find_phone(self, business_name: str, city: str, state: str) -> str:
        """
        Search Yelp for *business_name* in *city, state*.
        Returns a phone number string or empty string if not found.
        """
        from urllib.parse import quote_plus

        loc       = f"{city}, {state}"
        search_url = self.SEARCH_URL.format(
            name=quote_plus(business_name),
            loc=quote_plus(loc),
        )

        try:
            self.rate_limiter.wait()
            resp = self.session.get(search_url, timeout=12)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning(f"Yelp search request failed for '{business_name}': {exc}")
            return ""

        # Find the first business result link that looks like a match
        detail_url = self._find_best_match_url(resp.text, business_name)
        if not detail_url:
            logger.debug(f"No Yelp match found for '{business_name}'")
            return ""

        # Fetch the business detail page and extract the phone
        return self._extract_phone_from_detail(detail_url, business_name)

    def find_social_profiles(self, business_name: str, city: str, state: str) -> dict:
        """
        Attempt to find Facebook/Instagram links from the Yelp business page.
        Returns dict with keys: facebook, instagram (empty string if not found).
        """
        from urllib.parse import quote_plus

        loc        = f"{city}, {state}"
        search_url = self.SEARCH_URL.format(
            name=quote_plus(business_name),
            loc=quote_plus(loc),
        )

        profiles = {"facebook": "", "instagram": ""}

        try:
            self.rate_limiter.wait()
            resp = self.session.get(search_url, timeout=12)
            resp.raise_for_status()
        except Exception:
            return profiles

        detail_url = self._find_best_match_url(resp.text, business_name)
        if not detail_url:
            return profiles

        try:
            time.sleep(random.uniform(*self.SESSION_PAUSE))
            resp2 = self.session.get(detail_url, timeout=12)
            soup  = BeautifulSoup(resp2.text, "lxml")

            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                if "facebook.com" in href and not profiles["facebook"]:
                    profiles["facebook"] = href
                if "instagram.com" in href and not profiles["instagram"]:
                    profiles["instagram"] = href
        except Exception:
            pass

        return profiles

    # ── Private helpers ───────────────────────────────────────────────

    def _find_best_match_url(self, html: str, business_name: str) -> str:
        """
        Parse the Yelp search results page and return the URL of the
        best-matching business detail page.
        """
        soup = BeautifulSoup(html, "lxml")

        # Yelp's search result links look like /biz/business-slug-city
        # We look for links that are likely business profiles
        candidates = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/biz/" in href and not href.startswith("http"):
                # Relative URL → make absolute
                href = "https://www.yelp.com" + href.split("?")[0]
            if href.startswith("https://www.yelp.com/biz/"):
                # Avoid duplicate clicks (Yelp may repeat the same link)
                if href not in candidates:
                    candidates.append(href)

        if not candidates:
            return ""

        # Try to rank candidates by how closely the link slug matches the name
        name_slug = re.sub(r"[^a-z0-9]", "-", business_name.lower())
        for url in candidates:
            slug = url.split("/biz/")[-1].split("?")[0].lower()
            if name_slug[:10] in slug or slug[:10] in name_slug:
                return url

        # Fall back to the first result
        return candidates[0]

    def _extract_phone_from_detail(self, url: str, business_name: str) -> str:
        """Fetch a Yelp business page and extract the phone number."""
        try:
            time.sleep(random.uniform(*self.SESSION_PAUSE))
            resp = self.session.get(url, timeout=12)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning(f"Yelp detail page fetch failed ({url}): {exc}")
            return ""

        soup = BeautifulSoup(resp.text, "lxml")

        # Yelp typically puts the phone in a <p> with class containing "biz-phone"
        # or inside a <div> with a telephone-icon section.
        # CSS classes change, so we use multiple strategies.

        # Strategy 1: look for tel: links
        tel_links = soup.find_all("a", href=re.compile(r"^tel:"))
        for link in tel_links:
            phone_str = link["href"].replace("tel:", "").strip()
            if phone_str:
                return phone_str

        # Strategy 2: text pattern matching in common Yelp phone containers
        for sel in (
            "p.biz-phone",
            '[class*="phone"]',
            '[data-testid="phone"]',
            "p.css-1p9ibgf",      # Yelp's CSS changes but this pattern recurs
        ):
            elems = soup.select(sel)
            for elem in elems:
                text  = elem.get_text()
                match = _PHONE_RE.search(text)
                if match:
                    return match.group(0).strip()

        # Strategy 3: scan all text for phone-like patterns near the business name
        full_text = soup.get_text(" ", strip=True)
        matches   = _PHONE_RE.findall(full_text)
        if matches:
            return matches[0].strip()

        logger.debug(f"No phone found on Yelp for '{business_name}'")
        return ""
