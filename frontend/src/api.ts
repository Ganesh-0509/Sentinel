import type {
  AlarmPerformance,
  AlertItem,
  BlastRadius,
  ComplianceAnswer,
  ContributingFactor,
  GraphSnapshot,
  PermitToSuspend,
  Health,
  IncidentRecord,
  KpiSummary,
  PatternSummary,
  PermitDecision,
  PermitType,
  PreventionPriority,
  RiskDistribution,
  Scoreboard,
  TierSummary,
  TrendPoint,
  WorkflowResult,
  ZoneReading,
  ZoneState,
} from './types'

const BASE = '/api/v1'

class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.title ?? body.detail ?? detail
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(detail, res.status)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<Health>('/health'),
  zones: () => request<ZoneState[]>('/zones'),
  zoneHistory: (id: string, window = 90) =>
    request<ZoneReading[]>(`/zones/${id}/history?window=${window}`),
  alerts: () => request<AlertItem[]>('/alerts'),
  clock: () => request<{ minute: number }>('/clock'),
  tick: (steps = 1) =>
    request<{ minute: number }>(`/clock/tick?steps=${steps}`, { method: 'POST' }),
  setClock: (minute: number) =>
    request<{ minute: number }>(`/clock/set?minute=${minute}`, { method: 'POST' }),
  evaluatePermit: (zoneId: string, permitType: PermitType, useAiRisk = true) =>
    request<PermitDecision>('/permits/evaluate', {
      method: 'POST',
      body: JSON.stringify({
        permit_type: permitType,
        zone_id: zoneId,
        machine_id: `${zoneId}-07`,
        use_ai_risk: useAiRisk,
      }),
    }),
  ask: (question: string) =>
    request<ComplianceAnswer>('/compliance/ask', {
      method: 'POST',
      body: JSON.stringify({ question, top_k: 4 }),
    }),
  runWorkflow: (zoneId: string) =>
    request<WorkflowResult>(`/workflow/run/${zoneId}`, { method: 'POST' }),
  scoreboard: () => request<Scoreboard>('/evaluation/scoreboard'),

  // analytics
  kpis: () => request<KpiSummary>('/analytics/kpis'),
  tiers: () => request<TierSummary>('/analytics/tiers'),
  alarmPerformance: () => request<AlarmPerformance>('/analytics/alarm-performance'),
  riskDistribution: () => request<RiskDistribution>('/analytics/risk-distribution'),
  trend: (window = 120) => request<TrendPoint[]>(`/analytics/trend?window=${window}`),
  contributingFactors: (top = 10) =>
    request<ContributingFactor[]>(`/analytics/contributing-factors?top=${top}`),

  // incident intelligence
  patterns: () => request<PatternSummary>('/incidents/patterns'),
  priorities: () => request<PreventionPriority[]>('/incidents/priorities'),
  incidentRecords: (outcome?: 'INCIDENT' | 'NEAR_MISS', limit = 40) =>
    request<IncidentRecord[]>(
      `/incidents/records?limit=${limit}${outcome ? `&outcome=${outcome}` : ''}`,
    ),

  // knowledge graph
  graph: () => request<GraphSnapshot>('/graph'),
  blastRadius: (zoneId: string, maxHops = 2) =>
    request<BlastRadius>(`/graph/blast-radius/${zoneId}?max_hops=${maxHops}`),
  permitsToSuspend: (zoneId: string, maxHops = 2) =>
    request<PermitToSuspend[]>(`/graph/permits-to-suspend/${zoneId}?max_hops=${maxHops}`),
}

export { ApiError }
