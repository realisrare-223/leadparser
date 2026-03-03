'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import { NavBar } from '@/components/NavBar'
import { LeadTable } from '@/components/LeadTable'
import { LeadStatsGrid, CallerStatsTable } from '@/components/StatsGrid'
import { AssignPanel, type AssignFilters } from '@/components/AssignPanel'
import { ScraperPanel } from '@/components/ScraperPanel'
import { Combobox, type ComboOption } from '@/components/Combobox'
import { PRESET_NICHES } from '@/lib/niches'
import type { Lead, LeadStats, CallerStats, Caller } from '@/lib/types'

type Tab = 'overview' | 'leads' | 'scraper' | 'users'

// Toggles for the All Leads tab
interface LeadsTabFilters {
  status:     string
  assigned:   string
  niche:      string
  city:       string
  minScore:   number
  minRating:  number
  minReviews: number
  maxReviews: number
  hasWebsite: string
  hasPhone:   string
}

const DEFAULT_LEADS_FILTERS: LeadsTabFilters = {
  status:     'all',
  assigned:   'all',
  niche:      'all',
  city:       'all',
  minScore:   0,
  minRating:  0,
  minReviews: 0,
  maxReviews: 0,
  hasWebsite: 'any',
  hasPhone:   'any',
}

export default function AdminDashboard() {
  const router = useRouter()
  const [tab, setTab] = useState<Tab>('overview')

  const [stats,      setStats]      = useState<LeadStats | null>(null)
  const [callers,    setCallers]    = useState<CallerStats[]>([])
  const [leads,      setLeads]      = useState<Lead[]>([])
  const [callerList, setCallerList] = useState<Caller[]>([])
  const [niches,     setNiches]     = useState<string[]>([])
  const [cities,     setCities]     = useState<string[]>([])
  const [loading,    setLoading]    = useState(true)
  const [adminName,  setAdminName]  = useState('')

  // All Leads tab filters
  const [lf, setLf] = useState<LeadsTabFilters>(DEFAULT_LEADS_FILTERS)
  const [showAdvanced, setShowAdvanced] = useState(false)

  // New user form
  const [newName,     setNewName]     = useState('')
  const [newEmail,    setNewEmail]    = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newRole,     setNewRole]     = useState<'caller' | 'admin'>('caller')
  const [userResult,  setUserResult]  = useState<string | null>(null)
  const [userLoading, setUserLoading] = useState(false)

  const fetchStats = useCallback(async () => {
    const res = await fetch('/api/admin/stats')
    const data = await res.json()
    if (data.stats)   setStats(data.stats)
    if (data.callers) setCallers(data.callers)
  }, [])

  const fetchLeads = useCallback(async () => {
    const params = new URLSearchParams({ limit: '300' })
    if (lf.status     !== 'all') params.set('status',      lf.status)
    if (lf.assigned   !== 'all') params.set('assigned',    lf.assigned)
    if (lf.niche      !== 'all') params.set('niche',       lf.niche)
    if (lf.city       !== 'all') params.set('city',        lf.city)
    if (lf.minScore   > 0)       params.set('min_score',   String(lf.minScore))
    if (lf.minRating  > 0)       params.set('min_rating',  String(lf.minRating))
    if (lf.minReviews > 0)       params.set('min_reviews', String(lf.minReviews))
    if (lf.maxReviews > 0)       params.set('max_reviews', String(lf.maxReviews))
    if (lf.hasWebsite !== 'any') params.set('has_website', lf.hasWebsite)
    if (lf.hasPhone   !== 'any') params.set('has_phone',   lf.hasPhone)

    const res  = await fetch(`/api/admin/leads?${params}`)
    const data = await res.json()
    if (Array.isArray(data)) {
      setLeads(data)
      setNiches(Array.from(new Set(data.map((l: Lead) => l.niche))).sort() as string[])
      setCities(Array.from(new Set(data.map((l: Lead) => l.city))).sort() as string[])
    }
    setLoading(false)
  }, [lf])

  const fetchCallers = useCallback(async () => {
    const res = await fetch('/api/admin/users')
    const data = await res.json()
    if (Array.isArray(data)) setCallerList(data)
  }, [])

  useEffect(() => {
    const supabase = createClient()
    supabase.auth.getUser().then(async ({ data: { user } }) => {
      if (!user) { router.push('/login'); return }
      const { data: c } = await supabase.from('callers').select('name, role').eq('id', user.id).single()
      if (c?.role !== 'admin') { router.push('/dashboard'); return }
      setAdminName(c.name ?? user.email ?? '')
    })
    fetchStats()
    fetchCallers()
  }, [router, fetchStats, fetchCallers])

  useEffect(() => {
    fetchLeads()
    const iv = setInterval(() => { fetchStats(); fetchLeads() }, 30_000)
    return () => clearInterval(iv)
  }, [fetchLeads, fetchStats])

  async function handleAssign(callerId: string, count: number, filters: AssignFilters) {
    const res = await fetch('/api/admin/assign', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ caller_id: callerId, count, filters }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.error || 'Assignment failed')
    fetchStats(); fetchLeads()
    return data
  }

  async function handleCreateUser(e: React.FormEvent) {
    e.preventDefault()
    setUserLoading(true)
    setUserResult(null)
    const res = await fetch('/api/admin/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: newEmail, password: newPassword, name: newName, role: newRole }),
    })
    const data = await res.json()
    if (res.ok) {
      setUserResult(`Created: ${newName} (${newEmail})`)
      setNewName(''); setNewEmail(''); setNewPassword('')
      fetchCallers()
    } else {
      setUserResult(`Error: ${data.error}`)
    }
    setUserLoading(false)
  }

  function setLeadFilter<K extends keyof LeadsTabFilters>(key: K, val: LeadsTabFilters[K]) {
    setLf(f => ({ ...f, [key]: val }))
  }

  const activeLeadFilterCount = [
    lf.status     !== 'all',
    lf.assigned   !== 'all',
    lf.niche      !== 'all',
    lf.city       !== 'all',
    lf.minScore   > 0,
    lf.minRating  > 0,
    lf.minReviews > 0,
    lf.maxReviews > 0,
    lf.hasWebsite !== 'any',
    lf.hasPhone   !== 'any',
  ].filter(Boolean).length

  // Niche options for the All Leads filter bar (DB niches merged with presets)
  const nicheFilterOptions: ComboOption[] = [
    { value: 'all', label: 'All niches' },
    ...[...PRESET_NICHES, ...niches]
      .filter((n, i, arr) => arr.findIndex(x => x.toLowerCase() === n.toLowerCase()) === i)
      .sort()
      .map(n => ({ value: n, label: n })),
  ]
  const cityFilterOptions: ComboOption[] = [
    { value: 'all', label: 'All cities' },
    ...cities.map(c => ({ value: c, label: c })),
  ]

  const inputCls  = 'bg-slate-800 border border-slate-600 rounded-xl px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500'
  const selectCls = inputCls

  const TAB = (t: Tab) =>
    `px-4 py-2 text-sm font-semibold rounded-lg transition ${
      tab === t ? 'bg-blue-500 text-white' : 'text-slate-400 hover:text-white'
    }`

  return (
    <div className="min-h-screen bg-slate-950">
      <NavBar role="admin" subtitle={`Admin — ${adminName}`} />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4">
        <nav className="flex gap-1 border-b border-slate-800 pb-3 mb-6">
          <button className={TAB('overview')} onClick={() => setTab('overview')}>Overview</button>
          <button className={TAB('leads')}    onClick={() => setTab('leads')}>All Leads</button>
          <button className={TAB('scraper')}  onClick={() => setTab('scraper')}>Scraper</button>
          <button className={TAB('users')}    onClick={() => setTab('users')}>Users</button>
        </nav>
      </div>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 pb-12">

        {/* ── OVERVIEW ──────────────────────────────────────────────────────── */}
        {tab === 'overview' && (
          <>
            {stats && <LeadStatsGrid stats={stats} />}
            {callers.length > 0 && <CallerStatsTable callers={callers} />}
            <AssignPanel callers={callerList} niches={niches} cities={cities} onAssign={handleAssign} />
          </>
        )}

        {/* ── ALL LEADS ─────────────────────────────────────────────────────── */}
        {tab === 'leads' && (
          <div className="bg-slate-900 rounded-2xl border border-slate-700 p-6">
            <div className="flex flex-wrap items-center gap-2 mb-4">
              <h2 className="text-blue-400 font-semibold mr-2">All Leads</h2>

              {/* Basic filters always visible */}
              <select value={lf.status} onChange={e => setLeadFilter('status', e.target.value)}
                className={selectCls}>
                <option value="all">All statuses</option>
                {['new','called','sold','followup','dead'].map(s => <option key={s} value={s}>{s}</option>)}
              </select>

              <select value={lf.assigned} onChange={e => setLeadFilter('assigned', e.target.value)}
                className={selectCls}>
                <option value="all">All leads</option>
                <option value="no">Unassigned only</option>
                <option value="yes">Assigned only</option>
              </select>

              {/* Advanced filter toggle */}
              <button
                onClick={() => setShowAdvanced(x => !x)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-sm border transition ${
                  showAdvanced
                    ? 'bg-blue-500/20 border-blue-500/40 text-blue-400'
                    : 'border-slate-600 text-slate-400 hover:text-white'
                }`}
              >
                Filters
                {activeLeadFilterCount > 0 && (
                  <span className="bg-blue-500 text-white text-xs font-bold rounded-full w-4 h-4 flex items-center justify-center">
                    {activeLeadFilterCount}
                  </span>
                )}
              </button>

              {activeLeadFilterCount > 0 && (
                <button
                  onClick={() => setLf(DEFAULT_LEADS_FILTERS)}
                  className="text-xs text-slate-500 hover:text-red-400 transition px-2"
                >
                  Reset
                </button>
              )}

              <span className="ml-auto text-slate-400 text-sm">
                {loading ? 'Loading…' : `${leads.length} leads`}
              </span>
            </div>

            {/* Advanced filter panel */}
            {showAdvanced && (
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 mb-5 p-4 bg-slate-950/60 rounded-xl border border-slate-800">
                {/* Niche */}
                <div>
                  <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1 font-semibold">Niche</label>
                  <Combobox
                    value={lf.niche === 'all' ? '' : lf.niche}
                    onChange={v => setLeadFilter('niche', v || 'all')}
                    options={nicheFilterOptions}
                    placeholder="All niches"
                    allowFreeText
                  />
                </div>

                {/* City */}
                <div>
                  <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1 font-semibold">City</label>
                  <Combobox
                    value={lf.city === 'all' ? '' : lf.city}
                    onChange={v => setLeadFilter('city', v || 'all')}
                    options={cityFilterOptions}
                    placeholder="All cities"
                    allowFreeText
                  />
                </div>

                {/* Min score */}
                <div>
                  <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1 font-semibold">
                    Min Score: {lf.minScore}
                  </label>
                  <input type="range" min={0} max={50} step={1} value={lf.minScore}
                    onChange={e => setLeadFilter('minScore', Number(e.target.value))}
                    className="w-full accent-blue-500 mt-2" />
                </div>

                {/* Min rating */}
                <div>
                  <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1 font-semibold">
                    Min Rating: {lf.minRating === 0 ? 'Any' : `${lf.minRating}★`}
                  </label>
                  <input type="range" min={0} max={5} step={0.5} value={lf.minRating}
                    onChange={e => setLeadFilter('minRating', Number(e.target.value))}
                    className="w-full accent-blue-500 mt-2" />
                </div>

                {/* Min reviews */}
                <div>
                  <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1 font-semibold">Min Reviews</label>
                  <input type="number" min={0} value={lf.minReviews} placeholder="0 (any)"
                    onChange={e => setLeadFilter('minReviews', Math.max(0, Number(e.target.value)))}
                    className={`${inputCls} w-full`} />
                </div>

                {/* Max reviews */}
                <div>
                  <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1 font-semibold">Max Reviews</label>
                  <input type="number" min={0} value={lf.maxReviews} placeholder="0 (no limit)"
                    onChange={e => setLeadFilter('maxReviews', Math.max(0, Number(e.target.value)))}
                    className={`${inputCls} w-full`} />
                </div>

                {/* Has website */}
                <div>
                  <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1 font-semibold">Website</label>
                  <select value={lf.hasWebsite} onChange={e => setLeadFilter('hasWebsite', e.target.value)}
                    className={`${selectCls} w-full`}>
                    <option value="any">Any</option>
                    <option value="no">No website</option>
                    <option value="yes">Has website</option>
                  </select>
                </div>

                {/* Has phone */}
                <div>
                  <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1 font-semibold">Phone</label>
                  <select value={lf.hasPhone} onChange={e => setLeadFilter('hasPhone', e.target.value)}
                    className={`${selectCls} w-full`}>
                    <option value="any">Any</option>
                    <option value="yes">Has phone</option>
                    <option value="no">No phone</option>
                  </select>
                </div>
              </div>
            )}

            <LeadTable leads={leads} showCaller />
          </div>
        )}

        {/* ── SCRAPER ───────────────────────────────────────────────────────── */}
        {tab === 'scraper' && <ScraperPanel />}

        {/* ── USERS ─────────────────────────────────────────────────────────── */}
        {tab === 'users' && (
          <div className="space-y-6">
            <div className="bg-slate-900 rounded-2xl border border-slate-700 p-6">
              <h2 className="text-blue-400 font-semibold mb-5">Add New User</h2>
              <form onSubmit={handleCreateUser} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div>
                  <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1.5 font-semibold">Full Name</label>
                  <input value={newName} onChange={e => setNewName(e.target.value)} required placeholder="John Doe"
                    className="w-full bg-slate-800 border border-slate-600 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500" />
                </div>
                <div>
                  <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1.5 font-semibold">Email</label>
                  <input type="email" value={newEmail} onChange={e => setNewEmail(e.target.value)} required placeholder="john@company.com"
                    className="w-full bg-slate-800 border border-slate-600 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500" />
                </div>
                <div>
                  <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1.5 font-semibold">Password</label>
                  <input type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} required placeholder="Min 6 characters"
                    className="w-full bg-slate-800 border border-slate-600 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500" />
                </div>
                <div>
                  <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1.5 font-semibold">Role</label>
                  <select value={newRole} onChange={e => setNewRole(e.target.value as 'caller' | 'admin')}
                    className="w-full bg-slate-800 border border-slate-600 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500">
                    <option value="caller">Caller</option>
                    <option value="admin">Admin</option>
                  </select>
                </div>
                <div className="sm:col-span-2 lg:col-span-4 flex items-center gap-4">
                  <button type="submit" disabled={userLoading}
                    className="px-6 py-2.5 rounded-xl font-semibold text-sm bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 disabled:opacity-50 transition">
                    {userLoading ? 'Creating...' : 'Create User'}
                  </button>
                  {userResult && (
                    <span className={`text-sm ${userResult.startsWith('Error') ? 'text-red-400' : 'text-green-400'}`}>
                      {userResult}
                    </span>
                  )}
                </div>
              </form>
            </div>

            <div className="bg-slate-900 rounded-2xl border border-slate-700 overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-700">
                <h2 className="text-blue-400 font-semibold">All Users ({callerList.length})</h2>
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-slate-950 text-slate-400 text-xs uppercase tracking-wide">
                    <th className="px-6 py-3 text-left">Name</th>
                    <th className="px-6 py-3 text-left">Email</th>
                    <th className="px-6 py-3 text-left">Role</th>
                    <th className="px-6 py-3 text-left">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {callerList.map(c => (
                    <tr key={c.id} className="border-t border-slate-800 hover:bg-slate-800/40 transition">
                      <td className="px-6 py-3 font-medium">{c.name}</td>
                      <td className="px-6 py-3 text-slate-400 text-xs">{(c as any).email ?? '—'}</td>
                      <td className="px-6 py-3">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-semibold border ${
                          c.role === 'admin'
                            ? 'bg-violet-500/20 text-violet-400 border-violet-500/30'
                            : 'bg-blue-500/20 text-blue-400 border-blue-500/30'
                        }`}>{c.role}</span>
                      </td>
                      <td className="px-6 py-3 text-slate-400">{new Date(c.created_at).toLocaleDateString()}</td>
                    </tr>
                  ))}
                  {!callerList.length && (
                    <tr><td colSpan={4} className="px-6 py-8 text-center text-slate-500">No users yet.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

      </main>
    </div>
  )
}
