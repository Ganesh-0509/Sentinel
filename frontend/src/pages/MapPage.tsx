import { useNavigate } from 'react-router-dom'
import { PlantMap } from '../components/PlantMap'
import { PageHeader, Panel } from '../components/ui'
import { bandBadge } from '../lib/risk'
import { usePlant } from '../state/PlantContext'

export function MapPage() {
  const { zones } = usePlant()
  const navigate = useNavigate()

  const exposed = zones
    .filter((z) => z.risk >= 0.6)
    .reduce((sum, z) => sum + z.workers_in_zone, 0)

  return (
    <>
      <PageHeader
        title="Plant Map"
        subtitle="Geospatial risk with worker exposure and active hazardous work overlaid on the floor plan"
      />

      <div className="grid gap-3 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <PlantMap zones={zones} selected={null} onSelect={(id) => navigate(`/zones/${id}`)} />

        <div className="flex flex-col gap-3">
          <Panel title="Exposure summary">
            <div className="grid grid-cols-2 gap-px bg-ink-600">
              <Cell label="Workers in high-risk zones" value={exposed}
                    tone={exposed ? 'red' : 'ok'} />
              <Cell label="Zones with hot work"
                    value={zones.filter((z) => z.hot_work_active).length} tone="amber" />
              <Cell label="Zones under maintenance"
                    value={zones.filter((z) => z.maintenance_active).length} tone="amber" />
              <Cell label="Zones in shift changeover"
                    value={zones.filter((z) => z.in_changeover).length} tone="ok" />
            </div>
          </Panel>

          <Panel title="Zones by risk" className="flex-1">
            <ul className="divide-y divide-ink-600">
              {[...zones]
                .sort((a, b) => b.risk - a.risk)
                .map((z) => (
                  <li key={z.zone_id}>
                    <button
                      onClick={() => navigate(`/zones/${z.zone_id}`)}
                      className="flex w-full items-center justify-between gap-3 px-4 py-2 text-left transition hover:bg-ink-700/40"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-[11.5px] text-slate-200">{z.name}</p>
                        <p className="text-[10px] text-slate-600">
                          {z.workers_in_zone} workers · {z.gas_lel.toFixed(1)} %LEL
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <span className="stat text-[11px] text-slate-300">
                          {(z.risk * 100).toFixed(0)}%
                        </span>
                        <span className={`chip ${bandBadge[z.risk_band]}`}>
                          {z.risk_band}
                        </span>
                      </div>
                    </button>
                  </li>
                ))}
            </ul>
          </Panel>
        </div>
      </div>
    </>
  )
}

function Cell({ label, value, tone }: {
  label: string; value: number; tone: 'ok' | 'amber' | 'red'
}) {
  const tones = { ok: 'text-slate-200', amber: 'text-amber-300', red: 'text-red-300' }
  return (
    <div className="bg-ink-800 px-3 py-2.5">
      <p className="text-[10px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`stat mt-0.5 text-lg ${tones[tone]}`}>{value}</p>
    </div>
  )
}
