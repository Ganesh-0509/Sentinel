export type RiskBand = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
export type Priority = RiskBand
export type PermitStatus = 'APPROVED' | 'CONDITIONAL' | 'REJECTED'
export type PermitType = 'Hot Work' | 'Confined Space' | 'Cold Work' | 'Electrical'

export interface ShapDriver {
  feature: string
  label: string
  contribution: number
}

export interface ZoneState {
  zone_id: string
  name: string
  x: number
  y: number
  risk: number
  risk_band: RiskBand
  gas_lel: number
  gas_trend: number
  pressure: number
  temperature: number
  anomaly_score: number
  workers_in_zone: number
  maintenance_active: boolean
  hot_work_active: boolean
  night_shift: boolean
  in_changeover: boolean
  lead_time_min: number | null
  baseline_alarm: boolean
  drivers: ShapDriver[]
}

export interface ZoneReading {
  minute: number
  gas_lel: number
  pressure: number
  temperature: number
  vibration: number
  risk: number
}

export interface AlertItem {
  alert_id: string
  zone_id: string
  zone_name: string
  priority: Priority
  score: number
  risk: number
  lead_time_min: number | null
  drivers: string[]
  raised_at: string
}

export interface PermitDecision {
  status: PermitStatus
  reasons: string[]
  citations: string[]
}

export interface Citation {
  standard: string
  section: string
  provenance: 'STATUTE' | 'OFFICIAL' | 'SUMMARY' | 'REFERENCE_ONLY'
  is_official: boolean
  score: number
}

export interface ComplianceAnswer {
  question: string
  answer: string
  citations: Citation[]
  backend: string
  grounded: boolean
}

export interface WorkflowResult {
  zone_id: string
  trace: string[]
  priority: Priority | null
  permit_decision: PermitDecision | null
  interlocks: string[]
  compliance: ComplianceAnswer | null
  actions: string[]
  report: string | null
}

export interface Scoreboard {
  n_episodes: number
  n_incident_episodes: number
  n_safe_episodes: number
  baseline_detection_rate: number
  compound_detection_rate: number
  baseline_false_negative_rate: number
  compound_false_negative_rate: number
  baseline_false_alarm_rate: number
  compound_false_alarm_rate: number
  matched_baseline_lead_min: number | null
  matched_compound_lead_min: number | null
  incidents_missed_by_baseline_caught_by_compound: number
}

export interface Kpi {
  key: string
  label: string
  value: number
  unit: string
  kind: 'leading' | 'lagging'
  hint: string
  state: 'ok' | 'warn' | 'critical'
}

export interface KpiSummary {
  kpis: Kpi[]
  leading_count: number
  lagging_count: number
  leading_to_lagging_ratio: number
  ratio_target: number
  ratio_ok: boolean
}

export interface TierEvent {
  zone_id: string
  zone: string
  event: string
  detail: string
}

export interface Tier {
  tier: number
  name: string
  kind: 'leading' | 'lagging'
  external_reporting: boolean
  count: number
  events: TierEvent[]
}

export interface TierSummary {
  framework: string
  tiers: Tier[]
  leading_events: number
  lagging_events: number
  note: string
}

export interface AlarmSystem {
  system: string
  alarm_minutes: number
  false_alarm_rate: number
  alarms_per_zone_hour: number
  alarms_per_operator_hour: number
  band: 'TARGET' | 'ACCEPTABLE' | 'OVER_TARGET' | 'SERIOUSLY_DEFICIENT'
  within_eemua_target: boolean
}

export interface AlarmPerformance {
  available: boolean
  framework?: string
  benchmarks?: {
    target_per_hour: number
    seriously_deficient_per_hour: number
    peak_per_10min: number
  }
  systems?: AlarmSystem[]
  nuisance_reduction_pct?: number
  monitored_points?: number
  projection_note?: string
}

export interface RiskDistribution {
  bands: { band: RiskBand; count: number }[]
  by_zone: {
    zone_id: string
    zone: string
    risk: number
    band: RiskBand
    workers: number
  }[]
}

export interface TrendPoint {
  minute: number
  max_risk: number
  mean_risk: number
  zones_at_risk: number
}

export interface ContributingFactor {
  feature: string
  label: string
  group: string
  importance: number
  share: number
}

export interface PrecursorPattern {
  conditions: string[]
  label: string
  occurrences: number
  incidents: number
  near_misses: number
  confidence: number
  lift: number
  single_sensor_missed: number
}

export interface PatternSummary {
  n_records: number
  n_incidents: number
  n_near_misses: number
  base_incident_rate: number
  min_support_count: number
  patterns: PrecursorPattern[]
  method: string
}

export interface PreventionPriority {
  pattern: string
  lift: number
  occurrences: number
  incidents: number
  single_sensor_missed: number
  actions: string[]
}

export interface IncidentRecord {
  record_id: string
  outcome: 'INCIDENT' | 'NEAR_MISS'
  incident_type: string
  zone: string
  minute_of_event: number
  severity: string
  narrative: string
  detected_by_single_sensor: boolean
}

export interface GraphNodeT {
  id: string
  kind: string
  label: string
  attrs: Record<string, unknown>
}

export interface GraphEdgeT {
  source: string
  target: string
  relation: string
  attrs: Record<string, unknown>
}

export interface GraphSnapshot {
  nodes: GraphNodeT[]
  edges: GraphEdgeT[]
  counts: Record<string, number>
}

export interface ConnectedZone {
  zone_id: string
  zone: string
  hops: number
  workers: number
  hot_work_active: boolean
  risk: number
}

export interface BlastRadius {
  origin: string
  origin_zone: string
  origin_workers: number
  connected_zones: ConnectedZone[]
  total_workers_at_risk: number
  ignition_sources_in_radius: string[]
}

export interface PermitToSuspend {
  permit_id: string
  permit_type: string
  zone_id: string
  zone: string
  hops_from_origin: number
  is_ignition_source: boolean
}

export interface Health {
  status: 'ok' | 'degraded'
  version: string
  model_loaded: boolean
  llm_backend: string
  regulation_chunks: number
}
