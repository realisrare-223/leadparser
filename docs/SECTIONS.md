# LeadParser — Section Guide & Upgrade Paths

This document explains every major section of LeadParser: what it does,
how it's currently implemented, and exactly how/when to upgrade it.

---

## 1. Niche System

### What it does
The niche system controls *what types of businesses* the scraper looks for.
A niche is a search term like `"restaurants"` or `"plumbers"`.

### Where it lives
| File | Role |
|------|------|
| `vercel-app/lib/niches.ts` | Dropdown options for the dashboard (grouped, with sublabels) |
| `leadparser/scrapers/google_maps.py` — `NICHE_EXPANSIONS` | Maps each niche to 6–12 keyword variants searched automatically |
| `leadparser/config.yaml` — `niches:` | Default niche(s) used when running `main.py` from the CLI |

### General Categories
Entries marked **(General)** in the dropdown (e.g. "Food (General)") send a broad
keyword to the scraper. `NICHE_EXPANSIONS` then searches every sub-niche in that
category automatically. For example `"food"` expands to:
`restaurants → cafes → coffee shops → pizzerias → bakeries → bars → fast food → …`

### When to upgrade
- **Add a new specific niche**: add the string to `NICHE_COMBO_OPTIONS` in
  `niches.ts` + a matching key in `NICHE_EXPANSIONS` in `google_maps.py`.
- **Add keyword variants to an existing niche**: find the key in `NICHE_EXPANSIONS`
  and append to its list. More variants = more raw leads per run.
- **Add a new General category**: add an entry with `group: 'General Categories'`
  in `niches.ts` and a key in `NICHE_EXPANSIONS` whose expansion list contains
  all relevant sub-niche search terms.

---

## 2. City / Location System

### What it does
Determines *where* the scraper looks. City and state/province are passed to every
Google Maps search query as `"{niche} in {city}, {state}"`.

### Where it lives
| File | Role |
|------|------|
| `vercel-app/lib/cities.ts` — `MAJOR_CITIES` | ~220 major NA cities for city autocomplete |
| `vercel-app/lib/north-america.ts` — `NA_REGIONS` | All US states + Canadian provinces for state autocomplete |
| `vercel-app/components/ScraperPanel.tsx` | City combobox auto-fills State when a known city is selected |
| `leadparser/config.yaml` — `location:` | Default city/state for CLI runs |

### When to upgrade
- **Add more cities to autocomplete**: append to `MAJOR_CITIES` in `cities.ts`.
  Format: `{ city: 'Fort McMurray', state: 'AB', country: 'CA' }`.
- **Add international regions**: add entries to `NA_REGIONS` in `north-america.ts`
  (or rename the file to `regions.ts` and add `country: 'UK'` etc.).
- **Multi-city scraping**: queue multiple jobs from the dashboard, one per city.
  The worker runs them in sequence (parallel workers = parallel cities).

---

## 3. Scraper Engine (Google Maps)

### What it does
Phase 1 of the pipeline. Opens a Selenium browser, searches Google Maps for
`"{niche} in {city}, {state}"`, scrolls the results feed to collect business
profile URLs, then visits each URL to extract: name, phone, address, rating,
review count, website, hours.

### Where it lives
| File | Role |
|------|------|
| `leadparser/scrapers/google_maps.py` | Full scraper: `scrape_niche()`, `_collect_result_urls()`, `_extract_business()` + all field extractors |
| `leadparser/scrapers/base_scraper.py` | Selenium driver setup, undetected-chromedriver, helper methods |
| `leadparser/config.yaml` — `scraping:` | `headless`, `delay_min/max`, `max_results_per_niche`, `max_scroll_attempts` |

### Key config knobs
```yaml
scraping:
  max_results_per_niche: 200   # raise for bigger jobs (default 100 when --limit 50)
  max_scroll_attempts:   30    # scrolls before giving up on a search
  delay_min: 2.0               # seconds between requests (lower = faster, riskier)
  headless: true               # false = visible browser for debugging
```

