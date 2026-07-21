import { useEffect, useState } from 'react'
import { api } from '../api'
import { Empty, PageHeader, Panel } from '../components/ui'
import { usePlant } from '../state/PlantContext'
import type { BlastRadius, GraphSnapshot, PermitToSuspend } from '../types'

const KIND_COLOR: Record<string, string> = {
  Plant: '#64748b',
  Zone: '#38bdf8',
  Sensor: '#22c55e',
  Permit: '#f97316',
  Hazard: '#ef4444',
  Worker: '#eab308',
  Regulation: '#a78bfa',
}

export function Graph() {
  const { zones, minute } = usePlant()
  const [snapshot, setSnapshot] = useState<GraphSnapshot | null>(null)
  const [selected, setSelected] = useState<string>('')
  const [radius, setRadius] = useState<BlastRadius | null>(null)
  const [permits, setPermits] = useState<PermitToSuspend[]>([])

  const zoneId = selected || zones.find((z) => z.risk >= 0.6)?.zone_id || zones[0]?.zone_id

  useEffect(() => {
    api.graph().then(setSnapshot).catch(() => setSnapshot(null))
  }, [minute])

  useEffect(() => {
    if (!zoneId) return
    api.blastRadius(zoneId).then(setRadius).catch(() => setRadius(null))
    api.permitsToSuspend(zoneId).then(setPermits).catch(() => setPermits([]))
  }, [zoneId, minute])

  return (
    <>
      <PageHeader
        title="Knowledge Graph"
        subtitle="Equipment, permits, hazards and regulations as a connected model — so exposure can be traced, not just displayed"
        actions={
          <label className="flex items-center gap-2 text-[13px] text-slate-400">
            Trace from
            <select
              value={zoneId ?? ''}
              onChange={(e) => setSelected(e.target.value)}
              className="rounded border border-ink-600 bg-ink-900 px-2.5 py-1.5 text-[13px] text-slate-200"
            >
              {zones.map((z) => (
                <option key={z.zone_id} value={z.zone_id}>{z.name}</option>
              ))}
            </select>
          </label>
        }
      />

      {radius && (
        <div className="mb-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-5">
          <div className="flex flex-wrap items-baseline gap-x-8 gap-y-3">
            <div>
              <p className="text-[12px] uppercase tracking-wide text-slate-400">
                Workers in {radius.origin_zone}
              </p>
              <p className="stat text-3xl text-slate-200">{radius.origin_workers}</p>
            </div>
            <div className="text-2xl text-slate-600">→</div>
            <div>
              <p className="text-[12px] uppercase tracking-wide text-amber-300">
                Actually at risk across connected zones
              </p>
              <p className="stat text-3xl text-amber-300">
                {radius.total_workers_at_risk}
              </p>
            </div>
          </div>
          <p className="mt-3 max-w-3xl text-[14px] leading-relaxed text-slate-400">
            Gas travels along shared headers and into adjacent areas, so exposure is the
            reachable set — not the zone. A per-zone dashboard reports{' '}
            {radius.origin_workers}; the graph traces{' '}
            <span className="text-amber-300">{radius.total_workers_at_risk}</span>.
            {radius.ignition_sources_in_radius.length > 0 && (
              <>
                {' '}There {radius.ignition_sources_in_radius.length === 1 ? 'is' : 'are'}{' '}
                <span className="text-red-300">
                  {radius.ignition_sources_in_radius.length} active ignition source
                  {radius.ignition_sources_in_radius.length === 1 ? '' : 's'}
                </span>{' '}
                inside that radius ({radius.ignition_sources_in_radius.join(', ')}).
              </>
            )}
          </p>
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <Panel
          title="Graph structure"
          meta={
            snapshot && (
              <span className="text-[12px] text-slate-500">
                {snapshot.nodes.length} nodes · {snapshot.edges.length} edges
              </span>
            )
          }
        >
          {!snapshot ? (
            <Empty>Graph unavailable.</Empty>
          ) : (
            <div className="p-4">
              <div className="mb-4 flex flex-wrap gap-2">
                {Object.entries(snapshot.counts).map(([kind, n]) => (
                  <span
                    key={kind}
                    className="inline-flex items-center gap-2 rounded border border-ink-600 bg-ink-700/50 px-2.5 py-1 text-[13px] text-slate-300"
                  >
                    <span
                      className="h-2.5 w-2.5 rounded-full"
                      style={{ background: KIND_COLOR[kind] ?? '#64748b' }}
                    />
                    {kind}
                    <span className="text-slate-500">{n}</span>
                  </span>
                ))}
              </div>
              <GraphView snapshot={snapshot} highlight={zoneId} radius={radius} />
            </div>
          )}
        </Panel>

        <div className="flex flex-col gap-4">
          <Panel title="Connected zones">
            {!radius || radius.connected_zones.length === 0 ? (
              <Empty>No connected zones within range.</Empty>
            ) : (
              <ul className="divide-y divide-ink-600">
                {radius.connected_zones.map((c) => (
                  <li
                    key={c.zone_id}
                    className="flex items-center justify-between gap-3 px-4 py-3"
                  >
                    <div className="min-w-0">
                      <p className="text-[14px] text-slate-200">{c.zone}</p>
                      <p className="text-[12.5px] text-slate-500">
                        {c.hops} hop{c.hops === 1 ? '' : 's'} away · {c.workers} worker
                        {c.workers === 1 ? '' : 's'}
                      </p>
                    </div>
                    {c.hot_work_active && (
                      <span className="chip shrink-0 border border-red-500/30 bg-red-500/15 text-red-300">
                        ignition source
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel title="Permits requiring review">
            {permits.length === 0 ? (
              <Empty>No active permits in the traced radius.</Empty>
            ) : (
              <ul className="divide-y divide-ink-600">
                {permits.map((p) => (
                  <li key={p.permit_id} className="px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-[14px] text-slate-200">{p.permit_type}</p>
                        <p className="text-[12.5px] text-slate-500">
                          {p.zone} ·{' '}
                          {p.hops_from_origin === 0
                            ? 'origin zone'
                            : `${p.hops_from_origin} hop${p.hops_from_origin === 1 ? '' : 's'} away`}
                        </p>
                      </div>
                      {p.is_ignition_source && (
                        <span className="chip shrink-0 border border-red-500/30 bg-red-500/15 text-red-300">
                          suspend first
                        </span>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
            <p className="border-t border-ink-600 px-4 py-3 text-[12.5px] leading-relaxed text-slate-500">
              Includes permits in connected zones. The permit that kills you is often not
              in the zone that leaked.
            </p>
          </Panel>
        </div>
      </div>
    </>
  )
}

/** Zones are laid out on their real floor-plan coordinates; attached entities orbit them. */
function GraphView({ snapshot, highlight, radius }: {
  snapshot: GraphSnapshot
  highlight?: string
  radius: BlastRadius | null
}) {
  const pos = new Map<string, { x: number; y: number }>()
  const zoneNodes = snapshot.nodes.filter((n) => n.kind === 'Zone')

  zoneNodes.forEach((n) => {
    pos.set(n.id, { x: Number(n.attrs.x ?? 50), y: Number(n.attrs.y ?? 50) })
  })
  pos.set('PLANT', { x: 50, y: 50 })

  // orbit non-zone nodes around the zone they attach to
  const attachment = new Map<string, string>()
  snapshot.edges.forEach((e) => {
    if (pos.has(e.source) && !pos.has(e.target)) attachment.set(e.target, e.source)
  })
  const orbitCount = new Map<string, number>()
  snapshot.nodes.forEach((n) => {
    if (pos.has(n.id)) return
    const anchor = attachment.get(n.id)
    const base = anchor ? pos.get(anchor) : undefined
    if (!base) return
    const k = orbitCount.get(anchor!) ?? 0
    orbitCount.set(anchor!, k + 1)
    const angle = (k * 2 * Math.PI) / 5 - Math.PI / 4
    pos.set(n.id, { x: base.x + Math.cos(angle) * 7, y: base.y + Math.sin(angle) * 7 })
  })

  const inRadius = new Set(radius?.connected_zones.map((c) => c.zone_id) ?? [])

  return (
    <svg viewBox="-6 -6 112 112" className="h-[440px] w-full" role="img"
         aria-label="Knowledge graph of zones, sensors, permits and regulations">
      {snapshot.edges.map((e, i) => {
        const a = pos.get(e.source)
        const b = pos.get(e.target)
        if (!a || !b) return null
        const isSpread = e.relation === 'CONNECTED_TO' || e.relation === 'ADJACENT_TO'
        const lit =
          isSpread &&
          (e.source === highlight || e.target === highlight ||
            inRadius.has(e.source) || inRadius.has(e.target))
        return (
          <line
            key={i}
            x1={a.x} y1={a.y} x2={b.x} y2={b.y}
            stroke={lit ? '#f59e0b' : isSpread ? '#334155' : '#1e293b'}
            strokeWidth={lit ? 0.7 : isSpread ? 0.4 : 0.22}
            strokeDasharray={e.relation === 'ADJACENT_TO' ? '1 1' : undefined}
          />
        )
      })}

      {snapshot.nodes.map((n) => {
        const p = pos.get(n.id)
        if (!p) return null
        const isZone = n.kind === 'Zone'
        const isOrigin = n.id === highlight
        const r = isZone ? (isOrigin ? 3.4 : 2.6) : 1.3
        return (
          <g key={n.id}>
            {isOrigin && (
              <circle cx={p.x} cy={p.y} r={r + 2.2} fill="none"
                      stroke="#f59e0b" strokeWidth="0.5" />
            )}
            <circle
              cx={p.x} cy={p.y} r={r}
              fill={KIND_COLOR[n.kind] ?? '#64748b'}
              fillOpacity={isZone ? 0.95 : 0.75}
              stroke="#0a0e14" strokeWidth="0.3"
            />
            {isZone && (
              <text
                x={p.x} y={p.y + r + 3}
                textAnchor="middle" fontSize="2.8"
                fontFamily="ui-monospace, monospace"
                fill={isOrigin ? '#fbbf24' : inRadius.has(n.id) ? '#e2e8f0' : '#64748b'}
              >
                {n.id}
              </text>
            )}
          </g>
        )
      })}
    </svg>
  )
}
