'use client'

import { useState, useTransition } from 'react'
import type { Lead, LeadStatus } from '@/lib/types'
import { StatusBadge, ScoreBadge } from './StatusBadge'

const STATUS_OPTIONS: LeadStatus[] = ['new', 'called', 'sold', 'followup', 'dead']

interface Props {
  leads: Lead[]
  showCaller?: boolean  // admin view shows assigned_to name
  onStatusChange?: (id: string, status: LeadStatus) => Promise<void>
  onNotesChange?: (id: string, notes: string) => Promise<void>
}

export function LeadTable({ leads, showCaller, onStatusChange, onNotesChange }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null)
  const [pending, startTransition] = useTransition()

  if (!leads.length) {
    return (
      <div className="text-center py-16 text-slate-500">
        No leads to display.
      </div>
    )
  }

  function handleStatusChange(id: string, status: LeadStatus) {
    if (!onStatusChange) return
    startTransition(() => {
      onStatusChange(id, status)
    })
  }

  function handleNotesBlur(id: string, notes: string) {
    if (!onNotesChange) return
    startTransition(() => {
      onNotesChange(id, notes)
    })
  }

  return (
    <div className="bg-slate-900 rounded-2xl border border-slate-700 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-950 text-slate-400 text-xs uppercase tracking-wide">
              <th className="px-4 py-3 text-left">Business</th>
              <th className="px-4 py-3 text-left">Phone</th>
              <th className="px-4 py-3 text-left">Niche</th>
              <th className="px-4 py-3 text-left">City</th>
              <th className="px-4 py-3 text-left">Score</th>
              <th className="px-4 py-3 text-left">Status</th>
              <th className="px-4 py-3 text-left">Details</th>
            </tr>
          </thead>
          <tbody>
            {leads.map(lead => (
              <>
                <tr
                  key={lead.id}
                  className="border-t border-slate-800 hover:bg-slate-800/40 transition"
                >
                  <td className="px-4 py-3 font-medium max-w-[200px] truncate">{lead.name}</td>
                  <td className="px-4 py-3 font-mono text-green-400 text-xs">{lead.phone}</td>
                  <td className="px-4 py-3 text-slate-300 capitalize">{lead.niche}</td>
                  <td className="px-4 py-3 text-slate-300">{lead.city}, {lead.state}</td>
                  <td className="px-4 py-3">
                    <ScoreBadge score={lead.lead_score} />
                  </td>
                  <td className="px-4 py-3">
                    {onStatusChange ? (
                      <select
                        value={lead.status}
                        onChange={e => handleStatusChange(lead.id, e.target.value as LeadStatus)}
                        disabled={pending}
                        className="bg-slate-800 border border-slate-600 rounded-lg px-2 py-1 text-xs text-white focus:outline-none focus:border-blue-500 disabled:opacity-50"
                      >
                        {STATUS_OPTIONS.map(s => (
                          <option key={s} value={s}>{s}</option>
                        ))}
                      </select>
                    ) : (
                      <StatusBadge status={lead.status} />
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => setExpanded(expanded === lead.id ? null : lead.id)}
                      className="text-blue-400 hover:text-blue-300 text-xs underline"
                    >
                      {expanded === lead.id ? 'Hide' : 'Expand'}
                    </button>
                  </td>
                </tr>

                {/* Expanded row */}
                {expanded === lead.id && (
                  <tr key={`${lead.id}-exp`} className="border-t border-slate-700 bg-slate-800/40">
                    <td colSpan={7} className="px-4 py-4">
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 text-xs">
                        <Detail label="Address"      value={`${lead.address}, ${lead.city}, ${lead.state} ${lead.zip_code}`} />
                        <Detail label="Rating"       value={lead.rating ? `${lead.rating} ★  (${lead.review_count} reviews)` : '—'} />
                        <Detail label="Hours"        value={lead.hours || '—'} />
                        <Detail label="Website"      value={lead.website || 'None'} link={lead.website} />
                        <Detail label="Facebook"     value={lead.facebook || '—'} link={lead.facebook} />
                        <Detail label="GMB"          value={lead.gmb_link ? 'View' : '—'} link={lead.gmb_link} />
                        <div className="sm:col-span-2 lg:col-span-3">
                          <Detail label="Pitch Notes" value={lead.pitch_notes || '—'} block />
                        </div>
                        {onNotesChange && (
                          <div className="sm:col-span-2 lg:col-span-3">
                            <label className="block text-slate-400 mb-1 font-semibold uppercase">Your Notes</label>
                            <textarea
                              defaultValue={lead.caller_notes || ''}
                              onBlur={e => handleNotesBlur(lead.id, e.target.value)}
                              rows={2}
                              placeholder="Add call notes..."
                              className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white text-xs resize-none focus:outline-none focus:border-blue-500"
                            />
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Detail({
  label,
  value,
  link,
  block,
}: {
  label: string
  value: string
  link?: string
  block?: boolean
}) {
  return (
    <div className={block ? 'col-span-full' : ''}>
      <span className="text-slate-500 uppercase tracking-wide font-semibold">{label}: </span>
      {link ? (
        <a href={link} target="_blank" rel="noreferrer" className="text-blue-400 hover:underline">
          {value}
        </a>
      ) : (
        <span className="text-slate-300">{value}</span>
      )}
    </div>
  )
}
