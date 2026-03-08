import { createClient } from '@/lib/supabase/server'
import { NextRequest, NextResponse } from 'next/server'
import type { LeadStatus } from '@/lib/types'

// GET /api/leads — fetch caller's own assigned leads
export async function GET(request: NextRequest) {
  const supabase = createClient()

  const { data: { user }, error: authError } = await supabase.auth.getUser()
  if (!user || authError) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const { searchParams } = new URL(request.url)
  const status = searchParams.get('status')
  const niche  = searchParams.get('niche')
  const city   = searchParams.get('city')

  let query = supabase
    .from('leads')
    .select('*')
    .eq('assigned_to', user.id)
    .order('created_at', { ascending: false })  // newest leads first

  if (status && status !== 'all') query = query.eq('status', status as LeadStatus)
  if (niche  && niche  !== 'all') query = query.eq('niche', niche)
  if (city   && city   !== 'all') query = query.eq('city', city)

  const { data, error } = await query

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }

  return NextResponse.json(data ?? [])
}

// PATCH /api/leads — update status or notes on a single lead
export async function PATCH(request: NextRequest) {
  const supabase = createClient()

  const { data: { user }, error: authError } = await supabase.auth.getUser()
  if (!user || authError) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const body = await request.json()
  const { id, status, caller_notes } = body as {
    id: string
    status?: LeadStatus
    caller_notes?: string
  }

  if (!id) {
    return NextResponse.json({ error: 'Lead ID required' }, { status: 400 })
  }

  const updates: Record<string, unknown> = {}
  if (status       !== undefined) updates.status       = status
  if (caller_notes !== undefined) updates.caller_notes = caller_notes

  const { error } = await supabase
    .from('leads')
    .update(updates)
    .eq('id', id)
    .eq('assigned_to', user.id) // callers can only update their own leads

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }

  return NextResponse.json({ ok: true })
}
