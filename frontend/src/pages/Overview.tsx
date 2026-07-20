import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../api'
import { PlantMap } from '../components/PlantMap'
import { Empty, KpiCard, PageHeader, Panel } from '../components/ui'
import { bandBadge } from '../lib/risk'
import { usePlant } from '../state/PlantContext'
import type { KpiSummary, TierSummary, TrendPoint } from '../types'

export function Overview() {
  const { zones, alerts } = usePlant()
  const [kpis, setKpis] = useState<KpiSummary | null>(null)
  const [trend, setTrend] = useState<TrendPoint[]>([])
  const [tiers, setTiers] = useState<TierSummary | null>(null)

  useEffect(() => {
    api.kpis().then(setKpis).catch(() => setKpis(null))
    api.trend(120).then(setTrend).catch(() => setTrend([]))
    api.tiers().then(setTiers).catch(() => setTiers(null))
  }, [zones])

  const leadingEvents = tiers?.leading_events ?? 0

  return (
    <>
      <PageHeader
        title="Plant Overview"
        subtitle="Live compound risk posture across all monitored zones"
      />

      {kpis && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
            {kpis.kpis.map((k) => (
              <KpiCard key={k.key} kpi={k} />
            ))}
          </div>
          <p className="mt-2 text-[10.5px] text-slate-500">
            Leading-to-lagging ratio{' '}
            <span className={kpis.ratio_ok ? 'text-emerald-300' : 'text-amber-300'}>
              {kpis.leading_to_lagging_ratio}:1
            </span>{' '}
            (target ≥ {kpis.ratio_target}:1). A dashboard dominated by lagging indicators
            only reports how many people were already hurt.
          </p>
        </>
      )}

      <div className="mt-4 grid gap-3 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <PlantMap zones={zones} selected={null} onSelect={() => {}} />

        <div className="flex flex-col gap-3">
          <Panel
            title="Plant risk trend"
            meta={<span className="stat text-[10px] text-slate-500">last 120 min</span>}
          >
            <div className="p-2">
              <ResponsiveContainer width="100%" height={150}>
                <AreaChart data={trend} margin={{ top: 6, right: 8, left: -26, bottom: 0 }}>
                  <defs>
                    <linearGradient id="ovMax" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#ef4444" stopOpacity={0.5} />
                      <stop offset="100%" stopColor="#ef4444" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#1c2534" vertical={false} />
                  <XAxis dataKey="minute" stroke="#475569" fontSize={10} tickLine={false} />
                  <YAxis stroke="#475569" fontSize={10} tickLine={false} domain={[0, 1]} />
                  <Tooltip
                    contentStyle={{
                      background: '#111722', border: '1px solid #222c3d',
                      borderRadius: 6, fontSize: 11,
                    }}
                  />
                  <Area type="monotone" dataKey="max_risk" stroke="#ef4444"
                        strokeWidth={2} fill="url(#ovMax)" name="peak zone risk" />
                  <Area type="monotone" dataKey="mean_risk" stroke="#64748b"
                        strokeWidth={1.5} fill="none" name="plant mean" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Panel>

          <Panel
            title="Critical attention"
            meta={
              <Link to="/alerts" className="text-[10px] text-sky-400 hover:text-sky-300">
                all alerts →
              </Link>
            }
            className="flex-1"
          >
            {alerts.length === 0 ? (
              <Empty>No zone above alert threshold.</Empty>
            ) : (
              <ul className="divide-y divide-ink-600">
                {alerts.slice(0, 5).map((a) => (
                  <li key={a.alert_id}>
                    <Link
                      to={`/zones/${a.zone_id}`}
                      className="flex items-center justify-between gap-3 px-4 py-2.5 transition hover:bg-ink-700/40"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-[12px] text-slate-200">{a.zone_name}</p>
                        <p className="truncate text-[10.5px] text-slate-500">
                          {a.drivers.join(' · ') || 'no aggravating factors'}
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        {a.lead_time_min !== null && (
                          <span className="stat text-[10.5px] text-amber-300">
                            ~{a.lead_time_min}m
                          </span>
                        )}
                        <span className={`chip ${bandBadge[a.priority]}`}>{a.priority}</span>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          {tiers && (
            <Panel title="Process safety indicators" meta={
              <span className="text-[10px] text-slate-500">{tiers.framework}</span>
            }>
              <div className="grid grid-cols-4 gap-px bg-ink-600">
                {tiers.tiers.map((t) => (
                  <div key={t.tier} className="bg-ink-800 px-3 py-2.5 text-center">
                    <p className="text-[10px] uppercase tracking-wide text-slate-500">
                      Tier {t.tier}
                    </p>
                    <p className={`stat text-lg ${
                      t.count > 0
                        ? t.kind === 'leading' ? 'text-amber-300' : 'text-red-300'
                        : 'text-slate-400'
                    }`}>
                      {t.count}
                    </p>
                    <p className="text-[9.5px] text-slate-600">{t.kind}</p>
                  </div>
                ))}
              </div>
              <p className="px-4 py-2 text-[10.5px] leading-snug text-slate-500">
                {leadingEvents} leading events open — these are still actionable.
                Tier 1 and 2 are only counted after containment has already been lost.
              </p>
            </Panel>
          )}
        </div>
      </div>
    </>
  )
}
