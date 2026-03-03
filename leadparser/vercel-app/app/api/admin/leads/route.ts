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

// GET /api/admin/leads — all leads with optional filters
// Query params: status, niche, city, assigned, limit,
//               min_score, min_rating, min_reviews, max_reviews,
//               has_website, has_phone
export async function GET(request: NextRequest) {
  const supabase = createClient()
  const admin = await requireAdmin(supabase)
  if (!admin) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  const p = new URL(request.url).searchParams

  const status     = p.get('status')
  const niche      = p.get('niche')
  const city       = p.get('city')
  const assigned   = p.get('assigned')       // 'yes' | 'no' | all
  const limit      = parseInt(p.get('limit') ?? '300', 10)
  const minScore   = parseFloat(p.get('min_score')   ?? '0')
  const minRating  = parseFloat(p.get('min_rating')  ?? '0')
  const minReviews = parseInt(p.get('min_reviews')   ?? '0', 10)
  const maxReviews = parseInt(p.get('max_reviews')   ?? '0', 10)
  const hasWebsite = p.get('has_website') ?? 'any'  // 'any' | 'yes' | 'no'
  const hasPhone   = p.get('has_phone')   ?? 'any'  // 'any' | 'yes' | 'no'

  let query = supabase
    .from('leads')
    .select('*, callers(name)')
    .order('lead_score', { ascending: false })
    .limit(limit)

  // ── String filters ───────────────────────────────────────────────────────
  if (status   && status   !== 'all') query = query.eq('status', status)
  if (niche    && niche    !== 'all') query = query.eq('niche', niche)
  if (city     && city     !== 'all') query = query.eq('city',  city)

  if (assigned === 'yes') query = query.not('assigned_to', 'is', null)
  if (assigned === 'no')  query = query.is('assigned_to', null)

  // ── Numeric filters ──────────────────────────────────────────────────────
  if (minScore   > 0) query = query.gte('lead_score',   minScore)
  if (minReviews > 0) query = query.gte('review_count', minReviews)
  if (maxReviews > 0) query = query.lte('review_count', maxReviews)
  if (minRating  > 0) query = query.filter('rating', 'gte', String(minRating))

  // ── Boolean filters ──────────────────────────────────────────────────────
  if (hasWebsite === 'yes') {
    query = query.not('website', 'is', null).neq('website', '')
  } else if (hasWebsite === 'no') {
    query = query.or('website.is.null,website.eq.')
  }

  if (hasPhone === 'yes') {
    query = query
      .not('phone', 'is', null)
      .neq('phone', '')
      .neq('phone', 'NOT FOUND')
  } else if (hasPhone === 'no') {
    query = query.or('phone.is.null,phone.eq.,phone.eq.NOT FOUND')
  }

  const { data, error } = await query

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }

  return NextResponse.json(data ?? [])
}
