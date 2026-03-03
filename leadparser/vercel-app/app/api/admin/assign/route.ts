import { createClient } from '@/lib/supabase/server'
import { NextRequest, NextResponse } from 'next/server'

// Helper: verify caller is admin
async function requireAdmin(supabase: ReturnType<typeof createClient>) {
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return null

  const { data: caller } = await supabase
    .from('callers')
    .select('role')
    .eq('id', user.id)
    .single()

  return caller?.role === 'admin' ? user : null
}

// POST /api/admin/assign
// Body: { caller_id, count, niche?, city? }
// Selects `count` unassigned leads (best score first), locks them to caller.
export async function POST(request: NextRequest) {
  const supabase = createClient()
  const admin = await requireAdmin(supabase)
  if (!admin) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  const body = await request.json()
  const { caller_id, count, niche, city } = body as {
    caller_id: string
    count: number
    niche?: string
    city?: string
  }

  if (!caller_id || !count) {
    return NextResponse.json({ error: 'caller_id and count are required' }, { status: 400 })
  }

  // Select unassigned leads that match filters, ordered by score desc
  let query = supabase
    .from('leads')
    .select('id')
    .is('assigned_to', null)
    .eq('status', 'new')
    .order('lead_score', { ascending: false })
    .limit(count)

  if (niche && niche !== 'any') query = query.eq('niche', niche)
  if (city  && city  !== 'any') query = query.eq('city', city)

  const { data: candidates, error: selectError } = await query

  if (selectError) {
    return NextResponse.json({ error: selectError.message }, { status: 500 })
  }

  if (!candidates || candidates.length === 0) {
    return NextResponse.json({ assigned: 0, message: 'No unassigned leads match these filters.' })
  }

  const ids = candidates.map(l => l.id)
  const now = new Date().toISOString()

  // Lock leads — assign to caller atomically
  const { error: updateError } = await supabase
    .from('leads')
    .update({ assigned_to: caller_id, assigned_at: now, status: 'new' })
    .in('id', ids)
    .is('assigned_to', null) // double-check: only update still-unassigned rows

  if (updateError) {
    return NextResponse.json({ error: updateError.message }, { status: 500 })
  }

  return NextResponse.json({ assigned: ids.length })
}
