'use client'

// ============================================================
// AssignPanel — assign unassigned leads to a caller with rich
// filters: niche combobox, city dropdown, min score/rating/
// review count, has-website, has-phone toggles.
// ============================================================

import { useState, useMemo } from 'react'
import type { Caller } from '@/lib/types'
import { Combobox, type ComboOption } from '@/components/Combobox'
import { PRESET_NICHES } from '@/lib/niches'

export interface AssignFilters {
  niche:      string   // 'any' or specific niche
  city:       string   // 'any' or specific city
  minScore:   number   // 0–100
  minRating:  number   // 0.0–5.0
  minReviews: number   // 0–∞
  maxReviews: number   // 0 = no limit
  hasWebsite: string   // 'any' | 'yes' | 'no'
  hasPhone:   string   // 'any' | 'yes' | 'no'
}

interface Props {
  callers: Caller[]
  niches:  string[]   // unique niches already in DB
  cities:  string[]   // unique cities already in DB
  onAssign: (callerId: string, count: number, filters: AssignFilters) => Promise<{ assigned: number }>
}

const DEFAULT_FILTERS: AssignFilters = {
  niche:      'any',
  city:       'any',
  minScore:   0,
  minRating:  0,
  minReviews: 0,
  maxReviews: 0,
  hasWebsite: 'any',
  hasPhone:   'any',
}

// Merge preset niches with any custom niches pulled from the DB
function buildNicheOptions(dbNiches: string[]): ComboOption[] {
  const all = [...PRESET_NICHES]
  for (const n of dbNiches) {
    if (!all.some(p => p.toLowerCase() === n.toLowerCase())) all.push(n)
  }
  return [
    { value: 'any', label: 'Any niche' },
    ...all.sort().map(n => ({ value: n, label: n })),
  ]
}

// Small helper for filter label pill
function FilterPill({ label, active, children }: { label: string; active?: boolean; children?: React.ReactNode }) {
  return (
    <div className={`rounded-xl border p-3 ${active ? 'border-blue-500/40 bg-blue-500/5' : 'border-slate-700 bg-slate-800/50'}`}>
      <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1.5 font-semibold">{label}</label>
      {children}
    </div>
  )
}

