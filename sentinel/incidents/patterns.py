"""Mine recurring precursor patterns from the incident / near-miss corpus.

This is the "recurring patterns that manual investigations miss" problem. A human
investigator reads one report at a time and reasons about that event; what they cannot
easily do is notice that the same *combination* of conditions preceded thirty separate
events across eighteen months.

Method: association-rule style lift, deliberately not a clustering black box.

    support(A)     fraction of all records in which condition-set A held
    confidence     P(incident | A)  -- how often A ended badly
    lift           confidence / base rate  -- how much A multiplies the risk

Lift is the number that matters. A condition present in every record is not a finding;
a condition that triples the probability of a bad outcome is. Single conditions and
pairs are both mined, because the whole premise of this project is that combinations
carry information single signals do not.

Deliberately transparent: every number here can be recomputed by hand from the corpus,
which is what makes it usable as evidence in a safety review.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import combinations

from sentinel.incidents.records import IncidentRecord

# Boolean precursor flags worth mining. Continuous fields are excluded; they are
# summarised separately rather than thresholded arbitrarily.
FLAGS = [
    ("gas_rising", "gas rising"),
    ("pressure_rising", "pressure rising"),
    ("maintenance_active", "maintenance active"),
    ("hot_work_active", "hot work active"),
    ("confined_space", "confined-space entry"),
    ("night_shift", "night shift"),
    ("shift_changeover", "shift changeover"),
    ("simultaneous_operations", "simultaneous operations"),
    ("sensor_understated", "point sensor understating true gas"),
]

MIN_SUPPORT_COUNT = 5      # ignore patterns too rare to act on


@dataclass
class PrecursorPattern:
    conditions: list[str]
    label: str
    occurrences: int
    incidents: int
    near_misses: int
    confidence: float          # P(incident | conditions)
    lift: float                # confidence / base incident rate
    single_sensor_missed: int  # of the incidents, how many a point alarm did not catch

    def as_dict(self) -> dict:
        return asdict(self)


def _holds(rec: IncidentRecord, keys: tuple[str, ...]) -> bool:
    return all(bool(rec.precursors.get(k)) for k in keys)


def mine_patterns(records: list[IncidentRecord], max_order: int = 2,
                  top: int = 12) -> dict:
    """Return recurring precursor patterns ranked by lift."""
    n = len(records)
    if n == 0:
        return {"base_incident_rate": 0.0, "n_records": 0, "patterns": []}

    base_rate = sum(1 for r in records if r.outcome == "INCIDENT") / n
    label_of = dict(FLAGS)
    keys = [k for k, _ in FLAGS]

    found: list[PrecursorPattern] = []
    for order in range(1, max_order + 1):
        for combo in combinations(keys, order):
            matched = [r for r in records if _holds(r, combo)]
            if len(matched) < MIN_SUPPORT_COUNT:
                continue
            incidents = [r for r in matched if r.outcome == "INCIDENT"]
            conf = len(incidents) / len(matched)
            found.append(PrecursorPattern(
                conditions=list(combo),
                label=" + ".join(label_of[k] for k in combo),
                occurrences=len(matched),
                incidents=len(incidents),
                near_misses=len(matched) - len(incidents),
                confidence=round(conf, 4),
                lift=round(conf / base_rate, 3) if base_rate else 0.0,
                single_sensor_missed=sum(
                    1 for r in incidents if not r.detected_by_single_sensor
                ),
            ))

    # rank by lift, then by how many records back it up
    found.sort(key=lambda p: (p.lift, p.occurrences), reverse=True)

    return {
        "n_records": n,
        "n_incidents": sum(1 for r in records if r.outcome == "INCIDENT"),
        "n_near_misses": sum(1 for r in records if r.outcome == "NEAR_MISS"),
        "base_incident_rate": round(base_rate, 4),
        "min_support_count": MIN_SUPPORT_COUNT,
        "patterns": [p.as_dict() for p in found[:top]],
        "method": ("Association-rule lift over boolean precursor conditions. "
                   "Lift = P(incident | conditions) / base incident rate. "
                   "Patterns supported by fewer than "
                   f"{MIN_SUPPORT_COUNT} records are suppressed."),
    }


def prevention_priorities(mined: dict, top: int = 5) -> list[dict]:
    """Turn the highest-lift patterns into ranked prevention actions."""
    actions = {
        "simultaneous_operations": "Cross-check concurrent permits in shared areas; "
                                   "require continuous gas monitoring where maintenance "
                                   "and hot work overlap.",
        "hot_work_active": "Re-test the atmosphere immediately before and during hot work; "
                           "suspend on any rising trend rather than on threshold alone.",
        "maintenance_active": "Treat maintenance as a gas-release amplifier: raise "
                              "monitoring frequency for the duration of the work order.",
        "shift_changeover": "Require explicit handover acknowledgement for every open "
                            "permit and any unresolved gas concern.",
        "sensor_understated": "Review detector placement and calibration in this zone; "
                              "a point sensor that under-reads is worse than none.",
        "night_shift": "Review night-shift escalation staffing and response times.",
        "gas_rising": "Alarm on rate-of-change, not only on absolute concentration.",
        "pressure_rising": "Correlate pressure trend with gas trend; treat divergence as "
                           "a containment indicator.",
        "confined_space": "Verify isolation, ventilation and standby cover before entry.",
    }
    out = []
    for p in mined.get("patterns", [])[:top]:
        recs = [actions[c] for c in p["conditions"] if c in actions]
        out.append({
            "pattern": p["label"],
            "lift": p["lift"],
            "occurrences": p["occurrences"],
            "incidents": p["incidents"],
            "single_sensor_missed": p["single_sensor_missed"],
            "actions": recs,
        })
    return out
