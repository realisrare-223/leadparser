'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import { LeadTable } from '@/components/LeadTable'
import { LeadStatsGrid, CallerStatsTable } from '@/components/StatsGrid'
import { AssignPanel } from '@/components/AssignPanel'
import type { Lead, LeadStats, CallerStats, Caller } from '@/lib/types'

type Tab = 'overview' | 'leads' | 'users'

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

  // Lead filters
  const [statusFilter,   setStatusFilter]   = useState('all')
  const [assignedFilter, setAssignedFilter] = useState('all')

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
    if (statusFilter   !== 'all') params.set('status',   statusFilter)
    if (assignedFilter !== 'all') params.set('assigned', assignedFilter)
    const res  = await fetch(`/api/admin/leads?${params}`)
    const data = await res.json()
    if (Array.isArray(data)) {
      setLeads(data)
      setNiches(Array.from(new Set(data.map((l: Lead) => l.niche))).sort() as string[])
      setCities(Array.from(new Set(data.map((l: Lead) => l.city))).sort() as string[])
    }
    setLoading(false)
  }, [statusFilter, assignedFilter])

  const fetchCallers = useCallback(async () => {
    const res = await fetch('/api/admin/users')
    const data = await res.json()
    if (Array.isArray(data)) setCallerList(data)
  }, [])

  useEffect(() => {
    const supabase = createClient()
    supabase.auth.getUser().then(async ({ data: { user } }) => {
      if (!user) { router.push('/login'); return }
      const { data: c } = await supabase.from('callers').select('role').eq('id', user.id).single()
      if (c?.role !== 'admin') { router.push('/dashboard'); return }
    })
    fetchStats()
    fetchCallers()
  }, [router, fetchStats, fetchCallers])

  useEffect(() => {
    fetchLeads()
    const iv = setInterval(() => { fetchStats(); fetchLeads() }, 30_000)
    return () => clearInterval(iv)
  }, [fetchLeads, fetchStats])

  async function handleAssign(callerId: string, count: number, niche: string, city: string) {
    const res = await fetch('/api/admin/assign', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ caller_id: callerId, count, niche, city }),
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

  async function handleLogout() {
    const supabase = createClient()
    await supabase.auth.signOut()
    router.push('/login')
  }

  const TAB = (t: Tab) =>
    `px-4 py-2 text-sm font-semibold rounded-lg transition ${
      tab === t ? 'bg-blue-500 text-white' : 'text-slate-400 hover:text-white'
    }`

  return (
    <div className="min-h-screen bg-slate-950">
      <header className="bg-slate-900 border-b border-slate-700 px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-violet-400 bg-clip-text text-transparent">
            LeadParser Engine
          </h1>
          <p className="text-slate-400 text-sm mt-0.5">Admin Dashboard</p>
        </div>
        <div className="flex items-center gap-2">
          <nav className="flex gap-1">
            <button className={TAB('overview')} onClick={() => setTab('overview')}>Overview</button>
            <button className={TAB('leads')}    onClick={() => setTab('leads')}>All Leads</button>
            <button className={TAB('users')}    onClick={() => setTab('users')}>Users</button>
          </nav>
          <button onClick={handleLogout} className="text-slate-400 hover:text-white text-sm transition ml-4">
            Sign Out
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8">

        {/* OVERVIEW */}
        {tab === 'overview' && (
          <>
            {stats && <LeadStatsGrid stats={stats} />}
            {callers.length > 0 && <CallerStatsTable callers={callers} />}
            <AssignPanel callers={callerList} niches={niches} cities={cities} onAssign={handleAssign} />
          </>
        )}

        {/* ALL LEADS */}
        {tab === 'leads' && (
          <div className="bg-slate-900 rounded-2xl border border-slate-700 p-6">
            <div className="flex flex-wrap items-center gap-3 mb-5">
              <h2 className="text-blue-400 font-semibold mr-2">All Leads</h2>
              <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
                className="bg-slate-800 border border-slate-600 rounded-xl px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500">
                <option value="all">All statuses</option>
                {['new','called','sold','followup','dead'].map(s => <option key={s} value={s}>{s}</option>)}
              </select>
              <select value={assignedFilter} onChange={e => setAssignedFilter(e.target.value)}
                className="bg-slate-800 border border-slate-600 rounded-xl px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500">
                <option value="all">All leads</option>
                <option value="no">Unassigned only</option>
                <option value="yes">Assigned only</option>
              </select>
              <span className="ml-auto text-slate-400 text-sm">
                {loading ? 'Loading...' : `${leads.length} leads`}
              </span>
            </div>
            <LeadTable leads={leads} showCaller />
          </div>
        )}

        {/* USERS */}
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
                    <th className="px-6 py-3 text-left">Role</th>
                    <th className="px-6 py-3 text-left">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {callerList.map(c => (
                    <tr key={c.id} className="border-t border-slate-800 hover:bg-slate-800/40 transition">
                      <td className="px-6 py-3 font-medium">{c.name}</td>
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
                    <tr><td colSpan={3} className="px-6 py-8 text-center text-slate-500">No users yet.</td></tr>
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
