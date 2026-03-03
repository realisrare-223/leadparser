import { createClient } from '@/lib/supabase/server'
import { NextRequest, NextResponse } from 'next/server'

// Admin only: queue a new scraper run
export async function POST(request: NextRequest) {
  const supabase = createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { data: caller } = await supabase
    .from('callers').select('role').eq('id', user.id).single()
  if (caller?.role !== 'admin') {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  const {
    city,
    state,
    niche           = 'all',
    limit           = 50,
    min_reviews     = 0,
    max_reviews     = 9999,
    min_rating      = 0,
    max_rating      = 5,
    website_filter  = 'any',   // 'any' | 'yes' | 'no'
    min_score       = 0,
  } = await request.json()

  if (!city) return NextResponse.json({ error: 'city is required' }, { status: 400 })

  const { data, error } = await supabase
    .from('scraper_jobs')
    .insert({
      city,
      state:          state ?? '',
      niche,
      limit_count:    limit,
      status:         'pending',
      progress:       0,
      min_reviews,
      max_reviews,
      min_rating,
      max_rating,
      website_filter,
      require_phone:  true,   // always required — no toggle in UI
      min_score,
    })
    .select()
    .single()

  if (error) return NextResponse.json({ error: error.message }, { status: 500 })
  return NextResponse.json(data)
}

// Admin only: list recent jobs (exclude cancelled — they're removed from history)
export async function GET() {
  const supabase = createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { data: caller } = await supabase
    .from('callers').select('role').eq('id', user.id).single()
  if (caller?.role !== 'admin') {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  const { data } = await supabase
    .from('scraper_jobs')
    .select('*')
    .neq('status', 'cancelled')
    .order('created_at', { ascending: false })
    .limit(25)

  return NextResponse.json(data ?? [])
}

// Admin only: cancel (and remove) a pending or running job
export async function DELETE(request: NextRequest) {
  const supabase = createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { data: caller } = await supabase
    .from('callers').select('role').eq('id', user.id).single()
  if (caller?.role !== 'admin') {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  const { id } = await request.json()
  if (!id) return NextResponse.json({ error: 'id required' }, { status: 400 })

  const { data: job } = await supabase
    .from('scraper_jobs').select('status').eq('id', id).single()
  if (!job) return NextResponse.json({ error: 'Not found' }, { status: 404 })

  if (job.status === 'running') {
    // Signal the worker to kill the subprocess; worker will delete the row itself
    await supabase.from('scraper_jobs').update({ status: 'cancelled' }).eq('id', id)
  } else {
    // pending, done, failed, or already cancelled — delete immediately
    await supabase.from('scraper_jobs').delete().eq('id', id)
  }

  return NextResponse.json({ ok: true })
}
