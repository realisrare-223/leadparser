import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'

// GET /api/export — download all leads as CSV (admin only)
export async function GET() {
  const supabase = createClient()

  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { data: leads } = await supabase
    .from('leads')
    .select('*')
    .order('lead_score', { ascending: false })

  if (!leads?.length) {
    return NextResponse.json({ error: 'No leads' }, { status: 404 })
  }

  const headers = [
    'name', 'phone', 'niche', 'city', 'state', 'address',
    'rating', 'review_count', 'lead_score', 'status',
    'assigned_to', 'caller_notes', 'website', 'gmb_link', 'date_added',
  ]

  const csv = [
    headers.join(','),
    ...leads.map(l =>
      headers.map(h => `"${String((l as any)[h] ?? '').replace(/"/g, '""')}"`).join(',')
    ),
  ].join('\n')

  return new NextResponse(csv, {
    headers: {
      'Content-Type': 'text/csv',
      'Content-Disposition': 'attachment; filename=leads.csv',
    },
  })
}
