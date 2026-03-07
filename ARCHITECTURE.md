# LeadParser — Architecture & Roadmap

> **Goal:** Sell as a monthly SaaS membership to local-business marketing agencies,
> freelancers, and cold-calling teams who need a steady pipeline of high-quality leads.

---

## 1. System Overview

LeadParser is a self-hosted (or Vercel-deployed) full-stack lead generation pipeline
with a real-time dashboard. It scrapes Google Maps for local business listings, enriches
them with supplementary data, scores them, and delivers them to a team of callers through
a mini-CRM.

```
┌─────────────────────────────────────────────────────────────────┐
│  Next.js 14 Dashboard (Vercel)                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  /login      │  │  /dashboard  │  │  /admin              │  │
│  │  (auth)      │  │  (callers)   │  │  (stats + assign)    │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│         │                 │                     │               │
│         └─────────────────┼─────────────────────┘               │
│                           │  REST API routes                    │
│  ┌────────────────────────▼────────────────────────────────┐    │
│  │  /api/leads  /api/admin/*  /api/scrape  /api/scrape/logs│    │
│  └────────────────────────┬────────────────────────────────┘    │
└───────────────────────────┼─────────────────────────────────────┘
                            │ Supabase JS client (anon key, RLS)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  Supabase (PostgreSQL + Auth + Realtime)                        │
│  ┌──────────┐ ┌────────────┐ ┌───────────┐ ┌────────────────┐  │
│  │  leads   │ │  callers   │ │scraper_jobs│ │  scraper_logs  │  │
│  └──────────┘ └────────────┘ └───────────┘ └────────────────┘  │
│  ┌────────────────────┐ ┌──────────────────────────────────┐    │
│  │  lead_stats (view) │ │  caller_stats (view)             │    │
│  └────────────────────┘ └──────────────────────────────────┘    │
└──────────────────────────────┬──────────────────────────────────┘
                               │ supabase-py (service role key)
                               │ writes leads + logs, reads jobs
┌──────────────────────────────▼──────────────────────────────────┐
│  Python Scraper Stack (runs on user's machine / VPS)            │
│                                                                  │
│  worker.py  ←── heartbeat every 10s, polls scraper_jobs         │
│      │                                                           │
│      └── spawns: python main.py --city ... --niche ... --job-id │
│                                                                  │
│  main.py (pipeline orchestrator)                                │
│  ├── Phase 1: GoogleMapsScraper (undetected-chromedriver)       │
│  ├── Phase 2: SupplementaryScraper (Yelp / YP / BBB)           │
│  ├── Phase 3: apply_filters()                                   │
│  ├── Phase 4: trim to --limit                                   │
│  ├── Phase 5: SupabaseHandler.bulk_insert()  (upsert)          │
│  └── Phase 6: CSV export                                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Key Files

```
leadparser/
├── main.py                   Pipeline orchestrator + CLI
├── worker.py                 Job queue poller (runs forever on machine)
├── config.yaml               Niches, location, filters, scoring weights
├── .env                      SUPABASE_URL + SUPABASE_KEY (service role)
│
├── scrapers/
│   ├── base_scraper.py       Selenium + undetected-chromedriver base class
│   ├── google_maps.py        Primary scraper (name, phone, address, rating)
│   ├── supplementary.py      Orchestrates Yelp / Yellow Pages / BBB
│   ├── yelp_scraper.py       Phone lookup via Yelp (US-centric)
│   └── yellow_pages.py       Phone lookup via YP / Whitepages / BBB
│
├── exporters/
│   └── supabase_handler.py   Upsert leads (MD5 dedup key)
│
├── utils/
│   ├── lead_scorer.py        Score = f(reviews, rating, website, niche)
│   ├── phone_validator.py    NANP validation via libphonenumber
│   ├── address_parser.py     City/state/zip extraction + CA province support
│   ├── pitch_engine.py       Auto-generate cold-call pitch notes
│   ├── rate_limiter.py       Delay between requests
│   └── proxy_manager.py      Optional proxy rotation
│
├── supabase/
│   ├── schema.sql            Full PostgreSQL schema (run once in Supabase)
│   └── *.sql                 Migration scripts (add columns, constraints)
│
└── vercel-app/               Next.js 14 dashboard
    ├── app/
    │   ├── login/            Email + password auth (Supabase Auth)
    │   ├── dashboard/        Caller view — assigned leads + status updates
    │   ├── admin/            Admin — stats, assign leads, full table
    │   └── api/              REST endpoints (scrape, leads, admin/*)
    ├── components/
    │   ├── ScraperPanel.tsx  Queue jobs, live logs, progress bars
    │   ├── LeadTable.tsx     Sortable table — inline status + notes
    │   ├── StatsGrid.tsx     KPI cards + per-caller breakdown
    │   └── AssignPanel.tsx   Assign N leads to a caller by niche/city
    └── lib/
        ├── types.ts           Lead, ScraperJob, CallerStats types
        ├── niches.ts          NICHE_COMBO_OPTIONS — grouped niche list with General categories
        ├── cities.ts          CITY_OPTIONS — major NA cities for city autocomplete
        ├── supabase/          Browser + server Supabase clients
        └── north-america.ts   US states + Canadian provinces lookup
```

---

## 3. Data Model (Supabase)

### `leads` table (key columns)
| Column          | Type      | Notes                                    |
|-----------------|-----------|------------------------------------------|
| id              | uuid PK   |                                          |
| dedup_key       | text UNIQUE | MD5(lower(name) + city)               |
| name            | text      |                                          |
| phone           | text      | UNIQUE idx (non-empty values only)       |
| address / city / state / zip | text |                              |
| review_count    | int       | Primary lead scoring signal              |
| rating          | text      |                                          |
| website         | text      |                                          |
| lead_score      | int       | 0–31 (see §6 scoring)                   |
| status          | enum      | new → called → followup → sold → dead   |
| assigned_to     | uuid FK   | callers.id — set atomically, never overwritten |
| niche           | text      |                                          |
| data_source     | text      | "Google Maps"                            |

### `scraper_jobs` table
Drives the worker queue. Dashboard writes rows; worker.py polls and runs them.

### `callers` table
| Column | Type  | Notes            |
|--------|-------|------------------|
| id     | uuid  |                  |
| email  | text  | matches auth.users |
| name   | text  |                  |
| role   | text  | 'caller' or 'admin' |

### Row-Level Security
- Callers see only `leads` where `assigned_to = auth.uid()`
- Admins bypass via a policy that checks `callers.role = 'admin'`
- Python scraper uses **service role key** (bypasses RLS)
- Dashboard uses **anon key** (respects RLS)

---

## 4. Lead Scoring (current)

| Signal            | Score |
|-------------------|-------|
| 26–100 reviews    | +15   |
| 101–300 reviews   | +10   |
| 6–25 reviews      | +8    |
| 301–600 reviews   | +5    |
| 1–5 reviews       | +3    |
| 600+ reviews      | +1    |
| 0 reviews         | +0    |
| Rating ≤ 3.0      | +5    |
| Rating 3.0–3.8    | +3    |
| Rating 3.8–4.5    | +1    |
| No website        | +4    |
| High-value niche  | +5    |
| Complete contact  | +2    |
| **Max possible**  | **31**|

Labels: ≥22 = HOT, ≥15 = WARM, ≥8 = MEDIUM, <8 = LOW

---

## 5. Known Limitations (current)

1. **Supplementary scrapers are US-only** — Yelp/Yellow Pages/BBB have thin
   Canadian/international coverage. For non-US cities, phones must be found
   directly on Google Maps (the phone DOM wait was fixed in v2).

2. **Single-machine scraper** — worker.py runs on one machine. Parallel scraping
   requires running multiple worker instances or a distributed queue.

3. **No CAPTCHA handling** — if Google serves a CAPTCHA, the scraper gets 0
   results for that search with no retry.

4. **Keyword expansion run-time** — "General" category jobs search 10–15 query
   variants, so a `--limit 50` job can take 15–30 min depending on city size.
   Consider using specific niches for faster targeted runs.

---

## 6. Short-Term Improvements (1–4 weeks)

### Scraper quality
- [x] **Multi-query strategy** — `NICHE_EXPANSIONS` dict in `google_maps.py` searches
      the canonical niche + up to 12 keyword variants per niche, union-deduped.
      General categories (food, medical, beauty…) expand to all sub-niches.
- [x] **Keyword expansion for all niches** — 60+ niches covered, 6–12 variants each.
- [ ] **CAPTCHA wait** — detect the CAPTCHA page by checking the URL or title;
      pause and log a warning instead of silently returning 0 results.
- [ ] **Canadian supplementary source** — add a Canada411.ca or YellowPages.ca
      scraper so non-US phone lookup actually works.
- [ ] **Email extractor** — visit the business website (if present), scrape the
      contact page for email addresses using regex + `mailto:` links.

### Dashboard UX
- [ ] **Bulk status update** — select multiple leads → set status in one click.
- [ ] **Lead detail drawer** — click a row to open a full-width side panel with
      all fields, map embed, pitch notes, and call history.
- [ ] **Export selected** — download only filtered leads as CSV directly from UI.
- [ ] **Search/filter bar** — filter the lead table by name, city, status, score
      without leaving the page.

### Data quality
- [ ] **Duplicate phone merge** — when the same phone appears under two business
      names, flag them and let admin choose which to keep.
- [ ] **Address standardisation** — normalise to USPS/Canada Post format so
      addresses are sortable by route (great for in-person canvassing).

---

## 7. Medium-Term Features (1–3 months)

### Outreach engine
- **Email campaigns** — pull contact emails, generate personalised first emails
  using pitch_engine, send via SMTP (free with Gmail/Outlook). Track opens with
  a 1px tracking pixel hosted on Vercel.
- **SMS integration** — integrate Twilio free tier (trial credits) or TextBelt for
  follow-up texts.
- **Call recording notes** — log outcome (answered, voicemail, no answer) per call
  with a timestamp. Show call attempts count on the lead card.

### AI enrichment (free models)
- **Auto pitch personalisation** — use Ollama (local LLM) or the Anthropic API to
  generate a unique 2-sentence opener for each lead based on their review text,
  niche, and rating. Callers sound prepared without doing research.
- **Review sentiment analysis** — scrape the most recent 5 reviews, run sentiment
  analysis, flag leads where customers mention "no website", "hard to find", or
  "slow response". These are HOT sales signals.
- **Business health score** — compare review count growth rate (reviews/month)
  versus niche average. A stagnant business with declining reviews is a better
  pitch than one that's growing fast.

### CRM depth
- **Pipeline kanban** — drag-and-drop board: Prospect → Contacted → Interested →
  Proposal Sent → Closed Won / Lost.
- **Follow-up scheduler** — set a date/time to follow up; show due follow-ups at
  the top of the caller dashboard each day.
- **Deal value tracking** — log estimated deal value when marking sold. Admin
  dashboard shows total pipeline value and closed revenue.
- **Caller leaderboard** — visible to all callers; shows calls made, conversion
  rate, revenue closed. Drives competition.

### Scraper infrastructure
- **Scheduled scrapes** — cron jobs to auto-run niches on a schedule (daily/weekly)
  so the lead pool stays fresh without manual triggering.
- **Multi-city parallel runs** — queue multiple city+niche combinations and run them
  concurrently across worker instances.
- **Proxy rotation** — integrate free proxy lists or a cheap rotating proxy service
  to reduce CAPTCHA frequency on heavy scraping days.
- **Result deduplication across runs** — flag leads that appear in multiple searches
  (e.g. same business found via "plumber Calgary" and "plumbers Calgary AB") so the
  DB stays clean.

---

## 8. Long-Term / SaaS Monetisation (3–6 months)

### Multi-tenant architecture
Convert the single-org setup to multi-tenant:
- Each customer gets their own Supabase schema (or a `tenant_id` column on every table).
- Admin panel becomes a super-admin panel that manages all tenants.
- Worker.py gets a `--tenant-id` flag; one shared worker pool serves all tenants.

### Subscription tiers

| Tier         | Price      | Limits                               | Key features                          |
|--------------|------------|--------------------------------------|---------------------------------------|
| **Starter**  | $49/mo     | 500 leads/mo, 2 callers, 1 niche     | Basic CRM, CSV export                 |
| **Growth**   | $149/mo    | 2,500 leads/mo, 10 callers, 5 niches | Email outreach, AI pitch notes        |
| **Agency**   | $399/mo    | 10,000 leads/mo, unlimited callers   | White-label, API access, multi-city   |
| **Enterprise**| Custom    | Unlimited                            | Dedicated worker, custom integrations |

### Differentiators vs competitors
- **100% free data sources** — no per-lead API costs, unlike Apollo, ZoomInfo, or
  Seamless.ai which charge per contact.
- **Local business focus** — purpose-built for service businesses (HVAC, plumbers,
  restaurants, dentists) that B2B platforms ignore.
- **Real-time scraping** — data is fresh (scraped on demand), not 6-month-old
  database exports like competitors sell.
- **Built-in caller CRM** — no need to export to HubSpot; callers log calls and
  update status in the same UI where leads live.
- **Owned infrastructure** — customers can self-host the scraper on their own VPS
  to avoid usage limits and keep data private.

### Go-to-market
1. **Launch on AppSumo / ProductHunt** as a lifetime deal to build initial user base.
2. **Agency partnerships** — cold-email local marketing agencies and offer 30-day
   free trials with white-label option.
3. **Lead gen niches community** — build a Discord for users to share niche configs
   and best practices; community drives organic growth.
4. **YouTube tutorials** — "How I generate 200 qualified leads per day for free"
   drives inbound traffic from freelancers and agency owners.

### Technical SaaS requirements
- [ ] Stripe integration (subscription billing + usage metering)
- [ ] Tenant provisioning API (create schema + invite callers on signup)
- [ ] Usage dashboard (leads scraped / leads used this month)
- [ ] API key management (for Growth/Agency tiers)
- [ ] Audit log (who changed what lead status and when)
- [ ] GDPR/CCPA data deletion endpoint
- [ ] Status page (uptime monitoring for worker + dashboard)

---

## 9. Technology Decisions

| Component       | Current choice         | Alternative considered             |
|-----------------|------------------------|------------------------------------|
| Scraper browser | undetected-chromedriver| Playwright (better stealth, slower)|
| Database        | Supabase (PostgreSQL)  | PlanetScale, Neon, self-hosted PG  |
| Dashboard       | Next.js 14 (Vercel)    | SvelteKit, Remix                   |
| Auth            | Supabase Auth          | Auth.js / Clerk                    |
| Job queue       | Supabase table polling | BullMQ, Celery, Redis Queue        |
| Phone validation| libphonenumber (Python)| numverify API (paid)               |
| Proxy           | None / public lists    | Bright Data, Oxylabs (paid)        |
| AI              | None currently         | Ollama (local), Anthropic API      |

---

*Last updated: 2026-03-07*
