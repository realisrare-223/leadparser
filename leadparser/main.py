#!/usr/bin/env python3
"""
LeadParser -- Automated Local Business Lead Generation Pipeline
==============================================================
Scrapes Google Business listings (and supplementary free sources)
to build a cold-calling lead engine backed by Supabase (PostgreSQL).

ALL tools and services used are 100% FREE -- no paid API keys required.

Quick start
-----------
  1. pip install -r requirements.txt
  2. cp .env.example .env   # add your Supabase URL + service role key
  3. python main.py --city "Dallas" --state TX --limit 40

Full usage
----------
  python main.py                                # Run with default config.yaml
  python main.py --city "Miami" --state FL      # Override city/state from CLI
  python main.py --limit 50                     # Target N filtered leads
  python main.py --config my_config.yaml        # Use a different config file
  python main.py --niche "plumbers"             # Scrape a single niche
  python main.py --export-only                  # Export DB -> CSV, no scraping
  python main.py --no-csv                       # Skip local CSV export
  python main.py --dry-run                      # Scrape but don't write to DB
  python main.py --serve                        # Launch dashboard after run
"""

import argparse
import asyncio
import csv
import logging
import multiprocessing as mp
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

import yaml
from dotenv import load_dotenv
from colorama import init as colorama_init, Fore, Style

# -- Internal modules -------------------------------------------------
# GoogleMapsScraper (Selenium) kept as legacy fallback; default is Playwright.
# Parser selection is driven by config["scraping"]["parser"] at runtime.
from scrapers.google_maps       import GoogleMapsScraper
from exporters.supabase_handler import SupabaseHandler
from utils.rate_limiter         import RateLimiter
from utils.proxy_manager        import ProxyManager
from utils.phone_validator      import PhoneValidator
from utils.address_parser       import AddressParser
from utils.lead_scorer          import LeadScorer
from utils.pitch_engine         import PitchEngine
from utils.sentiment_analyzer   import SentimentAnalyzer


def _load_scraper_class(config: dict):
    """
    Return the scraper class to use based on config["scraping"]["parser"].

    "playwright" (default) — async Playwright, 4 parallel workers
    "xhr"                  — pure HTTP, no browser, 50 concurrent requests
    "selenium"             — legacy Selenium / undetected-chromedriver
    """
    parser = config["scraping"].get("parser", "playwright").lower()
    if parser == "xhr":
        from scrapers.xhr_scraper import XHRGoogleMapsScraper
        return XHRGoogleMapsScraper
    elif parser == "selenium":
        return GoogleMapsScraper
    else:  # default: playwright
        from scrapers.playwright_scraper import PlaywrightGoogleMapsScraper
        return PlaywrightGoogleMapsScraper


class ConcurrentXHRScraper:
    """
    Runs multiple XHR scrapers in parallel using process-based concurrency.
    
    Each XHR instance runs in its own process to maximize throughput
    and avoid any GIL contention. Results are aggregated from all workers.
    """
    
    def __init__(self, config: dict, num_workers: int = 4):
        self.config = config
        self.num_workers = num_workers
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def scrape_niche(self, niche: str, location: dict, on_progress: Callable = None) -> list[dict]:
        """
        Scrape a niche using multiple concurrent XHR workers.
        Distributes search terms across workers for parallel execution.
        """
        import multiprocessing as mp
        from scrapers.google_maps import NICHE_EXPANSIONS
        
        city_state = f"{location['city']}, {location['state']}"
        expansions = NICHE_EXPANSIONS.get(niche.lower().strip(), [])
        all_terms = [niche] + expansions
        
        # Split terms across workers
        term_chunks = self._split_chunks(all_terms, self.num_workers)
        self.logger.info(
            f"ConcurrentXHR: distributing {len(all_terms)} search terms "
            f"across {len(term_chunks)} workers for '{niche}' in {city_state}"
        )
        
        # Create work items
        work_items = [
            (chunk, location, self.config, i) 
            for i, chunk in enumerate(term_chunks) if chunk
        ]
        
        if not work_items:
            return []
        
        # Run workers in parallel
        with mp.Pool(processes=min(len(work_items), self.num_workers)) as pool:
            results = pool.map(_xhr_worker, work_items)
        
        # Aggregate results
        all_leads = []
        seen_gmb = set()
        for worker_leads in results:
            for lead in worker_leads:
                gmb = lead.get("gmb_link", "").strip()
                if gmb and gmb not in seen_gmb:
                    seen_gmb.add(gmb)
                    all_leads.append(lead)
        
        self.logger.info(
            f"ConcurrentXHR: collected {len(all_leads)} unique leads "
            f"for '{niche}' in {city_state}"
        )
        return all_leads
    
    def _split_chunks(self, lst: list, n: int) -> list[list]:
        """Split list into n roughly equal chunks."""
        if not lst or n <= 0:
            return [lst]
        k, rem = divmod(len(lst), n)
        chunks = []
        i = 0
        for c in range(n):
            size = k + (1 if c < rem else 0)
            chunks.append(lst[i:i + size])
            i += size
        return [c for c in chunks if c]


