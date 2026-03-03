"""
Yellow Pages Scraper — supplementary phone number lookup.

Searches yellowpages.com and whitepages.com (both free, public)
when a business is missing a phone number.  No API key required.
"""

import logging
import re
import time
import random

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,*/*;q=0.8"
    ),
}

_PHONE_RE = re.compile(
    r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}"
)


class YellowPagesScraper:
    """
    Supplementary scraper for Yellow Pages and White Pages.
    Call find_phone() with a business name + location.
    """

    YP_SEARCH  = "https://www.yellowpages.com/search?search_terms={name}&geo_location_terms={loc}"
    WP_SEARCH  = "https://www.whitepages.com/business/{name}/{city}-{state}"
    BBB_SEARCH = "https://www.bbb.org/search?find_text={name}&find_loc={loc}"

    def __init__(self, config: dict, rate_limiter):
        self.config       = config
        self.rate_limiter = rate_limiter
        self.session      = requests.Session()
        self.session.headers.update(_HEADERS)

    # ── Public API ────────────────────────────────────────────────────

    def find_phone(self, business_name: str, city: str, state: str) -> str:
        """
        Try Yellow Pages then White Pages.
        Returns first phone number found, or empty string.
        """
        phone = self._search_yellow_pages(business_name, city, state)
        if phone:
            return phone

        phone = self._search_white_pages(business_name, city, state)
        return phone

    def find_phone_bbb(self, business_name: str, city: str, state: str) -> str:
        """Better Business Bureau supplementary lookup."""
        return self._search_bbb(business_name, city, state)

    # ── Yellow Pages ──────────────────────────────────────────────────

    def _search_yellow_pages(self, name: str, city: str, state: str) -> str:
        from urllib.parse import quote_plus

        loc = f"{city}+{state}"
        url = self.YP_SEARCH.format(
            name=quote_plus(name),
            loc=quote_plus(loc),
        )

        try:
            self.rate_limiter.wait()
            resp = self.session.get(url, timeout=12)
            resp.raise_for_status()
        except Exception as exc:
            logger.debug(f"Yellow Pages request failed: {exc}")
            return ""

        soup = BeautifulSoup(resp.text, "lxml")

        # YP result cards have class "result" or "organic"
        # Phone numbers appear in <div class="phones"> or <a class="tel">
        for sel in (
            "div.phones.result-phones",
            "div.phones",
            "a.tel",
            '[class*="phone"]',
            "p.adr",
        ):
            elems = soup.select(sel)
            for elem in elems:
                text  = elem.get_text(" ", strip=True)
                match = _PHONE_RE.search(text)
                if match:
                    return match.group(0).strip()

        # Broader scan
        first_result = soup.select_one("div.result, article.result, div.organic")
        if first_result:
            text  = first_result.get_text(" ", strip=True)
            match = _PHONE_RE.search(text)
            if match:
                return match.group(0).strip()

        return ""

    # ── White Pages ───────────────────────────────────────────────────

    def _search_white_pages(self, name: str, city: str, state: str) -> str:
        from urllib.parse import quote_plus

        url = self.WP_SEARCH.format(
            name=quote_plus(name.replace(" ", "-")),
            city=quote_plus(city.replace(" ", "-")),
            state=state.upper(),
        )

        try:
            time.sleep(random.uniform(1.5, 3.0))
            resp = self.session.get(url, timeout=12)
            resp.raise_for_status()
        except Exception as exc:
            logger.debug(f"White Pages request failed: {exc}")
            return ""

        soup  = BeautifulSoup(resp.text, "lxml")
        # White Pages often shows phone in a <span> near the listing
        for sel in (
            "span.number",
            '[class*="phone"]',
            '[itemprop="telephone"]',
        ):
            elems = soup.select(sel)
            for elem in elems:
                text  = elem.get_text(strip=True)
                match = _PHONE_RE.search(text)
                if match:
                    return match.group(0).strip()

        # Scan the first 3000 characters of text for a phone number
        text  = soup.get_text(" ", strip=True)[:3000]
        match = _PHONE_RE.search(text)
        if match:
            return match.group(0).strip()

        return ""

    # ── Better Business Bureau ────────────────────────────────────────

    def _search_bbb(self, name: str, city: str, state: str) -> str:
        from urllib.parse import quote_plus

        loc = f"{city}, {state}"
        url = self.BBB_SEARCH.format(
            name=quote_plus(name),
            loc=quote_plus(loc),
        )

        try:
            time.sleep(random.uniform(1.5, 3.0))
            resp = self.session.get(url, timeout=12)
            resp.raise_for_status()
        except Exception as exc:
            logger.debug(f"BBB request failed: {exc}")
            return ""

        soup = BeautifulSoup(resp.text, "lxml")

        for sel in (
            '[class*="Phone"]',
            '[itemprop="telephone"]',
            'a[href^="tel:"]',
        ):
            elems = soup.select(sel)
            for elem in elems:
                href  = elem.get("href", "")
                if href.startswith("tel:"):
                    return href.replace("tel:", "").strip()
                text  = elem.get_text(strip=True)
                match = _PHONE_RE.search(text)
                if match:
                    return match.group(0).strip()

        return ""
