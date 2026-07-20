"""Turn simulated episodes into an incident / near-miss corpus.

The near-miss data is the valuable part and it already exists: once operator
intervention was modelled, every leak that was isolated in time became a genuine
near miss, with full telemetry attached. Real plants collect near-miss reports as
free text and then struggle to mine them; here we have the underlying signals too.

Each record carries:
    * structured **precursor conditions** captured at a fixed lookback before the
      event, which is what pattern mining runs on;
    * a natural-language **narrative**, which is what the RAG assistant retrieves.

A rising near-miss count is a positive signal in safety practice -- it means hazards
are surfacing while they are still recoverable. This corpus is therefore reported as
a leading indicator, not as a failure count.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from sentinel import config as C

LOOKBACK_MIN = 20          # how far before the event we characterise precursors


@dataclass
class IncidentRecord:
    record_id: str
    outcome: str                     # "INCIDENT" | "NEAR_MISS"
    incident_type: str               # "explosion_risk" | "toxic_accumulation" | "controlled_release"
    zone: str
    minute_of_event: int
    severity: str                    # "CRITICAL" | "HIGH" | "MEDIUM"
    precursors: dict = field(default_factory=dict)
    narrative: str = ""
    detected_by_single_sensor: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


def _severity(outcome: str, workers: int, hot_work: bool) -> str:
    if outcome == "INCIDENT":
        return "CRITICAL" if (workers >= 4 or hot_work) else "HIGH"
    return "MEDIUM" if workers >= 4 else "LOW"


def _classify(ep: pd.DataFrame, onset: int, intervened: int) -> tuple[str, str]:
    if onset >= 0:
        hot = bool(ep["hot_work_permit"].iloc[onset])
        return "INCIDENT", "explosion_risk" if hot else "toxic_accumulation"
    if intervened >= 0:
        return "NEAR_MISS", "controlled_release"
    return "", ""


def _precursors(ep: pd.DataFrame, at: int) -> dict:
    """Characterise conditions in the window before the event."""
    lo = max(0, at - LOOKBACK_MIN)
    win = ep.iloc[lo:at + 1]
    if len(win) < 2:
        win = ep.iloc[max(0, at - 1):at + 1]

    gas = win["gas_sensor"].to_numpy()
    gas_rate = float((gas[-1] - gas[0]) / max(len(gas) - 1, 1))
    pres = win["pressure"].to_numpy()

    return {
        "gas_rising": gas_rate > 0.05,
        "gas_rate_per_min": round(gas_rate, 3),
        "peak_gas_lel": round(float(gas.max()), 2),
        "pressure_rising": bool((pres[-1] - pres[0]) > 0.05),
        "maintenance_active": bool(win["maintenance_active"].max()),
        "hot_work_active": bool(win["hot_work_permit"].max()),
        "confined_space": bool(win["confined_space_permit"].max()),
        "night_shift": bool(win["night_shift"].iloc[-1]),
        "shift_changeover": bool(win["in_changeover"].max()),
        "workers_in_zone": int(win["workers_in_zone"].max()),
        "simultaneous_operations": bool(
            win["maintenance_active"].max() and win["hot_work_permit"].max()
        ),
        "sensor_understated": bool(
            win["gas_true"].max() - win["gas_sensor"].max() > 3.0
        ),
    }


def _narrative(rec_id: str, outcome: str, itype: str, zone: str, at: int,
               p: dict) -> str:
    lead = ("An incident threshold was reached"
            if outcome == "INCIDENT" else
            "A developing gas release was isolated before reaching the incident threshold")
    conds = []
    if p["gas_rising"]:
        conds.append(f"combustible gas rising at {p['gas_rate_per_min']:.2f} %LEL/min "
                     f"to a peak of {p['peak_gas_lel']:.1f} %LEL on the point sensor")
    if p["pressure_rising"]:
        conds.append("line pressure rising over the same window")
    if p["maintenance_active"]:
        conds.append("maintenance work active in the zone")
    if p["hot_work_active"]:
        conds.append("a hot-work permit open (ignition source present)")
    if p["confined_space"]:
        conds.append("a confined-space entry in progress")
    if p["shift_changeover"]:
        conds.append("the event spanning a crew changeover")
    if p["night_shift"]:
        conds.append("night shift staffing")
    if p["sensor_understated"]:
        conds.append("the point sensor reading materially below the true zone "
                     "concentration")

    body = "; ".join(conds) if conds else "no distinguishing precursor conditions recorded"
    tail = ""
    if p["simultaneous_operations"]:
        tail = (" Simultaneous operations (maintenance concurrent with hot work) were in "
                "effect, a combination requiring cross-checked permits and continuous "
                "gas monitoring.")
    return (f"{rec_id} — {lead} in {zone} at minute {at}. "
            f"Classification: {itype.replace('_', ' ')}. "
            f"Conditions in the {LOOKBACK_MIN} minutes beforehand: {body}."
            f"{tail} Personnel in zone at the time: {p['workers_in_zone']}.")


def build_incident_corpus(raw: pd.DataFrame, zone_names: list[str] | None = None
                          ) -> list[IncidentRecord]:
    """Extract incident and near-miss records from simulated episodes."""
    zone_names = zone_names or ["Coke Oven Battery A", "Coke Oven Battery B",
                                "By-Product Plant", "Sinter Plant", "Blast Furnace 2",
                                "Tank Farm 3", "Gas Holder Yard"]
    records: list[IncidentRecord] = []

    for eid, ep in raw.groupby("episode_id", sort=False):
        ep = ep.sort_values("minute").reset_index(drop=True)
        onset = int(ep["incident_onset"].iloc[0])
        intervened = int(ep["intervened_at"].iloc[0])
        outcome, itype = _classify(ep, onset, intervened)
        if not outcome:
            continue

        at = onset if onset >= 0 else intervened
        at = max(0, min(at, len(ep) - 1))
        p = _precursors(ep, at)
        zone = zone_names[int(eid) % len(zone_names)]
        rec_id = f"{'INC' if outcome == 'INCIDENT' else 'NM'}-{int(eid):04d}"

        # would a conventional single-sensor alarm have fired before the event?
        fired = bool((ep["gas_sensor"].iloc[:at] >= C.GAS_BASELINE_ALARM).any()) if at else False

        records.append(IncidentRecord(
            record_id=rec_id,
            outcome=outcome,
            incident_type=itype,
            zone=zone,
            minute_of_event=at,
            severity=_severity(outcome, p["workers_in_zone"], p["hot_work_active"]),
            precursors=p,
            narrative=_narrative(rec_id, outcome, itype, zone, at, p),
            detected_by_single_sensor=fired,
        ))
    return records
