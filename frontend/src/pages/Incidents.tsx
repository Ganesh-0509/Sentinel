import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, PageHeader, Panel } from '../components/ui'
import type { IncidentRecord, PatternSummary, PreventionPriority } from '../types'

export function Incidents() {
  const [summary, setSummary] = useState<PatternSummary | null>(null)
  const [priorities, setPriorities] = useState<PreventionPriority[]>([])
  const [records, setRecords] = useState<IncidentRecord[]>([])
  const [filter, setFilter] = useState<'ALL' | 'INCIDENT' | 'NEAR_MISS'>('ALL')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api.patterns().then(setSummary).catch(() => setSummary(null)),
      api.priorities().then(setPriorities).catch(() => setPriorities([])),
      api.incidentRecords(undefined, 60).then(setRecords).catch(() => setRecords([])),
    ]).finally(() => setLoading(false))
  }, [])

  const shown = filter === 'ALL' ? records : records.filter((r) => r.outcome === filter)

  return (
    <>
      <PageHeader
        title="Incident Pattern Intelligence"
        subtitle="Recurring precursor combinations mined across the incident and near-miss corpus"
      />

      {loading && <Empty>Mining patterns…</Empty>}

      {summary && (
        <>
          <div className="mb-3 grid gap-3 sm:grid-cols-4">
            <Stat label="Records analysed" value={summary.n_records} tone="slate"
                  hint="Incidents and near misses with full telemetry" />
            <Stat label="Incidents" value={summary.n_incidents} tone="red"
                  hint="Threshold was reached" />
            <Stat label="Near misses" value={summary.n_near_misses} tone="emerald"
                  hint="Isolated in time — a leading indicator, not a failure" />
            <Stat label="Base incident rate"
                  value={`${(summary.base_incident_rate * 100).toFixed(0)}%`} tone="slate"
                  hint="Reference for lift calculation" />
          </div>

          <Panel title="Recurring precursor patterns" meta={
            <span className="text-[10px] text-slate-500">ranked by lift</span>
          }>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[820px] text-[11.5px]">
                <thead>
                  <tr className="border-b border-ink-600 text-left text-[10px] uppercase tracking-wide text-slate-500">
                    <th className="px-4 py-2 font-medium">Precursor combination</th>
                    <th className="px-3 py-2 text-right font-medium">Lift</th>
                    <th className="px-3 py-2 text-right font-medium">Occurrences</th>
                    <th className="px-3 py-2 text-right font-medium">Incidents</th>
                    <th className="px-3 py-2 text-right font-medium">Near misses</th>
                    <th className="px-3 py-2 text-right font-medium">Sensor missed</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-700">
                  {summary.patterns.map((p) => (
                    <tr key={p.label} className="hover:bg-ink-700/40">
                      <td className="px-4 py-2 text-slate-200">{p.label}</td>
                      <td className="px-3 py-2 text-right">
                        <span
                          className={`stat font-semibold ${
                            p.lift >= 1.5 ? 'text-red-300'
                              : p.lift >= 1.15 ? 'text-amber-300' : 'text-slate-400'
                          }`}
                        >
                          {p.lift.toFixed(2)}×
                        </span>
                      </td>
                      <td className="stat px-3 py-2 text-right text-slate-400">{p.occurrences}</td>
                      <td className="stat px-3 py-2 text-right text-slate-300">{p.incidents}</td>
                      <td className="stat px-3 py-2 text-right text-slate-500">{p.near_misses}</td>
                      <td className="stat px-3 py-2 text-right text-amber-300">
                        {p.single_sensor_missed}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="border-t border-ink-600 px-4 py-2 text-[10.5px] leading-snug text-slate-500">
              {summary.method}
            </p>
          </Panel>

          {priorities.length > 0 && (
            <Panel title="Prevention priorities" className="mt-3">
              <ol className="divide-y divide-ink-600">
                {priorities.map((p, i) => (
                  <li key={p.pattern} className="px-4 py-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-start gap-3 min-w-0">
                        <span className="stat mt-0.5 shrink-0 text-[11px] text-slate-600">
                          {String(i + 1).padStart(2, '0')}
                        </span>
                        <div className="min-w-0">
                          <p className="text-[12px] text-slate-200">{p.pattern}</p>
                          <p className="text-[10.5px] text-slate-500">
                            {p.occurrences} occurrences · {p.incidents} incidents ·{' '}
                            <span className="text-amber-300">
                              {p.single_sensor_missed} not caught by a point sensor
                            </span>
                          </p>
                        </div>
                      </div>
                      <span className="chip shrink-0 border border-red-500/30 bg-red-500/15 text-red-300">
                        {p.lift.toFixed(2)}× risk
                      </span>
                    </div>
                    <ul className="mt-2 space-y-1 pl-9">
                      {p.actions.map((a, j) => (
                        <li key={j} className="flex gap-2 text-[11px] text-slate-400">
                          <span className="text-emerald-400">▸</span>
                          {a}
                        </li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ol>
            </Panel>
          )}
        </>
      )}

      <Panel title="Incident & near-miss register" className="mt-3" meta={
        <div className="flex gap-1.5">
          {(['ALL', 'INCIDENT', 'NEAR_MISS'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`rounded border px-2 py-0.5 text-[10px] transition ${
                filter === f
                  ? 'border-sky-500/50 bg-sky-500/15 text-sky-200'
                  : 'border-ink-600 text-slate-500 hover:text-slate-300'
              }`}
            >
              {f.replace('_', ' ').toLowerCase()}
            </button>
          ))}
        </div>
      }>
        {shown.length === 0 ? (
          <Empty>No records.</Empty>
        ) : (
          <ul className="divide-y divide-ink-600">
            {shown.slice(0, 25).map((r) => (
              <li key={r.record_id} className="px-4 py-2.5">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <span className="font-mono text-[10px] text-slate-600">
                      {r.record_id}
                    </span>
                    <span className="ml-2 text-[11.5px] text-slate-300">{r.zone}</span>
                  </div>
                  <div className="flex shrink-0 gap-1.5">
                    {!r.detected_by_single_sensor && r.outcome === 'INCIDENT' && (
                      <span className="chip border border-amber-500/30 bg-amber-500/15 text-amber-300">
                        sensor missed
                      </span>
                    )}
                    <span
                      className={`chip ${
                        r.outcome === 'INCIDENT'
                          ? 'border border-red-500/30 bg-red-500/15 text-red-300'
                          : 'border border-emerald-500/30 bg-emerald-500/15 text-emerald-300'
                      }`}
                    >
                      {r.outcome.replace('_', ' ').toLowerCase()}
                    </span>
                  </div>
                </div>
                <p className="mt-1 text-[10.5px] leading-snug text-slate-500">
                  {r.narrative}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </>
  )
}

function Stat({ label, value, hint, tone }: {
  label: string; value: number | string; hint: string
  tone: 'slate' | 'red' | 'emerald'
}) {
  const tones = {
    slate: 'border-ink-600 text-slate-200',
    red: 'border-red-500/30 text-red-300',
    emerald: 'border-emerald-500/30 text-emerald-300',
  }
  return (
    <div className={`rounded-lg border bg-ink-800/80 p-3 ${tones[tone]}`}>
      <p className="text-[10px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className="stat mt-0.5 text-xl">{value}</p>
      <p className="mt-0.5 text-[10.5px] leading-snug text-slate-500">{hint}</p>
    </div>
  )
}
