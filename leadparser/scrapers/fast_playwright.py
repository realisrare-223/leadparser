"""
Optimized Playwright Scraper - Maximum speed without sacrificing reliability
"""

import asyncio
import logging
import random
from typing import Callable, Optional
from urllib.parse import quote_plus

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


class FastPlaywrightScraper:
    """
    Highly optimized Playwright scraper.
    
    Optimizations:
    - Single browser, multiple contexts (4x faster than multiple browsers)
    - Aggressive timeouts (faster failures)
    - Parallel extraction with semaphore
    - Skip non-essential waits
    """
    
    def __init__(self, config: dict, rate_limiter, proxy_manager=None):
        self.config = config
        self.rate_limiter = rate_limiter
        self.proxy_manager = proxy_manager
        self.logger = logging.getLogger(self.__class__.__name__)
        self._n_workers = config["scraping"].get("workers", 4)
        
    def scrape_niche(self, niche: str, location: dict, on_progress: Callable = None) -> list[dict]:
        """Scrape niche with optimized Playwright."""
        return asyncio.run(self._scrape_async(niche, location, on_progress))
    
    async def _scrape_async(
        self,
        niche: str,
        location: dict,
        on_progress: Optional[Callable],
    ) -> list[dict]:
        """Fast async scraping."""
        from scrapers.google_maps import NICHE_EXPANSIONS
        
        headless = self.config["scraping"].get("headless", True)
        
        async with async_playwright() as pw:
            # Launch single browser
            browser = await pw.chromium.launch(
                headless=headless,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-web-security",
                    "--disable-features=IsolateOrigins,site-per-process",
                ]
            )
            
            try:
                # Phase A: Collect URLs quickly
                all_urls = await self._collect_urls_fast(
                    browser, niche, location
                )
                
                if not all_urls:
                    return []
                
                # Phase B: Parallel extraction
                leads = await self._extract_parallel(
                    browser, all_urls, niche, on_progress
                )
                
                return leads
                
            finally:
                await browser.close()
    
    async def _collect_urls_fast(
        self,
        browser,
        niche: str,
        location: dict,
    ) -> list[str]:
        """Fast URL collection with minimal overhead."""
        from scrapers.google_maps import NICHE_EXPANSIONS
        
        max_results = self.config["scraping"].get("max_results_per_niche", 60)
        city_state = f"{location['city']}, {location['state']}"
        expansions = NICHE_EXPANSIONS.get(niche.lower().strip(), [])
        search_terms = [niche] + expansions[:5]  # Limit expansion terms
        
        all_urls = []
        seen = set()
        
        # Single context for URL collection
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        
        page = await context.new_page()
        
        try:
            for term in search_terms:
                if len(all_urls) >= max_results:
                    break
                
                query = f"{term} in {city_state}"
                url = f"https://www.google.com/maps/search/{quote_plus(query)}"
                
                try:
                    # Fast navigation
                    await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    await asyncio.sleep(1)  # Short wait for JS
                    
                    # Extract URLs quickly
                    new_urls = await self._scroll_and_collect_fast(page, max_results - len(all_urls), seen)
                    all_urls.extend(new_urls)
                    
                    self.logger.debug(f"'{term}': +{len(new_urls)} URLs")
                    
                except Exception as exc:
                    self.logger.debug(f"Term '{term}' failed: {exc}")
                    continue
        
        finally:
            await context.close()
        
        return all_urls[:max_results]
    
    async def _scroll_and_collect_fast(self, page, max_collect: int, seen: set) -> list[str]:
        """Fast scroll and collect."""
        urls = []
        
        for _ in range(10):  # Max 10 scrolls
            # Extract links
            links = await page.query_selector_all("a[href*='/maps/place/']")
            
            for link in links:
                try:
                    href = await link.get_attribute("href")
                    if href and "/maps/place/" in href and href not in seen:
                        seen.add(href)
                        urls.append(href)
                        if len(urls) >= max_collect:
                            return urls
                except:
                    continue
            
            # Quick scroll
            await page.evaluate("""() => {
                const feed = document.querySelector('div[role="feed"]');
                if (feed) feed.scrollBy(0, 800);
            }""")
            await asyncio.sleep(0.5)  # Short pause
        
        return urls
    
    async def _extract_parallel(
        self,
        browser,
        urls: list[str],
        niche: str,
        on_progress: Optional[Callable],
    ) -> list[dict]:
        """Extract business data in parallel."""
        sem = asyncio.Semaphore(self._n_workers)
        progress = {"done": 0, "total": len(urls)}
        
        async def extract_one(url: str) -> Optional[dict]:
            async with sem:
                lead = await self._extract_business_fast(browser, url, niche)
                
                progress["done"] += 1
                if on_progress:
                    try:
                        on_progress(progress["done"], progress["total"])
                    except:
                        pass
                
                return lead
        
        tasks = [extract_one(url) for url in urls]
        results = await asyncio.gather(*tasks)
        
        return [r for r in results if r is not None]
    
    async def _extract_business_fast(
        self,
        browser,
        url: str,
        niche: str,
    ) -> Optional[dict]:
        """Fast business extraction."""
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
        )
        
        try:
            page = await context.new_page()
            
            # Fast navigation
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=10000)
            except:
                await context.close()
                return None
            
            # Quick extract - don't wait long
            try:
                await page.wait_for_selector("h1", timeout=3000)
            except:
                pass
            
            # Extract data
            name = await self._get_text(page, "h1")
            if not name:
                await context.close()
                return None
            
            # Get phone quickly
            phone = await self._get_phone_fast(page)
            
            # Build lead
            lead = {
                "source": "Google Maps",
                "gmb_link": url,
                "niche": niche,
                "name": name,
                "phone": phone,
                "secondary_phone": "",
                "address": "",
                "city": "",
                "state": "",
                "zip": "",
                "hours": "",
                "review_count": 0,
                "rating": "",
                "website": "",
                "facebook": "",
                "instagram": "",
                "notes": "",
                "category": "",
            }
            
            await context.close()
            return lead
            
        except Exception as exc:
            await context.close()
            return None
    
    async def _get_text(self, page, selector: str) -> str:
        """Get text from selector."""
        try:
            el = await page.query_selector(selector)
            if el:
                text = await el.text_content()
                return text.strip() if text else ""
        except:
            pass
        return ""
    
    async def _get_phone_fast(self, page) -> str:
        """Fast phone extraction."""
        try:
            # Try tel: link first (fastest)
            tel_link = await page.query_selector("a[href^='tel:']")
            if tel_link:
                href = await tel_link.get_attribute("href")
                if href:
                    return href.replace("tel:", "").strip()
            
            # Try data-item-id
            phone_btn = await page.query_selector('[data-item-id*="phone:"]')
            if phone_btn:
                item_id = await phone_btn.get_attribute("data-item-id")
                if item_id:
                    return item_id.replace("phone:", "").replace("tel:", "").strip()
            
            # Try aria-label
            phone_label = await page.query_selector('[aria-label*="Phone:"]')
            if phone_label:
                label = await phone_label.get_attribute("aria-label")
                if label:
                    return label.replace("Phone:", "").strip()
                    
        except:
            pass
        
        return ""
