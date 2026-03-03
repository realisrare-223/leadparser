# One-Click Deploy to Vercel

## Option 1: GitHub + Vercel (Easiest)

1. Push this code to GitHub (already done ✓)
2. Go to https://vercel.com/new
3. Import your GitHub repo: `realisrare-223/leadparser`
4. Set root directory to: `vercel-app`
5. Add environment variable:
   - Name: `GOOGLE_PLACES_API_KEY`
   - Value: (your Google Places API key)
6. Click Deploy

## Option 2: Vercel CLI (If you have token)

```bash
cd vercel-app
vercel login
vercel --prod
```

## Get Your Google Places API Key

1. Go to https://console.cloud.google.com/
2. Create a new project
3. Enable "Places API (New)"
4. Go to Credentials → Create API Key
5. Copy the key and add it to Vercel

**Free tier:** $200/month credit = ~20,000 API calls
