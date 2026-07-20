"""Alert prioritisation -- where shift/roster signals actually belong.

The ablation (scripts/ablation_shift.py) showed that feeding shift/roster features
into the RISK MODEL is actively harmful: they let the model infer "a human will
probably catch this" and under-alert by 17.8 points of detection at a matched
false-alarm rate.

But those signals are far from useless -- they were simply in the wrong layer.
Shift state does not change *how likely a hazard is*; it changes *how bad the
consequence is* and *how fast we must act*:

    risk  = P(incident)          <- the model's job, hazard only
    impact = people exposed      <- consequence
    urgency = response capacity  <- night shift / changeover slow response down

Keeping these separate means the model never learns complacency, while the
control room still sees "8 people in this zone, mid-handover" at the top of the
queue. This is also what de-noises the alert feed.
"""
from __future__ import annotations

from dataclasses import dataclass

PRIORITY_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


@dataclass
class AlertContext:
    risk: float                       # 0-1, from the compound forecaster
    workers_in_zone: int = 0
    night_shift: bool = False
    in_changeover: bool = False
    asset_criticality: float = 1.0    # 1.0 = normal, >1 for critical equipment
    lead_time_min: int | None = None


def _exposure_factor(workers: int) -> float:
    """More people in harm's way -> higher consequence (saturating)."""
    if workers <= 0:
        return 0.6            # unoccupied zone: still act, but lower queue position
    if workers <= 2:
        return 1.0
    if workers <= 5:
        return 1.3
    return 1.6


def _urgency_factor(night_shift: bool, in_changeover: bool) -> float:
    """Degraded response capacity means we need to escalate sooner."""
    f = 1.0
    if night_shift:
        f *= 1.20         # thinner staffing, slower escalation
    if in_changeover:
        f *= 1.35         # attention split, handover information loss risk
    return f


def prioritise(ctx: AlertContext) -> dict:
    """Return a priority label plus the factors that produced it (explainable)."""
    exposure = _exposure_factor(ctx.workers_in_zone)
    urgency = _urgency_factor(ctx.night_shift, ctx.in_changeover)
    score = ctx.risk * exposure * urgency * ctx.asset_criticality

    if score >= 1.10:
        level = "CRITICAL"
    elif score >= 0.70:
        level = "HIGH"
    elif score >= 0.35:
        level = "MEDIUM"
    else:
        level = "LOW"

    drivers = []
    if ctx.workers_in_zone > 0:
        drivers.append(f"{ctx.workers_in_zone} worker(s) in zone")
    if ctx.night_shift:
        drivers.append("night shift (slower response)")
    if ctx.in_changeover:
        drivers.append("shift changeover (handover risk)")
    if ctx.asset_criticality > 1.0:
        drivers.append("critical asset")
    if ctx.lead_time_min is not None:
        drivers.append(f"~{ctx.lead_time_min} min to threshold")

    return {
        "priority": level,
        "score": round(float(score), 3),
        "risk": round(float(ctx.risk), 3),
        "exposure_factor": exposure,
        "urgency_factor": round(urgency, 2),
        "drivers": drivers,
    }
