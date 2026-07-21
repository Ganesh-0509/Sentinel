import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { ZoneReading, ZoneState } from '../types'
import { bandBadge } from '../lib/risk'

interface Props {
  zone: ZoneState | null
  history: ZoneReading[]
}

export function ZoneDetail({ zone, history }: Props) {
  if (!zone) {
    return (
      <div className="panel flex h-full items-center justify-center">
        <p className="text-xs text-slate-500">Select a zone to inspect.</p>
      </div>
    )
  }

  return (
    <div className="panel flex h-full flex-col">
      <div className="panel-header">
        <div className="flex items-center gap-2">
          <h2 className="panel-title">{zone.name}</h2>
          <span className={`chip ${bandBadge[zone.risk_band]}`}>{zone.risk_band}</span>
        </div>
        <div className="flex items-center gap-3 text-[13px]">
          <span className="stat text-slate-400">
            risk <span className="text-slate-100">{(zone.risk * 100).toFixed(1)}%</span>
          </span>
          {zone.lead_time_min !== null && (
            <span className="stat text-amber-300">~{zone.lead_time_min} min lead</span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-px border-b border-ink-600 bg-ink-600 sm:grid-cols-4">
        <Metric label="Gas (point)" value={`${zone.gas_lel.toFixed(1)} %LEL`}
                sub={`${zone.gas_trend >= 0 ? '+' : ''}${zone.gas_trend.toFixed(2)}/min`}
                alert={zone.gas_trend > 0.05} />
        <Metric label="Pressure" value={`${zone.pressure.toFixed(2)} bar`} />
        <Metric label="Temperature" value={`${zone.temperature.toFixed(1)} °C`} />
        <Metric label="Anomaly" value={zone.anomaly_score.toFixed(1)}
                alert={zone.anomaly_score >= 3} />
      </div>

      <div className="flex flex-wrap items-center gap-1.5 border-b border-ink-600 px-4 py-2">
        <Flag on={zone.hot_work_active} label="Hot work" tone="red" />
        <Flag on={zone.maintenance_active} label="Maintenance" tone="amber" />
        <Flag on={zone.in_changeover} label="Shift changeover" tone="amber" />
        <Flag on={zone.night_shift} label="Night shift" tone="slate" />
        <span className="chip border border-ink-500 bg-ink-700 text-slate-300">
          {zone.workers_in_zone} workers
        </span>
        <span
          className={`chip ${
            zone.baseline_alarm
              ? 'border border-orange-500/30 bg-orange-500/15 text-orange-300'
              : 'border border-ink-500 bg-ink-700 text-slate-400'
          }`}
        >
          single-sensor alarm: {zone.baseline_alarm ? 'firing' : 'silent'}
        </span>
      </div>

      <div className="px-2 pt-3">
        <ResponsiveContainer width="100%" height={150}>
          <AreaChart data={history} margin={{ top: 4, right: 10, left: -22, bottom: 0 }}>
            <defs>
              <linearGradient id="riskArea" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#ef4444" stopOpacity={0.45} />
                <stop offset="100%" stopColor="#ef4444" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#1c2534" vertical={false} />
            <XAxis dataKey="minute" stroke="#475569" fontSize={10} tickLine={false} />
            <YAxis yAxisId="l" stroke="#475569" fontSize={10} tickLine={false} domain={[0, 1]} />
            <YAxis yAxisId="r" orientation="right" stroke="#475569" fontSize={10}
                   tickLine={false} width={30} />
            <Tooltip
              contentStyle={{
                background: '#111722', border: '1px solid #222c3d',
                borderRadius: 6, fontSize: 11,
              }}
              labelStyle={{ color: '#94a3b8' }}
            />
            <Area yAxisId="l" type="monotone" dataKey="risk" stroke="#ef4444"
                  strokeWidth={2} fill="url(#riskArea)" name="compound risk"
                  isAnimationActive={false} />
            <Line yAxisId="r" type="monotone" dataKey="gas_lel" stroke="#64748b"
                  strokeWidth={1.5} dot={false} name="gas %LEL"
                  isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="flex-1 overflow-y-auto px-4 pb-3 pt-2">
        <h3 className="panel-title mb-2">Why — SHAP attribution</h3>
        {zone.drivers.length === 0 ? (
          <p className="text-[13px] text-slate-500">
            Risk below explanation threshold.
          </p>
        ) : (
          <ul className="space-y-1.5">
            {zone.drivers.map((d) => {
              const mag = Math.min(Math.abs(d.contribution) / 2, 1)
              return (
                <li key={d.feature} className="text-[13px]">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-slate-300">{d.label}</span>
                    <span
                      className={`stat ${
                        d.contribution > 0 ? 'text-red-300' : 'text-emerald-300'
                      }`}
                    >
                      {d.contribution > 0 ? '+' : ''}
                      {d.contribution.toFixed(2)}
                    </span>
                  </div>
                  <div className="mt-0.5 h-1 rounded bg-ink-600">
                    <div
                      className={`h-1 rounded ${
                        d.contribution > 0 ? 'bg-red-400' : 'bg-emerald-400'
                      }`}
                      style={{ width: `${Math.max(mag * 100, 4)}%` }}
                    />
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}

function Metric({ label, value, sub, alert }: {
  label: string; value: string; sub?: string; alert?: boolean
}) {
  return (
    <div className="bg-ink-800 px-3 py-2">
      <p className="text-[11.5px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`stat text-sm ${alert ? 'text-amber-300' : 'text-slate-100'}`}>{value}</p>
      {sub && <p className="stat text-[11.5px] text-slate-500">{sub}</p>}
    </div>
  )
}

function Flag({ on, label, tone }: {
  on: boolean; label: string; tone: 'red' | 'amber' | 'slate'
}) {
  if (!on) return null
  const tones = {
    red: 'border border-red-500/30 bg-red-500/15 text-red-300',
    amber: 'border border-amber-500/30 bg-amber-500/15 text-amber-300',
    slate: 'border border-ink-500 bg-ink-700 text-slate-300',
  }
  return <span className={`chip ${tones[tone]}`}>{label}</span>
}
