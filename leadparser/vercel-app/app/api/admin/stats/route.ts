import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'

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

// GET /api/admin/stats — aggregated lead stats + per-caller breakdown
export async function GET() {
  const supabase = createClient()
  const admin = await requireAdmin(supabase)
  if (!admin) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  // Query the lead_stats and caller_stats views created in schema.sql
  const [{ data: leadStats }, { data: callerStats }] = await Promise.all([
    supabase.from('lead_stats').select('*').single(),
    supabase.from('caller_stats').select('*').order('total_assigned', { ascending: false }),
  ])

  // Fallback: if views not available, compute inline
  if (!leadStats) {
    const { data: leads } = await supabase.from('leads').select('status, lead_score, assigned_to')
    const rows = leads ?? []
    const inline = {
      total:          rows.length,
      new_count:      rows.filter(r => r.status === 'new').length,
      assigned:       rows.filter(r => r.assigned_to).length,
      called:         rows.filter(r => r.status === 'called').length,
      sold:           rows.filter(r => r.status === 'sold').length,
      followup:       rows.filter(r => r.status === 'followup').length,
      dead:           rows.filter(r => r.status === 'dead').length,
      hot:            rows.filter(r => r.lead_score >= 18).length,
      warm:           rows.filter(r => r.lead_score >= 12 && r.lead_score < 18).length,
      conversion_pct: null,
    }
    return NextResponse.json({ stats: inline, callers: callerStats ?? [] })
  }

  return NextResponse.json({ stats: leadStats, callers: callerStats ?? [] })
}
