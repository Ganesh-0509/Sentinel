import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Empty, PageHeader, Panel } from '../components/ui'
import { bandBadge } from '../lib/risk'
import { usePlant } from '../state/PlantContext'
import type { Priority } from '../types'

type Filter = 'ALL' | Priority

const ORDER: Priority[] = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']

export function Alerts() {
  const { alerts, zones } = usePlant()
  // Priority filter is URL state so a specific view can be shared.
  const [params, setParams] = useSearchParams()
  const filter = (params.get('priority') as Filter) ?? 'ALL'
  const setFilter = (f: Filter) => {
    const p = new URLSearchParams(params)
    if (f === 'ALL') p.delete('priority')
    else p.set('priority', f)
    setParams(p, { replace: true })
  }

  const counts = useMemo(() => {
    const c: Record<string, number> = { ALL: alerts.length }
    alerts.forEach((a) => {
      c[a.priority] = (c[a.priority] ?? 0) + 1
    })
    return c
  }, [alerts])

  const rows = filter === 'ALL' ? alerts : alerts.filter((a) => a.priority === filter)

  // How many alerts a conventional single-sensor system would be producing now.
  const baselineFiring = zones.filter((z) => z.baseline_alarm).length
  const silentButRisky = zones.filter((z) => z.risk >= 0.6 && !z.baseline_alarm).length

  return (
    <>
      <PageHeader
        title="Alert Queue"
        subtitle="Prioritised by risk × people exposed × response capacity — not by raw sensor value"
      />

      <div className="mb-3 grid gap-3 sm:grid-cols-3">
        <Stat label="Alerts raised" value={alerts.length}
              hint="Compound engine, prioritised" tone="sky" />
        <Stat label="Single-sensor alarms firing" value={baselineFiring}
              hint="What a conventional gas alarm would show right now" tone="slate" />
        <Stat label="High risk, sensor silent" value={silentButRisky}
              hint="Hazards a single sensor cannot see" tone={silentButRisky ? 'amber' : 'slate'} />
      </div>

      <div className="mb-3 flex flex-wrap gap-1.5">
        {(['ALL', ...ORDER] as Filter[]).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded border px-2.5 py-1 text-[13px] transition ${
              filter === f
                ? 'border-sky-500/50 bg-sky-500/15 text-sky-200'
                : 'border-ink-600 bg-ink-700/50 text-slate-400 hover:text-slate-200'
            }`}
          >
            {f === 'ALL' ? 'All' : f}
            <span className="ml-1.5 text-slate-600">{counts[f] ?? 0}</span>
          </button>
        ))}
      </div>

      <Panel>
        {rows.length === 0 ? (
          <Empty>No alerts at this priority.</Empty>
        ) : (
          <ul className="divide-y divide-ink-600">
            {rows.map((a) => (
              <li key={a.alert_id}>
                <Link
                  to={`/zones/${a.zone_id}`}
                  className="flex items-start justify-between gap-4 px-4 py-3 transition hover:bg-ink-700/40"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`chip ${bandBadge[a.priority]}`}>{a.priority}</span>
                      <span className="text-[14px] text-slate-200">{a.zone_name}</span>
                      <span className="font-mono text-[11.5px] text-slate-600">
                        {a.alert_id}
                      </span>
                    </div>
                    <p className="mt-1 text-[12.5px] text-slate-500">
                      {a.drivers.join(' · ') || 'no aggravating factors'}
                    </p>
                  </div>

                  <div className="flex shrink-0 items-center gap-4 text-right">
                    <div>
                      <p className="stat text-[14px] text-slate-200">
                        {(a.risk * 100).toFixed(0)}%
                      </p>
                      <p className="text-[11px] text-slate-600">risk</p>
                    </div>
                    <div>
                      <p className="stat text-[14px] text-amber-300">
                        {a.lead_time_min !== null ? `${a.lead_time_min}m` : '—'}
                      </p>
                      <p className="text-[11px] text-slate-600">lead</p>
                    </div>
                    <div>
                      <p className="stat text-[14px] text-slate-300">{a.score.toFixed(2)}</p>
                      <p className="text-[11px] text-slate-600">priority</p>
                    </div>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <p className="mt-2 text-[12.5px] leading-snug text-slate-500">
        Priority score = compound risk × exposure (people in zone) × urgency (night shift,
        shift changeover). Shift state deliberately affects <em>ranking</em>, never the risk
        model itself — see Model Evidence for why.
      </p>
    </>
  )
}

function Stat({ label, value, hint, tone }: {
  label: string; value: number; hint: string; tone: 'sky' | 'slate' | 'amber'
}) {
  const tones = {
    sky: 'text-sky-300 border-sky-500/30',
    slate: 'text-slate-300 border-ink-600',
    amber: 'text-amber-300 border-amber-500/30',
  }
  return (
    <div className={`rounded-lg border bg-ink-800/80 p-3 ${tones[tone]}`}>
      <p className="text-[11.5px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className="stat mt-0.5 text-xl">{value}</p>
      <p className="mt-0.5 text-[12.5px] leading-snug text-slate-500">{hint}</p>
    </div>
  )
}
