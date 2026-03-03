import type { LeadStatus } from '@/lib/types'

const STATUS_CONFIG: Record<LeadStatus, { label: string; classes: string }> = {
  new:      { label: 'New',       classes: 'bg-blue-500/20 text-blue-400 border-blue-500/30' },
  called:   { label: 'Called',    classes: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30' },
  sold:     { label: 'Sold',      classes: 'bg-green-500/20 text-green-400 border-green-500/30' },
  followup: { label: 'Follow Up', classes: 'bg-violet-500/20 text-violet-400 border-violet-500/30' },
  dead:     { label: 'Dead',      classes: 'bg-slate-500/20 text-slate-400 border-slate-500/30' },
}

export function StatusBadge({ status }: { status: LeadStatus }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.new
  return (
    <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold border ${cfg.classes}`}>
      {cfg.label}
    </span>
  )
}

export function ScoreBadge({ score }: { score: number }) {
  const isHot  = score >= 18
  const isWarm = score >= 12

  const classes = isHot
    ? 'bg-red-500/20 text-red-400 border-red-500/30'
    : isWarm
    ? 'bg-amber-500/20 text-amber-400 border-amber-500/30'
    : 'bg-slate-500/20 text-slate-400 border-slate-500/30'

  const label = isHot ? 'HOT' : isWarm ? 'WARM' : 'MED'

  return (
    <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold border ${classes}`}>
      {score} {label}
    </span>
  )
}
