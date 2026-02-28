import { NextResponse } from 'next/server';
import { kv } from '@vercel/kv';

export async function GET() {
  try {
    const leadIds = await kv.smembers('leads:ids');
    const leads: any[] = [];
    
    for (const id of leadIds) {
      const data = await kv.get(`lead:${id}`);
      if (data) {
        leads.push(typeof data === 'string' ? JSON.parse(data) : data);
      }
    }
    
    // Sort by score
    leads.sort((a, b) => (b.lead_score || 0) - (a.lead_score || 0));
    
    // Generate CSV
    const headers = ['name', 'phone', 'niche', 'city', 'state', 'address', 'rating', 'review_count', 'lead_score', 'gmb_link'];
    const csv = [
      headers.join(','),
      ...leads.map(lead => headers.map(h => `"${(lead[h] || '').toString().replace(/"/g, '\\"')}"`).join(','))
    ].join('\n');
    
    return new NextResponse(csv, {
      headers: {
        'Content-Type': 'text/csv',
        'Content-Disposition': 'attachment; filename=leads.csv'
      }
    });
    
  } catch (error) {
    return NextResponse.json({ error: 'Export failed' }, { status: 500 });
  }
}
