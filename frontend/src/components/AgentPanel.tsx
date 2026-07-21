import { useState } from 'react'
import { api } from '../api'
import type { WorkflowResult, ZoneState } from '../types'
import { permitBadge } from '../lib/risk'

interface Props {
  zone: ZoneState | null
}

export function AgentPanel({ zone }: Props) {
  const [result, setResult] = useState<WorkflowResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function run() {
    if (!zone) return
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      setResult(await api.runWorkflow(zone.zone_id))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'workflow failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="panel flex h-full flex-col">
      <div className="panel-header">
        <h2 className="panel-title">Agentic Response</h2>
        <button
          onClick={run}
          disabled={!zone || busy}
          className="rounded bg-sky-600 px-3 py-1 text-[13px] font-medium text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? 'Running…' : `Run workflow${zone ? ` · ${zone.zone_id}` : ''}`}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 text-[13px] leading-relaxed">
        {!result && !busy && !error && (
          <p className="text-slate-500">
            Runs the multi-agent workflow against this zone's live state:
            risk monitor → permit intelligence → compliance → emergency orchestration.
          </p>
        )}
        {busy && (
          <p className="text-slate-400">
            Agents executing — compliance and notification steps call the local model,
            this can take a few seconds…
          </p>
        )}
        {error && <p className="text-red-300">{error}</p>}

        {result && (
          <div className="space-y-4">
            <section>
              <h3 className="panel-title mb-1.5">Agent trace</h3>
              <ol className="space-y-1 font-mono text-[12.5px] text-slate-400">
                {result.trace.map((t, i) => (
                  <li key={i} className="border-l-2 border-ink-500 pl-2">{t}</li>
                ))}
              </ol>
            </section>

            {result.permit_decision && (
              <section>
                <div className="mb-1.5 flex items-center gap-2">
                  <h3 className="panel-title">Permit decision</h3>
                  <span className={`chip ${permitBadge[result.permit_decision.status]}`}>
                    {result.permit_decision.status}
                  </span>
                </div>
                <ul className="space-y-1 text-slate-300">
                  {result.permit_decision.reasons.map((r, i) => <li key={i}>• {r}</li>)}
                </ul>
                {result.permit_decision.citations.map((c, i) => (
                  <p key={i} className="mt-1 text-[11.5px] text-sky-300/80">[cite] {c}</p>
                ))}
              </section>
            )}

            {result.interlocks.length > 0 && (
              <section className="rounded border border-red-500/30 bg-red-500/10 p-2">
                <h3 className="panel-title mb-1 text-red-300">Interlocks tripped</h3>
                {result.interlocks.map((v, i) => (
                  <p key={i} className="text-red-200">{v}</p>
                ))}
              </section>
            )}

            {result.actions.length > 0 && (
              <section>
                <h3 className="panel-title mb-1.5">Actions initiated</h3>
                <ul className="space-y-1 text-slate-300">
                  {result.actions.map((a, i) => (
                    <li key={i} className="flex gap-2">
                      <span className="text-emerald-400">▸</span>{a}
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {result.report && (
              <section>
                <h3 className="panel-title mb-1.5">Draft regulatory notification</h3>
                <p className="whitespace-pre-wrap rounded border border-ink-600 bg-ink-900/60 p-2.5 text-slate-300">
                  {result.report}
                </p>
                <p className="mt-1 text-[11.5px] text-slate-500">
                  Preliminary automated draft — requires human verification before submission.
                </p>
              </section>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
