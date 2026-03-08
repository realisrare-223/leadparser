"""
Proxy Manager — fetches and rotates free public proxies.

Two categories of sources:
  HTML-table sources  — legacy; scrape a <table> from a web page.
  API / raw-text sources — faster; return plain text or JSON directly.

Tests each proxy before adding it to the pool so only working
proxies are ever used.  All services used are completely FREE.
"""

import json
import requests
import logging
import random
import time
from bs4 import BeautifulSoup
from typing import Optional

logger = logging.getLogger(__name__)

# ── HTML-table sources (legacy) ───────────────────────────────────────────────
_HTML_TABLE_SOURCES = {
    "free-proxy-list": "https://free-proxy-list.net/",
    "sslproxies":      "https://www.sslproxies.org/",
    "us-proxy":        "https://www.us-proxy.org/",
}

# ── API / raw-text sources (faster, more proxies) ─────────────────────────────
_PLAIN_TEXT_SOURCES = {
    # Returns one "ip:port" per line — hundreds of proxies
    "proxyscrape": (
        "https://api.proxyscrape.com/v2/"
        "?request=getproxies&protocol=http&timeout=5000"
        "&country=all&ssl=all&anonymity=all"
    ),
    # Raw GitHub proxy lists (community-maintained, updated frequently)
    "github-theSpeedX": (
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"
    ),
    "github-clarketm": (
        "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-status.txt"
    ),
    "github-shiftyTR": (
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt"
    ),
}

# ── JSON API sources ──────────────────────────────────────────────────────────
_JSON_SOURCES = {
    # Geonode JSON API — returns proxies with country metadata
    "geonode": (
        "https://proxylist.geonode.com/api/proxy-list"
        "?limit=500&page=1&sort_by=lastChecked&sort_type=desc&protocols=http"
    ),
}

# Unified lookup: all known source keys → (type, url)
PROXY_SOURCES = {
    **{k: ("html", v) for k, v in _HTML_TABLE_SOURCES.items()},
    **{k: ("txt",  v) for k, v in _PLAIN_TEXT_SOURCES.items()},
    **{k: ("json", v) for k, v in _JSON_SOURCES.items()},
}

# URL used to verify proxy connectivity
TEST_URL = "https://httpbin.org/ip"


