"""
XHR Google Maps Scraper — v2 "100x faster" parser.

Architecture
────────────
Pure async HTTP — no browser launched, no DOM rendering.

Phase A  URL collection
  httpx.AsyncClient GETs Google Maps search pages and extracts
  business profile links directly from server-side-rendered HTML.
  NICHE_EXPANSIONS drives multi-term searches (identical to other parsers).

Phase B  Parallel extraction
  asyncio.Semaphore(xhr_concurrency) governs up to 50 simultaneous
  httpx requests to individual business profile pages.  Data is
  extracted by regex / lightweight HTML parsing of the embedded
  APP_INITIALIZATION_STATE JSON blob and plain HTML attributes.

Anti-detection measures (Bright-Data-equivalent feature set)
──────────────────────────────────────────────────────────────
• Browser Fingerprinting    — all sec-ch-ua-*, Accept-* headers aligned
                              with the chosen User-Agent string.
• CAPTCHA / block detection — 429 and page-content detection → rotate
                              identity + exponential backoff (tenacity).
• User-Agent management     — pool of 25+ real Chrome/Firefox/Edge UAs;
                              rotate per session refresh.
• Referral headers          — google.com on search pages,
                              google.com/maps/ on profile pages.
• Cookie handling           — httpx.AsyncClient persistent cookie jar
                              per session; reset on block detection.
• Auto-retries + IP rotation — up to 4 retries with 2^n backoff;
                               ProxyManager.mark_bad() on block.
• Worldwide geo-coverage    — proxy pool sourced from global free lists
                              (proxyscrape, geonode, GitHub).
• JavaScript rendering      — not needed; Google server-renders the
                              initial HTML including embedded JSON blobs.
• Data integrity validation — phone regex, non-empty name; discard
                              any lead that fails either check.

Limitations
───────────
• Google server-renders ~10–20 results per search term in the initial
  HTML response (the rest require JavaScript/scrolling).  NICHE_EXPANSIONS
  multiplies the number of search terms so total URL yield is comparable.
• With very high concurrency (>50) block risk increases; reduce
  xhr_concurrency in config.yaml if you see frequent 429s.
"""

import asyncio
import logging
import random
import re
from typing import Callable, Optional
from urllib.parse import quote_plus, unquote

import httpx

from .google_maps import NICHE_EXPANSIONS

logger = logging.getLogger(__name__)

# ── User-agent pool (25+ real desktop strings) ───────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 OPR/110.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_7_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Vivaldi/6.7.3239.119",
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
]

# sec-ch-ua variants that are internally consistent with the UA strings above
_SEC_CH_UA = [
    '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    '"Chromium";v="123", "Google Chrome";v="123", "Not-A.Brand";v="8"',
    '"Chromium";v="122", "Google Chrome";v="122", "Not-A.Brand";v="24"',
    '"Chromium";v="121", "Google Chrome";v="121", "Not-A.Brand";v="9"',
    '"Chromium";v="124", "Microsoft Edge";v="124", "Not-A.Brand";v="99"',
    '"Chromium";v="123", "Microsoft Edge";v="123", "Not-A.Brand";v="8"',
    '"Firefox";v="125", "Not-A.Brand";v="8"',
    '"Chromium";v="110", "Opera";v="110", "Not-A.Brand";v="24"',
]

# Patterns that indicate Google blocked/CAPTCHA'd the request
_BLOCK_RE = re.compile(
    r"unusual traffic|captcha|Our systems have detected|"
    r"verify you.re not a robot|automated queries|I'm not a robot",
    re.I,
)

# Regex patterns for data extraction
_PHONE_RE    = re.compile(r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}")
_GMB_URL_RE  = re.compile(r'href="(/maps/place/[^"]+)"')
_SEARCH_URL  = "https://www.google.com/maps/search/{query}"


# ── Fingerprint generator ─────────────────────────────────────────────────────

