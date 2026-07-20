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

export interface Health {
  status: 'ok' | 'degraded'
  version: string
  model_loaded: boolean
  llm_backend: string
  regulation_chunks: number
}
