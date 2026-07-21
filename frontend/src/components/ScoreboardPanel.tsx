import type { Scoreboard } from '../types'

interface Props {
  data: Scoreboard | null
}

/**
 * The evidence panel. Compound engine vs a conventional single-sensor alarm on
 * held-out episodes -- the comparison the evaluation criteria actually ask for.
 */
export function ScoreboardPanel({ data }: Props) {
  if (!data) {
    return (
      <div className="panel p-4">
        <p className="text-[13px] text-slate-500">
          No evaluation report — run <code className="text-slate-400">scripts/run_pipeline.py</code>.
        </p>
      </div>
    )
  }

  const rows = [
    {
      label: 'Incident detection',
      base: data.baseline_detection_rate,
      ours: data.compound_detection_rate,
      higherIsBetter: true,
    },
    {
      label: 'False negatives (missed)',
      base: data.baseline_false_negative_rate,
      ours: data.compound_false_negative_rate,
      higherIsBetter: false,
    },
    {
      label: 'False alarms (safe zones)',
      base: data.baseline_false_alarm_rate,
      ours: data.compound_false_alarm_rate,
      higherIsBetter: false,
    },
  ]

  return (
    <div className="panel">
      <div className="panel-header">
        <h2 className="panel-title">Evidence — vs single-sensor baseline</h2>
        <span className="stat text-[11.5px] text-slate-500">
          {data.n_episodes} held-out episodes
        </span>
      </div>

      <div className="p-4">
        <div className="mb-3 grid grid-cols-[1fr_auto_auto] gap-x-4 gap-y-2 text-[13px]">
          <span />
          <span className="text-right text-[11.5px] uppercase tracking-wide text-slate-500">
            Baseline
          </span>
          <span className="text-right text-[11.5px] uppercase tracking-wide text-sky-400">
            SentinelAI
          </span>

          {rows.map((r) => {
            const better = r.higherIsBetter ? r.ours > r.base : r.ours < r.base
            return (
              <Row key={r.label} label={r.label} base={r.base} ours={r.ours} better={better} />
            )
          })}
        </div>

        <div className="rounded border border-emerald-500/25 bg-emerald-500/10 px-3 py-2">
          <p className="stat text-lg text-emerald-300">
            {data.incidents_missed_by_baseline_caught_by_compound}
          </p>
          <p className="text-[13px] text-emerald-200/80">
            incidents the single-sensor baseline missed entirely that SentinelAI caught —
            each one a compound event no single sensor could see.
          </p>
        </div>
      </div>
    </div>
  )
}

function Row({ label, base, ours, better }: {
  label: string; base: number; ours: number; better: boolean
}) {
  return (
    <>
      <span className="text-slate-300">{label}</span>
      <span className="stat text-right text-slate-500">{(base * 100).toFixed(1)}%</span>
      <span
        className={`stat text-right font-semibold ${
          better ? 'text-emerald-300' : 'text-slate-300'
        }`}
      >
        {(ours * 100).toFixed(1)}%
      </span>
    </>
  )
}
