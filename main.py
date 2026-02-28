#!/usr/bin/env python3
"""
LeadParser -- Automated Local Business Lead Generation Pipeline
==============================================================
Scrapes Google Business listings (and supplementary free sources)
to build cold-calling lead lists, then exports everything to Google Sheets.

ALL tools and services used are 100% FREE -- no paid API keys required.

Quick start
-----------
  1. pip install -r requirements.txt
  2. Edit config.yaml  (set your city, state, and target niches)
  3. Follow setup_guide.md to get a free Google Sheets credentials.json
  4. python main.py

Full usage
----------
  python main.py                          # Run with default config.yaml
  python main.py --config my_config.yaml  # Use a different config file
  python main.py --export-only            # Re-export from SQLite (no scraping)
  python main.py --niche "plumbers"       # Scrape a single niche
  python main.py --no-sheets             # Scrape but skip Google Sheets export
  python main.py --dry-run               # Scrape but don't save anything
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
from scrapers.google_maps   import GoogleMapsScraper
from scrapers.supplementary import SupplementaryScraper
from exporters.sqlite_handler  import SQLiteHandler
from exporters.sheets_exporter import SheetsExporter
from utils.rate_limiter     import RateLimiter
from utils.proxy_manager    import ProxyManager
from utils.phone_validator  import PhoneValidator
from utils.address_parser   import AddressParser
from utils.lead_scorer      import LeadScorer
from utils.pitch_engine     import PitchEngine
from utils.sentiment_analyzer import SentimentAnalyzer

# ---------------------------------------------------------------------


def setup_logging(config: dict) -> logging.Logger:
    """Configure rotating file + console logging."""
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

    # Quieten noisy third-party loggers
    for noisy in ("selenium", "urllib3", "undetected_chromedriver", "WDM"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logger = logging.getLogger("leadparser.main")
    logger.info(f"LeadParser started | log: {log_file}")
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
) -> dict:
    """
    Transform a raw scraped dict into the canonical 22-column lead dict.

    Applies:
      * Address component parsing (street / city / state / zip)
      * Phone number formatting / validation
      * Lead scoring
      * Sales pitch template population
    """
    # Parse address into components
    addr_parts = parser.infer_city_state(
        raw.get("address", ""), config["location"]
    )

    # Format phone numbers
    phone     = validator.format(raw.get("phone",           ""))
    sec_phone = validator.format(raw.get("secondary_phone", ""))

    # Compute lead score
    score = scorer.score(raw, niche, config)

    # Generate pitch
    pitch = pitcher.generate(niche, raw, config)

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

    # Flag leads with no phone so the operator knows to do manual lookup
    if not lead["phone"]:
        flag = "Phone Number Needed - Manual Research Required"
        if flag not in lead["additional_notes"]:
            sep = " | " if lead["additional_notes"] else ""
            lead["additional_notes"] += sep + flag
        lead["phone"] = "NOT FOUND"

    return lead


def apply_filters(leads: list[dict], config: dict) -> list[dict]:
    """
    Filter leads based on the criteria in config.yaml -> filters.
    Returns only the leads that pass all filters.
    """
    f = config.get("filters", {})
    min_reviews         = f.get("min_reviews",          0)
    max_reviews         = f.get("max_reviews",          9999)
    min_rating          = f.get("min_rating",           0.0)
    max_rating          = f.get("max_rating",           5.0)
    exclude_with_web    = f.get("exclude_with_website", False)
    min_score           = f.get("min_lead_score",       0)

    filtered = []
    for lead in leads:
        reviews = int(lead.get("review_count", 0) or 0)
        try:
            rating = float(lead.get("rating", 0.0) or 0.0)
        except (TypeError, ValueError):
            rating = 0.0

        score = int(lead.get("lead_score", 0) or 0)

        if reviews < min_reviews:
            continue
        if reviews > max_reviews:
            continue
        if rating and rating < min_rating:
            continue
        if rating and rating > max_rating:
            continue
        if exclude_with_web and lead.get("website"):
            continue
        if score < min_score:
            continue

        filtered.append(lead)

    return filtered


def print_banner():
    """Print a colorful startup banner."""
    colorama_init(autoreset=True)
    sep = "=" * 60
    print(f"\n{Fore.CYAN}{sep}")
    print(f"  LeadParser -- Free Local Business Lead Gen")
    print(f"  All tools: 100% FREE  |  No paid APIs")
    print(f"{sep}{Style.RESET_ALL}\n")


def export_csv(leads: list[dict], output_dir: str = "data") -> str:
    """
    Write all leads to a timestamped CSV file in *output_dir*.
    Returns the file path.  Always overwrites the 'leads_latest.csv'
    convenience symlink so you always know where to look.
    """
    from exporters.sheets_exporter import DISPLAY_HEADERS, LEAD_KEYS

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    dated_path = Path(output_dir) / f"leads_{timestamp}.csv"
    latest_path = Path(output_dir) / "leads_latest.csv"

    for path in (dated_path, latest_path):
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(DISPLAY_HEADERS)
            for lead in leads:
                writer.writerow([str(lead.get(k, "") or "") for k in LEAD_KEYS])

    return str(dated_path)


def print_stats(stats: dict, url: str = None, csv_path: str = None):
    """Print a summary report after the run."""
    sep = "-" * 60
    print(f"\n{Fore.GREEN}{sep}")
    print(f"  Run Complete")
    print(f"{sep}{Style.RESET_ALL}")
    print(f"  Niches searched : {stats.get('niches',      0)}")
    print(f"  Total scraped   : {stats.get('total',       0)}")
    print(f"  New leads saved : {stats.get('new',         0)}")
    print(f"  Duplicates skip : {stats.get('duplicates',  0)}")
    print(f"  Errors          : {stats.get('errors',      0)}")
    if csv_path:
        print(f"\n  CSV: {csv_path}")
        print(f"  CSV (latest): data/leads_latest.csv")
    if url:
        print(f"\n  Google Sheets: {url}")
    print()


# ---------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------

def run_pipeline(config: dict, args: argparse.Namespace, logger: logging.Logger):
    """
    Full lead-generation pipeline:
      1. Scrape Google Maps for each niche
      2. Supplement missing phones from Yelp / Yellow Pages / BBB
      3. Score leads and generate pitch notes
      4. Deduplicate against SQLite
      5. Export new leads to Google Sheets
    """

    # -- Initialise shared services ------------------------------------
    rate_limiter = RateLimiter(config)
    proxy_mgr    = ProxyManager(config)
    validator    = PhoneValidator()
    addr_parser  = AddressParser()
    scorer       = LeadScorer(config)
    pitcher      = PitchEngine(config)

    # Refresh proxy pool if enabled
    if config["proxies"].get("enabled"):
        proxy_mgr.refresh()

    # Determine which niches to run
    niches    = config["niches"]
    if args.niche:
        niches = [args.niche]
    location  = config["location"]

    all_leads:    list[dict] = []
    run_stats:    dict       = {
        "niches": len(niches), "total": 0, "new": 0,
        "duplicates": 0, "errors": 0
    }

    # -- Open database -------------------------------------------------
    with SQLiteHandler(config) as db:

        session_id = db.start_session(niches, config)
        logger.info(
            f"Session #{session_id} | "
            f"{len(niches)} niche(s) | location: {location['city']}, {location['state']}"
        )

        if not args.export_only:
            # -- PHASE 1: Google Maps scraping -------------------------
            print(f"\n{Fore.YELLOW}Phase 1: Scraping Google Maps...{Style.RESET_ALL}")

            with GoogleMapsScraper(config, rate_limiter, proxy_mgr) as gm_scraper:
                for i, niche in enumerate(niches, start=1):
                    print(
                        f"  [{i}/{len(niches)}] {Fore.CYAN}{niche}{Style.RESET_ALL} "
                        f"in {location['city']}, {location['state']}"
                    )
                    try:
                        raw_leads = gm_scraper.scrape_niche(niche, location)
                    except Exception as exc:
                        logger.error(f"Scraping failed for '{niche}': {exc}")
                        run_stats["errors"] += 1
                        continue

                    # Build canonical lead dicts
                    for raw in raw_leads:
                        try:
                            lead = build_lead(
                                raw, niche, config,
                                scorer, pitcher, validator, addr_parser
                            )
                            all_leads.append(lead)
                            run_stats["total"] += 1
                        except Exception as exc:
                            logger.warning(f"Lead build failed: {exc}")
                            run_stats["errors"] += 1

                    logger.info(
                        f"  -> {len(raw_leads)} raw leads for '{niche}'; "
                        f"running total: {run_stats['total']}"
                    )

            # -- PHASE 2: Supplementary phone/social enrichment --------
            if all_leads:
                print(f"\n{Fore.YELLOW}Phase 2: Supplementary enrichment...{Style.RESET_ALL}")
                supp = SupplementaryScraper(config, rate_limiter)
                supp.enrich_batch(all_leads)

            # -- PHASE 3: Apply filters --------------------------------
            before_filter = len(all_leads)
            all_leads     = apply_filters(all_leads, config)
            logger.info(
                f"Filters applied: {before_filter} -> {len(all_leads)} leads"
            )

            # -- PHASE 4: Deduplication + DB insert -------------------
            print(f"\n{Fore.YELLOW}Phase 3: Saving to local database...{Style.RESET_ALL}")
            insert_stats  = db.bulk_insert(all_leads)
            run_stats["new"]        = insert_stats["new"]
            run_stats["duplicates"] = insert_stats["duplicates"]
            run_stats["errors"]    += insert_stats["errors"]

            logger.info(
                f"DB insert: {insert_stats['new']} new, "
                f"{insert_stats['duplicates']} dupes, "
                f"{insert_stats['errors']} errors"
            )

        # -- PHASE 5: CSV export (always runs) -------------------------
        min_score       = config["filters"].get("min_lead_score", 0)
        all_db_leads    = db.get_all_leads(min_score=min_score)
        csv_path        = export_csv(all_db_leads)
        run_stats["csv_path"] = csv_path
        print(f"\n{Fore.GREEN}CSV saved: {csv_path}{Style.RESET_ALL}")
        logger.info(f"CSV export: {len(all_db_leads)} leads -> {csv_path}")

        # -- PHASE 6: Google Sheets export (optional) ------------------
        if not args.no_sheets:
            print(f"\n{Fore.YELLOW}Phase 4: Exporting to Google Sheets...{Style.RESET_ALL}")

            leads_to_export = db.get_unexported_leads(min_score=min_score)

            if leads_to_export:
                exporter = SheetsExporter(config)
                url      = exporter.export(leads_to_export)

                if url:
                    ids = [l["id"] for l in leads_to_export if "id" in l]
                    db.mark_exported(ids)
                    logger.info(f"Exported {len(leads_to_export)} leads -> {url}")
                    db.end_session(run_stats)
                    return run_stats, url
            else:
                logger.info("No new leads to export to Sheets (all already exported or below min score)")

        db.end_session(run_stats)

    return run_stats, None


def run_export_only(config: dict, logger: logging.Logger):
    """Re-export all leads from SQLite to Google Sheets without re-scraping."""
    logger.info("Export-only mode: reading all leads from database")
    with SQLiteHandler(config) as db:
        min_score = config["filters"].get("min_lead_score", 0)
        leads     = db.get_all_leads(min_score=min_score)

    if not leads:
        logger.warning("No leads in database to export")
        return {}, None

    exporter = SheetsExporter(config)
    url      = exporter.export(leads)
    stats    = {"total": len(leads), "new": len(leads), "duplicates": 0, "errors": 0}
    return stats, url


# ---------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="leadparser",
        description="LeadParser -- Free local business lead generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                           # Full run using config.yaml
  python main.py --config my_city.yaml    # Custom config file
  python main.py --niche "plumbers"       # Single niche
  python main.py --export-only            # Re-export existing DB -> Sheets
  python main.py --no-sheets              # Scrape & save DB, skip Sheets
  python main.py --dry-run                # Scrape only, no DB/Sheets writes
        """,
    )
    parser.add_argument(
        "--config",   default="config.yaml",
        help="Path to YAML configuration file (default: config.yaml)",
    )
    parser.add_argument(
        "--niche",    default=None,
        help="Scrape a single niche and exit",
    )
    parser.add_argument(
        "--export-only", action="store_true",
        help="Skip scraping; re-export existing database to Google Sheets",
    )
    parser.add_argument(
        "--no-sheets",   action="store_true",
        help="Scrape and save to SQLite but skip Google Sheets export",
    )
    parser.add_argument(
        "--dry-run",     action="store_true",
        help="Run scrapers but do not write to database or Google Sheets",
    )
    return parser.parse_args()


def main():
    print_banner()
    load_dotenv()    # Load .env file if present
    args   = parse_args()
    config = load_config(args.config)
    logger = setup_logging(config)

    start = time.time()

    try:
        if args.export_only:
            stats, url = run_export_only(config, logger)
        else:
            stats, url = run_pipeline(config, args, logger)
    except KeyboardInterrupt:
        logger.warning("Interrupted by user (Ctrl+C)")
        sys.exit(0)
    except Exception as exc:
        logger.exception(f"Fatal error: {exc}")
        sys.exit(1)

    elapsed = time.time() - start
    logger.info(f"Total runtime: {elapsed:.0f}s")

    print_stats(stats, url, csv_path=stats.get("csv_path"))


if __name__ == "__main__":
    main()
