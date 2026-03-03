'use client'

import { useState, useEffect, useCallback } from 'react'
import { createClient } from '@/lib/supabase/client'
import type { ScraperJob, JobStatus } from '@/lib/types'

const STATUS_STYLES: Record<JobStatus, string> = {
  pending: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  running: 'bg-blue-500/20   text-blue-400   border-blue-500/30',
  done:    'bg-green-500/20  text-green-400  border-green-500/30',
  failed:  'bg-red-500/20    text-red-400    border-red-500/30',
}

// Worker is "online" if it sent a heartbeat within the last 30 seconds
const ONLINE_THRESHOLD_MS = 30_000

export function ScraperPanel() {
  const [city,         setCity]         = useState('')
  const [state,        setState]        = useState('')
  const [niche,        setNiche]        = useState('all')
  const [limit,        setLimit]        = useState(50)
  const [jobs,         setJobs]         = useState<ScraperJob[]>([])
  const [queuing,      setQueuing]      = useState(false)
  const [result,       setResult]       = useState<string | null>(null)
  const [workerOnline, setWorkerOnline] = useState(false)
  const [lastSeen,     setLastSeen]     = useState<Date | null>(null)

  // ── Worker status ────────────────────────────────────────────────────────
  const checkWorker = useCallback(async () => {
    const supabase = createClient()
    const { data } = await supabase
      .from('worker_status')
      .select('last_seen')
      .eq('id', 1)
      .single()

    if (data?.last_seen) {
      const ts  = new Date(data.last_seen)
      const age = Date.now() - ts.getTime()
      setLastSeen(ts)
      setWorkerOnline(age < ONLINE_THRESHOLD_MS)
    } else {
      setWorkerOnline(false)
      setLastSeen(null)
    }
  }, [])

  // ── Job list ─────────────────────────────────────────────────────────────
  const fetchJobs = useCallback(async () => {
    const res  = await fetch('/api/scrape')
    const data = await res.json()
    if (Array.isArray(data)) setJobs(data)
  }, [])

  useEffect(() => {
    checkWorker()
    fetchJobs()
    // Poll worker status every 10s, jobs every 15s
    const wv = setInterval(checkWorker, 10_000)
    const jv = setInterval(fetchJobs,   15_000)
    return () => { clearInterval(wv); clearInterval(jv) }
  }, [checkWorker, fetchJobs])

  // ── Queue a job ──────────────────────────────────────────────────────────
  async function handleQueue(e: React.FormEvent) {
    e.preventDefault()
    setQueuing(true)
    setResult(null)
    const res  = await fetch('/api/scrape', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ city, state, niche, limit }),
    })
    const data = await res.json()
    if (res.ok) {
      setResult(`Queued! The engine will start shortly.`)
      setCity(''); setState('')
      fetchJobs()
    } else {
      setResult(`Error: ${data.error}`)
    }
    setQueuing(false)
  }

  // ── Helpers ──────────────────────────────────────────────────────────────
  function fmt(ts: string | null) {
    if (!ts) return '—'
    return new Date(ts).toLocaleString()
  }

  function duration(job: ScraperJob) {
    if (!job.started_at) return '—'
    const end = job.finished_at ? new Date(job.finished_at) : new Date()
    const sec = Math.round((end.getTime() - new Date(job.started_at).getTime()) / 1000)
    return sec < 60 ? `${sec}s` : `${Math.floor(sec / 60)}m ${sec % 60}s`
  }

  function lastSeenLabel() {
    if (!lastSeen) return 'Never connected'
    const sec = Math.round((Date.now() - lastSeen.getTime()) / 1000)
    if (sec < 5)  return 'just now'
    if (sec < 60) return `${sec}s ago`
    return `${Math.floor(sec / 60)}m ago`
  }

  return (
    <div className="space-y-6">

      {/* ── Engine status banner ── */}
      <div className={`rounded-2xl border p-5 flex items-center justify-between ${
        workerOnline
          ? 'bg-green-500/10 border-green-500/30'
          : 'bg-slate-900 border-slate-700'
      }`}>
        <div className="flex items-center gap-3">
          <span className={`relative flex h-3 w-3`}>
            {workerOnline && (
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
            )}
            <span className={`relative inline-flex rounded-full h-3 w-3 ${
              workerOnline ? 'bg-green-400' : 'bg-slate-600'
            }`} />
          </span>
          <div>
            <p className={`font-semibold text-sm ${workerOnline ? 'text-green-400' : 'text-slate-400'}`}>
              {workerOnline ? 'Engine Online' : 'Engine Offline'}
            </p>
            <p className="text-slate-500 text-xs mt-0.5">
              {workerOnline
                ? `worker.py is running — last heartbeat ${lastSeenLabel()}`
                : `Run python worker.py on any machine to go online (last seen: ${lastSeenLabel()})`}
            </p>
          </div>
        </div>
        {workerOnline && (
          <span className="text-green-400 text-xs font-semibold bg-green-500/20 border border-green-500/30 px-3 py-1 rounded-full">
            Ready
          </span>
        )}
      </div>

      {/* ── Generate leads form ── */}
      <div className="bg-slate-900 rounded-2xl border border-slate-700 p-6">
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-blue-400 font-semibold">Generate Leads</h2>
          {!workerOnline && (
            <span className="text-xs text-yellow-400 bg-yellow-500/10 border border-yellow-500/30 px-2.5 py-1 rounded-full">
              Start worker.py first
            </span>
          )}
        </div>
        <p className="text-slate-400 text-xs mb-5">
          Fill in the target market and click Generate. The engine picks it up instantly.
        </p>
        <form onSubmit={handleQueue} className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1.5 font-semibold">City *</label>
            <input
              value={city} onChange={e => setCity(e.target.value)} required
              placeholder="Dallas"
              className="w-full bg-slate-800 border border-slate-600 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1.5 font-semibold">State</label>
            <input
              value={state} onChange={e => setState(e.target.value)}
              placeholder="TX"
              className="w-full bg-slate-800 border border-slate-600 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1.5 font-semibold">Niche</label>
            <input
              value={niche} onChange={e => setNiche(e.target.value)}
              placeholder="all  (or e.g. plumbers)"
              className="w-full bg-slate-800 border border-slate-600 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1.5 font-semibold">Limit</label>
            <input
              type="number" min={1} max={500}
              value={limit} onChange={e => setLimit(Number(e.target.value))}
              className="w-full bg-slate-800 border border-slate-600 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500"
            />
          </div>
          <div className="col-span-2 sm:col-span-4 flex items-center gap-4">
            <button
              type="submit"
              disabled={queuing || !workerOnline}
              title={!workerOnline ? 'Start worker.py on your machine first' : ''}
              className="px-6 py-2.5 rounded-xl font-semibold text-sm bg-gradient-to-r from-violet-500 to-blue-500 hover:from-violet-600 hover:to-blue-600 disabled:opacity-40 disabled:cursor-not-allowed transition"
            >
              {queuing ? 'Queuing…' : 'Generate Leads'}
            </button>
            {result && (
              <span className={`text-sm ${result.startsWith('Error') ? 'text-red-400' : 'text-green-400'}`}>
                {result}
              </span>
            )}
          </div>
        </form>
      </div>

      {/* ── Job history ── */}
      <div className="bg-slate-900 rounded-2xl border border-slate-700 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-700 flex items-center justify-between">
          <h2 className="text-blue-400 font-semibold">Run History</h2>
          <button onClick={fetchJobs} className="text-slate-400 hover:text-white text-xs transition">
            Refresh
          </button>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-950 text-slate-400 text-xs uppercase tracking-wide">
              <th className="px-5 py-3 text-left">City / Niche</th>
              <th className="px-5 py-3 text-left">Status</th>
              <th className="px-5 py-3 text-left">Leads</th>
              <th className="px-5 py-3 text-left">Duration</th>
              <th className="px-5 py-3 text-left">Queued</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map(job => (
              <tr key={job.id} className="border-t border-slate-800 hover:bg-slate-800/40 transition">
                <td className="px-5 py-3 font-medium">
                  {job.city}{job.state ? `, ${job.state}` : ''}{' '}
                  <span className="text-slate-400 font-normal">— {job.niche}</span>
                </td>
                <td className="px-5 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-semibold border ${STATUS_STYLES[job.status]}`}>
                    {job.status}
                  </span>
                  {job.error_msg && (
                    <p className="text-red-400 text-xs mt-1 max-w-xs truncate">{job.error_msg}</p>
                  )}
                </td>
                <td className="px-5 py-3 text-slate-300">{job.result_count || '—'}</td>
                <td className="px-5 py-3 text-slate-400">{duration(job)}</td>
                <td className="px-5 py-3 text-slate-400">{fmt(job.created_at)}</td>
              </tr>
            ))}
            {!jobs.length && (
              <tr>
                <td colSpan={5} className="px-5 py-10 text-center text-slate-500">
                  No runs yet. Start <code>worker.py</code> and click Generate Leads above.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
