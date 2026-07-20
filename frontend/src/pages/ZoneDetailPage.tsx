import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { AgentPanel } from '../components/AgentPanel'
import { ZoneDetail } from '../components/ZoneDetail'
import { PageHeader } from '../components/ui'
import { usePlant } from '../state/PlantContext'
import type { ZoneReading } from '../types'

export function ZoneDetailPage() {
  const { zoneId } = useParams<{ zoneId: string }>()
  const { zones, minute } = usePlant()
  const [history, setHistory] = useState<ZoneReading[]>([])

  const zone = zones.find((z) => z.zone_id === zoneId) ?? null

  useEffect(() => {
    if (!zoneId) return
    api.zoneHistory(zoneId, 120).then(setHistory).catch(() => setHistory([]))
  }, [zoneId, minute])

  return (
    <>
      <PageHeader
        title={zone?.name ?? zoneId ?? 'Zone'}
        subtitle={`Zone ${zoneId} · live telemetry, model attribution and agent response`}
        actions={
          <Link
            to="/zones"
            className="rounded border border-ink-600 px-2.5 py-1 text-[11px] text-slate-400 hover:text-slate-200"
          >
            ← All zones
          </Link>
        }
      />

      <div className="grid gap-3 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
        <div className="min-h-[520px]">
          <ZoneDetail zone={zone} history={history} />
        </div>
        <div className="min-h-[520px]">
          <AgentPanel zone={zone} />
        </div>
      </div>
    </>
  )
}
