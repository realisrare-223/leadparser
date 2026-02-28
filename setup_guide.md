# LeadParser — Setup Guide
### 100% Free Lead Generation System · No Paid APIs Required

---

## Table of Contents
1. [Prerequisites](#1-prerequisites)
2. [Installation](#2-installation)
3. [Google Sheets API Setup (Free)](#3-google-sheets-api-setup-free)
4. [Configuration](#4-configuration)
5. [Running LeadParser](#5-running-leadparser)
6. [Scheduling Automated Runs](#6-scheduling-automated-runs)
7. [Reading Your Google Sheet](#7-reading-your-google-sheet)
8. [Customising Sales Pitch Templates](#8-customising-sales-pitch-templates)
9. [Troubleshooting](#9-troubleshooting)
10. [Architecture Overview](#10-architecture-overview)
11. [Version 2 Paid Upgrades (Optional)](#11-version-2-paid-upgrades-optional)

---

## 1. Prerequisites

| Requirement | Version | Free? | Download |
|---|---|---|---|
| Python | 3.10+ | ✅ | https://python.org/downloads |
| Google Chrome | Latest | ✅ | https://google.com/chrome |
| Google Account | Any | ✅ | https://accounts.google.com |

> **Windows users:** Make sure Python is added to your PATH during installation
> (check the box that says "Add Python to PATH").

---

## 2. Installation

### Step 1 — Download the project
If you received this as a zip file, extract it to a folder like `C:\leadparser\`.

### Step 2 — Open a terminal in the project folder
- **Windows:** Right-click the folder → "Open in Terminal" (or open CMD/PowerShell and `cd` to the folder)
- **Mac/Linux:** Open Terminal and `cd` to the folder

### Step 3 — Install Python dependencies
```bash
pip install -r requirements.txt
```

This installs everything needed — all packages are free and open-source.

### Step 4 — Verify Chrome is installed
LeadParser uses Chrome in headless mode to scrape Google Maps.
Run `google-chrome --version` (Linux/Mac) or look for Chrome in your
Start Menu (Windows) to confirm it's installed.

> **Chromium alternative:** If you prefer, install Chromium (free, open-source).
> Change `use_undetected_chrome: false` in config.yaml if Chrome is not found.

---

## 3. Google Sheets API Setup (Free)

This is the only setup that requires a few steps, but it's completely free
and takes about 10 minutes.

### Step 1 — Create a Google Cloud project
1. Go to https://console.cloud.google.com/
2. Click **"Select a project"** → **"New Project"**
3. Name it `leadparser` → click **"Create"**

### Step 2 — Enable the Google Sheets API
1. In your project, go to **APIs & Services → Library**
2. Search for **"Google Sheets API"** → click it → click **"Enable"**
3. Also search for **"Google Drive API"** → click it → click **"Enable"**

### Step 3 — Create a Service Account
1. Go to **APIs & Services → Credentials**
2. Click **"Create Credentials"** → **"Service Account"**
3. Name it `leadparser-service` → click **"Create and continue"**
4. For Role, select **"Editor"** → click **"Continue"** → click **"Done"**

### Step 4 — Download the credentials JSON
1. Click on your new service account in the list
2. Go to the **"Keys"** tab
3. Click **"Add Key"** → **"Create new key"** → **"JSON"** → **"Create"**
4. A `credentials.json` file downloads automatically
5. **Move this file into your LeadParser project folder** (same level as `main.py`)

### Step 5 — Note the service account email
Your service account has an email like:
`leadparser-service@your-project-id.iam.gserviceaccount.com`

You can find this in the service account details page.

### Step 6 — Create or share the Google Sheet (optional)
LeadParser will automatically create a new Google Sheet on first run.
The sheet will be owned by the service account.

**To access it with your personal Google account:**
1. After the first run, note the spreadsheet URL from the terminal output
2. Open it → click "Share" → enter your personal Gmail address → "Editor"

Alternatively, run LeadParser once — it prints the URL — then share it.

> **Cost:** The Google Sheets API has a free tier of 300 reads + 300 writes
> per minute, which is more than enough for this tool. No billing required.

---

## 4. Configuration

Open `config.yaml` in any text editor and set:

### Location
```yaml
location:
  city: "Austin"     # ← Change to your target city
  state: "TX"        # ← Change to your state (2-letter abbreviation)
```

### Target niches
```yaml
niches:
  - "plumbers"
  - "electricians"
  - "restaurants"
  # Add or remove as needed
```

### Filters
```yaml
filters:
  max_reviews: 100          # Only businesses with ≤100 reviews (need more help)
  exclude_with_website: false  # Set true to ONLY target businesses with NO website
```

### Lead scoring
Adjust scoring weights in `config.yaml → scoring` to prioritise the leads
most valuable to your business.

### Sales pitch templates
Customise `config.yaml → pitch_templates` with your own messaging.
See Section 8 for details.

---

## 5. Running LeadParser

### Full run (recommended for first use)
```bash
python main.py
```

### Other options
```bash
# Scrape a single niche only
python main.py --niche "plumbers"

# Re-export existing data to Google Sheets (no new scraping)
python main.py --export-only

# Scrape and save to database, but skip Google Sheets
python main.py --no-sheets

# Use a different config file (e.g. for a different city)
python main.py --config dallas_config.yaml
```

### First run checklist
- [ ] `requirements.txt` installed (`pip install -r requirements.txt`)
- [ ] `credentials.json` is in the project folder
- [ ] `config.yaml` has your city, state, and target niches
- [ ] Chrome is installed
- [ ] Internet connection is active

---

## 6. Scheduling Automated Runs

### Option A — Python scheduler (simplest)
Set `enabled: true` in `config.yaml → scheduling`, then run:
```bash
python scheduler.py
```
Keep this terminal window open. It will run LeadParser on your configured schedule.

### Option B — Windows Task Scheduler (runs even when terminal is closed)
```bash
python scheduler.py --print-task-scheduler
```
This prints the exact `schtasks` commands to paste into an elevated Command Prompt.

### Option C — Linux/macOS cron
```bash
python scheduler.py --print-cron
```
This prints the crontab entry to add. Run `crontab -e` and paste it.

### Example config.yaml scheduling section:
```yaml
scheduling:
  enabled: true
  frequency: "weekly"     # daily | weekly | monthly
  run_time: "08:00"        # 24-hour HH:MM
  day_of_week: "monday"   # Only used for weekly runs
```

---

## 7. Reading Your Google Sheet

After a run, open the Google Sheet URL printed in the terminal.

### Sheet tabs:
- **All Leads** — all smaller niches combined, color-coded by niche
- **[Niche name]** — separate tab for each niche with 50+ leads
- **📊 Summary** — total leads per niche, average lead score per niche

### Column guide:
| Column | Description |
|---|---|
| Business Niche | Search category (plumbers, restaurants, etc.) |
| Phone Number | Primary phone from Google Maps |
| Secondary Phone | Phone found from supplementary sources |
| Lead Score | 0–25+ priority score (higher = more likely to need your services) |
| Custom Sales Pitch Notes | Auto-generated, personalised pitch for each business |
| Call Status | Leave blank; fill in manually as you call |
| Follow-up Date | Leave blank; fill in manually for callbacks |
| Data Source | Which tool found this lead |

### Lead Score guide:
| Score | Priority | Meaning |
|---|---|---|
| 18+ | ★★★ HOT | Brand new, low rating, high-value niche, no website |
| 12–17 | ★★ WARM | Good opportunity, some missing info |
| 7–11 | ★ MEDIUM | Decent lead, more established business |
| < 7 | LOW | Established business, less likely to need help |

---

## 8. Customising Sales Pitch Templates

Open `config.yaml` and find the `pitch_templates` section.

**Available placeholders:**
- `{name}` — Business name
- `{city}` — City from their address
- `{niche}` — Search niche (e.g., "plumbers")
- `{review_count}` — Number of Google reviews
- `{rating}` — Star rating

**Example customisation:**
```yaml
pitch_templates:
  plumbers: >
    Hi {name}, I noticed your plumbing business has {review_count} reviews
    on Google. I help plumbers in {city} get 10–15 more service calls per
    month through our local SEO service. Would you have 10 minutes to chat?

  default: >
    Hi {name}, I help local businesses in {city} grow their customer base.
    Can we talk for 10 minutes?
```

Templates are **matched by niche name** (case-insensitive).
If no exact match is found, the `default` template is used.

---

## 9. Troubleshooting

### "Chrome not found" / WebDriver error
- Install Google Chrome from https://google.com/chrome
- Run `pip install --upgrade webdriver-manager`
- If on a server: `pip install --upgrade undetected-chromedriver`

### "No results found" for a niche
- Try running with `headless: false` in config.yaml to see what Chrome is loading
- Google Maps occasionally shows a CAPTCHA — solve it manually once, then headless works
- Try adding longer delays: `delay_min: 4.0`, `delay_max: 8.0`
- Reduce `max_results_per_niche` to a smaller number (e.g., 20)

### Google Sheets authentication error
- Confirm `credentials.json` is in the project root directory
- Verify the service account has the Google Sheets AND Google Drive APIs enabled
- Check the service account email has Editor access to the spreadsheet

### "Rate limited" or results stop loading
- Increase `delay_min` and `delay_max` in config.yaml
- Enable proxy rotation: `proxies.enabled: true`
- Run fewer niches at a time using `--niche`

### Duplicate leads appearing
The deduplication system uses business name + city as the unique key.
If you see duplicates, it means the business name or city differs slightly.
This is normal — use the Google Sheet's built-in "Remove duplicates" feature
for any edge cases.

### Phone numbers showing "NOT FOUND"
- Enable all supplementary scrapers in config.yaml:
  ```yaml
  supplementary_scrapers:
    yelp: true
    yellow_pages: true
    bbb: true
    whitepages: true
  ```
- Use the Google Maps link in column 12 to manually look up the number

### ImportError for any package
Run `pip install -r requirements.txt` again. If a specific package fails,
try `pip install <package-name>` individually.

---

## 10. Architecture Overview

```
leadparser/
├── main.py                  # Pipeline orchestrator + CLI
├── scheduler.py             # Recurring schedule runner
├── config.yaml              # All user settings
├── credentials.json         # Google Sheets service account key (you provide)
├── requirements.txt         # Python dependencies (all free)
│
├── scrapers/
│   ├── base_scraper.py      # Shared Selenium + anti-bot foundation
│   ├── google_maps.py       # Primary: Google Maps scraping
│   ├── yelp_scraper.py      # Supplementary: Yelp phone lookup
│   ├── yellow_pages.py      # Supplementary: YP / White Pages / BBB
│   └── supplementary.py    # Orchestrates all supplementary lookups
│
├── exporters/
│   ├── sqlite_handler.py    # Local SQLite storage + deduplication
│   └── sheets_exporter.py   # Google Sheets export + formatting
│
├── utils/
│   ├── rate_limiter.py      # Polite request delays
│   ├── proxy_manager.py     # Free proxy rotation
│   ├── phone_validator.py   # US phone number formatting
│   ├── address_parser.py    # Address → city/state/zip
│   ├── lead_scorer.py       # Priority score calculation
│   ├── pitch_engine.py      # Sales pitch template engine
│   └── sentiment_analyzer.py  # Review sentiment (VADER/TextBlob)
│
├── data/
│   └── leads.db             # SQLite database (auto-created)
└── logs/
    └── leadparser_*.log     # Rotating log files (auto-created)
```

### Data flow:
```
Google Maps (Selenium)
       ↓
   Raw leads
       ↓
  Build lead dicts (score + pitch)
       ↓
  Supplementary enrichment (Yelp, YP, BBB)
       ↓
  Apply filters
       ↓
  SQLite deduplication + storage
       ↓
  Google Sheets export
```

---

## 11. Version 2 Paid Upgrades (Optional)

These are NOT needed for v1. Everything works free without them.
Listed here for reference if you want to scale up in the future.

| Feature | Free (v1) | Paid upgrade (v2) |
|---|---|---|
| Google Maps data | Web scraping | SerpAPI ($50/mo) |
| Proxy rotation | Free proxy lists | BrightData ($500+/mo) |
| Phone validation | phonenumbers library | Twilio Lookup ($0.005/req) |
| Address parsing | Regex | SmartyStreets ($200/mo) |
| CRM integration | Google Sheets | HubSpot/Salesforce API |
| Email automation | Manual | Mailchimp/SendGrid |
| Captcha solving | Manual / avoidance | 2Captcha ($1–3/1000) |
| Residential proxies | N/A (too costly for v1) | Oxylabs ($100+/mo) |

---

*LeadParser v1 · Built entirely with free tools · No paid API keys required*
