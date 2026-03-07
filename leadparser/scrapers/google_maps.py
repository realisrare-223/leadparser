"""
Google Maps Scraper — primary lead source.

Strategy
────────
1. Navigate to https://www.google.com/maps/search/{niche}+{city}+{state}
2. Scroll the results feed to collect all business profile URLs.
3. For each URL, load the business detail panel and extract all fields.
4. Return a list of raw lead dicts.

Anti-detection measures
───────────────────────
• undetected-chromedriver (patches navigator.webdriver)
• Random user-agent rotation
• Randomised delays between every action
• Human-like incremental scrolling
• CDP stealth script injected on every new document

CSS selector robustness
───────────────────────
Google Maps changes its CSS classes frequently.  Every field uses
multiple fallback selectors (CSS + XPath + aria-label patterns) so
that if one breaks the others still work.
"""

import logging
import random
import re
import time
from urllib.parse import quote_plus

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
)

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword expansion map
# When a niche is searched, these variants are searched in order after the
# canonical term until max_results_per_niche unique listings are collected.
# This dramatically increases yield for niches where Google Maps caps results
# at ~60 per query (common in mid-size cities like Edmonton, Calgary, etc.).
# ---------------------------------------------------------------------------
NICHE_EXPANSIONS: dict[str, list[str]] = {

    # ── General / broad categories ────────────────────────────────────────────
    # These are triggered when the user selects a "General" category in the
    # dashboard (e.g. "Food (General)").  Each expansion term is a sub-niche
    # that gets its own full Google Maps search, maximising lead volume.

    "food": [
        "restaurants", "cafes", "coffee shops", "pizzerias", "bakeries",
        "bars", "fast food", "diners", "bistros", "food near me",
        "dessert shops", "catering services",
    ],
    "home services": [
        "plumbers", "electricians", "hvac contractors", "roofing contractors",
        "cleaning services", "landscaping services", "pest control", "painters",
        "tree services", "locksmiths", "moving companies", "water damage restoration",
        "pressure washing", "garage door repair", "junk removal",
    ],
    "medical": [
        "dentists", "chiropractors", "clinics", "urgent care",
        "pharmacies", "optometrists", "physical therapy",
        "massage therapy", "veterinarians", "mental health counselors",
    ],
    "beauty": [
        "hair salons", "barber shops", "nail salons", "spas",
        "massage therapy", "gyms", "yoga studios", "pet grooming",
        "tattoo parlors", "personal trainers",
    ],
    "automotive": [
        "auto repair shops", "auto detailing", "auto body shops",
        "tire shops", "car wash", "towing services",
        "auto glass repair", "car dealerships",
    ],
    "professional services": [
        "lawyers", "accountants", "real estate agents",
        "marketing agencies", "insurance agents", "financial advisors",
        "mortgage brokers", "it support", "web design", "photographers",
    ],

    # ── Food & Beverage ───────────────────────────────────────────────────────

    "restaurants": [
        "family restaurants", "local restaurants", "food near me",
        "diners", "eateries", "places to eat", "takeout restaurants",
        "outdoor seating restaurants", "sit-down restaurants",
        "neighbourhood restaurants", "bistros", "cafes",
    ],
    "food": [
        "restaurants", "diners", "eateries", "food shops", "cafes",
        "bistros", "takeout food", "local food spots", "places to eat",
    ],
    "cafes": [
        "coffee shops", "coffee near me", "local roasters", "espresso bar",
        "cafes with free wifi", "late-night cafes", "artisanal coffee",
        "tea house", "study cafes", "coffee houses", "brunch spots",
    ],
    "coffee shops": [
        "cafes", "coffee near me", "local roasters", "espresso bar",
        "artisanal coffee", "tea house", "late-night cafes", "coffee houses",
    ],
    "pizzerias": [
        "pizza delivery", "wood-fired pizza", "best pizza", "deep dish pizza",
        "gluten-free pizza", "24-hour pizza takeout", "pizza restaurants",
        "pizza near me", "Italian restaurant", "pizza shop",
    ],
    "pizza": [
        "pizzerias", "pizza delivery", "pizza restaurants", "wood-fired pizza",
        "best pizza near me", "pizza shop", "Italian restaurant",
    ],
    "bakeries": [
        "custom cakes", "local bakery", "fresh pastries", "gluten-free bakery",
        "dessert shop", "donut shop", "wedding cake baker", "vegan desserts",
        "cake shop", "pastry shop", "bread bakery",
    ],
    "dessert shops": [
        "ice cream parlor", "donut shop", "local bakery", "custom cakes",
        "vegan desserts", "gluten-free bakery", "cake shop", "sweet shop",
        "frozen yogurt", "gelato",
    ],
    "bars": [
        "sports bar", "cocktail lounge", "local pub", "dive bars",
        "craft brewery", "wine bar", "nightlife near me", "bars with live music",
        "bar and grill", "neighbourhood bar",
    ],
    "nightlife": [
        "bars near me", "sports bar", "cocktail lounge", "local pub",
        "craft brewery", "wine bar", "bars with live music", "nightclub",
        "dance club", "lounge",
    ],
    "fast food": [
        "drive-thru near me", "quick lunch spots", "burger joints",
        "taco stands", "sandwich shops", "late-night fast food",
        "takeout near me", "quick service restaurant", "food to go",
    ],

    # ── Home & Trade Services ─────────────────────────────────────────────────

    "plumbers": [
        "emergency plumber", "residential plumbing contractor", "leak repair",
        "water heater installation", "drain cleaning service", "24/7 plumbing",
        "plumbing services", "plumbing repair", "local plumbers",
        "pipe repair", "residential plumbing", "commercial plumbing",
    ],
    "plumbing": [
        "plumbers", "emergency plumber", "plumbing services", "plumbing repair",
        "drain cleaning", "pipe repair", "water heater installation",
        "local plumbing", "24/7 plumbing",
    ],
    "electricians": [
        "residential electrician", "emergency electrical repair",
        "licensed electrician", "home rewiring", "panel upgrade",
        "commercial electrician", "electrical contractors",
        "electrical services", "local electricians", "wiring services",
    ],
    "hvac contractors": [
        "AC repair near me", "furnace installation", "heating contractor",
        "duct cleaning", "emergency HVAC", "AC maintenance",
        "heating and cooling", "air conditioning repair", "HVAC services",
        "air conditioning installation", "furnace repair",
    ],
    "roofing contractors": [
        "local roofers", "roof leak repair", "roofing contractor",
        "shingle replacement", "commercial roofing", "roof inspection",
        "roofing services", "roof repair", "roofers", "residential roofing",
        "roof replacement",
    ],
    "cleaning services": [
        "maid service", "house cleaning near me", "move-out cleaning",
        "commercial janitorial services", "deep cleaning", "carpet cleaning",
        "residential cleaning", "office cleaning", "commercial cleaning",
        "janitorial services",
    ],
    "landscaping services": [
        "lawn mowing service", "landscape design", "tree removal",
        "local arborists", "hardscaping contractor", "seasonal yard cleanup",
        "lawn care", "landscapers", "yard maintenance", "garden services",
        "snow removal",
    ],
    "pest control": [
        "exterminator near me", "bed bug removal", "rodent control",
        "termite inspection", "eco-friendly pest control", "bug control",
        "pest management", "insect control", "local exterminators",
        "wildlife removal",
    ],
    "painters": [
        "painting contractors", "house painters", "interior painters",
        "exterior painting", "commercial painters", "local painters",
        "residential painters", "painting services",
    ],
    "tree services": [
        "tree removal", "tree trimming", "arborist", "tree cutting",
        "stump removal", "tree care", "tree pruning", "local arborists",
        "emergency tree removal",
    ],
    "water damage restoration": [
        "flood restoration", "water damage repair", "mold remediation",
        "water damage cleanup", "emergency restoration", "flood cleanup",
        "basement flooding repair",
    ],
    "moving companies": [
        "movers", "local movers", "residential moving", "commercial moving",
        "moving services", "furniture movers", "long distance movers",
        "moving and storage", "packing services",
    ],
    "locksmiths": [
        "locksmith services", "emergency locksmith", "lock and key",
        "car locksmith", "residential locksmith", "local locksmiths",
        "lock repair", "key cutting", "24 hour locksmith",
    ],
    "towing services": [
        "tow truck", "roadside assistance", "car towing", "vehicle recovery",
        "emergency towing", "local towing", "flatbed towing",
        "accident towing", "24 hour towing",
    ],
    "emergency services": [
        "24 hour emergency services", "emergency repair contractors",
        "urgent home repair", "emergency plumbers", "emergency electricians",
        "emergency HVAC", "emergency locksmith",
    ],

    # ── Medical & Healthcare ──────────────────────────────────────────────────

    "dentists": [
        "family dentist", "cosmetic dentistry", "emergency dental repair",
        "teeth whitening", "orthodontist near me", "oral surgeon",
        "pediatric dentist", "dental clinics", "dental care",
        "local dentist", "dental offices",
    ],
    "chiropractors": [
        "back pain relief", "local chiropractor", "sports injury rehab",
        "physical therapy clinic", "auto accident chiropractor",
        "chiropractic care", "chiropractic clinics", "spinal adjustment",
        "back pain treatment",
    ],
    "clinics": [
        "family doctor", "urgent care near me", "walk-in clinic",
        "general practitioner", "pediatric clinic", "telehealth services",
        "medical clinic", "health clinic", "primary care doctor",
    ],
    "urgent care": [
        "walk-in clinic", "emergency clinic", "urgent care near me",
        "after-hours clinic", "same-day doctor", "medical clinic",
    ],
    "pharmacies": [
        "24-hour pharmacy", "local drugstore", "prescription refill",
        "compounding pharmacy", "drive-thru pharmacy", "pharmacy near me",
        "drugstore", "chemist",
    ],
    "optometrists": [
        "eye doctor near me", "prescription glasses", "eye exam",
        "contact lens fitting", "local optometrist", "vision care",
        "eyeglasses store", "eye clinic",
    ],
    "physical therapy": [
        "physiotherapy", "sports rehab", "physical therapist near me",
        "sports injury clinic", "rehabilitation clinic",
        "back pain physical therapy", "physiotherapy clinic",
    ],

    # ── Beauty & Wellness ─────────────────────────────────────────────────────

    "hair salons": [
        "haircuts near me", "color specialist", "balayage salon",
        "curly hair specialist", "men's haircuts", "bridal hair styling",
        "hair stylists", "hair studios", "beauty salons",
        "women's hair salons", "blow dry bars",
    ],
    "barber shops": [
        "local barber", "fade haircut", "beard trim",
        "traditional hot towel shave", "men's grooming",
        "barbers", "men's hair salons", "barbershops", "hair cut shops",
    ],
    "nail salons": [
        "acrylic nails", "gel manicure", "pedicure spa", "nail art",
        "local nail bar", "dip powder nails", "nail studios",
        "manicure pedicure", "nail technicians", "nail spas",
    ],
    "spas": [
        "day spa near me", "facial treatments", "medical spa",
        "reflexology", "couples massage", "body wrap",
        "luxury spa", "wellness spa", "beauty spa",
    ],
    "massage therapy": [
        "deep tissue massage", "couples massage", "day spa near me",
        "massage therapists", "therapeutic massage", "sports massage",
        "relaxation massage", "registered massage therapists",
        "local massage therapy",
    ],
    "gyms": [
        "24-hour gym", "personal trainer", "yoga studio",
        "pilates class", "crossfit box", "martial arts school",
        "boutique fitness", "fitness centres", "fitness clubs",
        "workout gyms", "health clubs",
    ],
    "fitness": [
        "gym near me", "personal trainer", "yoga studio", "pilates",
        "crossfit", "fitness club", "workout studio", "health club",
        "bootcamp classes",
    ],
    "yoga studios": [
        "yoga classes near me", "hot yoga", "yoga instructor",
        "meditation classes", "pilates studio", "mindfulness classes",
    ],
    "pet grooming": [
        "dog grooming", "cat grooming", "pet salon", "animal grooming",
        "mobile pet grooming", "dog groomers", "pet spa", "dog wash",
    ],

    # ── Automotive ────────────────────────────────────────────────────────────

    "auto repair shops": [
        "mechanic near me", "auto repair shop", "oil change",
        "brake repair", "transmission specialist", "engine diagnostics",
        "car repair", "auto mechanics", "vehicle repair",
        "car service centre",
    ],
    "auto detailing": [
        "car detailing", "mobile car detailing", "auto detailing services",
        "vehicle detailing", "hand car wash", "ceramic coating",
        "interior car cleaning", "paint correction",
        "car wash detailing", "full detail car wash",
    ],
    "car detailing": [
        "auto detailing", "mobile detailing", "car detailing services",
        "vehicle detailing", "paint protection", "ceramic coating",
        "interior detailing", "exterior detailing",
    ],
    "mobile car detailing": [
        "mobile auto detailing", "at-home car detailing", "car detailing",
        "mobile vehicle detailing", "auto detailing", "mobile detailers",
    ],
    "auto body shops": [
        "collision repair", "dent removal", "auto paint shop",
        "scratch repair", "bumper repair", "auto body repair",
        "car body shop", "fender repair", "hail damage repair",
    ],
    "tire shops": [
        "discount tires", "tire repair", "wheel alignment",
        "winter tires", "local tire dealer", "tire change",
        "flat tire repair", "tire installation",
    ],
    "car wash": [
        "touchless car wash", "automatic car wash", "hand car wash",
        "full-service car wash", "car wash near me", "drive-through car wash",
    ],

    # ── Professional & B2B Services ───────────────────────────────────────────

    "real estate agents": [
        "realtors near me", "listing agent", "home buyers agent",
        "commercial real estate", "property management companies",
        "real estate broker", "local realtor", "home selling agent",
    ],
    "lawyers": [
        "personal injury lawyer", "family law attorney", "divorce lawyer",
        "criminal defense attorney", "estate planning attorney",
        "local attorney", "law firm near me", "legal services",
    ],
    "attorneys": [
        "personal injury lawyer", "family law attorney", "divorce lawyer",
        "criminal defense", "estate planning attorney", "local lawyer",
        "law firm", "legal services",
    ],
    "accountants": [
        "CPA near me", "tax preparation", "small business bookkeeping",
        "financial advisor", "payroll services", "tax accountant",
        "local accounting firm", "income tax services",
    ],
    "marketing agencies": [
        "local SEO agency", "web developers", "digital marketing consultant",
        "social media management", "graphic design studio",
        "online marketing agency", "advertising agency", "web design agency",
    ],
    "web design": [
        "web developers", "website design", "local SEO agency",
        "digital marketing", "web design agency", "website developers",
        "ecommerce website design",
    ],

    # ── Retail & Shopping ─────────────────────────────────────────────────────

    "clothing stores": [
        "local boutiques", "men's clothing store", "shoe store near me",
        "vintage clothing", "formal wear", "plus-size clothing",
        "fashion boutique", "women's clothing store", "thrift store",
    ],
    "florists": [
        "flower delivery", "wedding florist", "custom bouquets",
        "local flower shop", "sympathy flowers", "flower arrangements",
        "event florist", "same-day flower delivery",
    ],
    "electronics repair": [
        "phone repair near me", "computer repair shop", "screen replacement",
        "local electronics store", "laptop repair", "iphone repair",
        "tablet repair", "device repair",
    ],
    "furniture stores": [
        "mattress store", "local furniture shop", "home decor boutique",
        "office furniture", "vintage furniture", "sofa store",
        "bedroom furniture", "custom furniture",
    ],

    # ── Hospitality & Events ──────────────────────────────────────────────────

    "hotels": [
        "hotels near me", "boutique hotels", "pet-friendly motels",
        "bed and breakfast", "luxury resorts", "extended stay hotels",
        "affordable hotels", "local inn",
    ],
    "event venues": [
        "wedding venues", "banquet halls", "corporate event space",
        "party room rental", "outdoor venues", "reception hall",
        "conference centre", "function room",
    ],
    "wedding venues": [
        "wedding reception hall", "outdoor wedding venues",
        "banquet halls", "wedding event space", "bridal venue",
        "garden wedding venue",
    ],
    "travel agencies": [
        "local travel agency", "tour guides", "airport shuttle service",
        "passport photo service", "vacation packages", "travel consultants",
    ],
}