def _xhr_worker(args) -> list[dict]:
    """
    Worker function for concurrent XHR scraping.
    Runs in a separate process.
    """
    import asyncio
    from scrapers.xhr_scraper import XHRGoogleMapsScraper, _make_fingerprint
    from utils.rate_limiter import RateLimiter
    from utils.proxy_manager import ProxyManager
    
    terms, location, config, worker_id = args
    
    # Set up fresh instances in this process
    rate_limiter = RateLimiter(config)
    proxy_mgr = ProxyManager(config)
    proxy_mgr.refresh()
    
    logger = logging.getLogger(f"XHRWorker-{worker_id}")
    logger.info(f"Worker {worker_id}: processing {len(terms)} terms")
    
    # Create a minimal scraper that just does URL collection + extraction
    scraper = XHRGoogleMapsScraper(config, rate_limiter, proxy_mgr)
    
    # Run the scrape
    try:
        # We'll call the internal methods directly to use our term list
        return asyncio.run(_scrape_with_terms(scraper, terms, location))
    except Exception as exc:
        logger.error(f"Worker {worker_id} failed: {exc}")
        return []


async def _scrape_with_terms(scraper, terms: list[str], location: dict) -> list[dict]:
    """Async helper to scrape specific terms."""
    import httpx
    from urllib.parse import quote_plus
    from scrapers.xhr_scraper import _SEARCH_URL, _BLOCK_RE, _make_fingerprint
    
    fingerprint = _make_fingerprint()
    proxy_url = scraper._get_proxy_url()
    proxy_map = (
        {"http://": proxy_url, "https://": proxy_url}
        if proxy_url else None
    )
    
    city_state = f"{location['city']}, {location['state']}"
    all_urls = []
    seen = set()
    
    async with httpx.AsyncClient(
        headers=fingerprint["headers"],
        proxies=proxy_map,
        timeout=httpx.Timeout(30.0, connect=10.0),
        follow_redirects=True,
        http2=True,
    ) as client:
        # Phase A: Collect URLs for our assigned terms
        for term in terms:
            query = f"{term} in {city_state}"
            url = _SEARCH_URL.format(query=quote_plus(query))
            
            try:
                resp = await client.get(
                    url,
                    headers={**fingerprint["headers"], "Referer": "https://www.google.com/"},
                )
                
                if resp.status_code == 429 or _BLOCK_RE.search(resp[:3000]):
                    fingerprint = _make_fingerprint()
                    await asyncio.sleep(random.uniform(3, 8))
                    continue
                
                if resp.status_code == 200:
                    new_urls = scraper._extract_urls_from_html(resp.text, seen)
                    for u in new_urls:
                        if u not in seen:
                            seen.add(u)
                            all_urls.append(u)
                            
            except Exception as exc:
                scraper.logger.debug(f"Term '{term}' failed: {exc}")
            
            await asyncio.sleep(random.uniform(0.3, 0.8))
    
    # Phase B: Extract business details
    if not all_urls:
        return []
    
    async with httpx.AsyncClient(
        headers=fingerprint["headers"],
        proxies=proxy_map,
        timeout=httpx.Timeout(30.0, connect=10.0),
        follow_redirects=True,
        http2=True,
    ) as client:
        sem = asyncio.Semaphore(scraper._concurrency)
        tasks = [
            _fetch_business_worker(scraper, client, url, sem, fingerprint)
            for url in all_urls[:60]  # Cap per worker
        ]
        results = await asyncio.gather(*tasks)
    
    return [r for r in results if r is not None]


async def _fetch_business_worker(scraper, client, url, sem, fingerprint):
    """Fetch a single business in worker."""
    import httpx
    from scrapers.xhr_scraper import _BLOCK_RE
    
    async with sem:
        for attempt in range(3):
            try:
                resp = await client.get(
                    url,
                    headers={
                        **fingerprint["headers"],
                        "Referer": "https://www.google.com/maps/",
                    },
                )
                
                if resp.status_code == 429 or _BLOCK_RE.search(resp.text[:3000]):
                    await asyncio.sleep(2 ** attempt)
                    fingerprint = _make_fingerprint()
                    continue
                
                if resp.status_code == 200:
                    # Parse using the scraper's method
                    return scraper._parse_business_html(resp.text, url, "")
                    
            except (httpx.TimeoutException, httpx.ConnectError):
                await asyncio.sleep(2 ** attempt)
            except Exception:
                pass
        
        return None

# ---------------------------------------------------------------------


# ── Module-level progress updater ─────────────────────────────────────────────
# Set by setup_logging when --job-id is provided. Called from run_pipeline.

_progress_fn = None   # callable(pct: int) | None


