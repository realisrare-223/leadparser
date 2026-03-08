'use client'

// ============================================================
// ScraperPanel — queue scraper jobs, watch live logs, view history.
// Supports:
//   • Multi-select niches (chips)
//   • Multi-select cities (one job queued per city)
//   • Parser picker popup (Playwright vs XHR) on Generate click
//   • Parallel jobs with animated per-job progress bars
//   • Advanced per-job filter options
//   • date_added shown in job history
// ============================================================

import { useState, useEffect, useCallback, useRef } from 'react'
import { createClient } from '@/lib/supabase/client'
import type { ScraperJob, JobStatus } from '@/lib/types'
import { Combobox, type ComboOption } from '@/components/Combobox'
import { NA_REGIONS, COUNTRY_ORDER, COUNTRY_LABELS, resolveRegion } from '@/lib/north-america'
import { NICHE_COMBO_OPTIONS } from '@/lib/niches'
import { CITY_OPTIONS, CITY_STATE_MAP } from '@/lib/cities'

// ── Types ──────────────────────────────────────────────────────────────────

interface LogEntry {
  id:      number
  ts:      string
  level:   string
  message: string
}

type ParserChoice = 'playwright' | 'xhr'

// ── Constants ──────────────────────────────────────────────────────────────

const STATUS_STYLES: Record<JobStatus, string> = {
  pending:   'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  running:   'bg-blue-500/20   text-blue-400   border-blue-500/30',
  done:      'bg-green-500/20  text-green-400  border-green-500/30',
  failed:    'bg-red-500/20    text-red-400    border-red-500/30',
  cancelled: 'bg-slate-700/40  text-slate-400  border-slate-600',
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

const NICHE_OPTIONS: ComboOption[] = NICHE_COMBO_OPTIONS

// ── Multi-chip select ──────────────────────────────────────────────────────
// Renders selected items as dismissible chips above a Combobox.

function MultiChipSelect({
  label,
  values,
  options,
  placeholder,
  allowFreeText,
  onChange,
}: {
  label: string
  values: string[]
  options: ComboOption[]
  placeholder: string
  allowFreeText?: boolean
  onChange: (values: string[]) => void
}) {
  const [pending, setPending] = useState('')

  function addValue(v: string) {
    const trimmed = v.trim()
    if (!trimmed || values.includes(trimmed)) return
    onChange([...values, trimmed])
    setPending('')
  }

  function removeValue(v: string) {
    onChange(values.filter(x => x !== v))
  }

  return (
    <div>
      <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1.5 font-semibold">
        {label}
      </label>

      {/* Selected chips */}
      {values.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {values.map(v => (
            <span
              key={v}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-500/20 text-blue-300 border border-blue-500/30"
            >
              {v}
              <button
                type="button"
                onClick={() => removeValue(v)}
                className="text-blue-400 hover:text-red-400 transition leading-none"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Input */}
      <Combobox
        value={pending}
        onChange={v => {
          // Auto-add when user selects from list
          if (options.some(o => o.value === v || o.label === v)) {
            addValue(v)
          } else {
            setPending(v)
          }
        }}
        options={options.filter(o => !values.includes(o.value) && !values.includes(o.label))}
        placeholder={values.length ? `Add another ${label.toLowerCase()}…` : placeholder}
        allowFreeText={allowFreeText}
      />

      {/* Hint */}
      {allowFreeText && (
        <p className="text-slate-600 text-[10px] mt-1">
          Type and press Enter to add any value, or pick from the list.
        </p>
      )}
    </div>
  )
}

// ── Progress bar ───────────────────────────────────────────────────────────

function JobProgressBar({ status, smoothPct }: { status: JobStatus; smoothPct: number }) {
  const pct = Math.min(100, Math.max(0, smoothPct))

  if (status === 'pending') {
    return (
      <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
        <div className="h-full w-1/3 bg-slate-700 animate-pulse rounded-full" />
      </div>
    )
  }

  if (status === 'done') {
    return (
      <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
        <div className="h-full w-full bg-green-500 rounded-full" />
      </div>
    )
  }

  if (status === 'failed') {
    return (
      <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
        <div
          className="h-full bg-red-500 rounded-full"
          style={{ width: `${Math.max(pct, 15)}%`, transition: 'width 0.4s ease-out' }}
        />
      </div>
    )
  }

  if (pct < 1) {
    return (
      <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden relative">
        <div className="progress-indeterminate bg-gradient-to-r from-transparent via-blue-500 to-transparent rounded-full" />
      </div>
    )
  }

  return (
    <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden relative">
      <div
        className="h-full bg-gradient-to-r from-blue-600 to-violet-500 rounded-full"
        style={{ width: `${pct}%`, transition: 'width 0.25s linear' }}
      />
      <div
        className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent progress-shimmer"
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

// ── Parser picker modal ────────────────────────────────────────────────────

function ParserModal({
  onSelect,
  onClose,
}: {
  onSelect: (parser: ParserChoice) => void
  onClose: () => void
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl p-6 max-w-sm w-full mx-4">
        <h3 className="text-white font-semibold text-base mb-1">Choose Parser Engine</h3>
        <p className="text-slate-400 text-xs mb-5">
          Which scraper should collect leads for this job?
        </p>

        <div className="space-y-3">
          {/* XHR - Default/Recommended */}
          <button
            onClick={() => onSelect('xhr')}
            className="w-full text-left p-4 rounded-xl border border-violet-500/40 bg-violet-500/10 hover:bg-violet-500/20 transition group"
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-violet-300 font-semibold text-sm">XHR / HTTP</span>
              <span className="text-[10px] text-violet-400 bg-violet-500/20 px-2 py-0.5 rounded-full border border-violet-500/30 font-semibold">
                Recommended
              </span>
            </div>
            <p className="text-slate-400 text-xs leading-relaxed">
              No browser — pure async HTTP requests. Up to 100× faster with 4 concurrent workers.
              Best for large volume runs. Automatically uses direct connection (no proxy delays).
            </p>
          </button>

          {/* Playwright */}
          <button
            onClick={() => onSelect('playwright')}
            className="w-full text-left p-4 rounded-xl border border-blue-500/40 bg-blue-500/10 hover:bg-blue-500/20 transition"
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-blue-300 font-semibold text-sm">Playwright</span>
              <span className="text-[10px] text-blue-400 bg-blue-500/20 px-2 py-0.5 rounded-full border border-blue-500/30 font-semibold">
                Most Accurate
              </span>
            </div>
            <p className="text-slate-400 text-xs leading-relaxed">
              Real browser — 4× parallel workers. Better anti-bot evasion.
              Use if XHR gets blocked or for difficult-to-scrape cities.
            </p>
          </button>
        </div>

        <button
          onClick={onClose}
          className="mt-4 w-full text-center text-xs text-slate-500 hover:text-slate-300 transition py-1"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}

// ── Component ──────────────────────────────────────────────────────────────

export function ScraperPanel() {
  // ── Multi-select: cities and niches ──
  const [cities,  setCities]  = useState<string[]>([])
  const [states,  setStates]  = useState<string[]>([])   // parallel to cities
  const [niches,  setNiches]  = useState<string[]>([])

  // ── Pending single-entry helpers (for the Combobox inputs) ──
  const [cityInput,  setCityInput]  = useState('')
  const [stateInput, setStateInput] = useState('')

  const [limitStr, setLimitStr] = useState('50')

  // ── Advanced filter state ──
  const [showFilters,   setShowFilters]   = useState(false)
  const [minReviews,    setMinReviews]    = useState('')
  const [maxReviews,    setMaxReviews]    = useState('')
  const [minRating,     setMinRating]     = useState('')
  const [maxRating,     setMaxRating]     = useState('')
  const [websiteFilter, setWebsiteFilter] = useState<'any' | 'yes' | 'no'>('any')
  const [minScore,      setMinScore]      = useState('')

  // ── Parser modal ──
  const [showParserModal, setShowParserModal] = useState(false)
  const [parser, setParser] = useState<ParserChoice>('xhr')  // Default to XHR (fastest)

  // ── UI state ──
  const [queuing,      setQueuing]      = useState(false)
  const [result,       setResult]       = useState<string | null>(null)
  const [resultOk,     setResultOk]     = useState(true)
  const [workerOnline, setWorkerOnline] = useState(false)
  const [lastSeen,     setLastSeen]     = useState<Date | null>(null)

  // ── Job & log state ──
  const [jobs,          setJobs]          = useState<ScraperJob[]>([])
  const [selectedJob,   setSelectedJob]   = useState<string | null>(null)
  const [logs,          setLogs]          = useState<LogEntry[]>([])
  const [cancelling,    setCancelling]    = useState<Record<string, boolean>>({})
  const [smoothProgress, setSmoothProgress] = useState<Record<string, number>>({})
  const lastLogIdRef     = useRef(0)
  const logsContainerRef = useRef<HTMLDivElement>(null)

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
      const res  = await fetch(`/api/scrape/logs?job_id=${selectedJob}&after=${lastLogIdRef.current}`)
      const data = await res.json()
      if (Array.isArray(data) && data.length > 0) {
        setLogs(prev => [...prev, ...data])
        lastLogIdRef.current = data[data.length - 1].id
      }
    } catch {
      // ignore transient fetch errors
    }
  }, [selectedJob])

  useEffect(() => {
    const el = logsContainerRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [logs])

  useEffect(() => {
    setLogs([])
    lastLogIdRef.current = 0
  }, [selectedJob])

  useEffect(() => {
    checkWorker()
    fetchJobs()
    const wv = setInterval(checkWorker, 10_000)
    const jv = setInterval(fetchJobs,   5_000)
    return () => { clearInterval(wv); clearInterval(jv) }
  }, [checkWorker, fetchJobs])

  // ── Smooth progress animation ─────────────────────────────────────────
  useEffect(() => {
    const ticker = setInterval(() => {
      setSmoothProgress(prev => {
        const next: Record<string, number> = { ...prev }
        jobs.forEach(job => {
          if (job.status === 'done') {
            next[job.id] = 100
          } else if (job.status !== 'running') {
            next[job.id] = prev[job.id] ?? 0
          } else {
            const actual  = job.progress ?? 0
            const shown   = prev[job.id]  ?? 0
            if (shown < actual) {
              const step = Math.min(0.8, Math.max(0.4, (actual - shown) * 0.1))
              next[job.id] = Math.min(actual, shown + step)
            } else if (actual < 96) {
              next[job.id] = Math.min(actual + 4, shown + 0.06)
            }
          }
        })
        return next
      })
    }, 200)
    return () => clearInterval(ticker)
  }, [jobs])

  const selectedJobObj    = jobs.find(j => j.id === selectedJob)
  const selectedJobStatus = selectedJobObj?.status

  useEffect(() => {
    if (!selectedJob) return
    if (selectedJobStatus && !['running', 'pending'].includes(selectedJobStatus)) return
    fetchLogs()
    const lv = setInterval(fetchLogs, 2_000)
    return () => clearInterval(lv)
  }, [selectedJob, selectedJobStatus, fetchLogs])

  // ── Queue jobs ────────────────────────────────────────────────────────
  // Queues one job per city (each with all selected niches comma-joined).

  async function queueJobs(chosenParser: ParserChoice) {
    setShowParserModal(false)
    setParser(chosenParser)

    const limit = parseInt(limitStr, 10) || 1

    // Build city list — support freetext city input too
    let cityList = [...cities]
    if (cityInput.trim() && !cityList.includes(cityInput.trim())) {
      cityList.push(cityInput.trim())
    }
    if (!cityList.length) {
      setResult('Error: Select at least one city.')
      setResultOk(false)
      return
    }

    const nicheStr = niches.length ? niches.join(',') : 'all'

    setQueuing(true)
    setResult(null)

    let queued = 0
    let lastId: string | null = null

    for (const city of cityList) {
      // Auto-resolve state from city map or use the stateInput
      let resolvedState = CITY_STATE_MAP[city.toLowerCase()] || stateInput.trim()
      const matched = resolveRegion(resolvedState)
      if (matched) resolvedState = matched.name

      try {
        const res = await fetch('/api/scrape', {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            city,
            state:          resolvedState,
            niche:          nicheStr,
            limit,
            min_reviews:    parseInt(minReviews,  10) || 0,
            max_reviews:    parseInt(maxReviews,  10) || 9999,
            min_rating:     parseFloat(minRating) || 0,
            max_rating:     parseFloat(maxRating) || 5,
            website_filter: websiteFilter,
            min_score:      parseInt(minScore, 10) || 0,
            parser:         chosenParser,
          }),
        })
        const data = await res.json()
        if (res.ok) {
          queued++
          lastId = data?.id ?? null
        } else {
          setResult(`Error queuing ${city}: ${data.error ?? 'Unknown error'}`)
          setResultOk(false)
        }
      } catch (err: any) {
        setResult(`Error: ${err?.message ?? 'Network error'}`)
        setResultOk(false)
      }
    }

    if (queued > 0) {
      const cityLabel = cityList.length > 1 ? `${cityList.length} cities` : cityList[0]
      const nicheLabel = niches.length > 1 ? `${niches.length} niches` : (niches[0] || 'all')
      setResult(
        `Queued ${queued} job${queued > 1 ? 's' : ''} — ${cityLabel} × ${nicheLabel} [${chosenParser}]. Engine starting shortly.`
      )
      setResultOk(true)
      setCities([])
      setNiches([])
      setCityInput('')
      setStateInput('')
      await fetchJobs()
      if (lastId) setSelectedJob(lastId)
    }

    setQueuing(false)
  }

  function handleGenerateClick(e: React.FormEvent) {
    e.preventDefault()
    // Show parser selection modal before queuing
    setShowParserModal(true)
  }

  // ── Cancel job ───────────────────────────────────────────────────────

  async function handleCancel(jobId: string) {
    setCancelling(prev => ({ ...prev, [jobId]: true }))
    try {
      await fetch('/api/scrape', {
        method:  'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ id: jobId }),
      })
      setJobs(prev => prev.filter(j => j.id !== jobId))
      setSmoothProgress(prev => { const n = { ...prev }; delete n[jobId]; return n })
      setSelectedJob(prev => {
        if (prev !== jobId) return prev
        const remaining = jobs.filter(j => j.id !== jobId)
        return remaining[0]?.id ?? null
      })
    } finally {
      setCancelling(prev => { const n = { ...prev }; delete n[jobId]; return n })
    }
  }

  // ── Helpers ───────────────────────────────────────────────────────────

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
    const raw     = e.target.value.replace(/[^0-9]/g, '')
    const cleaned = raw.replace(/^0+(\d)/, '$1')
    setLimitStr(cleaned || '0')
  }

  const runningCount = jobs.filter(j => j.status === 'running').length
  const pendingCount = jobs.filter(j => j.status === 'pending').length
  
  // Calculate resource allocation display
  const totalActive = runningCount + pendingCount
  const maxParallel = 4  // Matches MAX_PARALLEL in worker.py
  const maxXhrWorkers = 4  // Matches MAX_XHR_WORKERS in worker.py
  
  // Same logic as worker.py calculate_resource_allocation()
  const xhrPerJob = totalActive > 0 ? Math.max(1, Math.floor(maxXhrWorkers / totalActive)) : maxXhrWorkers
  const actualXhrPerJob = Math.min(xhrPerJob, maxXhrWorkers)

  // ── Render ────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">

      {/* Parser modal */}
      {showParserModal && (
        <ParserModal
          onSelect={queueJobs}
          onClose={() => setShowParserModal(false)}
        />
      )}

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
                ? `worker.py is running — last heartbeat ${lastSeenLabel()}${runningCount > 0 ? ` · ${runningCount} job${runningCount > 1 ? 's' : ''} running${pendingCount > 0 ? ` · ${pendingCount} pending` : ''}` : ''}${totalActive > 0 ? ` · ${actualXhrPerJob} XHR workers per job` : ''}`
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
          Select multiple cities and niches. One job is queued per city.
          The scraper will <strong>keep parsing</strong> until you hit your target — it retries
          automatically with a wider search if filters are strict (e.g. No Website).
        </p>

        <form onSubmit={handleGenerateClick} className="space-y-4">

          {/* ── Row 1: Cities (multi) + State + Niches (multi) + Limit ── */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">

            {/* Cities multi-select */}
            <MultiChipSelect
              label="Cities *"
              values={cities}
              options={CITY_OPTIONS}
              placeholder="Edmonton, Dallas, Calgary…"
              allowFreeText
              onChange={setCities}
            />

            {/* State / Province (used when city not in map) */}
            <div>
              <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1.5 font-semibold">
                State / Province
                <span className="ml-1 text-slate-600 normal-case font-normal">(auto-filled for known cities)</span>
              </label>
              <Combobox
                value={stateInput}
                onChange={setStateInput}
                options={REGION_OPTIONS}
                placeholder="AB, Alberta, Texas…"
                allowFreeText
              />
            </div>

            {/* Niches multi-select */}
            <MultiChipSelect
              label="Niches"
              values={niches}
              options={NICHE_OPTIONS}
              placeholder="Plumbers, Restaurants, Barbershops…"
              allowFreeText
              onChange={setNiches}
            />

            {/* Target leads */}
            <div>
              <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1.5 font-semibold">
                Target Leads <span className="text-slate-600 normal-case font-normal">(per city)</span>
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
          </div>

          {/* ── Advanced Filters toggle ── */}
          <div>
            <button
              type="button"
              onClick={() => setShowFilters(v => !v)}
              className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition select-none"
            >
              <svg
                className={`w-3.5 h-3.5 transition-transform ${showFilters ? 'rotate-90' : ''}`}
                fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
              Advanced Filters
              {(minReviews || maxReviews || minRating || maxRating || websiteFilter !== 'any' || minScore) && (
                <span className="ml-1 px-1.5 py-0.5 rounded-full bg-blue-500/20 text-blue-400 border border-blue-500/30 text-[10px] font-semibold">
                  active
                </span>
              )}
            </button>

            {showFilters && (
              <div className="mt-3 p-4 bg-slate-800/60 border border-slate-700 rounded-xl space-y-4">

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div>
                    <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1.5 font-semibold">Min Reviews</label>
                    <input type="text" inputMode="numeric" value={minReviews}
                      onChange={e => setMinReviews(e.target.value.replace(/\D/g, ''))} placeholder="0"
                      className="w-full bg-slate-900 border border-slate-600 rounded-xl px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500" />
                  </div>
                  <div>
                    <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1.5 font-semibold">Max Reviews</label>
                    <input type="text" inputMode="numeric" value={maxReviews}
                      onChange={e => setMaxReviews(e.target.value.replace(/\D/g, ''))} placeholder="9999"
                      className="w-full bg-slate-900 border border-slate-600 rounded-xl px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500" />
                  </div>
                  <div>
                    <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1.5 font-semibold">Min Rating</label>
                    <input type="text" inputMode="decimal" value={minRating}
                      onChange={e => setMinRating(e.target.value.replace(/[^0-9.]/g, ''))} placeholder="0.0"
                      className="w-full bg-slate-900 border border-slate-600 rounded-xl px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500" />
                  </div>
                  <div>
                    <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1.5 font-semibold">Max Rating</label>
                    <input type="text" inputMode="decimal" value={maxRating}
                      onChange={e => setMaxRating(e.target.value.replace(/[^0-9.]/g, ''))} placeholder="5.0"
                      className="w-full bg-slate-900 border border-slate-600 rounded-xl px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500" />
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 items-end">
                  <div>
                    <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1.5 font-semibold">Min Lead Score</label>
                    <input type="text" inputMode="numeric" value={minScore}
                      onChange={e => setMinScore(e.target.value.replace(/\D/g, ''))} placeholder="0"
                      className="w-full bg-slate-900 border border-slate-600 rounded-xl px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500" />
                  </div>

                  <div className="col-span-2">
                    <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1.5 font-semibold">Website</label>
                    <div className="flex rounded-xl overflow-hidden border border-slate-600 text-xs font-semibold">
                      {(['any', 'no', 'yes'] as const).map(opt => (
                        <button key={opt} type="button" onClick={() => setWebsiteFilter(opt)}
                          className={`flex-1 py-2 transition ${
                            websiteFilter === opt
                              ? opt === 'no' ? 'bg-violet-500 text-white'
                                : opt === 'yes' ? 'bg-green-600 text-white'
                                : 'bg-blue-500 text-white'
                              : 'bg-slate-900 text-slate-400 hover:text-white'
                          }`}>
                          {opt === 'any' ? 'Any' : opt === 'no' ? 'No Website' : 'Has Website'}
                        </button>
                      ))}
                    </div>
                  </div>

                  <button type="button"
                    onClick={() => { setMinReviews(''); setMaxReviews(''); setMinRating(''); setMaxRating(''); setWebsiteFilter('any'); setMinScore('') }}
                    className="text-xs text-slate-500 hover:text-red-400 transition pt-5 text-left">
                    Clear filters
                  </button>
                </div>

                <p className="text-slate-500 text-xs">
                  Tip: <strong className="text-slate-400">No Website</strong> targets businesses
                  that need digital services most. The engine retries with a wider search if
                  fewer results pass your filters than your target count.
                </p>
              </div>
            )}
          </div>

          {/* ── Submit ── */}
          <div className="flex items-center gap-4">
            <button
              type="submit"
              disabled={queuing || !workerOnline}
              title={!workerOnline ? 'Start worker.py on your machine first' : ''}
              className="px-6 py-2.5 rounded-xl font-semibold text-sm bg-gradient-to-r from-violet-500 to-blue-500 hover:from-violet-600 hover:to-blue-600 disabled:opacity-40 disabled:cursor-not-allowed transition"
            >
              {queuing
                ? 'Queuing…'
                : `Generate ${limitStr || '?'} Leads${cities.length > 1 ? ` × ${cities.length} cities` : ''}`}
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

        {/* Job history table with progress bars */}
        <div className="bg-slate-900 rounded-2xl border border-slate-700 overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-700 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h2 className="text-blue-400 font-semibold">Run History</h2>
              {runningCount > 0 && (
                <span className="flex items-center gap-1.5 text-xs text-blue-400 bg-blue-500/10 border border-blue-500/30 px-2 py-0.5 rounded-full">
                  <span className="relative flex h-1.5 w-1.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-blue-400" />
                  </span>
                  {runningCount} running
                </span>
              )}
            </div>
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
                  <th className="px-4 py-3 text-left">Parser</th>
                  <th className="px-4 py-3 text-left">Time</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {jobs.map(job => {
                  const sp = smoothProgress[job.id] ?? 0
                  const canCancel = job.status === 'pending' || job.status === 'running'
                  return (
                    <>
                      <tr
                        key={job.id}
                        onClick={() => setSelectedJob(job.id)}
                        className={`border-t border-slate-800 cursor-pointer transition ${
                          selectedJob === job.id
                            ? 'bg-blue-500/10 border-l-2 border-l-blue-500'
                            : 'hover:bg-slate-800/40'
                        }`}
                      >
                        <td className="px-4 pt-3 pb-1 font-medium">
                          <span className="block">{job.city}{job.state ? `, ${job.state}` : ''}</span>
                          <span className="text-slate-400 text-xs font-normal">
                            {job.niche === 'all' ? 'All niches' : job.niche}
                          </span>
                        </td>
                        <td className="px-4 pt-3 pb-1">
                          <span className={`px-2 py-0.5 rounded-full text-xs font-semibold border ${STATUS_STYLES[job.status]}`}>
                            {job.status}
                          </span>
                          {job.status === 'running' && sp > 1 && (
                            <span className="ml-2 text-xs text-blue-400">{Math.round(sp)}%</span>
                          )}
                          {job.error_msg && (
                            <p className="text-red-400 text-xs mt-1 max-w-[180px] truncate" title={job.error_msg}>
                              {job.error_msg}
                            </p>
                          )}
                        </td>
                        <td className="px-4 pt-3 pb-1 text-slate-300">{job.result_count || '—'}</td>
                        <td className="px-4 pt-3 pb-1">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${
                            job.parser === 'xhr'
                              ? 'bg-violet-500/20 text-violet-400'
                              : 'bg-blue-500/20 text-blue-400'
                          }`}>
                            {job.parser ?? 'playwright'}
                          </span>
                        </td>
                        <td className="px-4 pt-3 pb-1 text-slate-400 text-xs">{duration(job)}</td>
                        <td className="px-4 pt-3 pb-1 text-right">
                          {canCancel && (
                            <button
                              onClick={e => { e.stopPropagation(); handleCancel(job.id) }}
                              disabled={cancelling[job.id]}
                              title="Cancel and remove this job"
                              className="inline-flex items-center justify-center w-6 h-6 rounded-md text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition disabled:opacity-40"
                            >
                              {cancelling[job.id] ? (
                                <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                                </svg>
                              ) : (
                                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                                </svg>
                              )}
                            </button>
                          )}
                        </td>
                      </tr>
                      {/* Progress bar sub-row */}
                      <tr
                        key={`${job.id}-bar`}
                        className={`border-0 ${selectedJob === job.id ? 'bg-blue-500/5' : ''}`}
                      >
                        <td colSpan={6} className="px-4 pb-2.5 pt-0">
                          <JobProgressBar status={job.status} smoothPct={sp} />
                        </td>
                      </tr>
                    </>
                  )
                })}
                {!jobs.length && (
                  <tr>
                    <td colSpan={6} className="px-4 py-10 text-center text-slate-500">
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
                <button onClick={() => setLogs([])} className="text-slate-500 hover:text-red-400 text-xs transition">
                  Clear
                </button>
              )}
            </div>
          </div>

          <div ref={logsContainerRef} className="flex-1 overflow-y-auto min-h-[280px] max-h-[420px] p-3 font-mono text-xs space-y-0.5 bg-slate-950/40">
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
          </div>
        </div>

      </div>
    </div>
  )
}
