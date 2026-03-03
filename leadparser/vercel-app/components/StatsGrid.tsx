import type { LeadStats, CallerStats } from '@/lib/types'

function StatCard({
  value,
  label,
  accent,
}: {
  value: string | number
  label: string
  accent: string
}) {
  return (
    <div className={`bg-slate-900 rounded-2xl p-6 border border-slate-700 border-l-4 ${accent}`}>
      <div className="text-4xl font-bold text-white">{value}</div>
      <div className="text-xs uppercase tracking-widest text-slate-400 mt-1">{label}</div>
    </div>
  )
}

export function LeadStatsGrid({ stats }: { stats: LeadStats }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
      <StatCard value={stats.total}       label="Total Leads"  accent="border-l-slate-500" />
      <StatCard value={stats.hot}         label="Hot (18+)"    accent="border-l-red-500" />
      <StatCard value={stats.assigned}    label="Assigned"     accent="border-l-blue-500" />
      <StatCard value={stats.called}      label="Called"       accent="border-l-yellow-500" />
      <StatCard value={stats.sold}        label="Sold"         accent="border-l-green-500" />
    </div>
  )
}

export function CallerStatsTable({ callers }: { callers: CallerStats[] }) {
  if (!callers.length) return null

  return (
    <div className="bg-slate-900 rounded-2xl border border-slate-700 overflow-hidden mb-8">
      <div className="px-6 py-4 border-b border-slate-700">
        <h2 className="text-blue-400 font-semibold">Caller Performance</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-950 text-slate-400 text-xs uppercase tracking-wide">
              <th className="px-6 py-3 text-left">Caller</th>
              <th className="px-6 py-3 text-right">Assigned</th>
              <th className="px-6 py-3 text-right">Called</th>
              <th className="px-6 py-3 text-right">Sold</th>
              <th className="px-6 py-3 text-right">Follow Up</th>
              <th className="px-6 py-3 text-right">Untouched</th>
              <th className="px-6 py-3 text-right">Conv %</th>
            </tr>
          </thead>
          <tbody>
            {callers.map(c => (
              <tr key={c.id} className="border-t border-slate-800 hover:bg-slate-800/40 transition">
                <td className="px-6 py-3 font-medium">{c.name}</td>
                <td className="px-6 py-3 text-right text-slate-300">{c.total_assigned}</td>
                <td className="px-6 py-3 text-right text-yellow-400">{c.called}</td>
                <td className="px-6 py-3 text-right text-green-400 font-semibold">{c.sold}</td>
                <td className="px-6 py-3 text-right text-violet-400">{c.followup}</td>
                <td className="px-6 py-3 text-right text-slate-400">{c.untouched}</td>
                <td className="px-6 py-3 text-right font-semibold">
                  {c.conversion_pct != null ? `${c.conversion_pct}%` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
