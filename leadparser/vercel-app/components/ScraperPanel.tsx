'use client'

import { useState, useEffect, useCallback } from 'react'
import type { ScraperJob, JobStatus } from '@/lib/types'

const STATUS_STYLES: Record<JobStatus, string> = {
  pending:  'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  running:  'bg-blue-500/20   text-blue-400   border-blue-500/30',
  done:     'bg-green-500/20  text-green-400  border-green-500/30',
  failed:   'bg-red-500/20    text-red-400    border-red-500/30',
}

export function ScraperPanel() {
  const [city,    setCity]    = useState('')
  const [state,   setState]   = useState('')
  const [niche,   setNiche]   = useState('all')
  const [limit,   setLimit]   = useState(50)
  const [jobs,    setJobs]    = useState<ScraperJob[]>([])
  const [loading, setLoading] = useState(false)
  const [result,  setResult]  = useState<string | null>(null)

  const fetchJobs = useCallback(async () => {
    const res  = await fetch('/api/scrape')
    const data = await res.json()
    if (Array.isArray(data)) setJobs(data)
  }, [])

  useEffect(() => {
    fetchJobs()
    // Poll every 15s so running jobs update live
    const iv = setInterval(fetchJobs, 15_000)
    return () => clearInterval(iv)
  }, [fetchJobs])

  async function handleQueue(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setResult(null)
    const res  = await fetch('/api/scrape', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ city, state, niche, limit }),
    })
    const data = await res.json()
    if (res.ok) {
      setResult(`Queued! Job ID: ${data.id.slice(0, 8)}…`)
      setCity(''); setState('')
      fetchJobs()
    } else {
      setResult(`Error: ${data.error}`)
    }
    setLoading(false)
  }

  function fmt(ts: string | null) {
    if (!ts) return '—'
    return new Date(ts).toLocaleString()
  }

  function duration(job: ScraperJob) {
    if (!job.started_at) return '—'
    const end = job.finished_at ? new Date(job.finished_at) : new Date()
    const sec = Math.round((end.getTime() - new Date(job.started_at).getTime()) / 1000)
    if (sec < 60) return `${sec}s`
    return `${Math.floor(sec / 60)}m ${sec % 60}s`
  }

  return (
    <div className="space-y-6">
      {/* Queue form */}
      <div className="bg-slate-900 rounded-2xl border border-slate-700 p-6">
        <h2 className="text-blue-400 font-semibold mb-1">Queue Scraper Run</h2>
        <p className="text-slate-400 text-xs mb-5">
          Your 24/7 PC running <code className="text-slate-300">worker.py</code> will pick this up automatically.
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
              type="submit" disabled={loading}
              className="px-6 py-2.5 rounded-xl font-semibold text-sm bg-gradient-to-r from-violet-500 to-blue-500 hover:from-violet-600 hover:to-blue-600 disabled:opacity-50 transition"
            >
              {loading ? 'Queuing…' : 'Queue Run'}
            </button>
            {result && (
              <span className={`text-sm ${result.startsWith('Error') ? 'text-red-400' : 'text-green-400'}`}>
                {result}
              </span>
            )}
          </div>
        </form>
      </div>

      {/* Job history */}
      <div className="bg-slate-900 rounded-2xl border border-slate-700 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-700 flex items-center justify-between">
          <h2 className="text-blue-400 font-semibold">Job History</h2>
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
                  No jobs yet. Queue a run above, then start <code>worker.py</code> on your PC.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
