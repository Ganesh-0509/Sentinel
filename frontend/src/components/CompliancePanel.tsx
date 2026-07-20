import { useState } from 'react'
import { api } from '../api'
import type { ComplianceAnswer } from '../types'

const SUGGESTED = [
  'Can hot work continue if gas readings are rising?',
  'What are the duties of the occupier for a hazardous process?',
  'What must happen at shift handover for an open permit?',
]

export function CompliancePanel() {
  const [q, setQ] = useState(SUGGESTED[0])
  const [ans, setAns] = useState<ComplianceAnswer | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function ask(question: string) {
    setBusy(true)
    setError(null)
    setAns(null)
    try {
      setAns(await api.ask(question))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'query failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="panel flex h-full flex-col">
      <div className="panel-header">
        <h2 className="panel-title">Compliance Assistant</h2>
        {ans && (
          <span className="stat text-[10px] text-slate-500">via {ans.backend}</span>
        )}
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); ask(q) }}
        className="flex gap-2 border-b border-ink-600 p-3"
      >
        <label htmlFor="q" className="sr-only">Compliance question</label>
        <input
          id="q"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Ask about a regulation…"
          className="flex-1 rounded border border-ink-600 bg-ink-900 px-2.5 py-1.5 text-[11px] text-slate-200 placeholder:text-slate-600"
        />
        <button
          type="submit"
          disabled={busy || q.trim().length < 5}
          className="rounded bg-slate-700 px-3 py-1.5 text-[11px] font-medium text-slate-100 transition hover:bg-slate-600 disabled:opacity-40"
        >
          {busy ? '…' : 'Ask'}
        </button>
      </form>

      <div className="flex flex-wrap gap-1.5 px-3 pt-2">
        {SUGGESTED.map((s) => (
          <button
            key={s}
            onClick={() => { setQ(s); ask(s) }}
            className="rounded border border-ink-600 bg-ink-700/60 px-2 py-1 text-[10px] text-slate-400 transition hover:border-ink-500 hover:text-slate-200"
          >
            {s.length > 42 ? `${s.slice(0, 42)}…` : s}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-3 text-[11px] leading-relaxed">
        {error && <p className="text-red-300">{error}</p>}
        {!ans && !busy && !error && (
          <p className="text-slate-500">
            Answers are grounded in the retrieved corpus only. If no passage is
            relevant, the assistant declines rather than guessing.
          </p>
        )}
        {busy && <p className="text-slate-400">Retrieving and grounding…</p>}

        {ans && (
          <>
            {!ans.grounded && (
              <p className="mb-2 rounded border border-amber-500/30 bg-amber-500/10 p-2 text-amber-200">
                Not answerable from the corpus.
              </p>
            )}
            <p className="whitespace-pre-wrap text-slate-200">{ans.answer}</p>

            {ans.citations.length > 0 && (
              <div className="mt-3 border-t border-ink-600 pt-2">
                <h3 className="panel-title mb-1.5">Sources</h3>
                <ul className="space-y-1">
                  {ans.citations.map((c, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span
                        className={`chip mt-px shrink-0 ${
                          c.is_official
                            ? 'border border-emerald-500/30 bg-emerald-500/15 text-emerald-300'
                            : 'border border-amber-500/30 bg-amber-500/15 text-amber-300'
                        }`}
                      >
                        {c.is_official ? 'official' : c.provenance.toLowerCase()}
                      </span>
                      <span className="text-slate-400">
                        {c.standard} — {c.section}
                      </span>
                    </li>
                  ))}
                </ul>
                <p className="mt-2 text-[10px] text-slate-600">
                  Sources marked non-official are development stand-ins, not the
                  operative standard text.
                </p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
