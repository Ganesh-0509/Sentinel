"""Safety performance analytics, built on two recognised industry frameworks.

**API RP 754** (Process Safety Performance Indicators) gives the leading/lagging
classification. Four tiers on a continuum, Tier 1 most lagging to Tier 4 most leading:

    Tier 1  loss of primary containment, greater consequence      (lagging)
    Tier 2  loss of primary containment, lesser consequence       (lagging)
    Tier 3  challenges to safety systems -- safe operating limit
            excursions, demands on safety systems                 (leading)
    Tier 4  operating discipline / management system performance  (most leading)

Tiers 1-2 are for external benchmarking; Tiers 3-4 are internal and are where a
predictive layer earns its keep -- they are the events you can still act on.

**EEMUA 191 / ISA-18.2** (Alarm Management) gives the alarm-load benchmarks:

    < 1 alarm per 10 min  ....  target in normal operation
    < 6 alarms/operator/hr ...  acceptable
    > 30 alarms/operator/hr ..  "seriously deficient"
    peak <= 10 per 10 min ....  above this the operator is overloaded

This matters because a detector that finds everything by alarming constantly is not
a safety system, it is noise. Benchmarking both the baseline and SentinelAI against
a published standard is what turns "fewer false alarms" into a defensible claim.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from sentinel import config as C

# --- EEMUA 191 benchmarks (alarms per operator per hour) --------------------
EEMUA_TARGET_PER_HR = 6.0
EEMUA_DEFICIENT_PER_HR = 30.0
EEMUA_PEAK_PER_10MIN = 10.0


def _rate_band(per_hour: float) -> str:
    if per_hour <= 1 * 6:          # <=6/hr
        return "ACCEPTABLE" if per_hour > 1.0 else "TARGET"
    if per_hour < EEMUA_DEFICIENT_PER_HR:
        return "OVER_TARGET"
    return "SERIOUSLY_DEFICIENT"


@dataclass
class ZoneSnapshot:
    """Minimal view of a zone the analytics functions need."""
    zone_id: str
    name: str
    risk: float
    risk_band: str
    gas_lel: float
    workers_in_zone: int
    hot_work_active: bool
    maintenance_active: bool
    in_changeover: bool
    baseline_alarm: bool
    lead_time_min: int | None
    anomaly_score: float


# ---------------------------------------------------------------- KPI summary
def kpi_summary(zones: list[dict], scoreboard: dict | None) -> dict:
    """Headline KPIs, each tagged leading or lagging.

    Best practice is a 3:1 leading-to-lagging ratio: a dashboard dominated by
    lagging indicators only tells you how many people were already hurt.
    """
    n = max(len(zones), 1)
    risks = np.array([z["risk"] for z in zones]) if zones else np.array([0.0])
    exposed = sum(z["workers_in_zone"] for z in zones
                  if z["risk"] >= 0.6)
    at_risk = [z for z in zones if z["risk"] >= 0.6]
    leads = [z["lead_time_min"] for z in zones if z.get("lead_time_min")]

    kpis = [
        {"key": "plant_risk_index", "label": "Plant risk index",
         "value": round(float(risks.max()) * 100, 1), "unit": "%",
         "kind": "leading", "hint": "Highest zone risk across the plant",
         "state": "critical" if risks.max() >= 0.85 else
                  "warn" if risks.max() >= 0.6 else "ok"},
        {"key": "zones_at_risk", "label": "Zones at risk",
         "value": len(at_risk), "unit": f"/ {n}", "kind": "leading",
         "hint": "Zones at HIGH or CRITICAL compound risk",
         "state": "critical" if at_risk else "ok"},
        {"key": "workers_exposed", "label": "Workers exposed",
         "value": exposed, "unit": "", "kind": "leading",
         "hint": "Headcount inside zones at HIGH or CRITICAL risk",
         "state": "critical" if exposed > 0 else "ok"},
        {"key": "mean_lead_time", "label": "Mean warning lead",
         "value": round(float(np.mean(leads)), 1) if leads else 0.0,
         "unit": "min", "kind": "leading",
         "hint": "Predicted minutes before threshold crossing",
         "state": "ok"},
        {"key": "active_hot_work", "label": "Active hot work",
         "value": sum(1 for z in zones if z["hot_work_active"]),
         "unit": "permits", "kind": "leading",
         "hint": "Ignition sources currently authorised in the plant",
         "state": "warn" if any(z["hot_work_active"] and z["risk"] >= 0.5
                                for z in zones) else "ok"},
        {"key": "anomalies", "label": "Anomalous zones",
         "value": sum(1 for z in zones if z["anomaly_score"] >= 3.0),
         "unit": "", "kind": "leading",
         "hint": "Behaviour outside the learned normal envelope",
         "state": "warn" if any(z["anomaly_score"] >= 3.0 for z in zones) else "ok"},
    ]

    if scoreboard:
        kpis += [
            {"key": "missed_incidents", "label": "Missed incidents (model)",
             "value": round(scoreboard["compound_false_negative_rate"] * 100, 1),
             "unit": "%", "kind": "lagging",
             "hint": "False-negative rate on held-out evaluation episodes",
             "state": "ok" if scoreboard["compound_false_negative_rate"] < 0.05 else "warn"},
            {"key": "baseline_missed", "label": "Missed by single sensor",
             "value": round(scoreboard["baseline_false_negative_rate"] * 100, 1),
             "unit": "%", "kind": "lagging",
             "hint": "What a conventional gas alarm alone would miss",
             "state": "critical"},
        ]

    leading = sum(1 for k in kpis if k["kind"] == "leading")
    lagging = max(sum(1 for k in kpis if k["kind"] == "lagging"), 1)
    return {
        "kpis": kpis,
        "leading_count": leading,
        "lagging_count": lagging,
        "leading_to_lagging_ratio": round(leading / lagging, 2),
        "ratio_target": 3.0,
        "ratio_ok": (leading / lagging) >= 3.0,
    }


# ------------------------------------------------- API RP 754 classification
def tier_events(zones: list[dict], scoreboard: dict | None) -> dict:
    """Classify current plant conditions into the API RP 754 tier structure."""
    t3, t4 = [], []

    for z in zones:
        # Tier 3 -- challenges to safety systems
        if z["gas_lel"] >= 10.0:
            t3.append({"zone_id": z["zone_id"], "zone": z["name"],
                       "event": "Safe operating limit excursion",
                       "detail": f"Combustible gas {z['gas_lel']:.1f} % LEL at or above "
                                 f"the first-alarm limit"})
        if z["hot_work_active"] and z["risk"] >= 0.5:
            t3.append({"zone_id": z["zone_id"], "zone": z["name"],
                       "event": "Demand on safety system",
                       "detail": "Hot-work permit challenged by rising compound risk"})
        if z["anomaly_score"] >= 3.0:
            t3.append({"zone_id": z["zone_id"], "zone": z["name"],
                       "event": "Process deviation outside normal envelope",
                       "detail": f"Anomaly score {z['anomaly_score']:.1f}"})

        # Tier 4 -- operating discipline
        if z["hot_work_active"] and z["maintenance_active"]:
            t4.append({"zone_id": z["zone_id"], "zone": z["name"],
                       "event": "Simultaneous operations",
                       "detail": "Hot work concurrent with maintenance in the same zone"})
        if z["in_changeover"] and z["risk"] >= 0.5:
            t4.append({"zone_id": z["zone_id"], "zone": z["name"],
                       "event": "Elevated risk spanning shift handover",
                       "detail": "Open hazard at crew changeover -- handover verification required"})

    tiers = [
        {"tier": 1, "name": "Loss of primary containment - greater consequence",
         "kind": "lagging", "external_reporting": True, "count": 0, "events": []},
        {"tier": 2, "name": "Loss of primary containment - lesser consequence",
         "kind": "lagging", "external_reporting": True, "count": 0, "events": []},
        {"tier": 3, "name": "Challenge to safety systems",
         "kind": "leading", "external_reporting": False,
         "count": len(t3), "events": t3},
        {"tier": 4, "name": "Operating discipline & management system",
         "kind": "leading", "external_reporting": False,
         "count": len(t4), "events": t4},
    ]
    return {
        "framework": "API RP 754 (3rd ed.)",
        "tiers": tiers,
        "leading_events": len(t3) + len(t4),
        "lagging_events": 0,
        "note": "Tier 1 and 2 are counted only after a loss of containment has already "
                "occurred. Tier 3 and 4 are where a predictive layer can still change "
                "the outcome.",
    }


# ------------------------------------------------ EEMUA 191 alarm performance
def alarm_performance(scoreboard: dict | None, episode_minutes: int = C.EPISODE_MINUTES,
                      monitored_points: int = 250) -> dict:
    """Translate nuisance-alarm load into EEMUA 191 operator-load terms.

    EEMUA counts *discrete annunciations* per operator per hour, so we use the
    per-episode false-alarm rate (one spurious alarm occurrence per zone per
    episode) rather than alarm-minutes, which measure duration.

    A measured rate on 8 simulated zones is not an operator load: a real console
    covers hundreds of points. We therefore report the measured per-zone rate AND
    a clearly-labelled projection to a console of `monitored_points`, which is what
    makes the EEMUA bands meaningful.
    """
    if not scoreboard:
        return {"available": False}

    zone_hours = episode_minutes / 60.0     # one episode = one zone-hour block

    def block(fa_rate: float, minutes: int, label: str) -> dict:
        per_zone_hr = fa_rate / zone_hours if zone_hours else 0.0
        per_operator_hr = per_zone_hr * monitored_points
        return {
            "system": label,
            "alarm_minutes": int(minutes),
            "false_alarm_rate": round(fa_rate, 4),
            "alarms_per_zone_hour": round(per_zone_hr, 4),
            "alarms_per_operator_hour": round(per_operator_hr, 1),
            "band": _rate_band(per_operator_hr),
            "within_eemua_target": per_operator_hr <= EEMUA_TARGET_PER_HR,
        }

    base = block(scoreboard.get("baseline_false_alarm_rate", 0.0),
                 scoreboard.get("baseline_nuisance_minutes", 0),
                 "Single-sensor baseline")
    ours = block(scoreboard.get("compound_false_alarm_rate", 0.0),
                 scoreboard.get("compound_nuisance_minutes", 0),
                 "SentinelAI")
    reduction = (1 - (ours["alarms_per_operator_hour"] /
                      base["alarms_per_operator_hour"])) * 100 \
        if base["alarms_per_operator_hour"] else 0.0

    return {
        "available": True,
        "framework": "EEMUA 191 / ISA-18.2",
        "benchmarks": {
            "target_per_hour": EEMUA_TARGET_PER_HR,
            "seriously_deficient_per_hour": EEMUA_DEFICIENT_PER_HR,
            "peak_per_10min": EEMUA_PEAK_PER_10MIN,
        },
        "systems": [base, ours],
        "nuisance_reduction_pct": round(reduction, 1),
        "monitored_points": monitored_points,
        "projection_note": (
            f"Measured per-zone false-alarm rates projected to a console covering "
            f"{monitored_points} monitored points, which is the scale at which EEMUA "
            f"operator-load bands apply."
        ),
    }


# --------------------------------------------------- distribution and trends
def risk_distribution(zones: list[dict]) -> dict:
    bands = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    for z in zones:
        bands[z["risk_band"]] = bands.get(z["risk_band"], 0) + 1
    return {
        "bands": [{"band": k, "count": v} for k, v in bands.items()],
        "by_zone": sorted(
            [{"zone_id": z["zone_id"], "zone": z["name"], "risk": z["risk"],
              "band": z["risk_band"], "workers": z["workers_in_zone"]}
             for z in zones],
            key=lambda r: r["risk"], reverse=True),
    }


def risk_trend(zone_series: dict[str, np.ndarray], upto: int,
               window: int = 120) -> list[dict]:
    """Plant-level risk over time: max and mean across zones."""
    lo = max(0, upto - window + 1)
    out = []
    for k in range(lo, upto + 1):
        vals = [s[k] for s in zone_series.values() if k < len(s)]
        if not vals:
            continue
        out.append({
            "minute": k,
            "max_risk": round(float(np.max(vals)), 4),
            "mean_risk": round(float(np.mean(vals)), 4),
            "zones_at_risk": int(sum(1 for v in vals if v >= 0.6)),
        })
    return out


def contributing_factors(model, top: int = 10) -> list[dict]:
    """Global feature importance -- which signals drive risk plant-wide."""
    from sentinel.ml.explain import _READABLE
    pairs = model.feature_importance(top=top)
    total = sum(v for _, v in pairs) or 1.0
    groups = {
        "gas": "Gas", "pressure": "Pressure", "temp": "Temperature",
        "vib": "Vibration", "maint": "Maintenance", "hotwork": "Hot work",
        "permit": "Permit",
    }

    def group_of(feature: str) -> str:
        for token, label in groups.items():
            if token in feature:
                return label
        return "Other"

    return [{
        "feature": f,
        "label": _READABLE.get(f, f),
        "group": group_of(f),
        "importance": round(float(v), 1),
        "share": round(float(v) / total, 4),
    } for f, v in pairs]
