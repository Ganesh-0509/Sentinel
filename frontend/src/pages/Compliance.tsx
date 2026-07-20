import { CompliancePanel } from '../components/CompliancePanel'
import { PageHeader, Panel } from '../components/ui'

const CORPUS = [
  {
    standard: 'Factories Act, 1948',
    issuer: 'Government of India',
    provenance: 'STATUTE',
    official: true,
    detail:
      'Sections 7A, 41B, 41C, 41F, 41G, 41H and 88 — occupier duties, hazardous-process ' +
      'obligations, exposure limits, safety committee, right to warn of imminent danger, ' +
      'accident notification.',
  },
  {
    standard: 'OISD-STD-105',
    issuer: 'Oil Industry Safety Directorate',
    provenance: 'REFERENCE_ONLY',
    official: false,
    detail:
      'Work permit system — hot work, confined space, cold work, electrical isolation. ' +
      'Marked FOR RESTRICTED CIRCULATION and not reproducible without written consent, so ' +
      'only a navigational index ships here. Place a licensed copy in data/regulations_local/ ' +
      'to upgrade citations to official.',
  },
  {
    standard: 'On-site emergency response',
    issuer: 'Site SOP template',
    provenance: 'SUMMARY',
    official: false,
    detail:
      'Declaration, zoning, evacuation and accounting, evidence preservation, reporting ' +
      'and return to normal. Replace with your approved on-site emergency plan.',
  },
]

export function Compliance() {
  return (
    <>
      <PageHeader
        title="Compliance"
        subtitle="Regulatory answers grounded in the indexed corpus, with provenance on every citation"
      />

      <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="min-h-[460px]">
          <CompliancePanel />
        </div>

        <Panel title="Regulation corpus">
          <ul className="divide-y divide-ink-600">
            {CORPUS.map((c) => (
              <li key={c.standard} className="px-4 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[12px] text-slate-200">{c.standard}</p>
                    <p className="text-[10.5px] text-slate-500">{c.issuer}</p>
                  </div>
                  <span
                    className={`chip shrink-0 ${
                      c.official
                        ? 'border border-emerald-500/30 bg-emerald-500/15 text-emerald-300'
                        : 'border border-amber-500/30 bg-amber-500/15 text-amber-300'
                    }`}
                  >
                    {c.provenance.replace('_', ' ').toLowerCase()}
                  </span>
                </div>
                <p className="mt-1.5 text-[10.5px] leading-snug text-slate-500">{c.detail}</p>
              </li>
            ))}
          </ul>

          <div className="border-t border-ink-600 p-4">
            <p className="text-[10.5px] leading-snug text-slate-500">
              The assistant answers only from retrieved passages. When no passage is
              relevant it declines rather than drawing on model memory — a confidently
              wrong regulatory answer is worse than none. Licensed standards are never
              committed to version control.
            </p>
          </div>
        </Panel>
      </div>
    </>
  )
}
