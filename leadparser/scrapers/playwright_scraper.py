"""
Playwright Google Maps Scraper — default parser (replaces Selenium).

Speed improvements over the Selenium version
─────────────────────────────────────────────
• Playwright async API — no per-request ChromeDriver startup overhead
• Phase B uses N_WORKERS (default 4) parallel browser contexts so 4
  business profile pages are extracted simultaneously
• playwright-stealth patches all fingerprint leaks automatically
• Leads with no phone are instantly skipped — no supplementary lookup

Anti-detection
──────────────
• playwright-stealth  — navigator.webdriver, chrome.runtime, plugins…
• Random user-agent from pool of 20+ real Chrome / Edge / Firefox strings
• Per-context unique viewport + locale + timezone
• Cookie persistence within each context across requests
• Referer: https://www.google.com/ set on every navigation
• Optional proxy per browser context (driven by ProxyManager)

Public interface
────────────────
PlaywrightGoogleMapsScraper.scrape_niche(niche, location, on_progress)
  Same signature as GoogleMapsScraper — drop-in replacement in main.py.
"""

import asyncio
import logging
import random
import re
import time
from typing import Callable, Optional
from urllib.parse import quote_plus, unquote

logger = logging.getLogger(__name__)

# playwright-stealth: newer versions use Stealth class; older used stealth_async.
# We support both and fall back gracefully if not installed.
_STEALTH_OK     = False
_stealth_obj    = None  # Stealth() instance (new API)
_stealth_legacy = None  # stealth_async function (old API)

try:
    from playwright_stealth import Stealth as _StealthClass
    _stealth_obj = _StealthClass()
    _STEALTH_OK  = True
except ImportError:
    try:
        from playwright_stealth import stealth_async as _stealth_legacy  # type: ignore
        _STEALTH_OK = True
    except ImportError:
        logger.warning(
            "playwright-stealth not installed — running without stealth patches. "
            "Install with: pip install playwright-stealth"
        )


async def _apply_stealth(page) -> None:
    """Apply playwright-stealth to a page using whichever API is available."""
    if not _STEALTH_OK:
        return
    if _stealth_obj is not None:
        await _stealth_obj.apply_stealth_async(page)
    elif _stealth_legacy is not None:
        await _stealth_legacy(page)

# Import NICHE_EXPANSIONS from the Selenium scraper — no duplication
from .google_maps import NICHE_EXPANSIONS

# ── User-agent pool (20+ real desktop strings) ───────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
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
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_7_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
]

TIMEZONES = [
    "America/New_York", "America/Chicago", "America/Denver",
    "America/Los_Angeles", "America/Phoenix", "America/Detroit",
    "America/Toronto", "America/Vancouver", "America/Edmonton",
    "America/Calgary", "America/Montreal", "America/Boston",
    "America/Atlanta", "America/Dallas", "America/Houston",
    "America/Miami", "America/Denver", "America/Seattle",
    # Note: America/Seattle is mapped to America/Los_Angeles in _get_timezone()
]

# Valid IANA timezone IDs (Seattle uses Los Angeles)
_IANA_TIMEZONE_MAP = {
    "America/Seattle": "America/Los_Angeles",
}


def _get_timezone() -> str:
    """Return a valid IANA timezone ID."""
    tz = random.choice(TIMEZONES)
    # Map invalid/legacy IDs to valid IANA IDs
    return _IANA_TIMEZONE_MAP.get(tz, tz)

_BASE_URL = "https://www.google.com/maps/search/{query}"

# Phone pattern for button-text fallback extraction
_PHONE_RE = re.compile(r"\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}")


# ─────────────────────────────────────────────────────────────────────────────

