import { NextRequest, NextResponse } from 'next/server';
import { kv } from '@vercel/kv';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const filter = searchParams.get('filter') || 'all';
    
    // Get all lead IDs
    const leadIds = await kv.smembers('leads:ids');
    
    if (!leadIds || leadIds.length === 0) {
      return NextResponse.json([]);
    }
    
    // Fetch all leads
    const leads: any[] = [];
    for (const id of leadIds) {
      const data = await kv.get(`lead:${id}`);
      if (data) {
        const lead = typeof data === 'string' ? JSON.parse(data) : data;
        
        // Apply filters
        if (filter === 'hot' && (lead.lead_score || 0) < 18) continue;
        if (filter === 'warm' && ((lead.lead_score || 0) < 12 || (lead.lead_score || 0) >= 18)) continue;
        if (filter === 'medium' && ((lead.lead_score || 0) < 7 || (lead.lead_score || 0) >= 12)) continue;
        
        leads.push(lead);
      }
    }
    
    // Sort by score descending
    leads.sort((a, b) => (b.lead_score || 0) - (a.lead_score || 0));
    
    return NextResponse.json(leads);
    
  } catch (error) {
    console.error('Error fetching leads:', error);
    return NextResponse.json({ error: 'Failed to fetch leads' }, { status: 500 });
  }
}

// Clear all leads
export async function DELETE() {
  try {
    const leadIds = await kv.smembers('leads:ids');
    for (const id of leadIds) {
      await kv.del(`lead:${id}`);
    }
    await kv.del('leads:ids');
    return NextResponse.json({ success: true });
  } catch (error) {
    return NextResponse.json({ error: 'Failed to clear leads' }, { status: 500 });
  }
}
