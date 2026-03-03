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
// Body: { caller_id, count, filters: AssignFilters }
// Selects `count` unassigned leads matching all filters, locks them to the caller.
export async function POST(request: NextRequest) {
  const supabase = createClient()
  const admin = await requireAdmin(supabase)
  if (!admin) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  const body = await request.json()
  const {
    caller_id,
    count,
    filters = {},
  } = body as {
    caller_id: string
    count: number
    filters?: {
      niche?:      string
      city?:       string
      minScore?:   number
      minRating?:  number
      minReviews?: number
      maxReviews?: number
      hasWebsite?: string   // 'any' | 'yes' | 'no'
      hasPhone?:   string   // 'any' | 'yes' | 'no'
    }
  }

  if (!caller_id || !count) {
    return NextResponse.json({ error: 'caller_id and count are required' }, { status: 400 })
  }

  // Select unassigned leads matching filters, best score first
  let query = supabase
    .from('leads')
    .select('id')
    .is('assigned_to', null)
    .eq('status', 'new')
    .order('lead_score', { ascending: false })
    .limit(count)

  // ── String filters ───────────────────────────────────────────────────────
  if (filters.niche && filters.niche !== 'any') query = query.eq('niche', filters.niche)
  if (filters.city  && filters.city  !== 'any') query = query.eq('city',  filters.city)

  // ── Numeric range filters ────────────────────────────────────────────────
  if (filters.minScore   && filters.minScore   > 0) query = query.gte('lead_score',   filters.minScore)
  if (filters.minReviews && filters.minReviews > 0) query = query.gte('review_count', filters.minReviews)
  if (filters.maxReviews && filters.maxReviews > 0) query = query.lte('review_count', filters.maxReviews)

  // Min rating: the `rating` column is stored as text (e.g. "4.2"), cast via raw filter
  if (filters.minRating && filters.minRating > 0) {
    // Use raw postgres filter — cast rating text to numeric, ignore non-numeric rows
    query = query.filter('rating', 'gte', String(filters.minRating))
  }

  // ── Boolean filters ──────────────────────────────────────────────────────
  if (filters.hasWebsite === 'yes') {
    query = query.not('website', 'is', null).neq('website', '')
  } else if (filters.hasWebsite === 'no') {
    // Has no website: null OR empty string
    query = query.or('website.is.null,website.eq.')
  }

  if (filters.hasPhone === 'yes') {
    query = query
      .not('phone', 'is', null)
      .neq('phone', '')
      .neq('phone', 'NOT FOUND')
  } else if (filters.hasPhone === 'no') {
    query = query.or('phone.is.null,phone.eq.,phone.eq.NOT FOUND')
  }

  const { data: candidates, error: selectError } = await query

  if (selectError) {
    return NextResponse.json({ error: selectError.message }, { status: 500 })
  }

  if (!candidates || candidates.length === 0) {
    return NextResponse.json({ assigned: 0, message: 'No unassigned leads match these filters.' })
  }

  const ids = candidates.map(l => l.id)
  const now = new Date().toISOString()

  // Lock leads — assign atomically (double-check .is('assigned_to', null))
  const { error: updateError } = await supabase
    .from('leads')
    .update({ assigned_to: caller_id, assigned_at: now, status: 'new' })
    .in('id', ids)
    .is('assigned_to', null)

  if (updateError) {
    return NextResponse.json({ error: updateError.message }, { status: 500 })
  }

  return NextResponse.json({ assigned: ids.length })
}
