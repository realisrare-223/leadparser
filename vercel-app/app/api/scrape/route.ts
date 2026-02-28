import { NextRequest, NextResponse } from 'next/server';
import { kv } from '@vercel/kv';

// Lead scoring function
function calculateLeadScore(place: any, niche: string): number {
  let score = 0;
  
  const reviews = place.user_ratings_total || 0;
  const rating = place.rating || 0;
  
  // Review count scoring
  if (reviews === 0) score += 10;
  else if (reviews <= 10) score += 8;
  else if (reviews <= 25) score += 5;
  else if (reviews <= 50) score += 3;
  else score += 1;
  
  // Rating scoring
  if (rating > 0 && rating <= 3.5) score += 9;
  else if (rating > 3.5 && rating <= 4.0) score += 4;
  
  // No website bonus
  if (!place.website) score += 3;
  
  // High-value niches
  const highValueNiches = ['plumbers', 'electricians', 'roofing', 'hvac', 'auto detailing', 'car detailing'];
  if (highValueNiches.some(n => niche.toLowerCase().includes(n))) score += 7;
  
  return Math.min(score, 30);
}

export async function POST(request: NextRequest) {
  try {
    const { niche, city, state, limit = 100 } = await request.json();
    
    if (!niche || !city || !state) {
      return NextResponse.json({ error: 'Missing required fields' }, { status: 400 });
    }
    
    const apiKey = process.env.GOOGLE_PLACES_API_KEY;
    if (!apiKey) {
      return NextResponse.json({ error: 'API key not configured' }, { status: 500 });
    }
    
    const query = `${niche} in ${city}, ${state}`;
    const leads: any[] = [];
    let nextPageToken: string | null = null;
    let attempts = 0;
    const maxAttempts = Math.ceil(limit / 20);
    
    // Fetch leads from Google Places API
    do {
      const url = new URL('https://maps.googleapis.com/maps/api/place/textsearch/json');
      url.searchParams.set('query', query);
      url.searchParams.set('key', apiKey);
      if (nextPageToken) {
        url.searchParams.set('pagetoken', nextPageToken);
      }
      
      const response = await fetch(url.toString());
      const data = await response.json();
      
      if (data.status !== 'OK' && data.status !== 'ZERO_RESULTS') {
        console.error('Places API error:', data.status, data.error_message);
        break;
      }
      
      // Get details for each place
      for (const place of data.results || []) {
        if (leads.length >= limit) break;
        
        // Get detailed info including phone and website
        const detailsUrl = new URL('https://maps.googleapis.com/maps/api/place/details/json');
        detailsUrl.searchParams.set('place_id', place.place_id);
        detailsUrl.searchParams.set('fields', 'name,formatted_phone_number,website,formatted_address,rating,user_ratings_total,url,vicinity');
        detailsUrl.searchParams.set('key', apiKey);
        
        const detailsRes = await fetch(detailsUrl.toString());
        const detailsData = await detailsRes.json();
        
        if (detailsData.status === 'OK') {
          const details = detailsData.result;
          
          // Only include if NO website AND HAS phone
          if (!details.website && details.formatted_phone_number) {
            const lead = {
              id: place.place_id,
              name: details.name || place.name,
              phone: details.formatted_phone_number,
              niche: niche,
              city: city,
              state: state,
              address: details.formatted_address || details.vicinity || place.formatted_address || '',
              rating: details.rating || place.rating || 0,
              review_count: details.user_ratings_total || place.user_ratings_total || 0,
              gmb_link: details.url || place.url || `https://www.google.com/maps/place/?q=place_id:${place.place_id}`,
              website: '',
              lead_score: 0,
              date_added: new Date().toISOString().split('T')[0]
            };
            
            lead.lead_score = calculateLeadScore({ ...place, ...details }, niche);
            
            // Check for duplicates
            const existing = await kv.get(`lead:${lead.id}`);
            if (!existing) {
              leads.push(lead);
              // Save to KV store
              await kv.set(`lead:${lead.id}`, JSON.stringify(lead));
              await kv.sadd('leads:ids', lead.id);
            }
          }
        }
        
        // Small delay to avoid rate limits
        await new Promise(r => setTimeout(r, 100));
      }
      
      nextPageToken = data.next_page_token;
      attempts++;
      
      // Wait before using next_page_token (required by Google)
      if (nextPageToken && leads.length < limit) {
        await new Promise(r => setTimeout(r, 2000));
      }
      
    } while (nextPageToken && leads.length < limit && attempts < maxAttempts);
    
    return NextResponse.json({ 
      success: true, 
      leads_found: leads.length,
      leads: leads
    });
    
  } catch (error) {
    console.error('Scrape error:', error);
    return NextResponse.json({ error: 'Scraping failed' }, { status: 500 });
  }
}
