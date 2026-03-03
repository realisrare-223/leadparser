'use client'

import { useState } from 'react'
import type { Caller } from '@/lib/types'

interface Props {
  callers: Caller[]
  niches: string[]
  cities: string[]
  onAssign: (callerId: string, count: number, niche: string, city: string) => Promise<{ assigned: number }>
}

export function AssignPanel({ callers, niches, cities, onAssign }: Props) {
  const [callerId, setCallerId] = useState('')
  const [niche,    setNiche]    = useState('any')
  const [city,     setCity]     = useState('any')
  const [count,    setCount]    = useState(50)
  const [result,   setResult]   = useState<string | null>(null)
  const [loading,  setLoading]  = useState(false)

  async function handleAssign() {
    if (!callerId) { setResult('Select a caller first.'); return }
    setLoading(true)
    setResult(null)
    try {
      const data = await onAssign(callerId, count, niche, city)
      setResult(`Assigned ${data.assigned} lead${data.assigned !== 1 ? 's' : ''} successfully.`)
    } catch (err: any) {
      setResult(err?.message || 'Assignment failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-slate-900 rounded-2xl border border-slate-700 p-6 mb-8">
      <h2 className="text-blue-400 font-semibold mb-5">Assign Leads</h2>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
        {/* Caller picker */}
        <div>
          <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1.5 font-semibold">
            Caller
          </label>
          <select
            value={callerId}
            onChange={e => setCallerId(e.target.value)}
            className="w-full bg-slate-800 border border-slate-600 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500"
          >
            <option value="">— Select caller —</option>
            {callers.map(c => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>

        {/* Niche filter */}
        <div>
          <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1.5 font-semibold">
            Niche
          </label>
          <select
            value={niche}
            onChange={e => setNiche(e.target.value)}
            className="w-full bg-slate-800 border border-slate-600 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500"
          >
            <option value="any">Any niche</option>
            {niches.map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>

        {/* City filter */}
        <div>
          <label className="block text-xs uppercase tracking-wide text-slate-400 mb-1.5 font-semibold">
            City
          </label>
          <select
            value={city}
            onChange={e => setCity(e.target.value)}
            className="w-full bg-slate-800 border border-slate-600 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500"
          >
            <option value="any">Any city</option>
            {cities.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>

        {/* Count */}
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
            className="w-full bg-slate-800 border border-slate-600 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500"
          />
        </div>
      </div>

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
        Only unassigned leads matching the filters will be selected. Leads are locked once assigned — no two callers will ever work the same prospect.
      </p>
    </div>
  )
}
