# LeadParser Pro — Vercel Edition

Unified single-app deployment for Vercel. No separate backend needed!

## Features

- ✅ Scrape 100 leads at a time
- ✅ Select niche, city, state for each scrape
- ✅ Only shows: NO website + HAS phone
- ✅ Automatic deduplication
- ✅ Hot/Warm/Medium lead scoring
- ✅ Export to CSV
- ✅ All-in-one deployment

## Tech Stack

- **Framework:** Next.js 14 (App Router)
- **Storage:** Vercel KV (Redis)
- **API:** Google Places API
- **Styling:** Inline CSS (no extra dependencies)

## Setup

### 1. Get Google Places API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable the **Places API**
4. Create an API key in **Credentials**
5. (Optional) Restrict the key for security

**Free tier:** $200/month credit (~20,000 requests)

### 2. Deploy to Vercel

```bash
cd vercel-app
npm install
vercel
```

### 3. Add Environment Variables

In Vercel dashboard:
1. Go to Project Settings → Environment Variables
2. Add `GOOGLE_PLACES_API_KEY` with your API key
3. Redeploy: `vercel --prod`

Or use CLI:
```bash
vercel env add GOOGLE_PLACES_API_KEY
vercel --prod
```

### 4. Add Vercel KV (for data storage)

In Vercel dashboard:
1. Go to **Storage** tab
2. Click **Connect Store** → **Create New** → **KV**
3. Connect to your project

## Usage

1. Open your Vercel URL
2. Enter niche (e.g., "plumbers")
3. Enter city (e.g., "Houston")
4. Enter state (e.g., "TX")
5. Click "Start Scraping"
6. Wait for results (may take 1-2 minutes for 100 leads)
7. Export to CSV when done

## How It Works

1. **Frontend:** React app with forms and tables
2. **API Routes:** Serverless functions handle scraping
3. **Google Places API:** Finds businesses matching criteria
4. **Filtering:** Only keeps businesses without websites that have phone numbers
5. **Deduplication:** Vercel KV ensures no duplicates
6. **Scoring:** Automatic lead scoring based on reviews, ratings, niche

## Important Notes

- **No Chrome/Selenium needed** — uses Google Places API instead
- **Data persists** in Vercel KV (not ephemeral)
- **Rate limits:** Google Places API has generous free tier
- **Timeouts:** Large scrape jobs may take 30-60 seconds

## Architecture

```
┌─────────────────────────────────────┐
│           Vercel Cloud              │
│  ┌───────────────────────────────┐  │
│  │      Next.js App              │  │
│  │  ┌─────────────────────────┐  │  │
│  │  │   React Frontend        │  │  │
│  │  └─────────────────────────┘  │  │
│  │  ┌─────────────────────────┐  │  │
│  │  │   API Routes            │  │  │
│  │  │   - /api/scrape         │  │  │
│  │  │   - /api/leads          │  │  │
│  │  │   - /api/stats          │  │  │
│  │  └─────────────────────────┘  │  │
│  └───────────────────────────────┘  │
│              │                      │
│              ▼                      │
│  ┌───────────────────────────────┐  │
│  │      Vercel KV                │  │
│  │   (Lead storage)              │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
              │
              ▼
┌───────────────────────────────┐
│   Google Places API           │
│   (Business data)             │
└───────────────────────────────┘
```

## Troubleshooting

**"API key not configured" error:**
- Add GOOGLE_PLACES_API_KEY to Vercel environment variables

**"No leads found":**
- Try different niches or cities
- Some areas have fewer businesses without websites

**Slow scraping:**
- Normal for large batches — Google Places API has rate limits
- Each lead requires a separate API call for details

**Data disappears:**
- Make sure Vercel KV is connected to your project
