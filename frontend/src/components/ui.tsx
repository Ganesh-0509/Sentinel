import type { ReactNode } from 'react'
import type { Kpi } from '../types'

export function PageHeader({ title, subtitle, actions }: {
  title: string; subtitle?: string; actions?: ReactNode
}) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-base font-semibold text-slate-100">{title}</h1>
        {subtitle && <p className="mt-0.5 text-[11.5px] text-slate-500">{subtitle}</p>}
      </div>
      {actions}
    </div>
  )
}

export function Panel({ title, meta, children, className = '' }: {
  title?: string; meta?: ReactNode; children: ReactNode; className?: string
}) {
  return (
    <section className={`panel flex min-w-0 flex-col ${className}`}>
      {title && (
        <div className="panel-header">
          <h2 className="panel-title">{title}</h2>
          {meta}
        </div>
      )}
      <div className="min-w-0 flex-1">{children}</div>
    </section>
  )
}

const STATE_RING: Record<Kpi['state'], string> = {
  ok: 'border-ink-600',
  warn: 'border-amber-500/40',
  critical: 'border-red-500/40',
}

const STATE_TEXT: Record<Kpi['state'], string> = {
  ok: 'text-slate-100',
  warn: 'text-amber-300',
  critical: 'text-red-300',
}

export function KpiCard({ kpi }: { kpi: Kpi }) {
  return (
    <div className={`rounded-lg border bg-ink-800/80 p-3 ${STATE_RING[kpi.state]}`}>
      <div className="flex items-start justify-between gap-2">
        <p className="text-[10px] uppercase tracking-wide text-slate-500">{kpi.label}</p>
        <span
          className={`chip shrink-0 ${
            kpi.kind === 'leading'
              ? 'border border-sky-500/30 bg-sky-500/10 text-sky-300'
              : 'border border-slate-500/30 bg-slate-500/10 text-slate-400'
          }`}
        >
          {kpi.kind}
        </span>
      </div>
      <p className={`stat mt-1 text-xl ${STATE_TEXT[kpi.state]}`}>
        {kpi.value}
        <span className="ml-1 text-[11px] text-slate-500">{kpi.unit}</span>
      </p>
      <p className="mt-1 text-[10.5px] leading-snug text-slate-500">{kpi.hint}</p>
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="px-4 py-8 text-center text-[11px] text-slate-500">{children}</p>
}

export function Bar({ value, max = 1, tone = 'sky' }: {
  value: number; max?: number; tone?: 'sky' | 'red' | 'emerald' | 'amber'
}) {
  const tones = {
    sky: 'bg-sky-400', red: 'bg-red-400',
    emerald: 'bg-emerald-400', amber: 'bg-amber-400',
  }
  const pct = Math.max(Math.min((value / max) * 100, 100), 2)
  return (
    <div className="h-1.5 w-full rounded bg-ink-600">
      <div className={`h-1.5 rounded ${tones[tone]}`} style={{ width: `${pct}%` }} />
    </div>
  )
}
