import { useEffect, useState } from 'react'
import {
  Bar as RBar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../api'
import { Empty, PageHeader, Panel } from '../components/ui'
import { riskHex } from '../lib/risk'
import { usePlant } from '../state/PlantContext'
import type {
  AlarmPerformance,
  ContributingFactor,
  RiskDistribution,
  TierSummary,
  TrendPoint,
} from '../types'

const BAND_BAR: Record<string, string> = {
  TARGET: 'text-emerald-300',
  ACCEPTABLE: 'text-emerald-300',
  OVER_TARGET: 'text-amber-300',
  SERIOUSLY_DEFICIENT: 'text-red-300',
}

export function Analytics() {
  const { zones } = usePlant()
  const [tiers, setTiers] = useState<TierSummary | null>(null)
  const [alarms, setAlarms] = useState<AlarmPerformance | null>(null)
  const [dist, setDist] = useState<RiskDistribution | null>(null)
  const [factors, setFactors] = useState<ContributingFactor[]>([])
  const [trend, setTrend] = useState<TrendPoint[]>([])

  useEffect(() => {
    api.tiers().then(setTiers).catch(() => setTiers(null))
    api.alarmPerformance().then(setAlarms).catch(() => setAlarms(null))
    api.riskDistribution().then(setDist).catch(() => setDist(null))
    api.contributingFactors(10).then(setFactors).catch(() => setFactors([]))
    api.trend(240).then(setTrend).catch(() => setTrend([]))
  }, [zones])

  return (
    <>
      <PageHeader
        title="Safety Analytics"
        subtitle="Process safety indicators (API RP 754) and alarm system performance (EEMUA 191 / ISA-18.2)"
      />

      {/* ---------------- API RP 754 tier classification ---------------- */}
      <Panel
        title="Process safety indicator tiers"
        meta={<span className="text-[10px] text-slate-500">{tiers?.framework}</span>}
      >
        {!tiers ? (
          <Empty>Analytics unavailable.</Empty>
        ) : (
          <>
            <div className="grid gap-px bg-ink-600 md:grid-cols-4">
              {tiers.tiers.map((t) => (
                <div key={t.tier} className="bg-ink-800 p-3">
                  <div className="flex items-center justify-between">
                    <p className="text-[10px] uppercase tracking-wide text-slate-500">
                      Tier {t.tier}
                    </p>
                    <span
                      className={`chip ${
                        t.kind === 'leading'
                          ? 'border border-sky-500/30 bg-sky-500/10 text-sky-300'
                          : 'border border-slate-500/30 bg-slate-500/10 text-slate-400'
                      }`}
                    >
                      {t.kind}
                    </span>
                  </div>
                  <p
                    className={`stat mt-1 text-2xl ${
                      t.count > 0 ? 'text-amber-300' : 'text-slate-500'
                    }`}
                  >
                    {t.count}
                  </p>
                  <p className="mt-0.5 text-[10.5px] leading-snug text-slate-500">{t.name}</p>
                  {t.external_reporting && (
                    <p className="mt-1 text-[9.5px] text-slate-600">
                      externally reportable
                    </p>
                  )}
                </div>
              ))}
            </div>

            <div className="border-t border-ink-600 p-3">
              <p className="mb-2 text-[10.5px] leading-snug text-slate-500">{tiers.note}</p>
              <div className="space-y-1.5">
                {tiers.tiers
                  .flatMap((t) => t.events.map((e) => ({ ...e, tier: t.tier })))
                  .map((e, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-3 rounded border border-ink-600 bg-ink-700/40 px-3 py-2"
                    >
                      <span className="chip shrink-0 border border-amber-500/30 bg-amber-500/10 text-amber-300">
                        T{e.tier}
                      </span>
                      <div className="min-w-0">
                        <p className="text-[11.5px] text-slate-200">
                          {e.event}{' '}
                          <span className="text-slate-500">· {e.zone}</span>
                        </p>
                        <p className="text-[10.5px] text-slate-500">{e.detail}</p>
                      </div>
                    </div>
                  ))}
                {tiers.leading_events === 0 && (
                  <Empty>No open process safety events.</Empty>
                )}
              </div>
            </div>
          </>
        )}
      </Panel>

      {/* ---------------- alarm performance ---------------- */}
      <div className="mt-3 grid gap-3 xl:grid-cols-2">
        <Panel
          title="Alarm system performance"
          meta={<span className="text-[10px] text-slate-500">{alarms?.framework}</span>}
        >
          {!alarms?.available ? (
            <Empty>Run the evaluation pipeline to populate alarm analytics.</Empty>
          ) : (
            <div className="p-3">
              <p className="mb-3 text-[10.5px] leading-snug text-slate-500">
                EEMUA 191 puts the acceptable operator load at under{' '}
                {alarms.benchmarks!.target_per_hour} alarms per hour; above{' '}
                {alarms.benchmarks!.seriously_deficient_per_hour} the alarm system is
                classed <span className="text-red-300">seriously deficient</span>. A
                detector that finds everything by alarming constantly is not a safety
                system — it is noise.
              </p>

              {alarms.systems!.map((s) => (
                <div key={s.system} className="mb-3">
                  <div className="mb-1 flex items-baseline justify-between">
                    <span className="text-[11.5px] text-slate-300">{s.system}</span>
                    <span className={`stat text-sm ${BAND_BAR[s.band]}`}>
                      {s.alarms_per_operator_hour}
                      <span className="ml-1 text-[10px] text-slate-500">/op/hr</span>
                    </span>
                  </div>
                  <div className="relative h-2 w-full rounded bg-ink-600">
                    <div
                      className={`h-2 rounded ${
                        s.within_eemua_target ? 'bg-emerald-400' : 'bg-red-400'
                      }`}
                      style={{
                        width: `${Math.min(
                          (s.alarms_per_operator_hour /
                            alarms.benchmarks!.seriously_deficient_per_hour) * 100, 100,
                        )}%`,
                      }}
                    />
                    {/* EEMUA target marker */}
                    <div
                      className="absolute top-[-3px] h-3 w-px bg-emerald-300"
                      style={{
                        left: `${(alarms.benchmarks!.target_per_hour /
                          alarms.benchmarks!.seriously_deficient_per_hour) * 100}%`,
                      }}
                      title="EEMUA 191 target"
                    />
                  </div>
                  <p className="mt-0.5 text-[10px] text-slate-600">
                    {s.band.replace(/_/g, ' ').toLowerCase()} · measured{' '}
                    {(s.false_alarm_rate * 100).toFixed(1)}% false-alarm rate per zone
                  </p>
                </div>
              ))}

              <div className="mt-3 rounded border border-emerald-500/25 bg-emerald-500/10 px-3 py-2">
                <p className="stat text-lg text-emerald-300">
                  âˆ’{alarms.nuisance_reduction_pct}%
                </p>
                <p className="text-[10.5px] text-emerald-200/80">
                  reduction in operator alarm load versus the single-sensor baseline.
                </p>
              </div>

              <p className="mt-2 text-[10px] leading-snug text-slate-600">
                {alarms.projection_note}
              </p>
            </div>
          )}
        </Panel>

        {/* ---------------- contributing factors ---------------- */}
        <Panel title="Contributing factors" meta={
          <span className="text-[10px] text-slate-500">global model attribution</span>
        }>
          {factors.length === 0 ? (
            <Empty>Model attribution unavailable.</Empty>
          ) : (
            <div className="p-3">
              <ResponsiveContainer width="100%" height={240}>
                <BarChart
                  data={factors}
                  layout="vertical"
                  margin={{ top: 0, right: 12, left: 78, bottom: 0 }}
                >
                  <CartesianGrid stroke="#1c2534" horizontal={false} />
                  <XAxis type="number" stroke="#475569" fontSize={10} tickLine={false} />
                  <YAxis
                    type="category"
                    dataKey="label"
                    stroke="#475569"
                    fontSize={9.5}
                    width={78}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      background: '#111722', border: '1px solid #222c3d',
                      borderRadius: 6, fontSize: 11,
                    }}
                  />
                  <RBar dataKey="importance" fill="#38bdf8" radius={[0, 2, 2, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <p className="mt-1 text-[10.5px] leading-snug text-slate-500">
                Which signals drive risk plant-wide. Note the spread across gas,
                pressure, vibration and operational context — a single-sensor alarm
                sees only the first of these.
              </p>
            </div>
          )}
        </Panel>
      </div>

      {/* ---------------- distribution + trend ---------------- */}
      <div className="mt-3 grid gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        <Panel title="Risk distribution by zone">
          {!dist ? (
            <Empty>No distribution data.</Empty>
          ) : (
            <div className="p-3">
              <ResponsiveContainer width="100%" height={190}>
                <BarChart data={dist.by_zone} margin={{ top: 4, right: 8, left: -26, bottom: 0 }}>
                  <CartesianGrid stroke="#1c2534" vertical={false} />
                  <XAxis dataKey="zone_id" stroke="#475569" fontSize={9.5} tickLine={false} />
                  <YAxis stroke="#475569" fontSize={10} tickLine={false} domain={[0, 1]} />
                  <Tooltip
                    contentStyle={{
                      background: '#111722', border: '1px solid #222c3d',
                      borderRadius: 6, fontSize: 11,
                    }}
                  />
                  <RBar dataKey="risk" radius={[2, 2, 0, 0]}>
                    {dist.by_zone.map((z) => (
                      <Cell
                        key={z.zone_id}
                        fill={riskHex[z.band.toLowerCase() as keyof typeof riskHex]}
                      />
                    ))}
                  </RBar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Panel>

        <Panel title="Plant risk & exposure over time">
          <div className="p-3">
            <ResponsiveContainer width="100%" height={190}>
              <LineChart data={trend} margin={{ top: 4, right: 10, left: -26, bottom: 0 }}>
                <CartesianGrid stroke="#1c2534" vertical={false} />
                <XAxis dataKey="minute" stroke="#475569" fontSize={10} tickLine={false} />
                <YAxis yAxisId="l" stroke="#475569" fontSize={10} tickLine={false} domain={[0, 1]} />
                <YAxis yAxisId="r" orientation="right" stroke="#475569" fontSize={10}
                       tickLine={false} width={26} allowDecimals={false} />
                <Tooltip
                  contentStyle={{
                    background: '#111722', border: '1px solid #222c3d',
                    borderRadius: 6, fontSize: 11,
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 10 }} />
                <Line yAxisId="l" type="monotone" dataKey="max_risk" stroke="#ef4444"
                      strokeWidth={2} dot={false} isAnimationActive={false} name="peak zone risk" />
                <Line yAxisId="l" type="monotone" dataKey="mean_risk" stroke="#64748b"
                      strokeWidth={1.5} dot={false} isAnimationActive={false} name="plant mean" />
                <Line yAxisId="r" type="stepAfter" dataKey="zones_at_risk" stroke="#f59e0b"
                      strokeWidth={1.5} dot={false} isAnimationActive={false} name="zones at risk" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>
    </>
  )
}



