"""
Base Scraper — shared foundation for all scraper modules.

Provides:
  • Selenium / undetected-chromedriver setup with anti-detection measures
  • Random user-agent rotation
  • Tenacity-based retry decorator
  • Common page-load and element-wait helpers
  • Context-manager interface so the browser always quits cleanly
"""

import logging
import random
import time
from abc import ABC, abstractmethod
from typing import Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
)
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

logger = logging.getLogger(__name__)

# Pool of realistic desktop user-agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",

    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",

    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",

    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.2 Safari/605.1.15",

    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]


class BaseScraper(ABC):
    """
    Abstract base class for all LeadParser scrapers.

    Subclasses must implement `scrape_niche(niche, location)` which
    returns a list of raw lead dicts.
    """

    def __init__(self, config: dict, rate_limiter, proxy_manager=None):
        self.config        = config
        self.rate_limiter  = rate_limiter
        self.proxy_manager = proxy_manager
        self.driver        = None
        self.logger        = logging.getLogger(self.__class__.__name__)
        self._max_retries  = config["scraping"].get("max_retries", 3)

    # ── Context manager ───────────────────────────────────────────────

    def __enter__(self):
        self._setup_driver()
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        """Quit the browser if it's running."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    # ── Driver setup ──────────────────────────────────────────────────

    def _setup_driver(self):
        """
        Initialise Chrome with stealth options.
        Tries undetected-chromedriver first; falls back to plain Selenium.
        """
        use_undetected = self.config["scraping"].get("use_undetected_chrome", True)
        headless       = self.config["scraping"].get("headless", True)
        user_agent     = random.choice(USER_AGENTS)

        if use_undetected:
            try:
                self.driver = self._build_undetected_driver(headless, user_agent)
                self.logger.info("Browser started (undetected-chromedriver)")
                return
            except Exception as exc:
                self.logger.warning(
                    f"undetected-chromedriver failed ({exc}); falling back to Selenium"
                )

        self.driver = self._build_selenium_driver(headless, user_agent)
        self.logger.info("Browser started (Selenium ChromeDriver)")

    def _build_undetected_driver(self, headless: bool, user_agent: str):
        import undetected_chromedriver as uc

        options = uc.ChromeOptions()
        options.add_argument(f"--user-agent={user_agent}")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        if headless:
            options.add_argument("--headless=new")

        w = self.config["scraping"].get("window_width",  1366)
        h = self.config["scraping"].get("window_height", 768)
        options.add_argument(f"--window-size={w},{h}")

        driver = uc.Chrome(options=options, version_main=145)
        self._apply_stealth_js(driver)
        return driver

    def _build_selenium_driver(self, headless: bool, user_agent: str):
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.chrome.service import Service

        options = Options()
        options.add_argument(f"--user-agent={user_agent}")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        if headless:
            options.add_argument("--headless=new")

        w = self.config["scraping"].get("window_width",  1366)
        h = self.config["scraping"].get("window_height", 768)
        options.add_argument(f"--window-size={w},{h}")

        service = Service(ChromeDriverManager().install())
        driver  = webdriver.Chrome(service=service, options=options)
        self._apply_stealth_js(driver)
        return driver

    @staticmethod
    def _apply_stealth_js(driver):
        """Patch navigator.webdriver so automated Chrome looks like a real user."""
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                """
            },
        )

    # ── Abstract interface ────────────────────────────────────────────

    @abstractmethod
    def scrape_niche(self, niche: str, location: dict) -> list[dict]:
        """
        Scrape businesses for *niche* in *location*.
        Must return a list of raw lead dicts.
        """

    # ── Shared helper methods ─────────────────────────────────────────

    def _wait_for(self, css_selector: str, timeout: int = 10) -> Optional[object]:
        """Wait for an element and return it, or None on timeout."""
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, css_selector))
            )
        except TimeoutException:
            return None

    def _find(self, *selectors: str) -> Optional[object]:
        """
        Try each CSS selector in order; return the first matching element
        or None if none match.
        """
        for sel in selectors:
            try:
                return self.driver.find_element(By.CSS_SELECTOR, sel)
            except NoSuchElementException:
                continue
        return None

    def _find_xpath(self, *xpaths: str) -> Optional[object]:
        """Try each XPath expression and return the first match or None."""
        for xpath in xpaths:
            try:
                return self.driver.find_element(By.XPATH, xpath)
            except NoSuchElementException:
                continue
        return None

    def _text(self, *selectors: str, attribute: str = None) -> str:
        """
        Return the text (or attribute value) of the first matching element,
        or empty string.
        """
        elem = self._find(*selectors)
        if elem is None:
            return ""
        if attribute:
            return (elem.get_attribute(attribute) or "").strip()
        return (elem.text or "").strip()

    def _text_xpath(self, *xpaths: str) -> str:
        """XPath version of _text()."""
        elem = self._find_xpath(*xpaths)
        if elem is None:
            return ""
        return (elem.text or "").strip()

    def _scroll_element(self, element, pixels: int = 800):
        """Scroll a specific DOM element (e.g. the results feed) by *pixels*."""
        self.driver.execute_script(
            "arguments[0].scrollBy(0, arguments[1]);", element, pixels
        )

    def _safe_get(self, url: str) -> bool:
        """
        Navigate to *url*.  Returns True on success, False on error.
        Applies the configured rate-limit delay before navigating.
        """
        self.rate_limiter.wait()
        try:
            self.driver.get(url)
            return True
        except WebDriverException as exc:
            self.logger.error(f"Failed to navigate to {url}: {exc}")
            return False

    def _human_scroll(self, element=None, total_pixels: int = 1200):
        """
        Scroll in small random increments to mimic human behaviour.
        Scrolls the page (or a specific element) by *total_pixels*.
        """
        scrolled = 0
        while scrolled < total_pixels:
            step = random.randint(200, 400)
            if element:
                self.driver.execute_script(
                    "arguments[0].scrollBy(0, arguments[1]);", element, step
                )
            else:
                self.driver.execute_script(f"window.scrollBy(0, {step});")
            scrolled += step
            time.sleep(random.uniform(0.1, 0.4))
