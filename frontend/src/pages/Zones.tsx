import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { PageHeader, Panel } from '../components/ui'
import { bandBadge } from '../lib/risk'
import { usePlant } from '../state/PlantContext'
import type { RiskBand } from '../types'

type Filter = 'ALL' | RiskBand | 'HAZARD'

const FILTERS: { key: Filter; label: string }[] = [
  { key: 'ALL', label: 'All zones' },
  { key: 'CRITICAL', label: 'Critical' },
  { key: 'HIGH', label: 'High' },
  { key: 'MEDIUM', label: 'Medium' },
  { key: 'LOW', label: 'Low' },
  { key: 'HAZARD', label: 'Active hazard work' },
]

export function Zones() {
  const { zones } = usePlant()
  // Filter state lives in the URL so views are shareable and deep-linkable.
  const [params, setParams] = useSearchParams()
  const filter = (params.get('band') as Filter) ?? 'ALL'
  const query = params.get('q') ?? ''

  const update = (next: Partial<{ band: Filter; q: string }>) => {
    const p = new URLSearchParams(params)
    Object.entries(next).forEach(([k, v]) => {
      if (!v || v === 'ALL' || v === '') p.delete(k)
      else p.set(k, String(v))
    })
    setParams(p, { replace: true })
  }
  const setFilter = (f: Filter) => update({ band: f })
  const setQuery = (q: string) => update({ q })

  const rows = useMemo(() => {
    let r = zones
    if (filter === 'HAZARD') {
      r = r.filter((z) => z.hot_work_active || z.maintenance_active)
    } else if (filter !== 'ALL') {
      r = r.filter((z) => z.risk_band === filter)
    }
    if (query.trim()) {
      const q = query.toLowerCase()
      r = r.filter(
        (z) => z.name.toLowerCase().includes(q) || z.zone_id.toLowerCase().includes(q),
      )
    }
    return [...r].sort((a, b) => b.risk - a.risk)
  }, [zones, filter, query])

  const counts = useMemo(() => {
    const c: Record<string, number> = { ALL: zones.length, HAZARD: 0 }
    zones.forEach((z) => {
      c[z.risk_band] = (c[z.risk_band] ?? 0) + 1
      if (z.hot_work_active || z.maintenance_active) c.HAZARD += 1
    })
    return c
  }, [zones])

  return (
    <>
      <PageHeader
        title="Zone Register"
        subtitle="Every monitored zone, classified by compound risk and active hazardous work"
        actions={
          <input
            type="search"
            name="zone-filter"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter zones…"
            aria-label="Filter zones by name or identifier"
            autoComplete="off"
            spellCheck={false}
            className="rounded border border-ink-600 bg-ink-900 px-2.5 py-1.5 text-[11px] text-slate-200 placeholder:text-slate-600"
          />
        }
      />

      <div className="mb-3 flex flex-wrap gap-1.5">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`rounded border px-2.5 py-1 text-[11px] transition ${
              filter === f.key
                ? 'border-sky-500/50 bg-sky-500/15 text-sky-200'
                : 'border-ink-600 bg-ink-700/50 text-slate-400 hover:text-slate-200'
            }`}
          >
            {f.label}
            <span className="ml-1.5 text-slate-600">{counts[f.key] ?? 0}</span>
          </button>
        ))}
      </div>

      <Panel>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] text-[11.5px]">
            <thead>
              <tr className="border-b border-ink-600 text-left text-[10px] uppercase tracking-wide text-slate-500">
                <th className="px-4 py-2 font-medium">Zone</th>
                <th className="px-3 py-2 font-medium">Risk</th>
                <th className="px-3 py-2 font-medium">Band</th>
                <th className="px-3 py-2 text-right font-medium">Gas %LEL</th>
                <th className="px-3 py-2 text-right font-medium">Trend</th>
                <th className="px-3 py-2 text-right font-medium">Workers</th>
                <th className="px-3 py-2 font-medium">Active work</th>
                <th className="px-3 py-2 text-right font-medium">Lead</th>
                <th className="px-3 py-2 font-medium">Single sensor</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-700">
              {rows.map((z) => (
                <tr key={z.zone_id} className="transition hover:bg-ink-700/40">
                  <td className="px-4 py-2">
                    <Link
                      to={`/zones/${z.zone_id}`}
                      className="text-slate-200 hover:text-sky-300"
                    >
                      {z.name}
                    </Link>
                    <span className="ml-2 font-mono text-[10px] text-slate-600">
                      {z.zone_id}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <div className="h-1 w-14 rounded bg-ink-600">
                        <div
                          className="h-1 rounded bg-sky-400"
                          style={{ width: `${Math.max(z.risk * 100, 2)}%` }}
                        />
                      </div>
                      <span className="stat text-slate-300">
                        {(z.risk * 100).toFixed(0)}%
                      </span>
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <span className={`chip ${bandBadge[z.risk_band]}`}>{z.risk_band}</span>
                  </td>
                  <td className="stat px-3 py-2 text-right text-slate-300">
                    {z.gas_lel.toFixed(1)}
                  </td>
                  <td
                    className={`stat px-3 py-2 text-right ${
                      z.gas_trend > 0.05 ? 'text-amber-300' : 'text-slate-500'
                    }`}
                  >
                    {z.gas_trend >= 0 ? '+' : ''}
                    {z.gas_trend.toFixed(2)}
                  </td>
                  <td className="stat px-3 py-2 text-right text-slate-300">
                    {z.workers_in_zone}
                  </td>
                  <td className="px-3 py-2">
                    <span className="flex gap-1">
                      {z.hot_work_active && (
                        <span className="chip border border-red-500/30 bg-red-500/15 text-red-300">
                          hot work
                        </span>
                      )}
                      {z.maintenance_active && (
                        <span className="chip border border-amber-500/30 bg-amber-500/15 text-amber-300">
                          maint
                        </span>
                      )}
                      {!z.hot_work_active && !z.maintenance_active && (
                        <span className="text-slate-600">—</span>
                      )}
                    </span>
                  </td>
                  <td className="stat px-3 py-2 text-right text-amber-300">
                    {z.lead_time_min !== null ? `${z.lead_time_min}m` : '—'}
                  </td>
                  <td className="px-3 py-2">
                    {z.risk >= 0.6 && !z.baseline_alarm ? (
                      <span className="chip border border-amber-500/30 bg-amber-500/15 text-amber-300">
                        silent
                      </span>
                    ) : z.baseline_alarm ? (
                      <span className="chip border border-orange-500/30 bg-orange-500/15 text-orange-300">
                        firing
                      </span>
                    ) : (
                      <span className="text-slate-600">quiet</span>
                    )}
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-4 py-8 text-center text-slate-500">
                    No zones match this filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Panel>

      <p className="mt-2 text-[10.5px] text-slate-500">
        <span className="text-amber-300">Silent</span> means the compound model is at HIGH
        or CRITICAL risk while a conventional single-sensor gas alarm would not be firing —
        the failure mode this system exists to close.
      </p>
    </>
  )
}
