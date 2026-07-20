import type { Priority, RiskBand } from '../types'

export const riskHex: Record<'low' | 'medium' | 'high' | 'critical', string> = {
  low: '#22c55e',
  medium: '#eab308',
  high: '#f97316',
  critical: '#ef4444',
}

export const riskFill: Record<'low' | 'medium' | 'high' | 'critical', string> = {
  low: 'bg-risk-low',
  medium: 'bg-risk-medium',
  high: 'bg-risk-high',
  critical: 'bg-risk-critical',
}

/** Badge styling per risk/priority band. Text colours meet WCAG AA on ink-800. */
export const bandBadge: Record<RiskBand, string> = {
  LOW: 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30',
  MEDIUM: 'bg-yellow-500/15 text-yellow-300 border border-yellow-500/30',
  HIGH: 'bg-orange-500/15 text-orange-300 border border-orange-500/30',
  CRITICAL: 'bg-red-500/15 text-red-300 border border-red-500/30',
}

export const permitBadge: Record<string, string> = {
  APPROVED: 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30',
  CONDITIONAL: 'bg-yellow-500/15 text-yellow-300 border border-yellow-500/30',
  REJECTED: 'bg-red-500/15 text-red-300 border border-red-500/30',
}

export const pct = (v: number, digits = 0) => `${(v * 100).toFixed(digits)}%`

export function bandOf(priority: Priority): keyof typeof riskHex {
  return priority.toLowerCase() as keyof typeof riskHex
}