export function AssignPanel({ callers, niches, cities, onAssign }: Props) {
  const [callerId, setCallerId] = useState('')
  const [count,    setCount]    = useState(50)
  const [filters,  setFilters]  = useState<AssignFilters>(DEFAULT_FILTERS)
  const [result,   setResult]   = useState<string | null>(null)
  const [loading,  setLoading]  = useState(false)
  const [expanded, setExpanded] = useState(false)

  const nicheOptions = useMemo(() => buildNicheOptions(niches), [niches])
  const cityOptions  = useMemo<ComboOption[]>(() => [
    { value: 'any', label: 'Any city' },
    ...cities.map(c => ({ value: c, label: c })),
  ], [cities])

  function setFilter<K extends keyof AssignFilters>(key: K, val: AssignFilters[K]) {
    setFilters(f => ({ ...f, [key]: val }))
  }

  // Count how many non-default filters are active (for the badge)
  const activeFilterCount = [
    filters.niche      !== 'any',
    filters.city       !== 'any',
    filters.minScore   > 0,
    filters.minRating  > 0,
    filters.minReviews > 0,
    filters.maxReviews > 0,
    filters.hasWebsite !== 'any',
    filters.hasPhone   !== 'any',
  ].filter(Boolean).length

  async function handleAssign() {
    if (!callerId) { setResult('Select a caller first.'); return }
    setLoading(true)
    setResult(null)
    try {
      const data = await onAssign(callerId, count, filters)
      setResult(`Assigned ${data.assigned} lead${data.assigned !== 1 ? 's' : ''} successfully.`)
    } catch (err: any) {
      setResult(err?.message || 'Assignment failed.')
    } finally {
      setLoading(false)
    }
  }

  function resetFilters() {
    setFilters(DEFAULT_FILTERS)
  }

  const inputCls = 'w-full bg-slate-800 border border-slate-600 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500'
  const selectCls = inputCls

  return (
    <div className="bg-slate-900 rounded-2xl border border-slate-700 p-6 mb-8">
      <h2 className="text-blue-400 font-semibold mb-5">Assign Leads</h2>

      {/* ── Row 1: Caller + Count ───────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
        <div>
          <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1.5 font-semibold">
            Caller
          </label>
          <select
            value={callerId}
            onChange={e => setCallerId(e.target.value)}
            className={selectCls}
          >
            <option value="">— Select caller —</option>
            {callers.map(c => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1.5 font-semibold">
            Number of leads
          </label>
          <input
            type="number"
            min={1}
            max={500}
            value={count}
            onChange={e => setCount(Number(e.target.value))}
            className={inputCls}
          />
        </div>
      </div>

      {/* ── Filters toggle ──────────────────────────────────── */}
      <div className="flex items-center gap-3 mb-4">
        <button
          type="button"
          onClick={() => setExpanded(x => !x)}
          className="flex items-center gap-2 text-sm text-slate-300 hover:text-white transition"
        >
          <span className={`transition-transform ${expanded ? 'rotate-90' : ''}`}>▶</span>
          Lead Filters
          {activeFilterCount > 0 && (
            <span className="bg-blue-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
              {activeFilterCount}
            </span>
          )}
        </button>
        {activeFilterCount > 0 && (
          <button
            type="button"
            onClick={resetFilters}
            className="text-xs text-slate-500 hover:text-red-400 transition"
          >
            Reset filters
          </button>
        )}
      </div>

      {expanded && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-5 p-4 bg-slate-950/50 rounded-xl border border-slate-800">

          {/* Niche */}
          <FilterPill label="Niche" active={filters.niche !== 'any'}>
            <Combobox
              value={filters.niche === 'any' ? '' : filters.niche}
              onChange={v => setFilter('niche', v || 'any')}
              options={nicheOptions}
              placeholder="Any niche"
              allowFreeText
            />
          </FilterPill>

          {/* City */}
          <FilterPill label="City" active={filters.city !== 'any'}>
            <Combobox
              value={filters.city === 'any' ? '' : filters.city}
              onChange={v => setFilter('city', v || 'any')}
              options={cityOptions}
              placeholder="Any city"
              allowFreeText
            />
          </FilterPill>

          {/* Min lead score */}
          <FilterPill label="Min Lead Score" active={filters.minScore > 0}>
            <div className="flex items-center gap-2">
              <input
                type="range"
                min={0}
                max={50}
                step={1}
                value={filters.minScore}
                onChange={e => setFilter('minScore', Number(e.target.value))}
                className="flex-1 accent-blue-500"
              />
              <span className="text-sm text-white font-semibold w-6 text-right">{filters.minScore}</span>
            </div>
          </FilterPill>

          {/* Min rating */}
          <FilterPill label="Min Rating ★" active={filters.minRating > 0}>
            <div className="flex items-center gap-2">
              <input
                type="range"
                min={0}
                max={5}
                step={0.5}
                value={filters.minRating}
                onChange={e => setFilter('minRating', Number(e.target.value))}
                className="flex-1 accent-blue-500"
              />
              <span className="text-sm text-white font-semibold w-8 text-right">{filters.minRating === 0 ? 'Any' : `${filters.minRating}★`}</span>
            </div>
          </FilterPill>

          {/* Min reviews */}
          <FilterPill label="Min Review Count" active={filters.minReviews > 0}>
            <input
              type="number"
              min={0}
              value={filters.minReviews}
              onChange={e => setFilter('minReviews', Math.max(0, Number(e.target.value)))}
              placeholder="0 (any)"
              className={inputCls}
            />
          </FilterPill>

          {/* Max reviews */}
          <FilterPill label="Max Review Count" active={filters.maxReviews > 0}>
            <input
              type="number"
              min={0}
              value={filters.maxReviews}
              onChange={e => setFilter('maxReviews', Math.max(0, Number(e.target.value)))}
              placeholder="0 (no limit)"
              className={inputCls}
            />
          </FilterPill>

          {/* Has website */}
          <FilterPill label="Has Website" active={filters.hasWebsite !== 'any'}>
            <select
              value={filters.hasWebsite}
              onChange={e => setFilter('hasWebsite', e.target.value)}
              className={selectCls}
            >
              <option value="any">Any</option>
              <option value="no">No website (better prospects)</option>
              <option value="yes">Has website</option>
            </select>
          </FilterPill>

          {/* Has phone */}
          <FilterPill label="Has Phone" active={filters.hasPhone !== 'any'}>
            <select
              value={filters.hasPhone}
              onChange={e => setFilter('hasPhone', e.target.value)}
              className={selectCls}
            >
              <option value="any">Any</option>
              <option value="yes">Has phone number</option>
              <option value="no">No phone (skip)</option>
            </select>
          </FilterPill>
        </div>
      )}

      {/* ── Action row ──────────────────────────────────────── */}
      <div className="flex items-center gap-4">
        <button
          onClick={handleAssign}
          disabled={loading || !callerId}
          className="px-6 py-2.5 rounded-xl font-semibold text-sm bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
        >
          {loading ? 'Assigning...' : `Assign ${count} Leads`}
        </button>

        {result && (
          <span className={`text-sm ${result.includes('success') ? 'text-green-400' : 'text-red-400'}`}>
            {result}
          </span>
        )}
      </div>

      <p className="text-xs text-slate-500 mt-3">
        Only unassigned leads matching all filters will be selected. Leads are locked once assigned — no two callers will ever work the same prospect.
      </p>
    </div>
  )
}
