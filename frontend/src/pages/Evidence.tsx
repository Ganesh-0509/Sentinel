import { useEffect, useState } from 'react'
import { api } from '../api'
import { ScoreboardPanel } from '../components/ScoreboardPanel'
import { PageHeader, Panel } from '../components/ui'
import type { Scoreboard } from '../types'

export function Evidence() {
  const [board, setBoard] = useState<Scoreboard | null>(null)

  useEffect(() => {
    api.scoreboard().then(setBoard).catch(() => setBoard(null))
  }, [])

  return (
    <>
      <PageHeader
        title="Model Evidence"
        subtitle="How the compound engine was validated, and the decisions that shaped it"
      />

      <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <div className="flex flex-col gap-3">
          <ScoreboardPanel data={board} />

          {board && (
            <Panel title="Compared at equal nuisance">
              <div className="p-4">
                <p className="mb-3 text-[10.5px] leading-snug text-slate-500">
                  A low fixed-threshold alarm buys lead time by alarming constantly, so the
                  two systems must be compared at the <em>same</em> false-alarm rate — not at
                  whatever operating point each happens to use.
                </p>
                <div className="grid grid-cols-2 gap-px rounded border border-ink-600 bg-ink-600">
                  <div className="bg-ink-800 p-3">
                    <p className="text-[10px] uppercase tracking-wide text-slate-500">
                      Single-sensor baseline
                    </p>
                    <p className="stat mt-1 text-lg text-slate-400">73.4%</p>
                    <p className="text-[10.5px] text-slate-600">detection · 27.3 min lead</p>
                  </div>
                  <div className="bg-ink-800 p-3">
                    <p className="text-[10px] uppercase tracking-wide text-sky-400">
                      SentinelAI
                    </p>
                    <p className="stat mt-1 text-lg text-emerald-300">100%</p>
                    <p className="text-[10.5px] text-slate-500">detection · 64.6 min lead</p>
                  </div>
                </div>
                <p className="mt-2 text-[10.5px] text-slate-500">
                  At the baseline's own false-alarm rate, the compound engine dominates on
                  every axis simultaneously — 2.4× the warning time and +26.6 points of
                  detection.
                </p>
              </div>
            </Panel>
          )}
        </div>

        <div className="flex flex-col gap-3">
          <Panel title="Why the model has no shift features">
            <div className="space-y-2.5 p-4 text-[11.5px] leading-relaxed text-slate-300">
              <p>
                Shift changeover was modelled properly — operator detection latency and
                handover information loss — and it turned out to be genuinely causal:
                night-shift leaks escalate to incidents{' '}
                <span className="text-amber-300">49.5%</span> of the time versus{' '}
                <span className="text-slate-400">28.7%</span> on day shift.
              </p>
              <p>
                An ablation then showed those features should still not be model inputs.
                Compared threshold-free and at a matched false-alarm rate, including them
                cost <span className="text-red-300">17.8 points of detection</span>{' '}
                (PR-AUC 0.457 → 0.412).
              </p>
              <p className="rounded border border-ink-600 bg-ink-900/60 p-2.5 text-slate-400">
                The features predict whether a <em>human</em> will rescue the situation, so
                the model learned “day shift, no changeover — someone will probably catch
                this” and under-alerted. A safety alert must reflect the hazard, not the
                odds that somebody else fixes it.
              </p>
              <p>
                Those signals now live in the decision layer as consequence and urgency
                multipliers for alert ranking, where they inform the operator without ever
                teaching the model complacency.
              </p>
              <p className="text-[10.5px] text-slate-500">
                Reproduce: <code className="text-slate-400">scripts/ablation_shift.py</code>
              </p>
            </div>
          </Panel>

          <Panel title="Model card">
            <dl className="divide-y divide-ink-600 text-[11.5px]">
              <Row k="Task" v="P(incident within 30 min) from observable signals" />
              <Row k="Algorithm" v="Gradient-boosted trees (LightGBM), 23 features" />
              <Row k="Labels" v="Physical threshold crossing emerging from simulated dynamics — not hand-written risk rules" />
              <Row k="Leakage control" v="True zone gas is excluded from features; it defines the label" />
              <Row k="Explainability" v="SHAP attribution on every alert" />
              <Row k="Novelty detection" v="Isolation Forest + PCA reconstruction, trained on normal operation only" />
              <Row k="Hard limits" v="Deterministic gas/oxygen interlocks hold veto; the model can only tighten a decision" />
              <Row k="External validation" v="Anomaly layer validated unchanged on Tennessee Eastman (84.7% detection @ 1% false alarms) and HAI (ROC-AUC 0.966, 5/5 attacks). Plant-specific numbers remain simulator-derived." />
              <Row k="Known limitation" v="Separability transfers across processes; calibration does not. Thresholds must be recalibrated per plant and per operating campaign." />
              <Row k="Not validated" v="The lead-time claim. TEP and HAI anomalies are injected, not developing hazards, so neither benchmark can test early warning." />
            </dl>
          </Panel>
        </div>
      </div>
    </>
  )
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="grid grid-cols-[128px_minmax(0,1fr)] gap-3 px-4 py-2">
      <dt className="text-[10px] uppercase tracking-wide text-slate-500">{k}</dt>
      <dd className="text-slate-300">{v}</dd>
    </div>
  )
}
