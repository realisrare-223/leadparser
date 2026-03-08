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
import csv
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

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

    location     = config["location"]
    target_count = config["scraping"].get("target_leads")

    run_stats: dict = {
        "niches": len(niches), "raw_total": 0, "total": 0,
        "new": 0, "duplicates": 0, "errors": 0,
    }

    update_job_progress(5)

    with SupabaseHandler(config) as db:

        session_id = db.start_session(niches, config)
        logger.info(
            f"Session #{session_id} | {len(niches)} niche(s) | "
            f"location: {location['city']}, {location['state']}"
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
        scraper      = ScraperClass(config, rate_limiter, proxy_mgr)

        # Context-manager support: Selenium/Playwright scrapers may need __enter__
        if hasattr(scraper, "__enter__"):
            scraper.__enter__()

        # seen_gmb: dedup across retry passes so we never count a lead twice
        seen_gmb: set[str] = set()
        raw_bucket: list[dict] = []   # all unique pre-filter leads accumulated so far
        all_leads: list[dict] = []

        MAX_PASSES = 3  # up to 3 passes; each doubles the raw-results ceiling

        try:
            for pass_num in range(MAX_PASSES):
                if pass_num > 0:
                    # Increase raw ceiling 2× for the retry — the scraper will
                    # explore more search-expansion terms it skipped first time.
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

                for niche_i, niche in enumerate(niches, start=1):
                    print(
                        f"  [{niche_i}/{len(niches)}] {Fore.CYAN}{niche}{Style.RESET_ALL} "
                        f"in {location['city']}, {location['state']}"
                    )

                    # Per-listing progress: spans 10%→70% across niches × passes
                    _niche_count = len(niches)
                    _niche_start = 10 + int(((niche_i - 1) / _niche_count) * 60)
                    _niche_end   = 10 + int((niche_i        / _niche_count) * 60)
                    _niche_width = max(_niche_end - _niche_start, 1)

                    def _listing_progress(current: int, total: int,
                                          _s=_niche_start, _w=_niche_width) -> None:
                        frac = current / max(total, 1)
                        update_job_progress(_s + int(frac * _w))

                    try:
                        raw_leads = scraper.scrape_niche(
                            niche, location, on_progress=_listing_progress
                        )
                    except Exception as exc:
                        logger.error(f"Scraping failed for '{niche}': {exc}", exc_info=True)
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
                                raw_bucket.append(lead)
                                run_stats["raw_total"] += 1
                                new_this_pass += 1
                        except Exception as exc:
                            logger.warning(f"Lead build failed: {exc}", exc_info=True)
                            run_stats["errors"] += 1

                    logger.info(
                        f"  -> {len(raw_leads)} raw scraped, "
                        f"{new_this_pass} new unique leads for '{niche}'; "
                        f"running total: {run_stats['raw_total']}"
                    )

                # ── Check after each full niche-pass whether target is met ──
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
                            f"{have}/{need} filtered leads available in this niche/city."
                        )
                        print(
                            f"{Fore.YELLOW}Note:{Style.RESET_ALL} "
                            f"Only {Fore.GREEN}{have}{Style.RESET_ALL}/{need} leads "
                            f"available after {MAX_PASSES} passes — "
                            f"Google Maps may be exhausted for this niche/city."
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
    parser.add_argument("--city",        default=None)
    parser.add_argument("--state",       default=None)
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

    if args.city:
        config["location"]["city"] = args.city
        config["location"]["full_address"] = (
            f"{args.city}, {config['location'].get('state', '')}"
        )
        print(f"  {Fore.CYAN}City:{Style.RESET_ALL} {args.city}")

    if args.state:
        config["location"]["state"] = args.state
        config["location"]["full_address"] = (
            f"{config['location'].get('city', '')}, {args.state}"
        )
        print(f"  {Fore.CYAN}State:{Style.RESET_ALL} {args.state}")

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
