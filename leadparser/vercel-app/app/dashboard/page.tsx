'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import { NavBar } from '@/components/NavBar'
import { LeadTable } from '@/components/LeadTable'
import type { Lead, LeadStatus } from '@/lib/types'

const STATUS_FILTERS = ['all', 'new', 'called', 'sold', 'followup', 'dead'] as const

export default function CallerDashboard() {
  const router  = useRouter()
  const [leads,        setLeads]        = useState<Lead[]>([])
  const [loading,      setLoading]      = useState(true)
  const [statusFilter, setStatusFilter] = useState('all')
  const [nicheFilter,  setNicheFilter]  = useState('all')
  const [niches,       setNiches]       = useState<string[]>([])
  const [callerName,   setCallerName]   = useState('')
  const [role,         setRole]         = useState<'caller' | 'admin'>('caller')

  const fetchLeads = useCallback(async () => {
    const params = new URLSearchParams()
    if (statusFilter !== 'all') params.set('status', statusFilter)
    if (nicheFilter  !== 'all') params.set('niche',  nicheFilter)

    const res  = await fetch(`/api/leads?${params}`)
    const data = await res.json()
    if (Array.isArray(data)) {
      setLeads(data)
      const unique = Array.from(new Set(data.map((l: Lead) => l.niche))).sort()
      setNiches(unique as string[])
    }
    setLoading(false)
  }, [statusFilter, nicheFilter])

  useEffect(() => {
    const supabase = createClient()
    supabase.auth.getUser().then(({ data: { user } }) => {
      if (!user) { router.push('/login'); return }
      supabase.from('callers').select('name, role').eq('id', user.id).single()
        .then(({ data }) => {
          setCallerName(data?.name ?? user.email ?? '')
          setRole(data?.role ?? 'caller')
        })
    })
  }, [router])

  useEffect(() => {
    fetchLeads()
    const interval = setInterval(fetchLeads, 30_000)
    return () => clearInterval(interval)
  }, [fetchLeads])

  async function handleStatusChange(id: string, status: LeadStatus) {
    await fetch('/api/leads', {
      method:  'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ id, status }),
    })
    fetchLeads()
  }

  async function handleNotesChange(id: string, caller_notes: string) {
    await fetch('/api/leads', {
      method:  'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ id, caller_notes }),
    })
  }

  // Counts per status for the tab badges
  const counts = leads.reduce((acc, l) => {
    acc[l.status] = (acc[l.status] ?? 0) + 1
    return acc
  }, {} as Record<string, number>)

  return (
    <div className="min-h-screen bg-slate-950">
      <NavBar role={role} subtitle={`Caller — ${callerName}`} />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
        {/* Quick stats bar */}
        <div className="grid grid-cols-3 sm:grid-cols-5 gap-3 mb-6">
          {([['new', 'New', 'text-blue-400'], ['called', 'Called', 'text-yellow-400'], ['sold', 'Sold', 'text-green-400'], ['followup', 'Follow Up', 'text-violet-400'], ['dead', 'Dead', 'text-slate-500']] as const).map(([s, label, color]) => (
            <div key={s} className="bg-slate-900 rounded-xl p-4 border border-slate-700 text-center">
              <div className={`text-2xl font-bold ${color}`}>{counts[s] ?? 0}</div>
              <div className="text-xs text-slate-400 uppercase mt-0.5">{label}</div>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3 mb-5">
          <div className="flex flex-wrap gap-2">
            {STATUS_FILTERS.map(f => (
              <button
                key={f}
                onClick={() => setStatusFilter(f)}
                className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition ${
                  statusFilter === f
                    ? 'bg-blue-500 border-blue-500 text-white'
                    : 'bg-slate-800 border-slate-600 text-slate-400 hover:border-blue-500'
                }`}
              >
                {f === 'all' ? 'All' : f.charAt(0).toUpperCase() + f.slice(1)}
                {f !== 'all' && counts[f] ? ` (${counts[f]})` : ''}
              </button>
            ))}
          </div>

          {niches.length > 0 && (
            <select
              value={nicheFilter}
              onChange={e => setNicheFilter(e.target.value)}
              className="ml-auto bg-slate-800 border border-slate-600 rounded-xl px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500"
            >
              <option value="all">All niches</option>
              {niches.map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          )}
        </div>

        <p className="text-slate-400 text-sm mb-4">
          {loading ? 'Loading...' : `${leads.length} lead${leads.length !== 1 ? 's' : ''}`}
        </p>

        {loading ? (
          <div className="text-center py-16 text-slate-500">Loading your leads...</div>
        ) : (
          <LeadTable
            leads={leads}
            onStatusChange={handleStatusChange}
            onNotesChange={handleNotesChange}
          />
        )}
      </main>
    </div>
  )
}
