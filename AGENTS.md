# LeadParser — AI Agent Guide

> **Purpose**: Local business lead generation pipeline with a real-time dashboard.  
> **Target Users**: Marketing agencies, freelancers, and cold-calling teams.

---

## 1. Project Overview

LeadParser is a full-stack SaaS application that scrapes Google Maps for local business listings, enriches them with supplementary data, scores them, and delivers them to a team of callers through a mini-CRM.

### System Architecture

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
│  ├── Phase 1: GoogleMapsScraper (playwright/xhr/selenium)       │
│  ├── Phase 2: apply_filters()                                   │
│  ├── Phase 3: trim to --limit                                   │
│  ├── Phase 4: SupabaseHandler.bulk_insert()  (upsert)          │
│  └── Phase 5: CSV export                                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Technology Stack

### Backend (Python)
| Component | Technology | Version |
|-----------|------------|---------|
| Language | Python | 3.10+ |
| Browser Automation | Playwright | 1.40+ (default) |
| Browser Automation | Selenium | 4.15+ (legacy fallback) |
| HTTP Client | httpx | 0.27+ (XHR parser) |
| Database | Supabase (PostgreSQL) | via supabase-py 2.3+ |
| Auth | Supabase Auth | - |
| Phone Validation | libphonenumber (phonenumbers) | 8.13+ |
| Sentiment Analysis | VADER + TextBlob | - |
| Scheduling | schedule | 1.2+ |

### Frontend
| Component | Technology | Version |
|-----------|------------|---------|
| Framework | Next.js | 14.2+ |
| UI Library | React | 18.3+ |
| Language | TypeScript | 5.4+ |
| Styling | Tailwind CSS | 3.4+ |
| Supabase Client | @supabase/supabase-js | 2.45+ |
| Testing | Vitest + React Testing Library | 1.6+ |

### Infrastructure
- **Database**: Supabase (PostgreSQL with RLS)
- **Hosting**: Vercel (frontend), Self-hosted/VPS (Python worker)
- **Auth**: Supabase Auth (email/password)

---

## 3. Project Structure

```
leadparser/
├── main.py                   # Pipeline orchestrator + CLI entry point
├── worker.py                 # Job queue poller (runs forever on machine)
├── config.yaml               # Niches, location, filters, scoring weights
├── .env                      # SUPABASE_URL + SUPABASE_KEY (service role)
├── requirements.txt          # Python dependencies
│
├── scrapers/                 # Scraping engines
│   ├── base_scraper.py       # Selenium base class
│   ├── google_maps.py        # Primary scraper with NICHE_EXPANSIONS
│   ├── playwright_scraper.py # Playwright async scraper (default)
│   ├── xhr_scraper.py        # Pure HTTP scraper (fastest)
│   ├── supplementary.py      # Orchestrates Yelp / Yellow Pages / BBB
│   ├── yelp_scraper.py       # Phone lookup via Yelp
│   └── yellow_pages.py       # Phone lookup via YP / Whitepages
│
├── exporters/                # Data output handlers
│   ├── supabase_handler.py   # Upsert leads (MD5 dedup key)
│   ├── sqlite_handler.py     # Local SQLite storage
│   └── sheets_exporter.py    # Google Sheets export
│
├── utils/                    # Utility modules
│   ├── lead_scorer.py        # Score = f(reviews, rating, website, niche)
│   ├── phone_validator.py    # NANP validation via libphonenumber
│   ├── address_parser.py     # City/state/zip extraction
│   ├── pitch_engine.py       # Auto-generate cold-call pitch notes
│   ├── rate_limiter.py       # Delay between requests
│   ├── proxy_manager.py      # Free proxy rotation
│   └── sentiment_analyzer.py # Review sentiment analysis
│
├── supabase/                 # Database schema
│   ├── schema.sql            # Full PostgreSQL schema
│   └── *.sql                 # Migration scripts
│
├── vercel-app/               # Next.js 14 dashboard
│   ├── app/                  # App Router pages
│   │   ├── login/            # Email + password auth
│   │   ├── dashboard/        # Caller view
│   │   ├── admin/            # Admin view
│   │   └── api/              # REST endpoints
│   ├── components/           # React components
│   │   ├── ScraperPanel.tsx  # Queue jobs, live logs
│   │   ├── LeadTable.tsx     # Sortable table
│   │   ├── StatsGrid.tsx     # KPI cards
│   │   └── AssignPanel.tsx   # Assign leads to callers
│   ├── lib/
│   │   ├── types.ts          # TypeScript types
│   │   ├── niches.ts         # Niche dropdown options
│   │   ├── cities.ts         # Major NA cities
│   │   └── supabase/         # Browser + server clients
│   └── package.json
│
└── tests/                    # Test suite
    └── python/
        ├── conftest.py       # pytest fixtures
        ├── unit/             # Unit tests
        └── integration/      # Integration tests
```

---

## 4. Build & Run Commands

### Python Scraper (Local Development)

```bash
# Setup
cd leadparser
pip install -r requirements.txt
playwright install chromium  # Required for Playwright parser
cp .env.example .env         # Add your Supabase credentials

# Basic run
python main.py

# With CLI overrides
python main.py --city "Dallas" --state TX --limit 40
python main.py --niche "plumbers" --parser xhr

# Run + launch dashboard
python main.py --city "Miami" --state FL --limit 30 --serve

# Export-only mode (no scraping)
python main.py --export-only

# Start worker (for queued jobs from dashboard)
python worker.py
```

### Next.js Dashboard

```bash
cd leadparser/vercel-app

# Install dependencies
npm install

# Development server
npm run dev

# Build for production
npm run build

# Run tests
npm run test
npm run test:run
```

### Python Tests