class PlaywrightGoogleMapsScraper:
    """
    Async Playwright-based Google Maps scraper.

    Replaces GoogleMapsScraper as the default parser.  Four parallel
    browser contexts extract business data simultaneously in Phase B,
    delivering roughly 4× throughput vs. the single-browser Selenium version.
    """

    def __init__(self, config: dict, rate_limiter, proxy_manager=None):
        self.config        = config
        self.rate_limiter  = rate_limiter
        self.proxy_manager = proxy_manager
        self.logger        = logging.getLogger(self.__class__.__name__)
        self._n_workers    = config["scraping"].get("workers", 4)

    # ── Public interface (sync — matches GoogleMapsScraper) ───────────────────

    def scrape_niche(
        self,
        niche:       str,
        location:    dict,
        on_progress: Callable = None,
    ) -> list[dict]:
        """
        Scrape Google Maps for *niche* in *location* and return all leads.

        Sync wrapper around the async implementation; safe to call from
        ordinary (non-async) code in main.py.
        """
        return asyncio.run(self._scrape_async(niche, location, on_progress))

    # ── Async core ────────────────────────────────────────────────────────────

    async def _scrape_async(
        self,
        niche:       str,
        location:    dict,
        on_progress: Optional[Callable],
    ) -> list[dict]:
        from playwright.async_api import async_playwright

        headless = self.config["scraping"].get("headless", True)

        launch_kwargs: dict = {
            "headless": headless,
            # Proxy is applied per-context, not at browser level, so a dead
            # proxy only kills one context and we can fall back to direct.
            "args": ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        }

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(**launch_kwargs)
            try:
                # ── Phase A: one context, sequential scroll, collect URLs ──────
                self.logger.info(f"Playwright Phase A: collecting URLs for '{niche}'")
                all_urls = await self._collect_all_urls(browser, niche, location)
                self.logger.info(f"  Phase A complete — {len(all_urls)} unique URLs")

                if not all_urls:
                    return []

                # ── Phase B: N workers extract in parallel ────────────────────
                n        = min(self._n_workers, len(all_urls))
                chunks   = _split_chunks(all_urls, n)
                self.logger.info(
                    f"Playwright Phase B: {len(all_urls)} profiles "
                    f"across {n} parallel worker(s)"
                )

                # Shared progress counter (updated by all workers)
                progress = {"done": 0, "total": len(all_urls)}

                contexts = [await self._new_context(browser) for _ in chunks]
                try:
                    batch_results = await asyncio.gather(*[
                        self._extract_chunk(ctx, chunk, niche, on_progress, progress)
                        for ctx, chunk in zip(contexts, chunks)
                    ])
                finally:
                    for ctx in contexts:
                        try:
                            await ctx.close()
                        except Exception:
                            pass

                leads = [lead for batch in batch_results for lead in batch]
                self.logger.info(f"  Phase B complete — {len(leads)} leads with phones")
                return leads

            finally:
                await browser.close()

    # ── Browser context factory ───────────────────────────────────────────────

    async def _new_context(self, browser, use_proxy: bool = True):
        """Create a new browser context with a unique randomised fingerprint.

        Proxy is applied at context level (not browser level) so a dead proxy
        only affects this context and the caller can fall back to direct.
        """
        ua  = random.choice(USER_AGENTS)
        tz  = _get_timezone()
        ctx_kwargs: dict = {
            "user_agent":   ua,
            "viewport": {
                "width":  random.randint(1280, 1920),
                "height": random.randint(720,  1080),
            },
            "locale":       "en-US",
            "timezone_id":  tz,
            "extra_http_headers": {"Referer": "https://www.google.com/"},
        }
        if use_proxy and self.proxy_manager:
            proxy_dict = self.proxy_manager.get_proxy()
            if proxy_dict:
                proxy_host = proxy_dict.get("http", "").replace("http://", "")
                ctx_kwargs["proxy"] = {"server": f"http://{proxy_host}"}
        ctx = await browser.new_context(**ctx_kwargs)
        return ctx

    # ── Phase A: URL collection ───────────────────────────────────────────────

    async def _collect_all_urls(
        self,
        browser,
        niche:    str,
        location: dict,
    ) -> list[str]:
        """One context scrolls through all search terms and collects URLs."""
        max_results  = self.config["scraping"].get("max_results_per_niche", 60)
        city_state   = f"{location['city']}, {location['state']}"
        expansions   = NICHE_EXPANSIONS.get(niche.lower().strip(), [])
        search_terms = [niche] + expansions

        global_seen: set[str] = set()
        all_urls:    list[str] = []

        # Start with a proxied context; fall back to direct after repeated resets.
        use_proxy   = True
        ctx  = await self._new_context(browser, use_proxy=use_proxy)
        page = await ctx.new_page()
        await _apply_stealth(page)
        consecutive_resets = 0
        _RESET_THRESHOLD   = 3  # switch to direct connection after this many resets

        try:
            for term in search_terms:
                remaining = max_results - len(all_urls)
                if remaining <= 0:
                    break

                query = f"{term} in {city_state}"
                url   = _BASE_URL.format(query=quote_plus(query))
                self.logger.info(f"  Searching: '{query}'")

                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                    await page.wait_for_timeout(2_000)
                    consecutive_resets = 0  # successful load resets the counter
                except Exception as exc:
                    err_str = str(exc)
                    self.logger.warning(f"  Could not load '{term}': {exc}")

                    # Detect dead-proxy symptoms and fall back to direct connection
                    if use_proxy and any(
                        marker in err_str
                        for marker in ("ERR_CONNECTION_RESET", "ERR_EMPTY_RESPONSE",
                                       "ERR_TUNNEL_CONNECTION_FAILED",
                                       "ERR_PROXY_CONNECTION_FAILED")
                    ):
                        consecutive_resets += 1
                        if consecutive_resets >= _RESET_THRESHOLD:
                            self.logger.warning(
                                f"  {consecutive_resets} consecutive proxy failures — "
                                "switching to direct connection"
                            )
                            await ctx.close()
                            use_proxy = False
                            ctx  = await self._new_context(browser, use_proxy=False)
                            page = await ctx.new_page()
                            await _apply_stealth(page)
                            consecutive_resets = 0
                            # Retry the current term with the new context
                            try:
                                await page.goto(url, wait_until="domcontentloaded",
                                                timeout=30_000)
                                await page.wait_for_timeout(2_000)
                            except Exception as exc2:
                                self.logger.warning(
                                    f"  Direct connection also failed for '{term}': {exc2}"
                                )
                                continue
                    else:
                        continue

                new_urls = await self._scroll_and_collect(page, remaining, global_seen)
                for u in new_urls:
                    global_seen.add(u)
                    all_urls.append(u)

                self.logger.info(
                    f"  '{term}': +{len(new_urls)} (total: {len(all_urls)}/{max_results})"
                )
                if len(all_urls) >= max_results:
                    break
        finally:
            await ctx.close()

        return all_urls

    async def _scroll_and_collect(
        self,
        page,
        max_collect: int,
        exclude:     set,
    ) -> list[str]:
        """Scroll the results sidebar and collect new business profile URLs."""
        pause   = self.config["scraping"].get("scroll_pause_time", 1.0)
        max_att = self.config["scraping"].get("max_scroll_attempts", 20)

        seen  = set(exclude)
        urls  = []
        no_new = 0

        # Wait for the results feed to appear
        try:
            await page.wait_for_selector('div[role="feed"]', timeout=10_000)
        except Exception:
            self.logger.warning("  Results feed not found — possible CAPTCHA")
            return []

        for _ in range(max_att):
            links = await page.query_selector_all("a.hfpxzc")
            prev  = len(urls)

            for link in links:
                try:
                    href = await link.get_attribute("href") or ""
                    if "/maps/place/" in href and href not in seen:
                        seen.add(href)
                        urls.append(href)
                except Exception:
                    continue

            if len(urls) == prev:
                no_new += 1
            else:
                no_new = 0

            if no_new >= 3 or len(urls) >= max_collect:
                break

            # Check end-of-results marker
            end_reached = await page.evaluate("""
                () => {
                    for (const el of document.querySelectorAll('p, span')) {
                        const t = el.textContent;
                        if (t.includes('end of the list') ||
                            t.includes('No more results')) return true;
                    }
                    return false;
                }
            """)
            if end_reached:
                self.logger.info("  Reached end of results")
                break

            # Scroll the feed panel
            await page.evaluate("""
                () => {
                    const feed = document.querySelector('div[role="feed"]');
                    if (feed) feed.scrollBy(0, 900);
                }
            """)
            await page.wait_for_timeout(
                int((pause + random.uniform(0, 0.5)) * 1_000)
            )

        return urls[:max_collect]

    # ── Phase B: parallel extraction ──────────────────────────────────────────

    async def _extract_chunk(
        self,
        ctx,
        urls:          list[str],
        niche:         str,
        on_progress:   Optional[Callable],
        progress:      dict,
    ) -> list[dict]:
        """Extract business data from a list of URLs using one browser context."""
        leads = []
        page  = await ctx.new_page()
        await _apply_stealth(page)

        for url in urls:
            try:
                lead = await self._extract_business(page, url, niche)
                if lead:
                    leads.append(lead)
            except Exception as exc:
                self.logger.warning(f"  Skipping {url[:60]}: {exc}")

            progress["done"] += 1
            if on_progress:
                try:
                    on_progress(progress["done"], progress["total"])
                except Exception:
                    pass

            # Respect the configured rate limit between business pages
            self.rate_limiter.wait()

        await page.close()
        return leads

    async def _extract_business(
        self,
        page,
        url:   str,
        niche: str,
    ) -> Optional[dict]:
        """Navigate to a business profile URL and extract all data fields."""
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        except Exception:
            return None

        # Wait for the name heading — confirms the detail panel loaded
        try:
            await page.wait_for_selector("h1", timeout=6_000)
        except Exception:
            return None

        name = await self._pw_text(page, "h1.DUwDvf", "h1")
        if not name:
            return None

        # Extract phone — insta-skip if not found (no supplementary lookup)
        phone = await self._extract_phone_pw(page)
        if not phone:
            self.logger.debug(f"  No phone on profile — skipping: {url[:60]}")
            return None

        return {
            "source":          "Google Maps",
            "gmb_link":        url,
            "niche":           niche,
            "name":            name,
            "phone":           phone,
            "secondary_phone": "",
            "address":         await self._extract_address_pw(page),
            "city":            "",
            "state":           "",
            "zip":             "",
            "hours":           await self._extract_hours_pw(page),
            "review_count":    await self._extract_review_count_pw(page),
            "rating":          await self._extract_rating_pw(page),
            "website":         await self._extract_website_pw(page),
            "facebook":        "",
            "instagram":       "",
            "notes":           "",
            "category":        await self._extract_category_pw(page),
        }

    # ── Playwright field extractors ───────────────────────────────────────────

    async def _pw_text(self, page, *selectors: str) -> str:
        """Return inner text of first matching CSS selector, or ''."""
        for sel in selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    txt = (await el.inner_text() or "").strip()
                    if txt:
                        return txt
            except Exception:
                continue
        return ""

    async def _extract_phone_pw(self, page) -> str:
        # Wait up to 6s for the phone element to render (loads after name)
        for xpath in (
            '//button[starts-with(@data-item-id,"phone:")]',
            '//a[starts-with(@data-item-id,"phone:")]',
            '//button[starts-with(@aria-label,"Phone:")]',
        ):
            try:
                await page.wait_for_selector(f"xpath={xpath}", timeout=6_000)
                break
            except Exception:
                pass

        # Approach 1: data-item-id="phone:tel:+1XXXXXXXXXX"
        for xpath in (
            '//button[starts-with(@data-item-id,"phone:")]',
            '//a[starts-with(@data-item-id,"phone:")]',
        ):
            el = await page.query_selector(f"xpath={xpath}")
            if el:
                item_id = (await el.get_attribute("data-item-id")) or ""
                phone   = item_id.replace("phone:", "").replace("tel:", "").strip()
                if phone:
                    return phone

        # Approach 2: aria-label="Phone: ..."
        for xpath in (
            '//button[starts-with(@aria-label,"Phone:")]',
            '//div[starts-with(@aria-label,"Phone:")]',
        ):
            el = await page.query_selector(f"xpath={xpath}")
            if el:
                label = (await el.get_attribute("aria-label")) or ""
                phone = label.replace("Phone:", "").strip()
                if phone:
                    return phone

        # Approach 3: regex scan of all button texts
        buttons = await page.query_selector_all("button")
        for btn in buttons:
            try:
                txt = (await btn.inner_text()) or ""
                m   = _PHONE_RE.search(txt)
                if m:
                    return m.group(0).strip()
            except Exception:
                continue

        return ""

    async def _extract_address_pw(self, page) -> str:
        for xpath in (
            '//button[@data-item-id="address"]',
            '//div[@data-item-id="address"]',
        ):
            el = await page.query_selector(f"xpath={xpath}")
            if el:
                child = await el.query_selector("div.fontBodyMedium")
                if child:
                    txt = (await child.inner_text() or "").strip()
                    if txt:
                        return txt
                txt = (await el.inner_text() or "").strip()
                if txt:
                    return txt

        for xpath in (
            '//button[starts-with(@aria-label,"Address:")]',
            '//div[starts-with(@aria-label,"Address:")]',
        ):
            el = await page.query_selector(f"xpath={xpath}")
            if el:
                label = (await el.get_attribute("aria-label")) or ""
                addr  = label.replace("Address:", "").strip()
                if addr:
                    return addr
        return ""

    async def _extract_hours_pw(self, page) -> str:
        try:
            el = await page.query_selector(
                'xpath=//button[contains(@aria-label,"hours")]'
                '|//div[contains(@aria-label,"hours")]'
            )
            if el:
                label = (await el.get_attribute("aria-label")) or ""
                if len(label) > 20:
                    return label.split(";")[0].strip()
        except Exception:
            pass
        for sel in ("div.MkV9", 'span[jstcache*="hour"]', "div.t39EBf"):
            txt = await self._pw_text(page, sel)
            if txt:
                return txt
        return ""

    async def _extract_rating_pw(self, page) -> str:
        for xpath in (
            '//span[@aria-label[contains(.,"star")]]',
            '//div[@class="F7nice"]//span[@aria-hidden="true"]',
        ):
            el = await page.query_selector(f"xpath={xpath}")
            if el:
                text  = (await el.inner_text()) or (await el.get_attribute("aria-label")) or ""
                match = re.search(r"(\d+\.?\d*)", text)
                if match:
                    return match.group(1)
        return ""

    async def _extract_review_count_pw(self, page) -> int:
        for xpath in (
            '//button[contains(@aria-label,"review")]',
            '//span[contains(@aria-label,"review")]',
        ):
            el = await page.query_selector(f"xpath={xpath}")
            if el:
                label = (await el.get_attribute("aria-label")) or (await el.inner_text()) or ""
                match = re.search(r"([\d,]+)\s+reviews?", label, re.I)
                if match:
                    return int(match.group(1).replace(",", ""))
        return 0

    async def _extract_website_pw(self, page) -> str:
        for xpath in (
            '//a[@data-item-id="authority"]',
            '//a[contains(@aria-label,"Website")]',
            '//a[contains(@aria-label,"website")]',
        ):
            el = await page.query_selector(f"xpath={xpath}")
            if el:
                href = (await el.get_attribute("href")) or ""
                if href and "google.com/url" not in href:
                    return href
                if href:
                    match = re.search(r"url=([^&]+)", href)
                    if match:
                        return unquote(match.group(1))
                    return href
        return ""

    async def _extract_category_pw(self, page) -> str:
        for sel in ("button.DkEaL", 'button[jsaction*="category"]', "span.DkEaL"):
            txt = await self._pw_text(page, sel)
            if txt:
                return txt
        return ""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _split_chunks(lst: list, n: int) -> list[list]:
    """Split *lst* into *n* roughly equal sublists."""
    if not lst or n <= 0:
        return [lst]
    k, rem = divmod(len(lst), n)
    chunks, i = [], 0
    for c in range(n):
        size = k + (1 if c < rem else 0)
        chunks.append(lst[i: i + size])
        i += size
    return [c for c in chunks if c]  # drop any empty slices
