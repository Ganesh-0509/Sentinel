"""Deterministic safety rule engine -- the hard guarantees.

Design principle: **we ML the predictions, but we hard-code the guarantees.**
A probabilistic model must never be allowed to *approve* a hot-work permit over a
gas-air mixture. These interlocks are plain, auditable boolean logic derived from
OISD-STD-105 (Work Permit System) gas-testing limits -- exactly the kind of rule a
factory inspector can read and sign off on.

Thresholds are expressed in % LEL / % O2 / ppm, matching OISD gas-testing units.
They are configurable so a plant can map them to its own permit conditions.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# --- OISD-STD-105-aligned limits (configurable per site) --------------------
HOT_WORK_MAX_LEL = 5.0        # combustible gas must be well below the explosive limit
GENERAL_MAX_LEL = 10.0        # first-alarm level for any occupied work
CONFINED_SPACE_MAX_LEL = 5.0
O2_MIN_PCT = 19.5             # oxygen-deficient below this
O2_MAX_PCT = 23.5            # oxygen-enriched (fire risk) above this
COMPOUND_WATCH_LEL = 3.0      # below the hard limit but worth watching if trending up


@dataclass
class PermitRequest:
    permit_type: str          # "Hot Work" | "Confined Space" | "Cold Work" | "Electrical"
    zone: str
    machine_id: str = ""


@dataclass
class ZoneConditions:
    gas_lel: float                    # combustible gas, % LEL (observed)
    o2_pct: float = 20.9              # oxygen, %
    toxic_ppm: float = 0.0            # toxic gas, ppm
    gas_trend: float = 0.0            # % LEL per minute (rising if > 0)
    maintenance_active: bool = False
    workers_in_zone: int = 0


@dataclass
class PermitDecision:
    status: str                       # "APPROVED" | "REJECTED" | "CONDITIONAL"
    reasons: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"status": self.status, "reasons": self.reasons, "citations": self.citations}


def evaluate_permit(
    req: PermitRequest,
    cond: ZoneConditions,
    compound_risk: float | None = None,
    lead_time_min: int | None = None,
) -> PermitDecision:
    """Return an APPROVE / REJECT / CONDITIONAL decision with citations.

    `compound_risk` (0-1) is the AI forecaster's predicted probability of an
    incident within the forecast horizon. It can only ever make the decision
    *stricter* -- the AI may escalate or veto, but it can never approve work that
    the deterministic gas/oxygen interlocks have rejected. Fail-safe by design.
    """
    reasons: list[str] = []
    citations: list[str] = []
    status = "APPROVED"

    ptype = req.permit_type.strip().lower()

    # ---- hard interlocks by permit type ------------------------------------
    if ptype == "hot work":
        if cond.gas_lel >= HOT_WORK_MAX_LEL:
            status = "REJECTED"
            reasons.append(
                f"Combustible gas {cond.gas_lel:.1f}% LEL >= hot-work limit "
                f"{HOT_WORK_MAX_LEL:.1f}% LEL. Ignition source not permitted."
            )
            citations.append("OISD-STD-105 §Hot Work / gas testing (%LEL)")
    elif ptype == "confined space":
        if cond.gas_lel >= CONFINED_SPACE_MAX_LEL:
            status = "REJECTED"
            reasons.append(
                f"Combustible gas {cond.gas_lel:.1f}% LEL >= confined-space limit "
                f"{CONFINED_SPACE_MAX_LEL:.1f}% LEL."
            )
            citations.append("OISD-STD-105 §Confined Space Entry")
        if not (O2_MIN_PCT <= cond.o2_pct <= O2_MAX_PCT):
            status = "REJECTED"
            reasons.append(
                f"Oxygen {cond.o2_pct:.1f}% outside safe range "
                f"{O2_MIN_PCT}-{O2_MAX_PCT}%."
            )
            citations.append("OISD-STD-105 §Confined Space Entry / O2 testing")
    else:  # cold work / electrical / other occupied work
        if cond.gas_lel >= GENERAL_MAX_LEL:
            status = "REJECTED"
            reasons.append(
                f"Combustible gas {cond.gas_lel:.1f}% LEL >= general work limit "
                f"{GENERAL_MAX_LEL:.1f}% LEL."
            )
            citations.append("OISD-STD-105 §Work Permit / gas testing")

    # ---- compound advisory (deterministic combination logic) ---------------
    if status == "APPROVED" and ptype == "hot work":
        if (cond.gas_lel >= COMPOUND_WATCH_LEL and cond.gas_trend > 0
                and cond.maintenance_active):
            status = "CONDITIONAL"
            reasons.append(
                f"Gas {cond.gas_lel:.1f}% LEL is rising ({cond.gas_trend:+.2f} %LEL/min) "
                f"during active maintenance near a hot-work zone -- compound ignition "
                f"risk. Continuous gas monitoring + standby firewatch required; suspend "
                f"if gas reaches {HOT_WORK_MAX_LEL:.1f}% LEL."
            )
            citations.append("OISD-STD-105 §Simultaneous Operations / continuous monitoring")

    # ---- AI compound-risk escalation (can only tighten, never loosen) ------
    if compound_risk is not None:
        lead_txt = f" Predicted threshold crossing in ~{lead_time_min} min." if lead_time_min else ""
        if compound_risk >= 0.85 and status != "REJECTED":
            status = "REJECTED"
            reasons.append(
                f"AI compound-risk model predicts {compound_risk:.0%} probability of an "
                f"incident within the forecast horizon despite point-sensor readings "
                f"being within limits.{lead_txt} Multi-signal evidence (pressure, "
                f"temperature, vibration, operational context) indicates a developing "
                f"hazard the single gas sensor cannot see."
            )
            citations.append("SentinelAI Compound Risk Forecaster (SHAP-explained)")
        elif compound_risk >= 0.50 and status == "APPROVED":
            status = "CONDITIONAL"
            reasons.append(
                f"AI compound-risk elevated ({compound_risk:.0%}).{lead_txt} "
                f"Continuous gas monitoring and standby firewatch required."
            )
            citations.append("SentinelAI Compound Risk Forecaster (SHAP-explained)")

    if not reasons:
        reasons.append("All gas/oxygen readings within permit limits.")
    return PermitDecision(status=status, reasons=reasons, citations=citations)


def evaluate_interlocks(cond: ZoneConditions, hot_work_active: bool) -> list[str]:
    """Standing interlocks that fire regardless of a specific permit request."""
    violations: list[str] = []
    if hot_work_active and cond.gas_lel >= HOT_WORK_MAX_LEL:
        violations.append(
            f"ACTIVE hot-work with gas {cond.gas_lel:.1f}% LEL >= "
            f"{HOT_WORK_MAX_LEL:.1f}% LEL -- SUSPEND immediately (OISD-STD-105)."
        )
    if cond.gas_lel >= GENERAL_MAX_LEL and cond.workers_in_zone > 0:
        violations.append(
            f"{cond.workers_in_zone} worker(s) in zone with gas {cond.gas_lel:.1f}% LEL "
            f">= {GENERAL_MAX_LEL:.1f}% LEL -- evacuation advised."
        )
    return violations
