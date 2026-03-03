# LeadParser Frontend

React frontend for LeadParser Pro - deploys to Vercel.

## Deployment Steps

1. **Install Vercel CLI:**
   ```bash
   npm i -g vercel
   ```

2. **Deploy:**
   ```bash
   cd frontend
   vercel
   ```

3. **Update API URL:**
   Edit `src/config.js` and change to your ngrok URL:
   ```javascript
   export const API_BASE_URL = 'https://your-ngrok-url.ngrok.io';
   ```

## Local Development

```bash
cd frontend
npm install
npm run dev
```

Make sure `api_server.py` is running locally!