def update_job_progress(pct: int) -> None:
    """Best-effort update of scraper_jobs.progress (no-op outside queued runs)."""
    if _progress_fn:
        try:
            _progress_fn(int(pct))
        except Exception:
            pass


# ── Supabase live log handler ─────────────────────────────────────────────────

class SupabaseLogHandler(logging.Handler):
    """
    Streams log records to the `scraper_logs` Supabase table so the
    dashboard can display live progress while the scraper runs.

    Buffers up to BATCH_SIZE records and flushes either when the buffer
    fills or every FLUSH_INTERVAL seconds — whichever comes first.
    """
    BATCH_SIZE     = 8
    FLUSH_INTERVAL = 3.0   # seconds

    def __init__(self, supabase_client, job_id: str):
        super().__init__()
        self._sb         = supabase_client
        self._job_id     = job_id
        self._buffer     = []
        self._last_flush = time.time()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg   = self.format(record)
            level = record.levelname.lower()
            self._buffer.append({
                'job_id':  self._job_id,
                'level':   level,
                'message': msg,
            })
            if len(self._buffer) >= self.BATCH_SIZE or \
               time.time() - self._last_flush >= self.FLUSH_INTERVAL:
                self.flush()
        except Exception:
            pass   # never let the log handler crash the scraper

    def flush(self) -> None:
        if not self._buffer:
            return
        try:
            self._sb.table('scraper_logs').insert(self._buffer).execute()
            self._buffer.clear()
            self._last_flush = time.time()
        except Exception:
            pass   # best-effort


# -----------------------------------------------------------------------------


