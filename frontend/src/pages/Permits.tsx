import { useState } from 'react'
import { api } from '../api'
import { Empty, PageHeader, Panel } from '../components/ui'
import { permitBadge } from '../lib/risk'
import { usePlant } from '../state/PlantContext'
import type { PermitDecision, PermitType } from '../types'

const TYPES: PermitType[] = ['Hot Work', 'Confined Space', 'Cold Work', 'Electrical']

export function Permits() {
  const { zones } = usePlant()
  const [zoneId, setZoneId] = useState('')
  const [type, setType] = useState<PermitType>('Hot Work')
  const [useAi, setUseAi] = useState(true)
  const [decision, setDecision] = useState<PermitDecision | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const zone = zones.find((z) => z.zone_id === (zoneId || zones[0]?.zone_id))

  async function evaluate() {
    if (!zone) return
    setBusy(true)
    setError(null)
    setDecision(null)
    try {
      setDecision(await api.evaluatePermit(zone.zone_id, type, useAi))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'evaluation failed')
    } finally {
      setBusy(false)
    }
  }

  const active = zones.filter((z) => z.hot_work_active)

  return (
    <>
      <PageHeader
        title="Permit Intelligence"
        subtitle="Deterministic gas and oxygen interlocks, optionally escalated by the compound-risk model"
      />

      <div className="grid gap-3 xl:grid-cols-2">
        <Panel title="Evaluate a permit request">
          <div className="space-y-3 p-4">
            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className="mb-1 block text-[11.5px] uppercase tracking-wide text-slate-500">
                  Zone
                </span>
                <select
                  value={zone?.zone_id ?? ''}
                  onChange={(e) => setZoneId(e.target.value)}
                  className="w-full rounded border border-ink-600 bg-ink-900 px-2 py-1.5 text-[13.5px] text-slate-200"
                >
                  {zones.map((z) => (
                    <option key={z.zone_id} value={z.zone_id}>
                      {z.name}
                    </option>
                  ))}
                </select>
              </label>

              <label className="block">
                <span className="mb-1 block text-[11.5px] uppercase tracking-wide text-slate-500">
                  Permit type
                </span>
                <select
                  value={type}
                  onChange={(e) => setType(e.target.value as PermitType)}
                  className="w-full rounded border border-ink-600 bg-ink-900 px-2 py-1.5 text-[13.5px] text-slate-200"
                >
                  {TYPES.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </label>
            </div>

            {zone && (
              <div className="grid grid-cols-3 gap-px rounded border border-ink-600 bg-ink-600 text-center">
                <Mini label="Gas" value={`${zone.gas_lel.toFixed(1)} %LEL`} />
                <Mini label="Trend" value={`${zone.gas_trend >= 0 ? '+' : ''}${zone.gas_trend.toFixed(2)}`} />
                <Mini label="Model risk" value={`${(zone.risk * 100).toFixed(0)}%`} />
              </div>
            )}

            <label className="flex items-center gap-2 text-[13px] text-slate-400">
              <input
                type="checkbox"
                checked={useAi}
                onChange={(e) => setUseAi(e.target.checked)}
                className="accent-sky-500"
              />
              Allow the compound-risk model to escalate the decision
            </label>

            <button
              onClick={evaluate}
              disabled={busy || !zone}
              className="w-full rounded bg-sky-600 px-3 py-2 text-[13.5px] font-medium text-white transition hover:bg-sky-500 disabled:opacity-40"
            >
              {busy ? 'Evaluating…' : 'Evaluate permit'}
            </button>

            <p className="text-[12.5px] leading-snug text-slate-500">
              The model can only make this decision <strong>stricter</strong>. It may escalate
              or reject, but it can never approve work the deterministic gas and oxygen
              interlocks have rejected.
            </p>
          </div>
        </Panel>

        <Panel title="Decision">
          {error && <p className="p-4 text-[13px] text-red-300">{error}</p>}
          {!decision && !error && (
            <Empty>Submit a request to see the interlock decision and its citations.</Empty>
          )}
          {decision && (
            <div className="space-y-3 p-4">
              <span className={`chip ${permitBadge[decision.status]}`}>{decision.status}</span>
              <ul className="space-y-1.5 text-[13.5px] leading-relaxed text-slate-300">
                {decision.reasons.map((r, i) => (
                  <li key={i}>• {r}</li>
                ))}
              </ul>
              {decision.citations.length > 0 && (
                <div className="border-t border-ink-600 pt-2">
                  {decision.citations.map((c, i) => (
                    <p key={i} className="text-[12.5px] text-sky-300/80">[cite] {c}</p>
                  ))}
                </div>
              )}
            </div>
          )}
        </Panel>
      </div>

      <Panel title="Active hot-work permits" className="mt-3">
        {active.length === 0 ? (
          <Empty>No hot-work permits currently active.</Empty>
        ) : (
          <ul className="divide-y divide-ink-600">
            {active.map((z) => (
              <li key={z.zone_id} className="flex items-center justify-between px-4 py-2.5">
                <div>
                  <p className="text-[13.5px] text-slate-200">{z.name}</p>
                  <p className="text-[12.5px] text-slate-500">
                    {z.gas_lel.toFixed(1)} %LEL · {z.workers_in_zone} workers
                    {z.maintenance_active && ' · concurrent maintenance'}
                  </p>
                </div>
                <span
                  className={`chip ${
                    z.risk >= 0.85
                      ? 'border border-red-500/30 bg-red-500/15 text-red-300'
                      : z.risk >= 0.5
                        ? 'border border-amber-500/30 bg-amber-500/15 text-amber-300'
                        : 'border border-emerald-500/30 bg-emerald-500/15 text-emerald-300'
                  }`}
                >
                  risk {(z.risk * 100).toFixed(0)}%
                </span>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </>
  )
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-ink-800 px-2 py-1.5">
      <p className="text-[11px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className="stat text-[14px] text-slate-200">{value}</p>
    </div>
  )
}
