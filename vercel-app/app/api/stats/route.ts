import { NextRequest, NextResponse } from 'next/server';
import { kv } from '@vercel/kv';

export async function GET() {
  try {
    const leadIds = await kv.smembers('leads:ids');
    
    if (!leadIds || leadIds.length === 0) {
      return NextResponse.json({ total: 0, hot: 0, warm: 0, new_this_session: 0 });
    }
    
    let total = 0;
    let hot = 0;
    let warm = 0;
    let newToday = 0;
    const today = new Date().toISOString().split('T')[0];
    
    for (const id of leadIds) {
      const data = await kv.get(`lead:${id}`);
      if (data) {
        const lead = typeof data === 'string' ? JSON.parse(data) : data;
        total++;
        
        const score = lead.lead_score || 0;
        if (score >= 18) hot++;
        else if (score >= 12) warm++;
        
        if (lead.date_added === today) newToday++;
      }
    }
    
    return NextResponse.json({
      total,
      hot,
      warm,
      new_this_session: newToday
    });
    
  } catch (error) {
    console.error('Stats error:', error);
    return NextResponse.json({ total: 0, hot: 0, warm: 0, new_this_session: 0 });
  }
}