def setup_logging(config: dict, job_id: str = None) -> logging.Logger:
    """Configure file + console logging.

    If *job_id* is provided (when run as a queued job), also attaches a
    SupabaseLogHandler so live progress streams to the dashboard.
    """
    log_cfg = config.get("logging", {})
    level   = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
    log_dir = Path(log_cfg.get("log_dir", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file  = log_dir / f"leadparser_{timestamp}.log"

    fmt = "%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s"
    logging.basicConfig(
        level=level,
        format=fmt,
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    for noisy in ("selenium", "urllib3", "undetected_chromedriver", "WDM",
                  "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logger = logging.getLogger("leadparser.main")
    logger.info(f"LeadParser started | log: {log_file}")

    # Attach Supabase handler when running as a queued job
    if job_id:
        try:
            from supabase import create_client
            sb_url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL', '')
            sb_key = os.getenv('SUPABASE_KEY', '')
            if sb_url and sb_key:
                sb_client  = create_client(sb_url, sb_key)
                sb_handler = SupabaseLogHandler(sb_client, job_id)
                sb_handler.setFormatter(logging.Formatter('%(levelname)-8s %(message)s'))
                sb_handler.setLevel(logging.DEBUG)
                logging.getLogger().addHandler(sb_handler)
                logger.info(f"Live log streaming active — job {job_id[:8]}")

                # Wire up module-level progress updater
                global _progress_fn
                _job_id_captured = job_id
                def _make_progress_fn(client, jid):
                    def _prog(pct: int) -> None:
                        client.table('scraper_jobs').update(
                            {'progress': pct}
                        ).eq('id', jid).execute()
                    return _prog
                _progress_fn = _make_progress_fn(sb_client, _job_id_captured)
            else:
                logger.warning("SUPABASE_URL/SUPABASE_KEY not set — live logs disabled")
        except Exception as exc:
            logger.warning(f"Could not start Supabase log handler: {exc}")

    return logger


def load_config(path: str) -> dict:
    """Load and return the YAML configuration file."""
    with open(path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    return cfg


def build_lead(
    raw:       dict,
    niche:     str,
    config:    dict,
    scorer:    LeadScorer,
    pitcher:   PitchEngine,
    validator: PhoneValidator,
    parser:    AddressParser,
) -> "dict | None":
    """Transform a raw scraped dict into the canonical lead dict."""
    addr_parts = parser.infer_city_state(
        raw.get("address", ""), config["location"]
    )

    phone     = validator.format(raw.get("phone",           ""))
    sec_phone = validator.format(raw.get("secondary_phone", ""))
    score     = scorer.score(raw, niche, config)
    pitch     = pitcher.generate(niche, raw, config)

    lead: dict = {
        "niche":            niche,
        "name":             (raw.get("name") or "").strip(),
        "phone":            phone,
        "secondary_phone":  sec_phone,
        "address":          addr_parts.get("street") or (raw.get("address") or "").strip(),
        "city":             addr_parts.get("city")   or (raw.get("city")    or "").strip(),
        "state":            addr_parts.get("state")  or (raw.get("state")   or "").strip(),
        "zip_code":         addr_parts.get("zip")    or (raw.get("zip")     or "").strip(),
        "hours":            (raw.get("hours")         or "").strip(),
        "review_count":     raw.get("review_count", 0) or 0,
        "rating":           str(raw.get("rating", "") or ""),
        "gmb_link":         (raw.get("gmb_link")      or "").strip(),
        "website":          (raw.get("website")        or "").strip(),
        "facebook":         (raw.get("facebook")       or "").strip(),
        "instagram":        (raw.get("instagram")      or "").strip(),
        "data_source":      raw.get("source", "Google Maps"),
        "date_added":       datetime.now().strftime("%Y-%m-%d"),
        "lead_score":       score,
        "pitch_notes":      pitch,
        "additional_notes": (raw.get("notes") or "").strip(),
        "call_status":      "",
        "follow_up_date":   "",
    }

    # Skip leads with no phone entirely — no supplementary lookup
    if not lead["phone"]:
        return None

    return lead


def apply_filters(leads: list[dict], config: dict) -> list[dict]:
    """Apply config.yaml filter criteria. Returns passing leads."""
    f = config.get("filters", {})
    min_reviews      = f.get("min_reviews",          0)
    max_reviews      = f.get("max_reviews",          9999)
    min_rating       = f.get("min_rating",           0.0)
    max_rating       = f.get("max_rating",           5.0)
    exclude_with_web = f.get("exclude_with_website", False)
    require_website  = f.get("require_website",      False)
    require_phone    = f.get("require_phone",        False)
    min_score        = f.get("min_lead_score",       0)

    filtered = []
    for lead in leads:
        reviews = int(lead.get("review_count", 0) or 0)
        try:
            rating = float(lead.get("rating", 0.0) or 0.0)
        except (TypeError, ValueError):
            rating = 0.0
        score = int(lead.get("lead_score", 0) or 0)
        phone = (lead.get("phone") or "").strip()

        if reviews < min_reviews:                                continue
        if reviews > max_reviews:                                continue
        if rating and rating < min_rating:                       continue
        if rating and rating > max_rating:                       continue
        if exclude_with_web and lead.get("website"):              continue
        if require_website  and not lead.get("website"):          continue
        if require_phone and (not phone or phone == "NOT FOUND"): continue
        if score < min_score:                                    continue

        filtered.append(lead)

    return filtered


def print_banner():
    colorama_init(autoreset=True)
    sep = "=" * 60
    print(f"\n{Fore.CYAN}{sep}")
    print(f"  LeadParser -- Free Local Business Lead Gen")
    print(f"  All tools: 100% FREE  |  No paid APIs")
    print(f"{sep}{Style.RESET_ALL}\n")


CSV_HEADERS = [
    "Niche", "Business Name", "Phone", "Secondary Phone", "Address",
    "City", "State", "Zip Code", "Hours", "Review Count", "Rating",
    "GMB Link", "Website", "Facebook", "Instagram", "Data Source",
    "Date Added", "Lead Score", "Pitch Notes", "Additional Notes",
    "Status", "Caller Notes",
]
CSV_KEYS = [
    "niche", "name", "phone", "secondary_phone", "address",
    "city", "state", "zip_code", "hours", "review_count", "rating",
    "gmb_link", "website", "facebook", "instagram", "data_source",
    "date_added", "lead_score", "pitch_notes", "additional_notes",
    "status", "caller_notes",
]


def export_csv(leads: list[dict], output_dir: str = "data") -> str:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    dated_path  = Path(output_dir) / f"leads_{timestamp}.csv"
    latest_path = Path(output_dir) / "leads_latest.csv"

    for path in (dated_path, latest_path):
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(CSV_HEADERS)
            for lead in leads:
                writer.writerow([str(lead.get(k, "") or "") for k in CSV_KEYS])

    return str(dated_path)


def print_stats(stats: dict, dashboard_url: str = None, csv_path: str = None):
    sep = "-" * 60
    print(f"\n{Fore.GREEN}{sep}")
    print(f"  Run Complete")
    print(f"{sep}{Style.RESET_ALL}")
    print(f"  Niches searched : {stats.get('niches',      0)}")
    print(f"  Raw scraped     : {stats.get('raw_total',   0)}")
    print(f"  After filters   : {stats.get('total',       0)}")
    print(f"  New leads saved : {stats.get('new',         0)}")
    print(f"  Duplicates skip : {stats.get('duplicates',  0)}")
    print(f"  Errors          : {stats.get('errors',      0)}")
    if csv_path:
        print(f"\n  CSV: {csv_path}")
        print(f"  CSV (latest): data/leads_latest.csv")
    if dashboard_url:
        print(f"\n  Supabase: {dashboard_url}")
    print()


# ---------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------

def run_pipeline(config: dict, args: argparse.Namespace, logger: logging.Logger):
    """
    Full lead-generation pipeline:
      1. Scrape Google Maps (over-collect to guarantee target count)
      2. Supplement missing phones from Yelp / Yellow Pages / BBB
      3. Score + filter leads
      4. Trim to --limit target (guarantees N filtered leads)
      5. Upsert into Supabase
      6. Optional CSV export
    """
    rate_limiter = RateLimiter(config)
    proxy_mgr    = ProxyManager(config)
    validator    = PhoneValidator()
    addr_parser  = AddressParser()
    scorer       = LeadScorer(config)
    pitcher      = PitchEngine(config)

    # Always refresh proxy pool — proxies are now always enabled by default.
    # ProxyManager.refresh() is a no-op when enabled=False (legacy config support).
    proxy_mgr.refresh()

    # Support comma-separated niches from CLI (e.g. --niche "plumbers,electricians")
    if args.niche:
        niches = [n.strip() for n in args.niche.split(",") if n.strip()]
    else:
        niches = config["niches"]

    # Support comma-separated cities from CLI (e.g. --city "Seattle,Portland")
    if args.city:
        cities = [c.strip() for c in args.city.split(",") if c.strip()]
    else:
        cities = [config["location"]["city"]]
    
    # Support comma-separated states (either one state for all cities, or per-city)
    if args.state:
        states = [s.strip() for s in args.state.split(",") if s.strip()]
        # If only one state provided but multiple cities, use that state for all
        if len(states) == 1 and len(cities) > 1:
            states = states * len(cities)
    else:
        base_state = config["location"].get("state", "")
        states = [base_state] * len(cities)
    
    # Build location list
    locations = []
    for i, city in enumerate(cities):
        state = states[i] if i < len(states) else states[-1] if states else ""
        locations.append({"city": city, "state": state})

    target_count = config["scraping"].get("target_leads")

    total_combinations = len(niches) * len(locations)
    
    # Distribute target across all niche+city combinations
    # If user wants 100 leads across 3 niches and 2 cities (6 combinations),
    # each combination should get ~17 leads (100/6)
    per_combination_target = None
    if target_count:
        per_combination_target = max(1, target_count // total_combinations)
        # Round up for first N combinations to hit exact target
        remainder = target_count - (per_combination_target * total_combinations)
        logger.info(
            f"Distributing {target_count} leads across {total_combinations} "
            f"niche+city combinations (~{per_combination_target} per combination, "
            f"remainder: {remainder})"
        )

    run_stats: dict = {
        "niches": len(niches), "cities": len(locations), 
        "combinations": total_combinations,
        "raw_total": 0, "total": 0,
        "new": 0, "duplicates": 0, "errors": 0,
    }

    update_job_progress(5)

    with SupabaseHandler(config) as db:

        session_id = db.start_session(niches, config)
        logger.info(
            f"Session #{session_id} | {len(niches)} niche(s) | "
            f"{len(locations)} location(s) | {total_combinations} total combinations"
            + (f" | target: {target_count} filtered leads" if target_count else "")
        )

        # ── Phase 1: Scraping (with retry until target count met) ─────────────
        _parser_name = config["scraping"].get("parser", "playwright").upper()
        print(
            f"\n{Fore.YELLOW}Phase 1: Scraping Google Maps "
            f"[{_parser_name}]...{Style.RESET_ALL}"
        )
        update_job_progress(10)

        ScraperClass = _load_scraper_class(config)
        
        # Use concurrent XHR if specified and using XHR parser
        if (config["scraping"].get("parser") == "xhr" and 
            args.concurrent_xhr is not None and args.concurrent_xhr > 1):
            scraper = ConcurrentXHRScraper(config, num_workers=args.concurrent_xhr)
            logger.info(f"Using concurrent XHR scraper with {args.concurrent_xhr} workers")
        else:
            scraper = ScraperClass(config, rate_limiter, proxy_mgr)

        # Context-manager support: Selenium/Playwright scrapers may need __enter__
        if hasattr(scraper, "__enter__"):
            scraper.__enter__()

        # seen_gmb: dedup across retry passes so we never count a lead twice
        seen_gmb: set[str] = set()
        raw_bucket: list[dict] = []   # all unique pre-filter leads accumulated so far
        all_leads: list[dict] = []

        MAX_PASSES = 3  # up to 3 passes; each doubles the raw-results ceiling

        try:
            combination_idx = 0
            for pass_num in range(MAX_PASSES):
                if pass_num > 0:
                    # Increase raw ceiling 2× for the retry
                    new_raw = min(
                        config["scraping"]["max_results_per_niche"] * 2, 2000
                    )
                    config["scraping"]["max_results_per_niche"] = new_raw
                    logger.info(
                        f"  Retry pass {pass_num + 1}/{MAX_PASSES}: "
                        f"raising raw ceiling to {new_raw} to collect more matches"
                    )
                    print(
                        f"\n{Fore.YELLOW}  Retry pass {pass_num + 1}: "
                        f"collecting up to {new_raw} raw results...{Style.RESET_ALL}"
                    )

                # Iterate over all niche + location combinations
                for loc_i, location in enumerate(locations):
                    for niche_i, niche in enumerate(niches):
                        combination_idx += 1
                        
                        # Calculate per-combination target if distributing
                        current_target = None
                        if per_combination_target:
                            # First 'remainder' combinations get +1
                            extra = 1 if combination_idx <= (target_count - per_combination_target * total_combinations) else 0
                            current_target = per_combination_target + extra
                            # Adjust raw ceiling for this combination
                            config["scraping"]["max_results_per_niche"] = max(20, min(current_target * 10, 500))
                        
                        print(
                            f"  [{combination_idx}/{total_combinations}] "
                            f"{Fore.CYAN}{niche}{Style.RESET_ALL} "
                            f"in {location['city']}, {location['state']}"
                            + (f" (target: ~{current_target})" if current_target else "")
                        )

                        # Per-listing progress
                        _progress_pct = 10 + int((combination_idx / total_combinations) * 60)

                        def _listing_progress(current: int, total: int,
                                              _pct=_progress_pct) -> None:
                            update_job_progress(_pct)

                        try:
                            raw_leads = scraper.scrape_niche(
                                niche, location, on_progress=_listing_progress
                            )
                        except Exception as exc:
                            logger.error(f"Scraping failed for '{niche}' in {location['city']}: {exc}", exc_info=True)
                            run_stats["errors"] += 1
                            continue

                        new_this_pass = 0
                        for raw in raw_leads:
                            gmb = (raw.get("gmb_link") or "").strip()
                            if gmb in seen_gmb:
                                continue   # already processed in an earlier pass
                            seen_gmb.add(gmb)
                            try:
                                lead = build_lead(
                                    raw, niche, config,
                                    scorer, pitcher, validator, addr_parser
                                )
                                if lead:
                                    # Tag with location for tracking
                                    lead['_source_city'] = location['city']
                                    raw_bucket.append(lead)
                                    run_stats["raw_total"] += 1
                                    new_this_pass += 1
                            except Exception as exc:
                                logger.warning(f"Lead build failed: {exc}", exc_info=True)
                                run_stats["errors"] += 1

                        logger.info(
                            f"  -> {len(raw_leads)} raw scraped, "
                            f"{new_this_pass} new unique leads for '{niche}' in {location['city']}; "
                            f"running total: {run_stats['raw_total']}"
                        )

                # ── Check after each full pass whether target is met ──
                filtered_so_far = apply_filters(raw_bucket, config)
                have  = len(filtered_so_far)
                need  = target_count or 0

                if need and have < need:
                    logger.info(
                        f"  Pass {pass_num + 1} result: {have}/{need} leads pass filters"
                    )
                    if pass_num < MAX_PASSES - 1:
                        continue   # do another pass with higher ceiling
                    else:
                        logger.warning(
                            f"Exhausted {MAX_PASSES} passes — "
                            f"{have}/{need} filtered leads available."
                        )
                        print(
                            f"{Fore.YELLOW}Note:{Style.RESET_ALL} "
                            f"Only {Fore.GREEN}{have}{Style.RESET_ALL}/{need} leads "
                            f"available after {MAX_PASSES} passes — "
                            f"Google Maps may be exhausted for these niches/cities."
                        )
                else:
                    # Target met (or no target) — stop early
                    if need:
                        logger.info(f"  Target reached: {have}/{need} leads pass filters")
                    break

            # Collapse to final filtered set
            all_leads = apply_filters(raw_bucket, config)

        finally:
            if hasattr(scraper, "__exit__"):
                scraper.__exit__(None, None, None)

        # ── Phase 3: Filter ────────────────────────────────────────────
        update_job_progress(75)
        before_filter = run_stats["raw_total"]
        logger.info(f"Filters applied: {before_filter} raw -> {len(all_leads)} passed")
        print(
            f"\n{Fore.YELLOW}Phase 3: Filtering...{Style.RESET_ALL} "
            f"{before_filter} raw -> {Fore.GREEN}{len(all_leads)}{Style.RESET_ALL} passed"
        )

        # ── Phase 4: Trim to target count ─────────────────────────────
        update_job_progress(85)
        if target_count:
            if len(all_leads) > target_count:
                all_leads = all_leads[:target_count]
                logger.info(f"Trimmed to target: {target_count} leads")
                print(
                    f"{Fore.YELLOW}Trimming to target:{Style.RESET_ALL} "
                    f"keeping {Fore.GREEN}{target_count}{Style.RESET_ALL}"
                )

        run_stats["total"] = len(all_leads)

        # ── Phase 5: Upsert into Supabase ─────────────────────────────
        print(f"\n{Fore.YELLOW}Saving to Supabase...{Style.RESET_ALL}")
        update_job_progress(88)
        try:
            insert_stats            = db.bulk_insert(all_leads)
            run_stats["new"]        = insert_stats["new"]
            run_stats["duplicates"] = insert_stats["duplicates"]
            run_stats["errors"]    += insert_stats["errors"]
            logger.info(
                f"Supabase insert: {insert_stats['new']} new, "
                f"{insert_stats['duplicates']} dupes, "
                f"{insert_stats['errors']} errors"
            )
        except Exception as exc:
            logger.error(f"Supabase insert failed: {exc}", exc_info=True)
            run_stats["errors"] += 1

        # ── Phase 6: Optional CSV export ──────────────────────────────
        update_job_progress(95)
        if not args.no_csv:
            try:
                min_score_val = config["filters"].get("min_lead_score", 0)
                all_db_leads  = db.get_all_leads(min_score=min_score_val)
                csv_path      = export_csv(all_db_leads)
                run_stats["csv_path"] = csv_path
                print(f"\n{Fore.GREEN}CSV saved: {csv_path}{Style.RESET_ALL}")
                logger.info(f"CSV export: {len(all_db_leads)} leads -> {csv_path}")
            except Exception as exc:
                logger.error(f"CSV export failed: {exc}", exc_info=True)

        db.end_session(run_stats)
    update_job_progress(100)

    supabase_url   = os.environ.get("SUPABASE_URL", "")
    dashboard_hint = (
        supabase_url.replace("supabase.co", "supabase.com/dashboard")
        if supabase_url else ""
    )
    return run_stats, dashboard_hint


def run_export_only(config: dict, logger: logging.Logger):
    logger.info("Export-only mode: reading all leads from Supabase")
    try:
        with SupabaseHandler(config) as db:
            min_score = config["filters"].get("min_lead_score", 0)
            leads     = db.get_all_leads(min_score=min_score)
    except Exception as exc:
        logger.error(f"Export failed: {exc}", exc_info=True)
        return {}, None

    if not leads:
        logger.warning("No leads in Supabase to export")
        return {}, None

    csv_path = export_csv(leads)
    stats    = {
        "total": len(leads), "raw_total": len(leads),
        "new": 0, "duplicates": 0, "errors": 0, "csv_path": csv_path,
    }
    return stats, None


# ---------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="leadparser",
        description="LeadParser -- Free local business lead generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config",      default="config.yaml")
    parser.add_argument("--city",        default=None,
        help="City to scrape; comma-separated for multiple (e.g. 'Seattle,Portland,Vancouver')")
    parser.add_argument("--state",       default=None,
        help="State to scrape; single value or comma-separated to match cities")
    parser.add_argument(
        "--limit", type=int, default=None,
        help="TARGET number of leads after all filters. "
             "The scraper over-collects raw results (4x) to guarantee this.",
    )
    parser.add_argument("--niche",       default=None,
        help="Niche to scrape; comma-separated for multiple (e.g. 'plumbers,electricians')")
    parser.add_argument(
        "--parser", default=None, dest="parser",
        choices=["playwright", "xhr", "selenium"],
        help="Override scraper parser (playwright/xhr/selenium)",
    )
    parser.add_argument(
        "--concurrent-xhr", type=int, default=None, dest="concurrent_xhr",
        help="Run N XHR scrapers in parallel (default: 4 when using XHR parser)",
    )
    parser.add_argument(
        "--job-id", default=None, dest="job_id",
        help="Supabase scraper_jobs UUID — enables live log streaming to dashboard",
    )
    # Per-job filter overrides (worker.py passes these from scraper_jobs columns)
    parser.add_argument("--min-reviews",     type=int,   default=None, dest="min_reviews")
    parser.add_argument("--max-reviews",     type=int,   default=None, dest="max_reviews")
    parser.add_argument("--min-rating",      type=float, default=None, dest="min_rating")
    parser.add_argument("--max-rating",      type=float, default=None, dest="max_rating")
    parser.add_argument("--exclude-website", action="store_true",       dest="exclude_website")
    parser.add_argument("--require-website", action="store_true",       dest="require_website")
    parser.add_argument("--require-phone",   action="store_true",       dest="require_phone")
    parser.add_argument("--min-score",       type=int,   default=None, dest="min_score")
    parser.add_argument("--export-only", action="store_true")
    parser.add_argument("--no-csv",      action="store_true")
    parser.add_argument("--dry-run",     action="store_true")
    parser.add_argument("--serve",       action="store_true")
    parser.add_argument("--port",        type=int, default=5000)
    return parser.parse_args()


def _apply_cli_overrides(config: dict, args: argparse.Namespace):
    colorama_init(autoreset=True)

    # Handle comma-separated cities
    if args.city:
        cities = [c.strip() for c in args.city.split(",") if c.strip()]
        if len(cities) == 1:
            config["location"]["city"] = cities[0]
            config["location"]["full_address"] = (
                f"{cities[0]}, {config['location'].get('state', '')}"
            )
            print(f"  {Fore.CYAN}City:{Style.RESET_ALL} {cities[0]}")
        else:
            # Store multiple cities for run_pipeline to use
            config["_cli_cities"] = cities
            print(f"  {Fore.CYAN}Cities:{Style.RESET_ALL} {', '.join(cities)}")

    if args.state:
        states = [s.strip() for s in args.state.split(",") if s.strip()]
        if len(states) == 1:
            config["location"]["state"] = states[0]
            config["location"]["full_address"] = (
                f"{config['location'].get('city', '')}, {states[0]}"
            )
            print(f"  {Fore.CYAN}State:{Style.RESET_ALL} {states[0]}")
        else:
            config["_cli_states"] = states
            print(f"  {Fore.CYAN}States:{Style.RESET_ALL} {', '.join(states)}")

    if args.limit is not None:
        # Over-collect 10x raw listings so filters still leave us with the target.
        # The pipeline retries with a higher raw limit if the first pass falls short.
        # Cap at 1000 to keep run times reasonable.
        raw_limit = min(args.limit * 10, 1000)
        config["scraping"]["max_results_per_niche"] = raw_limit
        config["scraping"]["target_leads"]          = args.limit
        print(
            f"  {Fore.CYAN}Target:{Style.RESET_ALL} {args.limit} filtered leads "
            f"(collecting up to {raw_limit} raw, retrying if needed)"
        )

    if args.parser is not None:
        config["scraping"]["parser"] = args.parser
        print(f"  {Fore.CYAN}Parser:{Style.RESET_ALL} {args.parser}")
    
    if args.concurrent_xhr is not None:
        config["scraping"]["concurrent_xhr"] = args.concurrent_xhr
        print(f"  {Fore.CYAN}Concurrent XHR workers:{Style.RESET_ALL} {args.concurrent_xhr}")

    # Apply per-job filter overrides from CLI (worker.py passes these)
    filters = config.setdefault("filters", {})
    if args.min_reviews is not None:
        filters["min_reviews"] = args.min_reviews
        print(f"  {Fore.CYAN}Min reviews:{Style.RESET_ALL} {args.min_reviews}")
    if args.max_reviews is not None:
        filters["max_reviews"] = args.max_reviews
        print(f"  {Fore.CYAN}Max reviews:{Style.RESET_ALL} {args.max_reviews}")
    if args.min_rating is not None:
        filters["min_rating"] = args.min_rating
        print(f"  {Fore.CYAN}Min rating:{Style.RESET_ALL} {args.min_rating}")
    if args.max_rating is not None:
        filters["max_rating"] = args.max_rating
        print(f"  {Fore.CYAN}Max rating:{Style.RESET_ALL} {args.max_rating}")
    if args.exclude_website:
        filters["exclude_with_website"] = True
        print(f"  {Fore.CYAN}Filter:{Style.RESET_ALL} no website only")
    if args.require_website:
        filters["require_website"] = True
        print(f"  {Fore.CYAN}Filter:{Style.RESET_ALL} has website only")
    if args.require_phone:
        filters["require_phone"] = True
        print(f"  {Fore.CYAN}Require phone:{Style.RESET_ALL} yes")
    if args.min_score is not None:
        filters["min_lead_score"] = args.min_score
        print(f"  {Fore.CYAN}Min lead score:{Style.RESET_ALL} {args.min_score}")


def _launch_dashboard(port: int):
    import subprocess
    from threading import Timer
    import webbrowser

    dashboard = Path(__file__).parent / "dashboard.py"
    if not dashboard.exists():
        print(f"\n{Fore.RED}dashboard.py not found — skipping.{Style.RESET_ALL}")
        return

    url = f"http://localhost:{port}"
    print(f"\n{Fore.CYAN}Starting dashboard → {url}{Style.RESET_ALL}")
    subprocess.Popen([sys.executable, str(dashboard), "--port", str(port)])
    Timer(1.5, webbrowser.open, args=[url]).start()


def main():
    print_banner()
    load_dotenv()
    args   = parse_args()
    config = load_config(args.config)
    _apply_cli_overrides(config, args)
    logger = setup_logging(config, job_id=args.job_id)

    start = time.time()

    try:
        if args.export_only:
            stats, _url = run_export_only(config, logger)
        else:
            stats, _url = run_pipeline(config, args, logger)
    except KeyboardInterrupt:
        logger.warning("Interrupted by user (Ctrl+C)")
        sys.exit(0)
    except Exception as exc:
        logger.exception(f"Fatal error: {exc}")
        sys.exit(1)

    elapsed = time.time() - start
    logger.info(f"Total runtime: {elapsed:.0f}s")
    print_stats(
        stats,
        dashboard_url=stats.get("dashboard_url"),
        csv_path=stats.get("csv_path"),
    )

    if args.serve:
        _launch_dashboard(args.port)

    # Flush any remaining buffered Supabase log entries
    for handler in logging.getLogger().handlers:
        if isinstance(handler, SupabaseLogHandler):
            handler.flush()


if __name__ == "__main__":
    main()
