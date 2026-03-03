# LeadParser v1 — Project Memory

## Project Overview
- **Purpose**: Free local business lead generation via Google Maps scraping
- **Stack**: Python 3.10+, Selenium, undetected-chromedriver, SQLite, Flask
- **Config**: All settings in `config.yaml` — no code changes needed for most runs

## Key Files
- [main.py](../main.py) — Pipeline orchestrator + CLI entry point
- [config.yaml](../config.yaml) — All user settings (city, niches, delays, filters)
- [dashboard.py](../dashboard.py) — Flask localhost dashboard (new — shows no-website leads)
- [scrapers/google_maps.py](../scrapers/google_maps.py) — Primary scraper
- [scrapers/base_scraper.py](../scrapers/base_scraper.py) — Selenium base with anti-bot
- [exporters/sqlite_handler.py](../exporters/sqlite_handler.py) — Deduplication + storage
- [data/leads_latest.csv](../data/leads_latest.csv) — Always the most recent export

## Run Commands
```bash
# Basic run
python main.py

# With CLI overrides (city, state, max results per niche)
python main.py --city "Dallas" --state TX --limit 40

# Run + open dashboard automatically
python main.py --city "Miami" --state FL --limit 30 --serve

# Dashboard only (view existing data)
python dashboard.py
python dashboard.py --open   # auto-opens browser

# Re-export existing DB to CSV without scraping
python main.py --export-only --no-sheets
```

## CLI Arguments (main.py)
- `--city "City Name"` — Override location city
- `--state XX` — Override state abbreviation
- `--limit N` — Max results per niche (overrides config)
- `--niche "plumbers"` — Single niche only
- `--serve` — Launch dashboard after run (opens browser)
- `--port N` — Dashboard port (default 5000, used with --serve)
- `--no-sheets` — Skip Google Sheets export
- `--export-only` — Re-export DB to CSV/Sheets without scraping
- `--dry-run` — Scrape but don't save

## Dashboard (dashboard.py)
- URL: http://localhost:5000
- Filters to businesses WITHOUT a website automatically
- Sortable/searchable table via DataTables.js
- Color-coded by lead score: HOT (18+), WARM (12-17), MED (7-11), LOW (<7)
- JSON APIs: /api/leads, /api/stats
- Reads data/leads_latest.csv on every page load

## Performance Settings (config.yaml)
- `delay_min: 1.0` / `delay_max: 2.5` — rate limit between requests
- `scroll_pause_time: 1.0` — pause between scroll actions
- `max_results_per_niche: 25` — default cap (override with --limit)
- `headless: true` — hidden browser (faster)
- Hours button click removed from google_maps.py — saves ~0.5s per business

## Filter Behavior
- `exclude_with_website: true` in config (default) — only no-website leads
- Filter also defaults to True in apply_filters() code fallback
- Dashboard independently filters no-website rows from CSV

## Lead Score Tiers
- 18+ = HOT (brand new / high-value niche / no website)
- 12-17 = WARM
- 7-11 = MEDIUM
- <7 = LOW

## Output
- CSV: `data/leads_latest.csv` + timestamped copy
- SQLite: `data/leads.db`
- 22-column format (niche, name, phone, address, city, state, zip, hours, reviews, rating, gmb_link, website, facebook, instagram, source, date, score, pitch, notes, call_status, follow_up_date)