```bash
# Run all tests
pytest tests/python/

# Run unit tests only
pytest tests/python/unit/

# Run with verbose output
pytest tests/python/ -v
```

---

## 5. Configuration

### Environment Variables (`.env`)

```bash
# Supabase (required)
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-service-role-key-here  # Never expose in frontend!
```

### Parser Selection (`config.yaml`)

```yaml
scraping:
  parser: "playwright"   # Options: "playwright" | "xhr" | "selenium"
  workers: 4             # Parallel browser contexts (playwright only)
  xhr_concurrency: 50    # Concurrent HTTP requests (xhr only)
```

| Parser | Speed (100 leads) | Notes |
|--------|-------------------|-------|
| `playwright` | ~4-5 min | Default, 4 parallel workers |
| `xhr` | ~30-90 sec | Fastest, no browser, 50 concurrent HTTP |
| `selenium` | ~15-20 min | Legacy fallback |

---

## 6. Code Style Guidelines

### Python
- **Type hints**: Use `dict`, `list`, `Optional`, `Union` from `typing`
- **Docstrings**: Google-style docstrings for public functions
- **Naming**: `snake_case` for variables/functions, `PascalCase` for classes
- **Imports**: Group as stdlib → third-party → internal modules
- **Logging**: Use `logging.getLogger("leadparser.module")` instead of print

### TypeScript/React
- **Types**: Always define interfaces in `lib/types.ts`
- **Components**: Functional components with explicit return types
- **Naming**: `PascalCase` for components/interfaces, `camelCase` for functions/vars
- **Imports**: Use `@/` path aliases where configured

---

## 7. Testing Strategy

### Python Tests (pytest)
```
tests/python/
├── conftest.py                    # Shared fixtures
├── unit/
│   ├── test_address_parser.py
│   ├── test_lead_scorer.py
│   ├── test_phone_validator.py
│   ├── test_pitch_engine.py
│   └── test_sentiment_analyzer.py
└── integration/
    └── test_supabase_handler.py
```

**Key Fixtures** (from `conftest.py`):
- `sample_config` - Minimal config dict for testing
- `sample_raw_lead` - Raw lead dict from scraper
- `sample_raw_lead_no_phone` - Lead missing phone
- `sample_raw_lead_canadian` - Canadian lead with province

### Frontend Tests (Vitest)
```
vercel-app/__tests__/
├── api/
│   ├── admin.test.ts
│   └── leads.test.ts
└── components/
    └── LeadTable.test.tsx
```

---

## 8. Key Data Models

### Lead (TypeScript/Python)
```typescript
interface Lead {
  id: string
  dedup_key: string          // MD5(lower(name) + city)
  niche: string
  name: string
  phone: string
  city: string
  state: string
  review_count: number
  rating: string
  website: string
  lead_score: number         // 0-31
  status: 'new' | 'called' | 'sold' | 'followup' | 'dead'
  assigned_to: string | null
  pitch_notes: string
  // ... (see lib/types.ts for full schema)
}
```

### Lead Score Thresholds
| Score | Label |
|-------|-------|
| ≥ 22 | HOT |
| ≥ 15 | WARM |
| ≥ 8 | MEDIUM |
| < 8 | LOW |

---

## 9. Development Conventions

### Adding a New Niche
1. Add to `vercel-app/lib/niches.ts` (dropdown options)
2. Add keyword expansions to `leadparser/scrapers/google_maps.py` (`NICHE_EXPANSIONS`)
3. Add pitch template to `leadparser/config.yaml` (`pitch_templates:`)

### Adding a New Filter
1. Add to `apply_filters()` in `leadparser/main.py`
2. Add CLI flag in `parse_args()`
3. Add UI control in `ScraperPanel.tsx`
4. Add worker passthrough in `worker.py`

### Database Migrations
1. Write SQL in `leadparser/supabase/*.sql`
2. Run in Supabase SQL Editor
3. Update `schema.sql` with final state
4. Update `types.ts` if columns changed
5. Update `supabase_handler.py` `_prepare_row()` method

---

## 10. Security Considerations

### Row-Level Security (RLS)
- **Callers** see only `leads` where `assigned_to = auth.uid()`
- **Admins** bypass via policy checking `callers.role = 'admin'`
- **Python scraper** uses **service role key** (bypasses RLS)
- **Dashboard** uses **anon key** (respects RLS)

### Sensitive Files (Never Commit)
- `.env` - Contains service role keys
- `credentials.json` - Google Sheets service account
- `*.db` - SQLite databases with lead data

### API Routes
- All `/api/admin/*` routes should verify admin role
- Use `createClient()` from `lib/supabase/server.ts` for server-side auth

---

## 11. Common Tasks

### Switch Parser Engine
Edit `leadparser/config.yaml`:
```yaml
scraping:
  parser: "xhr"   # or "playwright" | "selenium"
```

### Run Specific Niche
```bash
python main.py --niche "plumbers" --city "Austin" --state TX
```

### Test Proxy Configuration
```yaml
proxies:
  enabled: true
  sources:
    - "proxyscrape"
    - "geonode"
  test_before_use: true
```

### Reset Database (Development)
```sql
-- In Supabase SQL Editor
TRUNCATE leads;
TRUNCATE scraper_jobs;
```

---

## 12. Documentation References

| File | Purpose |
|------|---------|
| `ARCHITECTURE.md` | Full system architecture & roadmap |
| `PARSER_UPGRADE.md` | Parser engine comparison & migration guide |
| `docs/SECTIONS.md` | Component-by-component upgrade guide |
| `leadparser/memory/MEMORY.md` | Quick reference for common commands |
| `leadparser/setup_guide.md` | Initial setup instructions |
| `leadparser/vercel-app/DEPLOY.md` | Vercel deployment guide |

---

*Last updated: 2026-03-08*
