import { createClient } from '@/lib/supabase/server'
import { NextRequest, NextResponse } from 'next/server'

// GET /api/scrape/logs?job_id=UUID&after=0
// Returns log entries for a scraper job, optionally only those with id > after
// (for incremental polling).
export async function GET(request: NextRequest) {
  const supabase = createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { data: caller } = await supabase
    .from('callers').select('role').eq('id', user.id).single()
  if (caller?.role !== 'admin') {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  const p      = new URL(request.url).searchParams
  const job_id = p.get('job_id')
  const after  = parseInt(p.get('after') ?? '0', 10)

  if (!job_id) {
    return NextResponse.json({ error: 'job_id is required' }, { status: 400 })
  }

  let query = supabase
    .from('scraper_logs')
    .select('id, ts, level, message')
    .eq('job_id', job_id)
    .order('id', { ascending: true })
    .limit(200)

  if (after > 0) query = query.gt('id', after)

  const { data, error } = await query
  if (error) return NextResponse.json({ error: error.message }, { status: 500 })

  return NextResponse.json(data ?? [])
}