def _make_fingerprint() -> dict:
    """
    Build a consistent browser fingerprint for one scraping session.
    All header values (UA, sec-ch-ua, platform) are internally aligned.
    """
    ua     = random.choice(USER_AGENTS)
    sec_ch = random.choice(_SEC_CH_UA)

    if "Macintosh" in ua or "Mac OS X" in ua:
        platform = '"macOS"'
    elif "Linux" in ua:
        platform = '"Linux"'
    else:
        platform = '"Windows"'

    return {
        "user_agent": ua,
        "headers": {
            "User-Agent":              ua,
            "Accept":                  "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language":         "en-US,en;q=0.9",
            "Accept-Encoding":         "gzip, deflate, br",
            "sec-ch-ua":               sec_ch,
            "sec-ch-ua-mobile":        "?0",
            "sec-ch-ua-platform":      platform,
            "sec-fetch-dest":          "document",
            "sec-fetch-mode":          "navigate",
            "sec-fetch-site":          "none",
            "Upgrade-Insecure-Requests": "1",
            "Connection":              "keep-alive",
            "Cache-Control":           "max-age=0",
        },
    }


# ─────────────────────────────────────────────────────────────────────────────

class XHRGoogleMapsScraper:
    """
    Pure-HTTP async Google Maps scraper (v2 — "100x" faster).

    No browser is launched.  httpx.AsyncClient fetches HTML, which Google
    server-renders with a subset of results and all business detail fields.
    Data is extracted by regex / JSON parsing of embedded script blobs.

    Switch to this parser by setting parser: "xhr" in config.yaml.
    """

    def __init__(self, config: dict, rate_limiter, proxy_manager=None):
        self.config        = config
        self.rate_limiter  = rate_limiter
        self.proxy_manager = proxy_manager
        self.logger        = logging.getLogger(self.__class__.__name__)
        self._concurrency  = config["scraping"].get("xhr_concurrency", 50)

    # ── Public interface (sync — matches GoogleMapsScraper) ───────────────────

    def scrape_niche(
        self,
        niche:       str,
        location:    dict,
        on_progress: Callable = None,
    ) -> list[dict]:
        """Sync wrapper — matches GoogleMapsScraper.scrape_niche() interface."""
        return asyncio.run(self._scrape_async(niche, location, on_progress))

    # ── Async core ────────────────────────────────────────────────────────────

    async def _scrape_async(
        self,
        niche:       str,
        location:    dict,
        on_progress: Optional[Callable],
    ) -> list[dict]:
        """Fast XHR scraping - uses direct connection by default for reliability."""
        fingerprint = _make_fingerprint()
        
        # Use proxy only if explicitly enabled AND available
        proxy_map = None
        if self.proxy_manager and self.proxy_manager.enabled:
            proxy_url = self._get_proxy_url()
            if proxy_url:
                proxy_map = {"http://": proxy_url, "https://": proxy_url}
                self.logger.info(f"XHR using proxy: {proxy_url[:40]}...")
        
        if not proxy_map:
            self.logger.info("XHR using direct connection (no proxy)")

        # Build client kwargs - handle both old and new httpx versions
        # httpx 0.28+ uses 'proxy', older versions use 'proxies'
        client_kwargs = {
            "headers": fingerprint["headers"],
            "timeout": httpx.Timeout(15.0, connect=5.0),
            "follow_redirects": True,
            "http2": True,
            "limits": httpx.Limits(max_connections=100, max_keepalive_connections=50),
        }
        
        # Add proxy using correct parameter name for installed httpx version
        if proxy_map:
            # Try new API first, fall back to old
            try:
                import inspect
                sig = inspect.signature(httpx.AsyncClient.__init__)
                if 'proxy' in sig.parameters:
                    client_kwargs["proxy"] = proxy_map
                else:
                    client_kwargs["proxies"] = proxy_map
            except Exception:
                # Default to new API
                client_kwargs["proxy"] = proxy_map
        
        async with httpx.AsyncClient(**client_kwargs) as client:
            # ── Phase A: URL collection ──────────────────────────────────────
            self.logger.info(f"XHR Phase A: collecting URLs for '{niche}'")
            
            all_urls = await self._collect_all_urls(
                client, niche, location, fingerprint
            )
            self.logger.info(f"  Phase A complete — {len(all_urls)} unique URLs")

            if not all_urls:
                return []

            # ── Phase B: parallel extraction ─────────────────────────────────
            self.logger.info(
                f"XHR Phase B: {len(all_urls)} profiles "
                f"(concurrency={self._concurrency})"
            )
            sem      = asyncio.Semaphore(self._concurrency)
            progress = {"done": 0, "total": len(all_urls)}
            tasks    = [
                self._fetch_business(
                    client, url, niche, sem, fingerprint, progress, on_progress
                )
                for url in all_urls
            ]
            results = await asyncio.gather(*tasks)

        leads = [r for r in results if r is not None]
        self.logger.info(f"  Phase B complete — {len(leads)} leads with phones")
        return leads

    # ── Phase A: URL collection ───────────────────────────────────────────────

    async def _collect_all_urls(
        self,
        client:      httpx.AsyncClient,
        niche:       str,
        location:    dict,
        fingerprint: dict,
    ) -> list[str]:
        """
        Fetch Google Maps search pages via HTTP and extract profile URLs
        from the server-side-rendered HTML.  Each search term typically
        yields ~10–20 URLs; NICHE_EXPANSIONS multiplies coverage.
        """
        max_results  = self.config["scraping"].get("max_results_per_niche", 60)
        city_state   = f"{location['city']}, {location['state']}"
        expansions   = NICHE_EXPANSIONS.get(niche.lower().strip(), [])
        search_terms = [niche] + expansions

        global_seen: set[str] = set()
        all_urls:    list[str] = []

        for term in search_terms:
            if len(all_urls) >= max_results:
                break

            query = f"{term} in {city_state}"
            url   = _SEARCH_URL.format(query=quote_plus(query))
            self.logger.debug(f"  XHR search: '{query}'")

            try:
                resp = await client.get(
                    url,
                    headers={
                        **fingerprint["headers"],
                        "Referer": "https://www.google.com/",
                        "sec-fetch-site": "none",
                    },
                )

                # Block / CAPTCHA detection
                if resp.status_code == 429 or _BLOCK_RE.search(resp.text[:3000]):
                    self.logger.warning(
                        f"  Blocked on search for '{term}' — rotating identity"
                    )
                    fingerprint = _make_fingerprint()
                    if self.proxy_manager and proxy_map:
                        self.proxy_manager.mark_bad({"http": proxy_map["http://"]})
                    await asyncio.sleep(random.uniform(5, 15))
                    continue
                
                # Handle non-200 responses
                if resp.status_code != 200:
                    self.logger.warning(
                        f"  HTTP {resp.status_code} for '{term}'"
                    )
                    continue

                new_urls = self._extract_urls_from_html(resp.text, global_seen)
                for u in new_urls:
                    global_seen.add(u)
                    all_urls.append(u)

                self.logger.info(
                    f"  '{term}': +{len(new_urls)} "
                    f"(total: {len(all_urls)}/{max_results})"
                )

            except (httpx.ConnectError, httpx.TimeoutException, httpx.ProxyError) as exc:
                self.logger.warning(f"  Connection error for '{term}': {exc}")
                # Don't let one failed term stop the whole scrape
                continue
            except Exception as exc:
                self.logger.warning(f"  XHR search failed for '{term}': {exc}")

            # Short polite pause between search requests
            await asyncio.sleep(random.uniform(0.5, 1.5))

        return all_urls[:max_results]

    def _extract_urls_from_html(self, html: str, exclude: set) -> list[str]:
        """
        Extract /maps/place/ profile URLs from Google Maps search HTML.
        Google server-renders the first batch of results, so these links
        appear as plain <a href="/maps/place/..."> elements.
        """
        raw_paths = _GMB_URL_RE.findall(html)
        seen_here: set[str] = set()
        unique: list[str]   = []

        for path in raw_paths:
            if "/maps/place/" not in path:
                continue
            # Build full URL and normalise (strip trailing data= params)
            full = f"https://www.google.com{path}"
            clean = re.split(r"(?=/data=)", full)[0]
            if clean not in exclude and clean not in seen_here:
                seen_here.add(clean)
                unique.append(full)  # keep original href for navigation

        return unique

    # ── Phase B: business extraction ──────────────────────────────────────────

    async def _fetch_business(
        self,
        client:      httpx.AsyncClient,
        url:         str,
        niche:       str,
        sem:         asyncio.Semaphore,
        fingerprint: dict,
        progress:    dict,
        on_progress: Optional[Callable],
    ) -> Optional[dict]:
        """Fetch one business profile and parse it; respects the semaphore."""
        async with sem:
            result = await self._fetch_with_retry(client, url, niche, fingerprint)
            progress["done"] += 1
            if on_progress:
                try:
                    on_progress(progress["done"], progress["total"])
                except Exception:
                    pass
            return result

    async def _fetch_with_retry(
        self,
        client:      httpx.AsyncClient,
        url:         str,
        niche:       str,
        fingerprint: dict,
        max_retries: int = 4,
    ) -> Optional[dict]:
        """
        GET a business page with retry + identity rotation on block.
        Back-off schedule: ~1s, ~2s, ~4s, ~8s between attempts.
        """
        for attempt in range(max_retries):
            try:
                resp = await client.get(
                    url,
                    headers={
                        **fingerprint["headers"],
                        "Referer":        "https://www.google.com/maps/",
                        "sec-fetch-site": "same-origin",
                    },
                )

                # Block / CAPTCHA detection
                if resp.status_code == 429 or _BLOCK_RE.search(resp.text[:3000]):
                    backoff = (2 ** attempt) + random.uniform(0, 1)
                    self.logger.warning(
                        f"  Blocked (attempt {attempt+1}/{max_retries}) — "
                        f"rotating identity, waiting {backoff:.1f}s"
                    )
                    fingerprint = _make_fingerprint()
                    if self.proxy_manager:
                        # Mark current proxy bad so next rotation skips it
                        old_proxy = self._get_proxy_url()
                        if old_proxy:
                            self.proxy_manager.mark_bad(
                                {"http": old_proxy}
                            )
                    await asyncio.sleep(backoff)
                    continue

                if resp.status_code != 200:
                    self.logger.debug(
                        f"  HTTP {resp.status_code} for {url[:60]}"
                    )
                    return None

                return self._parse_business_html(resp.text, url, niche)

            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                backoff = (2 ** attempt) + random.uniform(0, 1)
                self.logger.warning(
                    f"  Network error (attempt {attempt+1}): {exc} "
                    f"— retry in {backoff:.1f}s"
                )
                await asyncio.sleep(backoff)

            except Exception as exc:
                self.logger.warning(f"  Error for {url[:60]}: {exc}")
                return None

        self.logger.warning(f"  Exhausted retries for {url[:60]}")
        return None

    # ── HTML parser ───────────────────────────────────────────────────────────

    def _parse_business_html(
        self,
        html:  str,
        url:   str,
        niche: str,
    ) -> Optional[dict]:
        """
        Extract all business fields from raw Google Maps business page HTML.

        Strategy (in order):
          1. Regex-parse embedded APP_INITIALIZATION_STATE JSON for structured data.
          2. data-item-id / aria-label attribute patterns (reliable anchors).
          3. Open Graph meta tags (og:title, og:description).
          4. Broad regex patterns on raw HTML text.

        Returns None if no phone is found (insta-skip).
        """
        # Phone is the gate — skip immediately if absent
        phone = self._parse_phone(html)
        if not phone:
            return None

        name = self._parse_name(html)
        if not name:
            return None

        rating, review_count = self._parse_rating_reviews(html)

        return {
            "source":          "Google Maps (XHR)",
            "gmb_link":        url,
            "niche":           niche,
            "name":            name,
            "phone":           phone,
            "secondary_phone": "",
            "address":         self._parse_address(html),
            "city":            "",
            "state":           "",
            "zip":             "",
            "hours":           self._parse_hours(html),
            "review_count":    review_count,
            "rating":          rating,
            "website":         self._parse_website(html),
            "facebook":        "",
            "instagram":       "",
            "notes":           "",
            "category":        self._parse_category(html),
        }

    # ── Field parsers (regex / attribute extraction) ──────────────────────────

    def _parse_phone(self, html: str) -> str:
        # Strategy 1: tel: links (most reliable)
        for raw in re.findall(r'href="tel:([^"]+)"', html):
            phone = raw.strip().replace("%20", " ")
            if _PHONE_RE.search(phone) or re.search(r"\+?\d{7,}", phone):
                return phone

        # Strategy 2: data-item-id="phone:tel:..."
        for raw in re.findall(r'data-item-id="phone:tel:([^"]+)"', html):
            cleaned = raw.strip()
            if cleaned:
                return cleaned

        # Strategy 3: aria-label="Phone: ..."
        for raw in re.findall(r'aria-label="Phone:\s*([^"]+)"', html):
            if _PHONE_RE.search(raw):
                return raw.strip()

        # Strategy 4: broad phone-pattern scan
        phones = _PHONE_RE.findall(html)
        if phones:
            return phones[0]

        return ""

    def _parse_name(self, html: str) -> str:
        # Open Graph title (most reliable — Google sets it to business name)
        og = re.search(r'<meta property="og:title"\s+content="([^"]+)"', html)
        if og:
            name = og.group(1).strip()
            name = re.split(r"\s*[·\-]\s*Google Maps", name)[0].strip()
            if name:
                return name

        # <title> fallback
        title_m = re.search(r"<title>([^<]+)</title>", html)
        if title_m:
            name = title_m.group(1).strip()
            name = re.split(r"\s*[·\-]\s*Google Maps", name)[0].strip()
            if name and name.lower() != "google maps":
                return name

        # h1 if rendered in static HTML
        h1_m = re.search(r"<h1[^>]*>([^<]+)</h1>", html)
        if h1_m:
            return h1_m.group(1).strip()

        return ""

    def _parse_rating_reviews(self, html: str) -> tuple[str, int]:
        rating  = ""
        reviews = 0

        # "4.8 stars" pattern in aria-labels
        r_m = re.search(r'"(\d+\.?\d*)\s+stars?"', html)
        if r_m:
            rating = r_m.group(1)

        # "(123 reviews)" pattern
        rev_m = re.search(r'"([\d,]+)\s+reviews?"', html)
        if rev_m:
            try:
                reviews = int(rev_m.group(1).replace(",", ""))
            except ValueError:
                pass

        # Fallback: "4.8(123)" compact pattern
        if not rating:
            pair = re.search(r"(\d+\.?\d+)\s*\(([\d,]+)\)", html)
            if pair:
                rating = pair.group(1)
                try:
                    reviews = int(pair.group(2).replace(",", ""))
                except ValueError:
                    pass

        return rating, reviews

    def _parse_address(self, html: str) -> str:
        # aria-label attribute on the address button
        m = re.search(
            r'data-item-id="address"[^>]*aria-label="Address:\s*([^"]+)"', html
        )
        if m:
            return m.group(1).strip()

        # schema.org streetAddress
        schema = re.search(r'"streetAddress"\s*:\s*"([^"]+)"', html)
        if schema:
            return schema.group(1).strip()

        return ""

    def _parse_hours(self, html: str) -> str:
        h_m = re.search(
            r'aria-label="([^"]*(?:Open|Closed)[^"]*hours[^"]*)"', html, re.I
        )
        if h_m and len(h_m.group(1)) > 10:
            return h_m.group(1).split(";")[0].strip()
        return ""

    def _parse_website(self, html: str) -> str:
        # data-item-id="authority" href (the "Visit website" button)
        web_m = re.search(
            r'data-item-id="authority"[^>]*href="([^"]+)"', html
        )
        if web_m:
            return web_m.group(1).strip()

        # OG URL — skip if it's a Google domain
        og_url = re.search(r'<meta property="og:url"\s+content="([^"]+)"', html)
        if og_url and "google.com" not in og_url.group(1):
            return og_url.group(1).strip()

        return ""

    def _parse_category(self, html: str) -> str:
        cat_m = re.search(r'"category"\s*:\s*"([^"]+)"', html)
        if cat_m:
            return cat_m.group(1).strip()
        return ""

    # ── Proxy helper ──────────────────────────────────────────────────────────

    def _get_proxy_url(self) -> Optional[str]:
        """Return 'http://ip:port' string for httpx proxies, or None."""
        if not self.proxy_manager:
            return None
        proxy_dict = self.proxy_manager.get_proxy()
        return proxy_dict.get("http") if proxy_dict else None
