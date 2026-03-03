'use client'

// ============================================================
// ScraperPanel — queue scraper jobs, watch live logs, view history.
// ============================================================

import { useState, useEffect, useCallback, useRef } from 'react'
import { createClient } from '@/lib/supabase/client'
import type { ScraperJob, JobStatus } from '@/lib/types'
import { Combobox, type ComboOption } from '@/components/Combobox'
import { NA_REGIONS, COUNTRY_ORDER, COUNTRY_LABELS, resolveRegion } from '@/lib/north-america'
import { PRESET_NICHES } from '@/lib/niches'

// ── Types ──────────────────────────────────────────────────────────────────

interface LogEntry {
  id:      number
  ts:      string
  level:   string
  message: string
}

// ── Constants ──────────────────────────────────────────────────────────────

const STATUS_STYLES: Record<JobStatus, string> = {
  pending: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  running: 'bg-blue-500/20   text-blue-400   border-blue-500/30',
  done:    'bg-green-500/20  text-green-400  border-green-500/30',
  failed:  'bg-red-500/20    text-red-400    border-red-500/30',
}

const LOG_LEVEL_STYLES: Record<string, string> = {
  debug:   'text-slate-500',
  info:    'text-slate-300',
  warning: 'text-yellow-400',
  error:   'text-red-400',
}

const ONLINE_THRESHOLD_MS = 30_000

// ── Static option lists ────────────────────────────────────────────────────

const REGION_OPTIONS: ComboOption[] = COUNTRY_ORDER.flatMap(country => {
  const regions = NA_REGIONS.filter(r => r.country === country)
  return regions.map(r => ({
    value:    r.name,
    label:    r.name,
    sublabel: `${r.abbr} · ${r.countryLabel}`,
    group:    COUNTRY_LABELS[country],
  }))
})

const NICHE_OPTIONS: ComboOption[] = PRESET_NICHES.map(n => ({ value: n, label: n }))

// ── Component ──────────────────────────────────────────────────────────────

