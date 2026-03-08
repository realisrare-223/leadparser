# LeadParser — Parser Upgrade Reference

## What Changed

| Item | Before | After |
|------|--------|-------|
| Default parser | Selenium (1 browser, sequential) | Playwright (4 parallel workers) |
| Rate limiter delays | 2.0 – 4.0 s | 1.0 – 2.0 s |
| No-phone leads | Sent to Yelp/YP/BBB for enrichment | Skipped immediately |
| Supplementary phase | Enabled (Phase 2) | Removed entirely |
| v2 XHR parser | Not available | Available — switch in config.yaml |
| Proxy sources | 3 HTML-table sources | 3 HTML + 4 API/raw-text sources |

---

## Switching Parsers

Edit `leadparser/config.yaml`:

```yaml
scraping:
  parser: "playwright"   # ← change this line
```

| Value | Engine | Speed estimate (100 leads) |
|-------|--------|---------------------------|
| `"playwright"` | Async Playwright, 4 parallel browser contexts | ~4–5 min |
| `"xhr"` | Pure httpx, 50 concurrent HTTP requests, no browser | ~30–90 sec |
| `"selenium"` | Legacy undetected-chromedriver (original) | ~15–20 min |

---

## Playwright Parser (`parser: "playwright"`)

### How It Works
1. **Phase A** — One Playwright browser context scrolls through Google Maps search results
   and collects profile URLs (same scroll logic as the old Selenium scraper).
2. **Phase B** — `workers` (default: 4) parallel browser contexts each extract a
   quarter of the URLs simultaneously, then results are merged.

### Tuning
```yaml
scraping:
  workers: 4       # increase for more parallelism (4–8 recommended)
  headless: true   # set false to watch the browser (debugging)
```

### Anti-detection
- `playwright-stealth` patches all fingerprint leaks (`navigator.webdriver`,
  `chrome.runtime`, plugins, etc.)
- Each context gets a unique random user-agent, viewport, locale, and timezone
- `Referer: https://www.google.com/` set on all navigations

### Setup
```bash
pip install playwright playwright-stealth
playwright install chromium
```

---

## XHR Parser (`parser: "xhr"`)

### How It Works
1. **Phase A** — `httpx.AsyncClient` GETs Google Maps search result pages; the
   server-side-rendered HTML contains `<a href="/maps/place/...">` links that
   are extracted by regex. Each search term yields ~10–20 URLs; NICHE_EXPANSIONS
   multiplies coverage across synonym terms.
2. **Phase B** — Up to `xhr_concurrency` (default: 50) simultaneous GET requests
   fetch individual business profile pages. Data is extracted from:
   - `tel:` href links (most reliable phone source)
   - `data-item-id="phone:tel:..."` attribute
   - `aria-label="Phone: ..."` attribute
   - Open Graph `og:title` (business name)
   - Embedded JSON patterns for rating, reviews, address

### Tuning
```yaml
scraping:
  xhr_concurrency: 50   # 10–50 recommended; higher = faster but more blocks
```

### Anti-detection (Bright Data-equivalent)

| Feature | Implementation |
|---------|---------------|
| Browser Fingerprinting | `User-Agent`, `sec-ch-ua`, `sec-ch-ua-platform`, `Accept-*` headers are all internally consistent per session |
| CAPTCHA / block detection | Checks for 429 status and page content patterns ("unusual traffic", "verify you're not a robot") → rotates identity + exponential backoff |
| User-Agent management | Pool of 25+ real Chrome/Firefox/Edge/Opera strings; rotated per identity refresh |
| Referral headers | `Referer: https://www.google.com/` on search pages; `Referer: https://www.google.com/maps/` on profile pages |
| Cookie handling | `httpx.AsyncClient` session with persistent cookie jar; reset on block |
| Auto-retries + IP rotation | Up to 4 retries with `2^n + jitter` backoff; `ProxyManager.mark_bad()` called on block |
| Worldwide geo-coverage | Proxy pool from global free lists; geonode API supports country filtering |
| JavaScript rendering | Not needed — data extracted from server-rendered HTML and embedded JSON |
| Data integrity validation | Phone regex validation; non-empty name check; discards malformed rows |

### Setup
```bash
pip install httpx[http2]
```

### Troubleshooting XHR Blocks
If you see frequent "Blocked — rotating identity" log lines:
1. Lower `xhr_concurrency` to 10–20
2. Enable proxies: `proxies.enabled: true` in config.yaml
3. Add a sleep between search terms (currently 0.5–1.5s; increase if needed)
4. If fully blocked, switch back to `parser: "playwright"` temporarily

---

## Phone-Skip Policy

Both new parsers skip leads with no phone number immediately.
No Yelp, Yellow Pages, or BBB lookup is performed.

**Why:** Only businesses with a publicly listed phone in their Google Business
profile are worth calling. Leads without one require manual research and clog
your pipeline. This also eliminates the old Phase 2 (~3–5 min of extra scraping).

---

## Proxy Configuration

```yaml
proxies:
  enabled: false        # ← set true to activate
  sources:
    - "proxyscrape"     # plain-text API — fast, hundreds of proxies
    - "geonode"         # JSON API with country metadata
    - "github-theSpeedX" # community raw text list
    - "free-proxy-list" # HTML table (legacy)
  test_before_use: true
  rotate_every: 10
```

### Proxy Source Details

| Key | URL | Format | Notes |
|-----|-----|--------|-------|
| `proxyscrape` | api.proxyscrape.com | plain text ip:port | Updated frequently |
| `geonode` | proxylist.geonode.com | JSON | Country filter available |
| `github-theSpeedX` | raw.githubusercontent.com | plain text | Community list |
| `github-clarketm` | raw.githubusercontent.com | plain text + status | With UP/DOWN flag |
| `free-proxy-list` | free-proxy-list.net | HTML table | Legacy |
| `sslproxies` | sslproxies.org | HTML table | Legacy |

---

## Speed Comparison (100 leads, single niche)

| Parser | Time | Notes |
|--------|------|-------|
| Selenium (old) | ~15–20 min | 1 browser, 2–4s delay/lead |
| Playwright (new default) | ~4–5 min | 4 browsers × 1–2s delay |
| XHR (v2) | ~30–90 sec | 50 concurrent HTTP, no browser |

*Times are estimates. Actual speed depends on Google Maps response latency,
proxy quality, and whether blocks/CAPTCHAs occur.*

---

## Re-discovering XHR Endpoints (if Google changes structure)

The XHR scraper relies on these stable HTML patterns:

1. **Profile URL extraction from search page:**
   Pattern: `href="/maps/place/..."` in raw HTML
   File: [xhr_scraper.py `_extract_urls_from_html()`](leadparser/scrapers/xhr_scraper.py)

2. **Phone extraction from profile page:**
   Patterns: `href="tel:..."`, `data-item-id="phone:tel:..."`, `aria-label="Phone: ..."`
   File: [xhr_scraper.py `_parse_phone()`](leadparser/scrapers/xhr_scraper.py)

3. **Business name:**
   Pattern: `<meta property="og:title" content="...">` / `<title>`
   File: [xhr_scraper.py `_parse_name()`](leadparser/scrapers/xhr_scraper.py)

To update after a Google HTML change:
1. Open Chrome DevTools → Network → fetch a Maps search/profile page
2. Find the pattern that contains the field you need
3. Update the regex in the corresponding `_parse_*()` method
