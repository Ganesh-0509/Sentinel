import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api } from '../api'
import type { AlertItem, Health, ZoneState } from '../types'

const POLL_MS = 2000

interface PlantContextValue {
  zones: ZoneState[]
  alerts: AlertItem[]
  health: Health | null
  minute: number
  live: boolean
  error: string | null
  setLive: (v: boolean) => void
  setMinute: (m: number) => Promise<void>
  refresh: () => Promise<void>
}

const PlantContext = createContext<PlantContextValue | null>(null)

export function PlantProvider({ children }: { children: ReactNode }) {
  const [zones, setZones] = useState<ZoneState[]>([])
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [health, setHealth] = useState<Health | null>(null)
  const [minute, setMinuteState] = useState(0)
  const [live, setLive] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [z, a, c] = await Promise.all([api.zones(), api.alerts(), api.clock()])
      setZones(z)
      setAlerts(a)
      setMinuteState(c.minute)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'backend unreachable')
    }
  }, [])

  const setMinute = useCallback(
    async (m: number) => {
      await api.setClock(m)
      await refresh()
    },
    [refresh],
  )

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null))
    refresh()
  }, [refresh])

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

  const value = useMemo(
    () => ({ zones, alerts, health, minute, live, error, setLive, setMinute, refresh }),
    [zones, alerts, health, minute, live, error, setMinute, refresh],
  )

  return <PlantContext.Provider value={value}>{children}</PlantContext.Provider>
}

export function usePlant() {
  const ctx = useContext(PlantContext)
  if (!ctx) throw new Error('usePlant must be used inside PlantProvider')
  return ctx
}