export function ScraperPanel() {
  // Form state
  const [city,    setCity]    = useState('')
  const [state,   setState]   = useState('')
  const [niche,   setNiche]   = useState('')
  const [limitStr, setLimitStr] = useState('50')   // string to avoid "020" bug

  // UI state
  const [queuing,      setQueuing]      = useState(false)
  const [result,       setResult]       = useState<string | null>(null)
  const [resultOk,     setResultOk]     = useState(true)
  const [workerOnline, setWorkerOnline] = useState(false)
  const [lastSeen,     setLastSeen]     = useState<Date | null>(null)

  // Job & log state
  const [jobs,         setJobs]         = useState<ScraperJob[]>([])
  const [selectedJob,  setSelectedJob]  = useState<string | null>(null)
  const [logs,         setLogs]         = useState<LogEntry[]>([])
  const [lastLogId,    setLastLogId]    = useState(0)
  const logsEndRef = useRef<HTMLDivElement>(null)

  // ── Worker status ──────────────────────────────────────────────────────

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

  // ── Job list ──────────────────────────────────────────────────────────

  const fetchJobs = useCallback(async () => {
    const res  = await fetch('/api/scrape')
    const data = await res.json()
    if (Array.isArray(data)) {
      setJobs(data)
      // Auto-select the most recent running job if none selected
      setSelectedJob(prev => {
        if (prev) return prev
        const running = data.find((j: ScraperJob) => j.status === 'running')
        return running?.id ?? data[0]?.id ?? null
      })
    }
  }, [])

  // ── Log polling ───────────────────────────────────────────────────────

  const fetchLogs = useCallback(async () => {
    if (!selectedJob) return
    try {
      const res  = await fetch(`/api/scrape/logs?job_id=${selectedJob}&after=${lastLogId}`)
      const data = await res.json()
      if (Array.isArray(data) && data.length > 0) {
        setLogs(prev => [...prev, ...data])
        setLastLogId(data[data.length - 1].id)
      }
    } catch {
      // ignore transient fetch errors
    }
  }, [selectedJob, lastLogId])

  // Scroll logs to bottom on new entries
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  // Reset logs when selected job changes
  useEffect(() => {
    setLogs([])
    setLastLogId(0)
  }, [selectedJob])

  useEffect(() => {
    checkWorker()
    fetchJobs()
    const wv = setInterval(checkWorker, 10_000)
    const jv = setInterval(fetchJobs,   15_000)
    return () => { clearInterval(wv); clearInterval(jv) }
  }, [checkWorker, fetchJobs])

  // Poll logs every 2s when a running job is selected
  const selectedJobObj = jobs.find(j => j.id === selectedJob)
  useEffect(() => {
    if (!selectedJob) return
    fetchLogs()   // immediate on selection
    const lv = setInterval(fetchLogs, 2_000)
    return () => clearInterval(lv)
  }, [selectedJob, fetchLogs])

  // ── Queue job ─────────────────────────────────────────────────────────

  async function handleQueue(e: React.FormEvent) {
    e.preventDefault()

    const limit = parseInt(limitStr, 10) || 1

    // Normalize state abbreviation → canonical name
    let resolvedState = state.trim()
    const matched = resolveRegion(resolvedState)
    if (matched) resolvedState = matched.name

    setQueuing(true)
    setResult(null)

    try {
      const res  = await fetch('/api/scrape', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ city, state: resolvedState, niche: niche || 'all', limit }),
      })
      const data = await res.json()

      if (res.ok) {
        setResult(`Queued — collecting up to ${limit} leads. The engine will start shortly.`)
        setResultOk(true)
        setCity(''); setState(''); setNiche('')
        await fetchJobs()
        // Auto-select the new job to show its logs
        if (data?.id) setSelectedJob(data.id)
      } else {
        setResult(`Error: ${data.error ?? 'Unknown error'}`)
        setResultOk(false)
      }
    } catch (err: any) {
      setResult(`Error: ${err?.message ?? 'Network error'}`)
      setResultOk(false)
    } finally {
      setQueuing(false)
    }
  }

  // ── Helpers ───────────────────────────────────────────────────────────

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

  function handleLimitChange(e: React.ChangeEvent<HTMLInputElement>) {
    // Strip leading zeros so "020" never appears
    const raw     = e.target.value.replace(/[^0-9]/g, '')
    const cleaned = raw.replace(/^0+(\d)/, '$1')
    setLimitStr(cleaned || '0')
  }

  // ── Render ────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">

      {/* ── Engine status ── */}
      <div className={`rounded-2xl border p-5 flex items-center justify-between ${
        workerOnline
          ? 'bg-green-500/10 border-green-500/30'
          : 'bg-slate-900 border-slate-700'
      }`}>
        <div className="flex items-center gap-3">
          <span className="relative flex h-3 w-3">
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
                : `Run python worker.py to go online (last seen: ${lastSeenLabel()})`}
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
          The <strong>Limit</strong> is your <em>target</em> — the scraper collects up to 4× raw
          listings and filters down, so you always get that many leads (or all available if fewer exist).
        </p>

        <form onSubmit={handleQueue} className="grid grid-cols-2 sm:grid-cols-4 gap-4">

          {/* City */}
          <div>
            <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1.5 font-semibold">
              City *
            </label>
            <input
              value={city}
              onChange={e => setCity(e.target.value)}
              required
              placeholder="e.g. Dallas"
              className="w-full bg-slate-800 border border-slate-600 rounded-xl px-3 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* State / Province — autocomplete */}
          <div>
            <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1.5 font-semibold">
              State / Province
            </label>
            <Combobox
              value={state}
              onChange={setState}
              options={REGION_OPTIONS}
              placeholder="TX, Texas, Ontario…"
              allowFreeText
            />
          </div>

          {/* Niche — autocomplete */}
          <div>
            <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1.5 font-semibold">
              Niche
            </label>
            <Combobox
              value={niche}
              onChange={setNiche}
              options={NICHE_OPTIONS}
              placeholder="Plumbers, HVAC…"
              allowFreeText
            />
          </div>

          {/* Limit — fixed 020 bug by using string state */}
          <div>
            <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1.5 font-semibold">
              Target Leads
            </label>
            <input
              type="text"
              inputMode="numeric"
              value={limitStr}
              onChange={handleLimitChange}
              onFocus={e => e.target.select()}
              placeholder="50"
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
              {queuing ? 'Queuing…' : `Generate ${limitStr || '?'} Leads`}
            </button>
            {result && (
              <span className={`text-sm ${resultOk ? 'text-green-400' : 'text-red-400'}`}>
                {result}
              </span>
            )}
          </div>
        </form>
      </div>

      {/* ── Job history + live logs ── */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">

        {/* Job history table */}
        <div className="bg-slate-900 rounded-2xl border border-slate-700 overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-700 flex items-center justify-between">
            <h2 className="text-blue-400 font-semibold">Run History</h2>
            <button onClick={fetchJobs} className="text-slate-400 hover:text-white text-xs transition">
              Refresh
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-950 text-slate-400 text-xs uppercase tracking-wide">
                  <th className="px-4 py-3 text-left">City / Niche</th>
                  <th className="px-4 py-3 text-left">Status</th>
                  <th className="px-4 py-3 text-left">Leads</th>
                  <th className="px-4 py-3 text-left">Time</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map(job => (
                  <tr
                    key={job.id}
                    onClick={() => setSelectedJob(job.id)}
                    className={`border-t border-slate-800 cursor-pointer transition ${
                      selectedJob === job.id
                        ? 'bg-blue-500/10 border-l-2 border-l-blue-500'
                        : 'hover:bg-slate-800/40'
                    }`}
                  >
                    <td className="px-4 py-3 font-medium">
                      <span className="block">{job.city}{job.state ? `, ${job.state}` : ''}</span>
                      <span className="text-slate-400 text-xs font-normal">{job.niche}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-semibold border ${STATUS_STYLES[job.status]}`}>
                        {job.status}
                      </span>
                      {job.error_msg && (
                        <p className="text-red-400 text-xs mt-1 max-w-[180px] truncate" title={job.error_msg}>
                          {job.error_msg}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-300">{job.result_count || '—'}</td>
                    <td className="px-4 py-3 text-slate-400 text-xs">{duration(job)}</td>
                  </tr>
                ))}
                {!jobs.length && (
                  <tr>
                    <td colSpan={4} className="px-4 py-10 text-center text-slate-500">
                      No runs yet. Start <code>worker.py</code> and click Generate Leads.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Live logs panel */}
        <div className="bg-slate-900 rounded-2xl border border-slate-700 overflow-hidden flex flex-col">
          <div className="px-5 py-4 border-b border-slate-700 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h2 className="text-blue-400 font-semibold">Logs</h2>
              {selectedJobObj && (
                <span className={`px-2 py-0.5 rounded-full text-xs font-semibold border ${STATUS_STYLES[selectedJobObj.status]}`}>
                  {selectedJobObj.status}
                </span>
              )}
              {selectedJobObj?.status === 'running' && (
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-400" />
                </span>
              )}
            </div>
            <div className="flex items-center gap-3">
              {selectedJobObj && (
                <span className="text-slate-500 text-xs">
                  {selectedJobObj.city}{selectedJobObj.state ? `, ${selectedJobObj.state}` : ''} — {selectedJobObj.niche}
                </span>
              )}
              {logs.length > 0 && (
                <button
                  onClick={() => { setLogs([]); setLastLogId(0) }}
                  className="text-slate-500 hover:text-red-400 text-xs transition"
                >
                  Clear
                </button>
              )}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto min-h-[280px] max-h-[420px] p-3 font-mono text-xs space-y-0.5 bg-slate-950/40">
            {!selectedJob ? (
              <p className="text-slate-600 p-4 text-center">Click a job row to see its logs.</p>
            ) : logs.length === 0 ? (
              <p className="text-slate-600 p-4 text-center">
                {selectedJobObj?.status === 'pending'
                  ? 'Job is pending — waiting for worker to pick it up…'
                  : 'No logs yet. Run the job with the latest worker.py to see live output.'}
              </p>
            ) : (
              logs.map(entry => (
                <div key={entry.id} className="flex gap-2 leading-5">
                  <span className="text-slate-600 shrink-0 select-none">
                    {new Date(entry.ts).toLocaleTimeString()}
                  </span>
                  <span className={`shrink-0 uppercase text-[10px] font-bold mt-0.5 w-14 ${LOG_LEVEL_STYLES[entry.level] ?? 'text-slate-400'}`}>
                    {entry.level}
                  </span>
                  <span className={`break-all ${LOG_LEVEL_STYLES[entry.level] ?? 'text-slate-300'}`}>
                    {entry.message}
                  </span>
                </div>
              ))
            )}
            <div ref={logsEndRef} />
          </div>
        </div>

      </div>
    </div>
  )
}
