import { NavLink, Outlet } from 'react-router-dom'
import { usePlant } from '../state/PlantContext'

const NAV = [
  { to: '/', label: 'Overview', end: true, glyph: '◱' },
  { to: '/map', label: 'Plant Map', glyph: '◈' },
  { to: '/zones', label: 'Zones', glyph: '▤' },
  { to: '/alerts', label: 'Alerts', glyph: '▲' },
  { to: '/analytics', label: 'Analytics', glyph: '◴' },
  { to: '/incidents', label: 'Incident Patterns', glyph: '◉' },
  { to: '/permits', label: 'Permits', glyph: '▦' },
  { to: '/compliance', label: 'Compliance', glyph: '§' },
  { to: '/evidence', label: 'Model Evidence', glyph: '◎' },
]

export function Layout() {
  const { health, minute, live, setLive, setMinute, error, alerts } = usePlant()
  const critical = alerts.filter((a) => a.priority === 'CRITICAL').length

  return (
    <div className="flex min-h-full">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <aside className="flex w-56 shrink-0 flex-col border-r border-ink-600 bg-ink-800/60">
        <div className="border-b border-ink-600 px-4 py-4">
          <p className="text-sm font-semibold tracking-wide text-slate-100">
            SENTINEL<span className="text-sky-400">AI</span>
          </p>
          <p className="mt-0.5 text-[10px] leading-tight text-slate-500">
            Compound Safety Intelligence
          </p>
        </div>

        <nav className="flex-1 space-y-0.5 p-2">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `flex items-center justify-between rounded px-3 py-2 text-[12px] transition ${
                  isActive
                    ? 'bg-sky-500/15 text-sky-200'
                    : 'text-slate-400 hover:bg-ink-700/60 hover:text-slate-200'
                }`
              }
            >
              <span className="flex items-center gap-2.5">
                <span className="w-3 text-center text-slate-500">{n.glyph}</span>
                {n.label}
              </span>
              {n.to === '/alerts' && critical > 0 && (
                <span
                  className="rounded bg-red-500/20 px-1.5 text-[10px] font-semibold text-red-300"
                  aria-live="polite"
                  aria-label={`${critical} critical alerts`}
                >
                  {critical}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-ink-600 p-3 text-[10px] text-slate-500">
          <div className="flex items-center gap-1.5">
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                !error && health?.status === 'ok' ? 'bg-emerald-400' : 'bg-red-400'
              }`}
            />
            {!error && health ? `${health.llm_backend} · v${health.version}` : 'offline'}
          </div>
          <p className="mt-1 leading-snug">
            {health?.regulation_chunks ?? 0} regulation passages indexed
          </p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-4 border-b border-ink-600 bg-ink-800/40 px-5 py-2.5">
          <div className="flex items-center gap-2 text-[11px] text-slate-500">
            <span className="rounded border border-ink-600 px-2 py-0.5 font-mono text-slate-300">
              Visakhapatnam Works
            </span>
            <span>simulated plant feed</span>
          </div>

          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-[11px] text-slate-400">
              <span className="stat w-12 text-right text-slate-200">T+{minute}m</span>
              <input
                type="range"
                min={0}
                max={239}
                value={minute}
                onChange={(e) => setMinute(Number(e.target.value))}
                className="w-44 accent-sky-500"
                aria-label="Scrub plant timeline"
              />
            </label>
            <button
              onClick={() => setLive(!live)}
              className={`rounded px-3 py-1 text-[11px] font-medium transition ${
                live
                  ? 'bg-red-600 text-white hover:bg-red-500'
                  : 'bg-emerald-600 text-white hover:bg-emerald-500'
              }`}
            >
              {live ? '■ Pause' : '▶ Live'}
            </button>
          </div>
        </header>

        {error && (
          <div className="border-b border-red-500/30 bg-red-500/10 px-5 py-1.5 text-[11px] text-red-200">
            {error} — is the API running on :8000?
          </div>
        )}

        <main id="main" className="min-w-0 flex-1 overflow-x-hidden p-4">
          <Outlet />
        </main>

        <footer className="border-t border-ink-600 px-5 py-2 text-[10px] text-slate-600">
          Decision-support only. Deterministic gas and oxygen interlocks hold veto
          authority; the model may escalate or reject work but never approves work the
          interlocks rejected.
        </footer>
      </div>
    </div>
  )
}
