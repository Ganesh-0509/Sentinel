import type { AlertItem } from '../types'
import { bandBadge } from '../lib/risk'

interface Props {
  alerts: AlertItem[]
  selected: string | null
  onSelect: (zoneId: string) => void
}

export function AlertQueue({ alerts, selected, onSelect }: Props) {
  return (
    <div className="panel flex h-full flex-col">
      <div className="panel-header">
        <h2 className="panel-title">Alert Queue</h2>
        <span className="stat text-[13px] text-slate-500">
          {alerts.length} active
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {alerts.length === 0 && (
          <p className="px-2 py-6 text-center text-xs text-slate-500">
            No zone above alert threshold.
          </p>
        )}

        <ul className="space-y-1.5">
          {alerts.map((a) => (
            <li key={a.alert_id}>
              <button
                onClick={() => onSelect(a.zone_id)}
                className={`w-full rounded border px-3 py-2 text-left transition ${
                  selected === a.zone_id
                    ? 'border-sky-500/60 bg-sky-500/10'
                    : 'border-ink-600 bg-ink-700/50 hover:border-ink-500'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs font-semibold text-slate-200">
                    {a.zone_name}
                  </span>
                  <span className={`chip ${bandBadge[a.priority]}`}>{a.priority}</span>
                </div>

                <div className="mt-1 flex items-center gap-3 text-[13px] text-slate-400">
                  <span className="stat">
                    risk <span className="text-slate-200">{(a.risk * 100).toFixed(0)}%</span>
                  </span>
                  {a.lead_time_min !== null && (
                    <span className="stat text-amber-300">~{a.lead_time_min} min to threshold</span>
                  )}
                </div>

                {a.drivers.length > 0 && (
                  <p className="mt-1 line-clamp-2 text-[13px] leading-snug text-slate-500">
                    {a.drivers.join(' · ')}
                  </p>
                )}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
