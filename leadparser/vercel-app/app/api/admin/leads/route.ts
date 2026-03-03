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
export async function GET(request: NextRequest) {
  const supabase = createClient()
  const admin = await requireAdmin(supabase)
  if (!admin) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  const { searchParams } = new URL(request.url)
  const status     = searchParams.get('status')
  const niche      = searchParams.get('niche')
  const city       = searchParams.get('city')
  const assigned   = searchParams.get('assigned')   // 'yes' | 'no' | all
  const limitParam = searchParams.get('limit')
  const limit      = limitParam ? parseInt(limitParam, 10) : 200

  let query = supabase
    .from('leads')
    .select('*, callers(name)')
    .order('lead_score', { ascending: false })
    .limit(limit)

  if (status   && status   !== 'all') query = query.eq('status', status)
  if (niche    && niche    !== 'all') query = query.eq('niche', niche)
  if (city     && city     !== 'all') query = query.eq('city', city)
  if (assigned === 'yes')             query = query.not('assigned_to', 'is', null)
  if (assigned === 'no')              query = query.is('assigned_to', null)

  const { data, error } = await query

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }

  return NextResponse.json(data ?? [])
}