### When to upgrade
- **More results per query**: raise `max_scroll_attempts` (Google Maps typically
  caps at 120 results per search; more scrolls won't help beyond that).
- **Faster runs**: lower `delay_min` / `delay_max` — risk: more CAPTCHAs.
- **CAPTCHA handling**: detect `"/sorry/"` in the URL inside `_safe_get()` and
  pause + log a warning instead of returning empty.
- **Playwright migration**: Playwright has better stealth and auto-wait. Swap
  `base_scraper.py` to use `playwright.sync_api`. Slower to set up, more reliable
  long-term.
- **Headless detection**: Google changes anti-bot signals periodically. If the
  scraper starts returning 0 results, try `headless: false` first to diagnose.

---

## 4. Supplementary Scrapers (Phone Enrichment)

### What it does
Phase 2. For every lead that came back from Google Maps *without* a phone number,
the supplementary scrapers search Yelp, Yellow Pages, WhitePages, and BBB to find
the phone.

### Where it lives
| File | Role |
|------|------|
| `leadparser/scrapers/supplementary.py` | Orchestrator — loops through missing-phone leads |
| `leadparser/scrapers/yelp_scraper.py` | Searches Yelp by business name + city |
| `leadparser/scrapers/yellow_pages.py` | Searches YP / WhitePages / BBB |
| `leadparser/config.yaml` — `supplementary_scrapers:` | Enable/disable each source |

### Current limitation
All sources are US-centric. **Canadian / international leads won't get enriched**
here — their phone must come from Google Maps directly.

### When to upgrade
- **Add Canada 411**: create `canada411_scraper.py`, scrape
  `canada411.ca/search/si/1/{name}/{city}+{province}/`, add to `supplementary.py`.
- **Add more US sources**: add `manta.py` (Manta.com) or `bbb.py` as standalone
  scrapers following the same pattern as `yelp_scraper.py`.
- **Email extraction**: after finding a website URL on Google Maps, visit the
  `/contact` page and scrape `mailto:` links with a regex. Store in an `email`
  column (requires a Supabase schema migration to add the column first).

---

## 5. Lead Filtering

### What it does
Phase 3. Drops leads that don't meet the configured criteria before saving.

### Where it lives
| File | Role |
|------|------|
| `leadparser/main.py` — `apply_filters()` | The filter logic |
| `leadparser/config.yaml` — `filters:` | Default filter values |
| `leadparser/vercel-app/components/ScraperPanel.tsx` | Per-job filter overrides in the dashboard UI |
| `leadparser/worker.py` | Translates job filter fields → CLI flags passed to `main.py` |

### Available filters
| Filter | Default | Notes |
|--------|---------|-------|
| `min_reviews` | 0 | Drop leads with fewer reviews |
| `max_reviews` | 9999 | Drop leads with more reviews (targets small businesses) |
| `min_rating` | 0.0 | |
| `max_rating` | 5.0 | |
| `exclude_with_website` | false | Only leads with no website |
| `require_website` | false | Only leads that have a website |
| `require_phone` | false | Drop leads without a phone number |
| `min_lead_score` | 0 | |

### When to upgrade
- **Add a new filter**: add a param to `apply_filters()` in `main.py`, add a CLI
  flag in `parse_args()`, add the UI control in `ScraperPanel.tsx`, and add the
  `worker.py` line that passes it to main.
- **Filter by city/radius**: add a bounding-box check in `apply_filters()` using
  the lead's parsed address — useful for tight geographic campaigns.
- **Filter by category**: Google Maps returns a `category` field (e.g. "Italian
  Restaurant"). Filter to only keep businesses whose category matches a keyword.

---

## 6. Lead Scoring

### What it does
Assigns a numeric score (0–31) to each lead based on review count, rating,
website presence, and niche. Higher score = better cold-call target.

### Where it lives
| File | Role |
|------|------|
| `leadparser/utils/lead_scorer.py` | Scoring logic |
| `leadparser/config.yaml` — `scoring:` | All score weights (edit without touching code) |
| `leadparser/config.yaml` — `high_value_niches:` | Niches that earn the niche bonus |

### Score thresholds
| Score | Label |
|-------|-------|
| ≥ 22  | HOT   |
| ≥ 15  | WARM  |
| ≥ 8   | MEDIUM |
| < 8   | LOW   |

### When to upgrade
- **Reweight signals**: edit the `scoring:` block in `config.yaml` — no code change needed.
- **Add new signals**: e.g. "no Facebook page" → add `has_facebook` to the scraper
  output, then add a scoring rule in `lead_scorer.py`.
- **AI scoring**: replace the rule-based scorer with a prompt sent to Claude or
  a local Ollama model that reads the business name, category, reviews, and city
  to produce a score + reasoning. See `ARCHITECTURE.md §7`.

---

## 7. Pitch Engine

### What it does
Auto-generates a cold-call opening line for each lead, stored in `pitch_notes`.
Callers see it in their dashboard to sound prepared.

### Where it lives
| File | Role |
|------|------|
| `leadparser/utils/pitch_engine.py` | Generates pitch from template + lead data |
| `leadparser/config.yaml` — `pitch_templates:` | One template per niche; `{name}`, `{city}`, `{review_count}`, `{rating}` placeholders |

### When to upgrade
- **Add a niche pitch**: add a key matching the niche name to `pitch_templates:` in
  `config.yaml`. No code change needed.
- **AI-generated pitches**: replace the template lookup with a call to the
  Anthropic API (or Ollama) that receives the full lead context and returns a
  personalised 2-sentence opener.
- **Multi-language pitches**: add a `language:` field to the config and pass it
  to the pitch engine / API call.

---

## 8. Database (Supabase)

### What it does
Central PostgreSQL database. Stores leads, callers, scraper jobs, logs, and
auth users. The Python scraper writes via service role key (bypasses RLS).
The dashboard reads via anon key (respects RLS — callers see only their leads).

### Where it lives
| File | Role |
|------|------|
| `leadparser/supabase/schema.sql` | Full schema — run once in Supabase SQL Editor |
| `leadparser/supabase/*.sql` | Migration scripts for adding columns/tables |
| `leadparser/exporters/supabase_handler.py` | Python upsert logic + dedup key |

### When to upgrade
- **Add a column**: add it to `schema.sql`, run a migration in Supabase SQL Editor
  (`ALTER TABLE leads ADD COLUMN email text DEFAULT '';`), then add the field to
  `_prepare_row()` in `supabase_handler.py` and `LEAD_COLUMNS`.
- **Add a table**: write a migration `.sql` file, run it in Supabase, update
  `types.ts` in the dashboard.
- **Email column** (planned): `ALTER TABLE leads ADD COLUMN email text DEFAULT '';`
  then add `"email"` back to `LEAD_COLUMNS` and `_prepare_row`.

---

## 9. Worker & Job Queue

### What it does
`worker.py` runs permanently on your machine/VPS. It polls the `scraper_jobs`
Supabase table every 5 seconds, picks up pending jobs, and spawns `main.py` as a
subprocess with the right flags. It also sends a heartbeat every 10s so the
dashboard can show the engine status.

### Where it lives
| File | Role |
|------|------|
| `leadparser/worker.py` | Heartbeat + job polling loop |
| Supabase `scraper_jobs` table | Job queue (status, filters, city, niche) |
| Supabase `worker_status` table | Heartbeat timestamp |

### When to upgrade
- **Multiple workers**: run `worker.py` on multiple machines. Use a Supabase
  `SELECT ... FOR UPDATE SKIP LOCKED` query instead of the current `eq('status','pending')`
  so two workers don't grab the same job.
- **Scheduled scrapes**: add a cron column to `scraper_jobs`; have worker check
  for jobs whose `scheduled_at <= now()`.
- **Cloud worker**: deploy `worker.py` as a Railway/Render background worker
  so it runs 24/7 without needing your machine.

---

## 10. Dashboard (Next.js / Vercel)

### What it does
Web UI for admins and callers. Admins queue scraper jobs, assign leads to callers,
and view stats. Callers see their assigned leads and update status/notes.

### Where it lives
```
vercel-app/
  app/
    login/         Email + password auth
    dashboard/     Caller view
    admin/         Admin view (ScraperPanel + StatsGrid + AssignPanel + LeadTable)
  components/
    ScraperPanel   Queue jobs, live logs, progress bars
    LeadTable      Sortable table with inline status + notes
    StatsGrid      KPI cards + per-caller breakdown
    AssignPanel    Assign N leads to a caller
    Combobox       Reusable grouped autocomplete
  lib/
    niches.ts      All niche options (grouped, with General categories)
    cities.ts      Major NA cities for city autocomplete
    north-america.ts  US/CA/MX states & provinces
```

### When to upgrade
- **Add a new niche to the dropdown**: edit `lib/niches.ts` only.
- **Add a city to autocomplete**: edit `lib/cities.ts` — append to `MAJOR_CITIES`.
- **Add a new General category**: add an entry in `lib/niches.ts` with
  `group: 'General Categories'` and a matching key in `NICHE_EXPANSIONS`
  in `google_maps.py`.
- **Lead detail drawer**: add an `onClick` handler on `LeadTable` rows that opens
  a slide-over panel with all fields + pitch notes + GMB link.
- **Bulk status update**: add checkboxes to `LeadTable` + a bulk-action toolbar.
- **Export selected**: add a "Download CSV" button that generates a CSV from
  currently-filtered rows.

---

## 11. Auth & Roles

### What it does
Supabase Auth (email + password). Two roles: `caller` and `admin`. RLS policies
enforce that callers only see leads assigned to them.

### When to upgrade
- **Add magic-link auth**: Supabase supports this natively — enable in dashboard,
  add a `/api/auth/magic` route.
- **Google / GitHub OAuth**: enable in Supabase Auth > Providers, add a button
  in `login/page.tsx`.
- **Invite-only registration**: add a Supabase function that checks an
  `invites` table before allowing sign-up.

---

## Quick-Reference: What's Easy to Change

| Change | Difficulty | Files |
|--------|-----------|-------|
| Add niche to dropdown | ★☆☆ | `lib/niches.ts` |
| Add keyword variants to niche | ★☆☆ | `google_maps.py` → `NICHE_EXPANSIONS` |
| Add a General category | ★☆☆ | `niches.ts` + `google_maps.py` |
| Add city to autocomplete | ★☆☆ | `lib/cities.ts` |
| Change scoring weights | ★☆☆ | `config.yaml` → `scoring:` |
| Add/edit a pitch template | ★☆☆ | `config.yaml` → `pitch_templates:` |
| Add a new lead filter | ★★☆ | `main.py` + `worker.py` + `ScraperPanel.tsx` |
| Add a DB column | ★★☆ | Supabase SQL + `supabase_handler.py` + `types.ts` |
| Add a supplementary scraper | ★★☆ | new `scrapers/xxx_scraper.py` + `supplementary.py` |
| Email extraction | ★★★ | new scraper + DB column migration |
| AI pitch personalisation | ★★★ | `pitch_engine.py` → Anthropic/Ollama call |
| Multi-tenant SaaS | ★★★ | schema + auth + worker `--tenant-id` flag |

---

*Last updated: 2026-03-07*
