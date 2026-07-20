import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import { AgentPanel } from './components/AgentPanel'
import { AlertQueue } from './components/AlertQueue'
import { CompliancePanel } from './components/CompliancePanel'
import { PlantMap } from './components/PlantMap'
import { ScoreboardPanel } from './components/ScoreboardPanel'
import { ZoneDetail } from './components/ZoneDetail'
import type { AlertItem, Health, Scoreboard, ZoneReading, ZoneState } from './types'

const POLL_MS = 1500

export default function App() {
  const [zones, setZones] = useState<ZoneState[]>([])
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [history, setHistory] = useState<ZoneReading[]>([])
  const [health, setHealth] = useState<Health | null>(null)
  const [board, setBoard] = useState<Scoreboard | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [minute, setMinute] = useState(0)
  const [live, setLive] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const selectedRef = useRef<string | null>(null)
  selectedRef.current = selected

  const refresh = useCallback(async () => {
    try {
      const [z, a, c] = await Promise.all([api.zones(), api.alerts(), api.clock()])
      setZones(z)
      setAlerts(a)
      setMinute(c.minute)
      setError(null)

      const sel = selectedRef.current ?? a[0]?.zone_id ?? z[0]?.zone_id ?? null
      if (sel !== selectedRef.current) setSelected(sel)
      if (sel) setHistory(await api.zoneHistory(sel))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'backend unreachable')
    }
  }, [])

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null))
    api.scoreboard().then(setBoard).catch(() => setBoard(null))
    refresh()
  }, [refresh])

  // live clock advance
  useEffect(() => {
    if (!live) return
    const id = setInterval(async () => {
      try {
        await api.tick(1)
        await refresh()
      } catch {
        /* surfaced by refresh */
      }
    }, POLL_MS)
    return () => clearInterval(id)
  }, [live, refresh])

  const zone = zones.find((z) => z.zone_id === selected) ?? null

  async function select(zoneId: string) {
    setSelected(zoneId)
    try {
      setHistory(await api.zoneHistory(zoneId))
    } catch {
      setHistory([])
    }
  }

  async function scrub(value: number) {
    await api.setClock(value)
    await refresh()
  }

  return (
    <div className="flex min-h-full flex-col">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-ink-600 bg-ink-800/70 px-5 py-3">
        <div className="flex items-baseline gap-3">
          <h1 className="text-sm font-semibold tracking-wide text-slate-100">
            SENTINEL<span className="text-sky-400">AI</span>
          </h1>
          <p className="hidden text-[11px] text-slate-500 sm:block">
            Compound Industrial Safety Intelligence
          </p>
        </div>

        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-[11px] text-slate-400">
            <span className="hidden sm:inline">T+</span>
            <span className="stat w-10 text-right text-slate-200">{minute}m</span>
            <input
              type="range"
              min={0}
              max={239}
              value={minute}
              onChange={(e) => scrub(Number(e.target.value))}
              className="w-40 accent-sky-500"
              aria-label="Scrub plant timeline"
            />
          </label>

          <button
            onClick={() => setLive((v) => !v)}
            className={`rounded px-3 py-1 text-[11px] font-medium transition ${
              live
                ? 'bg-red-600 text-white hover:bg-red-500'
                : 'bg-emerald-600 text-white hover:bg-emerald-500'
            }`}
          >
            {live ? '■ Pause' : '▶ Live'}
          </button>

          <StatusDot health={health} error={error} />
        </div>
      </header>

      {error && (
        <div className="border-b border-red-500/30 bg-red-500/10 px-5 py-1.5 text-[11px] text-red-200">
          {error} — is the API running on :8000?
        </div>
      )}

      <main className="grid flex-1 grid-cols-1 gap-3 p-3 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <div className="flex flex-col gap-3">
          <PlantMap zones={zones} selected={selected} onSelect={select} />
          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_320px]">
            <ZoneDetail zone={zone} history={history} />
            <AlertQueue alerts={alerts} selected={selected} onSelect={select} />
          </div>
        </div>

        <div className="flex flex-col gap-3">
          <ScoreboardPanel data={board} />
          <div className="min-h-[280px] flex-1">
            <AgentPanel zone={zone} />
          </div>
          <div className="min-h-[260px]">
            <CompliancePanel />
          </div>
        </div>
      </main>

      <footer className="border-t border-ink-600 px-5 py-2 text-[10px] text-slate-600">
        Decision-support only. Deterministic gas and oxygen interlocks hold veto authority;
        the model may escalate or reject work but never approves work the interlocks rejected.
      </footer>
    </div>
  )
}

function StatusDot({ health, error }: { health: Health | null; error: string | null }) {
  const ok = !error && health?.status === 'ok'
  return (
    <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
      <span
        className={`h-2 w-2 rounded-full ${ok ? 'bg-emerald-400' : 'bg-red-400'}`}
        aria-hidden
      />
      <span className="hidden sm:inline">
        {ok ? `${health?.llm_backend}` : 'offline'}
      </span>
    </div>
  )
}
