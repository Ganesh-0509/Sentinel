import type { ZoneState } from '../types'
import { riskFill, riskHex } from '../lib/risk'

interface Props {
  zones: ZoneState[]
  selected: string | null
  onSelect: (zoneId: string) => void
}

/**
 * Geospatial risk heatmap over the plant floor plan.
 *
 * Encodes four things at once, which is the point of the geospatial layer:
 *   position  -> where in the plant
 *   colour    -> compound risk band
 *   halo size -> workers exposed (consequence, not probability)
 *   markers   -> active hot work / maintenance, and whether a conventional
 *                single-sensor alarm would be firing at all
 */
export function PlantMap({ zones, selected, onSelect }: Props) {
  return (
    <div className="panel h-full">
      <div className="panel-header">
        <h2 className="panel-title">Plant Risk Heatmap</h2>
        <Legend />
      </div>

      <div className="p-3">
        <svg
          viewBox="0 0 100 100"
          className="h-[420px] w-full"
          role="img"
          aria-label="Plant floor plan showing compound risk by zone"
        >
          <defs>
            <pattern id="grid" width="5" height="5" patternUnits="userSpaceOnUse">
              <path d="M 5 0 L 0 0 0 5" fill="none" stroke="#1c2534" strokeWidth="0.3" />
            </pattern>
            {(['low', 'medium', 'high', 'critical'] as const).map((band) => (
              <radialGradient id={`glow-${band}`} key={band}>
                <stop offset="0%" stopColor={riskHex[band]} stopOpacity="0.55" />
                <stop offset="100%" stopColor={riskHex[band]} stopOpacity="0" />
              </radialGradient>
            ))}
          </defs>

          <rect width="100" height="100" fill="url(#grid)" />

          {/* static plant structures for spatial context */}
          <g stroke="#2a3548" fill="#141c28" strokeWidth="0.4">
            <rect x="8" y="12" width="46" height="24" rx="1" />
            <rect x="58" y="12" width="34" height="24" rx="1" />
            <rect x="10" y="46" width="44" height="28" rx="1" />
            <rect x="60" y="46" width="32" height="28" rx="1" />
            <rect x="16" y="78" width="40" height="16" rx="1" />
          </g>
          <g fill="#41506b" fontSize="2.4" fontFamily="ui-monospace, monospace">
            <text x="10" y="10.5">COKE OVEN AREA</text>
            <text x="60" y="10.5">BY-PRODUCT / GAS</text>
            <text x="12" y="44.5">SINTER / FURNACE</text>
            <text x="62" y="44.5">POWER</text>
            <text x="18" y="76.5">TANK FARM</text>
          </g>

          {zones.map((z) => {
            const band = z.risk_band.toLowerCase() as keyof typeof riskHex
            const isSel = selected === z.zone_id
            const exposure = 3.2 + Math.min(z.workers_in_zone, 10) * 0.42
            return (
              <g
                key={z.zone_id}
                onClick={() => onSelect(z.zone_id)}
                onKeyDown={(e) => e.key === 'Enter' && onSelect(z.zone_id)}
                tabIndex={0}
                role="button"
                aria-label={`${z.name}: risk ${(z.risk * 100).toFixed(0)} percent, ${z.risk_band}, ${z.workers_in_zone} workers`}
                className="cursor-pointer focus:outline-none"
              >
                <circle cx={z.x} cy={z.y} r={exposure * 2.4} fill={`url(#glow-${band})`} />
                {z.risk_band === 'CRITICAL' && (
                  <circle
                    cx={z.x}
                    cy={z.y}
                    r={exposure}
                    fill="none"
                    stroke={riskHex.critical}
                    strokeWidth="0.5"
                    className="origin-center animate-pulseRing"
                    style={{ transformBox: 'fill-box', transformOrigin: 'center' }}
                  />
                )}
                <circle
                  cx={z.x}
                  cy={z.y}
                  r={exposure}
                  fill={riskHex[band]}
                  fillOpacity={0.9}
                  stroke={isSel ? '#e2e8f0' : '#0a0e14'}
                  strokeWidth={isSel ? 0.9 : 0.4}
                />
                <text
                  x={z.x}
                  y={z.y + 0.9}
                  textAnchor="middle"
                  fontSize="2.4"
                  fontFamily="ui-monospace, monospace"
                  fill="#0a0e14"
                  fontWeight="700"
                >
                  {z.workers_in_zone}
                </text>

                {/* hazard markers */}
                <g fontSize="3">
                  {z.hot_work_active && <text x={z.x + exposure + 0.6} y={z.y - 1.4}>🔥</text>}
                  {z.maintenance_active && (
                    <text x={z.x + exposure + 0.6} y={z.y + 2.6}>🔧</text>
                  )}
                </g>

                <text
                  x={z.x}
                  y={z.y + exposure + 3.4}
                  textAnchor="middle"
                  fontSize="2.5"
                  fontFamily="ui-monospace, monospace"
                  fill={isSel ? '#e2e8f0' : '#94a3b8'}
                >
                  {z.zone_id}
                </text>

                {/* the contrast that sells the product */}
                {z.risk >= 0.6 && !z.baseline_alarm && (
                  <text
                    x={z.x}
                    y={z.y - exposure - 1.6}
                    textAnchor="middle"
                    fontSize="2.2"
                    fontFamily="ui-monospace, monospace"
                    fill="#fbbf24"
                  >
                    single sensor silent
                  </text>
                )}
              </g>
            )
          })}
        </svg>
      </div>
    </div>
  )
}

function Legend() {
  return (
    <div className="flex items-center gap-3 text-[11.5px] text-slate-400">
      {(['low', 'medium', 'high', 'critical'] as const).map((b) => (
        <span key={b} className="flex items-center gap-1">
          <span className={`h-2 w-2 rounded-full ${riskFill[b]}`} />
          {b}
        </span>
      ))}
      <span className="ml-1 border-l border-ink-600 pl-3">◯ size = workers exposed</span>
    </div>
  )
}