class ProxyManager:
    """
    Maintains a pool of free, tested HTTP/HTTPS proxies.

    When enabled (proxies.enabled: true in config.yaml) the
    scraper (Playwright, XHR, or Selenium) calls get_proxy() to
    obtain the next proxy in rotation.

    Supports three source types:
      html  — scrape <table> from free-proxy-list.net etc.
      txt   — fetch plain ip:port list (proxyscrape, GitHub lists)
      json  — fetch Geonode JSON API (with country metadata)
    """

    def __init__(self, config: dict):
        self.enabled: bool = config["proxies"].get("enabled", False)
        self.sources: list = config["proxies"].get("sources", ["free-proxy-list"])
        self.test_before_use: bool = config["proxies"].get("test_before_use", True)
        self.test_timeout: int = config["proxies"].get("test_timeout", 5)
        self.rotate_every: int = config["proxies"].get("rotate_every", 10)

        self._pool: list[str] = []
        self._index: int = 0
        self._request_count: int = 0

    # ── Public API ───────────────────────────────────────────────────

    def refresh(self) -> int:
        """
        Fetch proxies from all configured sources and test them.
        Automatically selects the right fetch method per source type.
        Returns the number of working proxies added to the pool.
        """
        if not self.enabled:
            return 0

        raw: list[str] = []
        for source_key in self.sources:
            entry = PROXY_SOURCES.get(source_key)
            if not entry:
                logger.warning(f"Unknown proxy source: {source_key}")
                continue
            source_type, url = entry
            if source_type == "html":
                raw.extend(self._fetch_from_source(url))
            elif source_type == "txt":
                raw.extend(self._fetch_plain_text(url))
            elif source_type == "json":
                raw.extend(self._fetch_geonode_json(url))

        logger.info(f"Fetched {len(raw)} raw proxies; testing…")

        if self.test_before_use:
            working = [p for p in raw if self._test_proxy(p)]
        else:
            working = raw

        self._pool = working
        self._index = 0
        logger.info(f"Proxy pool ready: {len(self._pool)} working proxies")
        return len(self._pool)

    def get_proxy(self) -> Optional[dict]:
        """
        Return the next proxy dict suitable for use with requests or Selenium.
        Returns None when proxies are disabled or pool is empty.

        Example return value:
            {"http": "http://1.2.3.4:8080", "https": "http://1.2.3.4:8080"}
        """
        if not self.enabled or not self._pool:
            return None

        self._request_count += 1

        # Auto-rotate on schedule
        if self._request_count % self.rotate_every == 0:
            self._index = (self._index + 1) % len(self._pool)
            logger.debug(f"Rotated to proxy index {self._index}")

        proxy_str = self._pool[self._index]
        return {"http": f"http://{proxy_str}", "https": f"http://{proxy_str}"}

    def mark_bad(self, proxy: dict) -> None:
        """Remove a proxy that triggered a block or error from the pool."""
        if not proxy:
            return
        proxy_str = proxy.get("http", "").replace("http://", "")
        if proxy_str in self._pool:
            self._pool.remove(proxy_str)
            logger.info(f"Removed bad proxy {proxy_str}; pool size: {len(self._pool)}")
        if not self._pool:
            logger.warning("Proxy pool is now empty — consider refreshing or disabling proxies")

    # ── Internal helpers ─────────────────────────────────────────────

    def _fetch_from_source(self, url: str) -> list[str]:
        """Scrape a proxy list HTML page and return 'ip:port' strings."""
        proxies = []
        try:
            resp = requests.get(url, timeout=10, headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            })
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            # All three sources use the same <table> structure
            table = soup.find("table", {"id": "proxylisttable"}) or \
                    soup.find("table", class_="table")
            if not table:
                logger.warning(f"Could not parse proxy table from {url}")
                return proxies

            rows = table.find("tbody").find_all("tr")
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 2:
                    ip   = cols[0].text.strip()
                    port = cols[1].text.strip()
                    if ip and port.isdigit():
                        proxies.append(f"{ip}:{port}")

            logger.info(f"Parsed {len(proxies)} proxies from {url}")
        except Exception as exc:
            logger.error(f"Failed to fetch proxies from {url}: {exc}")
        return proxies

    def _fetch_plain_text(self, url: str) -> list[str]:
        """
        Fetch a plain-text proxy list where each line is 'ip:port'.
        Used for proxyscrape, GitHub raw lists, etc.
        """
        proxies = []
        try:
            resp = requests.get(url, timeout=15, headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            })
            resp.raise_for_status()
            for line in resp.text.splitlines():
                # Strip status info from clarketm format: "1.2.3.4:8080 US+"
                parts = line.strip().split()
                if parts:
                    candidate = parts[0]
                    # Validate ip:port format
                    if ":" in candidate:
                        ip, port = candidate.rsplit(":", 1)
                        if ip and port.isdigit():
                            proxies.append(candidate)
            logger.info(f"Parsed {len(proxies)} proxies from {url[:60]}")
        except Exception as exc:
            logger.error(f"Failed to fetch plain-text proxies from {url[:60]}: {exc}")
        return proxies

    def _fetch_geonode_json(self, url: str) -> list[str]:
        """
        Fetch proxies from the Geonode JSON API.
        Response: {"data": [{"ip": "...", "port": "...", ...}, ...]}
        """
        proxies = []
        try:
            resp = requests.get(url, timeout=15, headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            })
            resp.raise_for_status()
            data = resp.json()
            for entry in data.get("data", []):
                ip   = entry.get("ip", "").strip()
                port = str(entry.get("port", "")).strip()
                if ip and port.isdigit():
                    proxies.append(f"{ip}:{port}")
            logger.info(f"Parsed {len(proxies)} proxies from Geonode API")
        except Exception as exc:
            logger.error(f"Failed to fetch Geonode proxies: {exc}")
        return proxies

    def _test_proxy(self, proxy_str: str) -> bool:
        """Return True if the proxy successfully reaches the test URL."""
        proxy = {"http": f"http://{proxy_str}", "https": f"http://{proxy_str}"}
        try:
            resp = requests.get(TEST_URL, proxies=proxy,
                                timeout=self.test_timeout)
            return resp.status_code == 200
        except Exception:
            return False