class GoogleMapsScraper(BaseScraper):
    """
    Scrapes Google Maps search results for a given niche and location.
    Returns a list of raw lead dicts — one dict per business found.
    """

    BASE_URL = "https://www.google.com/maps/search/{query}"

    # ── Public entry point ────────────────────────────────────────────

    def scrape_niche(self, niche: str, location: dict, on_progress=None) -> list[dict]:
        """
        Search Google Maps for *niche* in *location* and return all leads.

        Searches the canonical niche term first, then keyword expansions from
        NICHE_EXPANSIONS in order until max_results_per_niche unique listings
        are collected.  This overcomes Google Maps' ~60-result cap per query
        and ensures enough raw leads to hit the user's --limit target.

        Parameters
        ----------
        niche       : e.g. "restaurants"
        location    : dict with keys city, state (from config.yaml → location)
        on_progress : optional callable(current: int, total: int)
        """
        max_results  = self.config["scraping"].get("max_results_per_niche", 60)
        city_state   = f"{location['city']}, {location['state']}"

        # Build ordered list of search terms: canonical niche first, then expansions
        expansions   = NICHE_EXPANSIONS.get(niche.lower().strip(), [])
        search_terms = [niche] + expansions

        # Phase A: collect profile URLs across all search term variants
        global_seen: set[str]  = set()
        all_urls:    list[str] = []

        for term in search_terms:
            remaining = max_results - len(all_urls)
            if remaining <= 0:
                break

            query = f"{term} in {city_state}"
            url   = self.BASE_URL.format(query=quote_plus(query))
            self.logger.info(f"Searching Google Maps: '{query}'")

            if not self._safe_get(url):
                self.logger.warning(f"Could not load Google Maps for '{term}' — skipping")
                continue

            new_urls = self._collect_result_urls(
                max_collect=remaining,
                exclude_urls=global_seen,
            )
            for u in new_urls:
                global_seen.add(u)
                all_urls.append(u)

            self.logger.info(
                f"  '{term}': +{len(new_urls)} listings "
                f"(total unique: {len(all_urls)}/{max_results})"
            )

            if len(all_urls) >= max_results:
                break

        self.logger.info(
            f"Collected {len(all_urls)} unique listings for '{niche}' "
            f"across {len(search_terms)} search terms"
        )

        # Phase B: extract business data from each profile URL
        leads = []
        for i, profile_url in enumerate(all_urls, start=1):
            self.logger.info(f"  [{i}/{len(all_urls)}] Extracting: {profile_url[:80]}…")
            try:
                lead = self._extract_business(profile_url, niche)
                if lead:
                    leads.append(lead)
            except Exception as exc:
                self.logger.warning(f"  Skipping listing {i}: {exc}")
            if on_progress:
                try:
                    on_progress(i, len(all_urls))
                except Exception:
                    pass
            self.rate_limiter.wait()

        return leads

    # ── Step 1: collect profile URLs from the search results feed ─────

    def _collect_result_urls(
        self,
        max_collect: int = None,
        exclude_urls: set = None,
    ) -> list[str]:
        """
        Scroll the Google Maps sidebar and collect business profile URLs.

        Parameters
        ----------
        max_collect  : stop after this many NEW (non-excluded) URLs.
                       Defaults to max_results_per_niche from config.
        exclude_urls : set of URLs already collected — skipped here so
                       callers can merge results across multiple searches
                       without duplicates.

        Returns a list of new, deduplicated URLs up to max_collect.
        """
        if max_collect is None:
            max_collect = self.config["scraping"].get("max_results_per_niche", 60)
        pause          = self.config["scraping"].get("scroll_pause_time", 2.0)
        max_scroll_att = self.config["scraping"].get("max_scroll_attempts", 20)

        # seen includes already-collected URLs so we skip them transparently
        seen: set[str] = set(exclude_urls) if exclude_urls else set()

        # Wait for the results feed container to appear
        feed = self._wait_for('div[role="feed"]', timeout=10)
        if not feed:
            feed = self._wait_for("div.m6QErb", timeout=5)
        if not feed:
            self.logger.error("Results feed did not load — possible CAPTCHA or rate-limit")
            return []

        urls: list[str] = []   # only NEW (non-excluded) URLs
        no_new_count    = 0
        scroll_attempts = 0

        while scroll_attempts < max_scroll_att and no_new_count < 3:
            links    = self.driver.find_elements(By.CSS_SELECTOR, "a.hfpxzc")
            prev_len = len(urls)

            for link in links:
                try:
                    href = link.get_attribute("href") or ""
                    if "/maps/place/" in href and href not in seen:
                        seen.add(href)
                        urls.append(href)
                except StaleElementReferenceException:
                    continue

            if len(urls) == prev_len:
                no_new_count += 1
            else:
                no_new_count = 0

            if self._end_of_results_reached():
                self.logger.info("Reached end of Google Maps results")
                break

            if len(urls) >= max_collect:
                self.logger.info(f"Collected {max_collect} new listings — stopping scroll")
                break

            try:
                self._scroll_element(feed, pixels=random.randint(700, 1000))
            except Exception:
                feed = self._wait_for('div[role="feed"]', timeout=5)

            time.sleep(pause + random.uniform(0, 1.0))
            scroll_attempts += 1

        self.logger.debug(f"Collected {len(urls)} new URLs after {scroll_attempts} scrolls")
        return urls[:max_collect]

    def _end_of_results_reached(self) -> bool:
        """Detect the "You've reached the end of the list" notice."""
        try:
            end_divs = self.driver.find_elements(
                By.XPATH,
                '//p[contains(text(),"end of the list") '
                'or contains(text(),"No more results")]'
                '| //span[contains(text(),"end of results")]',
            )
            return any(d.is_displayed() for d in end_divs)
        except Exception:
            return False

    # ── Step 2: extract all data from a business detail page ──────────

    def _extract_business(self, url: str, niche: str) -> dict | None:
        """
        Navigate to a business profile URL and extract all data fields.
        Returns a raw lead dict, or None if the page fails to load.
        """
        if not self._safe_get(url):
            return None

        # Wait for the business name heading to confirm the page loaded
        name_elem = self._wait_for_name()
        if not name_elem:
            self.logger.warning(f"Business detail page did not load: {url[:80]}")
            return None

        lead: dict = {
            "source":          "Google Maps",
            "gmb_link":        url,
            "niche":           niche,
            "name":            "",
            "phone":           "",
            "secondary_phone": "",
            "address":         "",
            "city":            "",
            "state":           "",
            "zip":             "",
            "hours":           "",
            "review_count":    0,
            "rating":          "",
            "website":         "",
            "facebook":        "",
            "instagram":       "",
            "notes":           "",
        }

        lead["name"]         = self._extract_name()
        lead["rating"]       = self._extract_rating()
        lead["review_count"] = self._extract_review_count()
        lead["phone"]        = self._extract_phone()
        lead["address"]      = self._extract_address()
        lead["hours"]        = self._extract_hours()
        lead["website"]      = self._extract_website()
        lead["category"]     = self._extract_category()

        # Flag if no phone was found so supplementary scrapers know to look
        if not lead["phone"]:
            lead["notes"] = "Phone Number Needed - Manual Research Required"

        return lead

    # ── Field extractors (each tries multiple fallback selectors) ──────

    def _wait_for_name(self):
        """Wait up to 6 s for the business name heading to appear."""
        for sel in ("h1.DUwDvf", 'h1[class*="fontHeadline"]', "h1"):
            try:
                return WebDriverWait(self.driver, 6).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                )
            except TimeoutException:
                continue
        return None

    def _extract_name(self) -> str:
        return self._text(
            "h1.DUwDvf",
            'h1[class*="fontHeadline"]',
            "h1",
        )

    def _extract_rating(self) -> str:
        # Approach 1: aria-label on the star-rating span (most stable)
        for xpath in (
            '//span[@aria-label[contains(., "star")]]',
            '//div[@class="F7nice"]//span[@aria-hidden="true"]',
        ):
            elem = self._find_xpath(xpath)
            if elem:
                text = elem.text or elem.get_attribute("aria-label") or ""
                match = re.search(r"(\d+\.?\d*)", text)
                if match:
                    return match.group(1)

        # Approach 2: CSS class selectors
        for sel in ("div.F7nice span[aria-hidden='true']", "span.ceNzKf"):
            text = self._text(sel)
            if text:
                match = re.search(r"(\d+\.?\d*)", text)
                if match:
                    return match.group(1)
        return ""

    def _extract_review_count(self) -> int:
        # Approach 1: button/span with aria-label containing "review" (singular OR plural)
        for xpath in (
            '//button[contains(@aria-label, "review")]',
            '//span[contains(@aria-label, "review")]',
        ):
            elem = self._find_xpath(xpath)
            if elem:
                label = elem.get_attribute("aria-label") or elem.text or ""
                match = re.search(r"([\d,]+)\s+reviews?", label, re.I)
                if match:
                    return int(match.group(1).replace(",", ""))

        # Approach 2: look for parenthesised number after the rating
        for sel in ('div.F7nice span[aria-label]', 'button[data-value*="review"]'):
            elem = self._find(sel)
            if elem:
                text = elem.text or ""
                match = re.search(r"\(([\d,]+)\)", text)
                if match:
                    return int(match.group(1).replace(",", ""))
        return 0

    def _extract_phone(self) -> str:
        # Give the contact section up to 6 s to render before extracting.
        # Google Maps loads the business name first and contact details
        # (phone, address) a beat later via a secondary XHR.  Without
        # this wait, fast machines grab the name element and immediately
        # call find_element for the phone — which isn't in the DOM yet.
        phone_xpath = (
            '//button[starts-with(@data-item-id, "phone:")]'
            ' | //a[starts-with(@data-item-id, "phone:")]'
            ' | //button[starts-with(@aria-label, "Phone:")]'
        )
        try:
            WebDriverWait(self.driver, 6).until(
                EC.presence_of_element_located((By.XPATH, phone_xpath))
            )
        except TimeoutException:
            pass  # phone element may simply not exist for this business

        # Approach 1: data-item-id is "phone:tel:+1XXXXXXXXXX"
        for xpath in (
            '//button[starts-with(@data-item-id, "phone:")]',
            '//a[starts-with(@data-item-id, "phone:")]',
        ):
            elem = self._find_xpath(xpath)
            if elem:
                item_id = elem.get_attribute("data-item-id") or ""
                # Strip both "phone:" and optional "tel:" prefixes
                phone = item_id.replace("phone:", "").replace("tel:", "").strip()
                if phone:
                    return phone

        # Approach 2: aria-label starts with "Phone:"
        for xpath in (
            '//button[starts-with(@aria-label, "Phone:")]',
            '//div[starts-with(@aria-label, "Phone:")]',
        ):
            elem = self._find_xpath(xpath)
            if elem:
                label = elem.get_attribute("aria-label") or ""
                phone = label.replace("Phone:", "").strip()
                if phone:
                    return phone

        # Approach 3: scan all button texts for phone-like patterns
        phone_re = re.compile(r"\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}")
        buttons  = self.driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
            text = btn.text or ""
            match = phone_re.search(text)
            if match:
                return match.group(0).strip()

        return ""

    def _extract_address(self) -> str:
        # Approach 1: data-item-id="address"
        for xpath in (
            '//button[@data-item-id="address"]',
            '//div[@data-item-id="address"]',
        ):
            elem = self._find_xpath(xpath)
            if elem:
                # The address text is usually in a child div
                try:
                    addr = elem.find_element(By.CSS_SELECTOR, "div.fontBodyMedium")
                    if addr.text:
                        return addr.text.strip()
                except NoSuchElementException:
                    pass
                if elem.text:
                    return elem.text.strip()

        # Approach 2: aria-label starts with "Address:"
        for xpath in (
            '//button[starts-with(@aria-label, "Address:")]',
            '//div[starts-with(@aria-label, "Address:")]',
        ):
            elem = self._find_xpath(xpath)
            if elem:
                label = elem.get_attribute("aria-label") or ""
                addr  = label.replace("Address:", "").strip()
                if addr:
                    return addr

        return ""

    def _extract_hours(self) -> str:
        """Extract operating hours as a compact string (no button click for speed)."""
        # Approach 1: aria-label on hours button often contains the full schedule
        try:
            hours_btn = self._find_xpath(
                '//button[contains(@aria-label, "hours")]'
                '| //div[contains(@aria-label, "hours")]'
            )
            if hours_btn:
                label = hours_btn.get_attribute("aria-label") or ""
                # aria-label commonly holds the full schedule when > 20 chars
                if len(label) > 20:
                    return label.split(";")[0].strip()
        except Exception:
            pass

        # Approach 2: look for "Open" / "Closed" status text via CSS
        for sel in ("div.MkV9", 'span[jstcache*="hour"]', "div.t39EBf"):
            text = self._text(sel)
            if text:
                return text
        return ""

    def _extract_website(self) -> str:
        # Most reliable: data-item-id="authority"
        for xpath in (
            '//a[@data-item-id="authority"]',
            '//a[contains(@aria-label, "Website")]',
            '//a[contains(@aria-label, "website")]',
        ):
            elem = self._find_xpath(xpath)
            if elem:
                href = elem.get_attribute("href") or ""
                # Filter out Google's own redirect URLs when possible
                if href and "google.com/url" not in href:
                    return href
                if href:
                    # Extract the actual destination from Google redirect
                    match = re.search(r"url=([^&]+)", href)
                    if match:
                        from urllib.parse import unquote
                        return unquote(match.group(1))
                    return href
        return ""

    def _extract_category(self) -> str:
        """Extract the primary category label (e.g. 'Plumber', 'Restaurant')."""
        for sel in (
            "button.DkEaL",
            'button[jsaction*="category"]',
            "span.DkEaL",
        ):
            text = self._text(sel)
            if text:
                return text
        return ""
