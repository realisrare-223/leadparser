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

// ── Website badge ──────────────────────────────────────────────────────────

function WebsiteBadge({ url }: { url: string }) {
  return url ? (
    <a
      href={url} target="_blank" rel="noreferrer"
      onClick={e => e.stopPropagation()}
      className="px-2 py-0.5 rounded-full text-xs font-semibold border bg-green-500/15 text-green-400 border-green-500/30 hover:bg-green-500/25 transition"
    >
      YES
    </a>
  ) : (
    <span className="px-2 py-0.5 rounded-full text-xs font-semibold border bg-slate-700/50 text-slate-400 border-slate-600">
      NO
    </span>
  )
}

// ── Section divider ────────────────────────────────────────────────────────

function SectionDivider({ label, count }: { label: string; count: number }) {
  return (
    <tr className="bg-slate-950/80">
      <td colSpan={9} className="px-4 py-2 text-xs font-semibold uppercase tracking-widest text-slate-500 border-t border-slate-800">
        {label} <span className="text-slate-600 font-normal">({count})</span>
      </td>
    </tr>
  )
}

// ── Main component ─────────────────────────────────────────────────────────

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
    startTransition(() => { onStatusChange(id, status) })
  }

  function handleNotesBlur(id: string, notes: string) {
    if (!onNotesChange) return
    startTransition(() => { onNotesChange(id, notes) })
  }

  // Sort newest first (created_at → date_added fallback)
  const sorted = [...leads].sort((a, b) => {
    const ta = a.created_at || a.date_added || ''
    const tb = b.created_at || b.date_added || ''
    return tb.localeCompare(ta)
  })

  // "No Website" group first (higher priority cold-call leads), then "Has Website"
  const noWebsite  = sorted.filter(l => !l.website?.trim())
  const hasWebsite = sorted.filter(l =>  l.website?.trim())
  const showGroups = noWebsite.length > 0 && hasWebsite.length > 0

  function renderRows(group: Lead[]) {
    return group.map(lead => (
      <>
        <tr
          key={lead.id}
          className="border-t border-slate-800 hover:bg-slate-800/40 transition"
        >
          <td className="px-4 py-3 font-medium max-w-[180px] truncate">{lead.name}</td>
          <td className="px-4 py-3 font-mono text-green-400 text-xs">{lead.phone}</td>
          <td className="px-4 py-3 text-slate-300 capitalize">{lead.niche}</td>
          <td className="px-4 py-3 text-slate-300">{lead.city}{lead.state ? `, ${lead.state}` : ''}</td>
          <td className="px-4 py-3">
            <WebsiteBadge url={lead.website} />
          </td>
          <td className="px-4 py-3">
            <ScoreBadge score={lead.lead_score} />
          </td>
          {/* Date added — newest leads at top */}
          <td className="px-4 py-3 text-slate-500 text-xs whitespace-nowrap">
            {lead.date_added || (lead.created_at ? lead.created_at.slice(0, 10) : '—')}
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
            <td colSpan={9} className="px-4 py-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 text-xs">
                <Detail label="Address"     value={`${lead.address}, ${lead.city}, ${lead.state} ${lead.zip_code}`} />
                <Detail label="Rating"      value={lead.rating ? `${lead.rating} ★  (${lead.review_count} review${lead.review_count === 1 ? '' : 's'})` : '—'} />
                <Detail label="Hours"       value={lead.hours || '—'} />
                <Detail label="Date Added"  value={lead.date_added || lead.created_at?.slice(0, 10) || '—'} />
                <Detail label="Website"     value={lead.website || 'None'} link={lead.website} />
                <Detail label="Facebook"    value={lead.facebook || '—'} link={lead.facebook} />
                <Detail label="GMB"         value={lead.gmb_link ? 'View' : '—'} link={lead.gmb_link} />
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
    ))
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
              <th className="px-4 py-3 text-left">Website</th>
              <th className="px-4 py-3 text-left">Score</th>
              <th className="px-4 py-3 text-left">Added</th>
              <th className="px-4 py-3 text-left">Status</th>
              <th className="px-4 py-3 text-left">Details</th>
            </tr>
          </thead>
          <tbody>
            {showGroups ? (
              <>
                <SectionDivider label="No Website" count={noWebsite.length} />
                {renderRows(noWebsite)}
                <SectionDivider label="Has Website" count={hasWebsite.length} />
                {renderRows(hasWebsite)}
              </>
            ) : (
              renderRows(sorted)
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Detail({
  label, value, link, block,
}: {
  label: string; value: string; link?: string; block?: boolean
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
