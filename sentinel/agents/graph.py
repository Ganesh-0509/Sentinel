"""Multi-agent safety workflow (LangGraph).

    START -> risk_monitor -> [stand down | escalate]
                                  |
                          permit_intelligence
                                  |
                             compliance
                                  |
                    [advisory | emergency_orchestrator] -> END

Division of labour -- this is the important design decision:

    DETERMINISTIC agents (no LLM): risk_monitor, permit_intelligence.
        Anything that can stop work or clear work is plain auditable logic. An
        LLM never decides whether a hot-work permit is safe.

    LLM agents: compliance (grounded RAG, cites sources), emergency_orchestrator
        (drafts the regulatory notification). Both operate on language, after the
        safety decision has already been made deterministically.

So the agents add autonomy in *coordination and communication*, not in the safety
verdict itself. That is the honest answer to "why agents?".
"""
from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from sentinel.decision.priority import AlertContext, prioritise
from sentinel.llm.provider import LLMUnavailable, get_llm
from sentinel.rules.engine import PermitRequest, ZoneConditions, evaluate_permit, evaluate_interlocks

ESCALATE_RISK = 0.50          # below this the situation is logged, not escalated
EMERGENCY_RISK = 0.85         # at/above this with a rejected permit -> emergency


class SafetyState(TypedDict, total=False):
    # --- inputs ---
    zone: str
    machine_id: str
    risk: float
    lead_time_min: int
    anomaly_score: float
    explanation: str
    gas_lel: float
    gas_trend: float
    o2_pct: float
    maintenance_active: bool
    hot_work_active: bool
    workers_in_zone: int
    night_shift: bool
    in_changeover: bool
    # --- produced by agents ---
    escalate: bool
    priority: dict
    permit_decision: dict
    interlocks: list
    compliance: dict
    actions: list
    report: str
    trace: list


def _log(state: SafetyState, agent: str, msg: str) -> list:
    return list(state.get("trace", [])) + [f"[{agent}] {msg}"]


# --------------------------------------------------------------- agent nodes
def risk_monitor(state: SafetyState) -> dict:
    """Deterministic: fuse risk + exposure, decide whether to escalate."""
    ctx = AlertContext(
        risk=state.get("risk", 0.0),
        workers_in_zone=state.get("workers_in_zone", 0),
        night_shift=state.get("night_shift", False),
        in_changeover=state.get("in_changeover", False),
        lead_time_min=state.get("lead_time_min"),
    )
    pr = prioritise(ctx)
    escalate = state.get("risk", 0.0) >= ESCALATE_RISK
    msg = (f"risk={state.get('risk', 0):.0%} priority={pr['priority']} "
           f"({', '.join(pr['drivers']) or 'no aggravating factors'}) -> "
           f"{'ESCALATE' if escalate else 'monitor only'}")
    return {"priority": pr, "escalate": escalate, "trace": _log(state, "RiskMonitor", msg)}


def permit_intelligence(state: SafetyState) -> dict:
    """Deterministic: check live conditions against active/requested permits."""
    cond = ZoneConditions(
        gas_lel=state.get("gas_lel", 0.0),
        o2_pct=state.get("o2_pct", 20.9),
        gas_trend=state.get("gas_trend", 0.0),
        maintenance_active=state.get("maintenance_active", False),
        workers_in_zone=state.get("workers_in_zone", 0),
    )
    decision = evaluate_permit(
        PermitRequest("Hot Work", zone=state.get("zone", "unknown"),
                      machine_id=state.get("machine_id", "")),
        cond,
        compound_risk=state.get("risk"),
        lead_time_min=state.get("lead_time_min"),
    )
    interlocks = evaluate_interlocks(cond, state.get("hot_work_active", False))
    msg = f"Hot Work permit -> {decision.status}"
    if interlocks:
        msg += f"; {len(interlocks)} standing interlock(s) tripped"
    return {"permit_decision": decision.as_dict(), "interlocks": interlocks,
            "trace": _log(state, "PermitIntelligence", msg)}


def compliance(state: SafetyState) -> dict:
    """LLM + RAG: what does the governing standard require here?"""
    from sentinel.rag.assistant import ComplianceAssistant
    question = (
        "Hot work is in progress in a zone where combustible gas is rising during "
        "active maintenance. What does the work permit standard require, and what "
        "must the shift in-charge do?"
    )
    try:
        assistant = ComplianceAssistant()
        ans = assistant.ask(question)
        payload = ans.as_dict()
        msg = f"grounded via {ans.backend}; {len(ans.citations)} citation(s)"
    except Exception as e:                      # never let the assistant break the workflow
        payload = {"question": question, "answer": f"compliance lookup unavailable: {e}",
                   "citations": [], "grounded": False, "backend": "none"}
        msg = f"unavailable ({e}); deterministic interlocks still enforce"
    return {"compliance": payload, "trace": _log(state, "ComplianceAgent", msg)}


def emergency_orchestrator(state: SafetyState) -> dict:
    """LLM-assisted: coordinate the first ten minutes and draft the notification."""
    zone = state.get("zone", "unknown")
    workers = state.get("workers_in_zone", 0)
    actions = [
        f"SUSPEND all hot work in {zone} and adjoining areas (remove ignition sources).",
        f"EVACUATE {workers} worker(s) from {zone} via designated routes, crosswind.",
        "ACCOUNT for all personnel at the assembly point against permit and roster records.",
        "ALERT emergency response team + control room on the designated channel.",
        "ISOLATE the suspected release source remotely where safe to do so.",
        "PRESERVE evidence: freeze process trends, gas readings, alarm/interlock history "
        "and active-permit state for the statutory investigation.",
    ]

    from datetime import datetime, timezone
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    cites = "; ".join(state.get("compliance", {}).get("citations", [])) or "n/a"
    prompt = (
        "Draft a factual preliminary incident notification for a plant safety regulator.\n\n"
        f"Detected at: {stamp}\n"
        f"Zone: {zone}\nEquipment: {state.get('machine_id', 'n/a')}\n"
        f"Predicted incident probability: {state.get('risk', 0):.0%}\n"
        f"Predicted time to threshold: ~{state.get('lead_time_min', 'n/a')} minutes\n"
        f"Gas (point sensor): {state.get('gas_lel', 0):.1f} %LEL, "
        f"trend {state.get('gas_trend', 0):+.2f} %LEL/min\n"
        f"Maintenance active: {state.get('maintenance_active')}\n"
        f"Hot work active: {state.get('hot_work_active')}\n"
        f"Workers in zone: {workers}\n"
        f"Model attribution: {state.get('explanation', 'n/a')}\n"
        f"Permit decision: {state.get('permit_decision', {}).get('status', 'n/a')}\n"
        f"References: {cites}\n\n"
        "Write 4-6 short factual sentences in plain prose: what was detected, when, on "
        "what evidence, and what actions were initiated. Use the exact timestamp given "
        "above. NEVER write placeholders such as [date] or [time] -- every field you need "
        "is supplied. Note that hot work was active and has been ordered suspended. End by "
        "stating plainly that this is a preliminary automated notification pending human "
        "verification. Do not speculate about cause or blame. No headings, no bullet points."
    )
    try:
        report = get_llm().generate(prompt, system="You write precise, factual regulatory "
                                                   "notifications. No speculation.")
    except LLMUnavailable:
        report = (f"PRELIMINARY AUTOMATED NOTIFICATION (no language model available)\n"
                  f"Zone {zone}: compound risk {state.get('risk', 0):.0%}, predicted "
                  f"threshold crossing in ~{state.get('lead_time_min', 'n/a')} min. "
                  f"Gas {state.get('gas_lel', 0):.1f} %LEL rising during active "
                  f"maintenance with hot work in progress. Evacuation and hot-work "
                  f"suspension initiated. Pending human verification.")
    return {"actions": actions, "report": report.strip(),
            "trace": _log(state, "EmergencyOrchestrator",
                          f"{len(actions)} actions initiated; notification drafted")}


def advisory(state: SafetyState) -> dict:
    actions = [
        "Continuous gas monitoring in the affected zone.",
        "Standby firewatch posted while hot work continues.",
        "Re-test atmosphere before any permit extension.",
    ]
    return {"actions": actions,
            "trace": _log(state, "Advisory", "conditional controls issued, no evacuation")}


# ------------------------------------------------------------------- routing
def route_after_risk(state: SafetyState) -> str:
    return "escalate" if state.get("escalate") else "stand_down"


def route_after_compliance(state: SafetyState) -> str:
    status = state.get("permit_decision", {}).get("status")
    critical = state.get("priority", {}).get("priority") == "CRITICAL"
    if status == "REJECTED" or state.get("risk", 0) >= EMERGENCY_RISK or critical:
        return "emergency"
    return "advisory"


def build_safety_graph():
    g = StateGraph(SafetyState)
    g.add_node("risk_monitor", risk_monitor)
    g.add_node("permit_intelligence", permit_intelligence)
    g.add_node("compliance", compliance)
    g.add_node("emergency_orchestrator", emergency_orchestrator)
    g.add_node("advisory", advisory)

    g.set_entry_point("risk_monitor")
    g.add_conditional_edges("risk_monitor", route_after_risk,
                            {"escalate": "permit_intelligence", "stand_down": END})
    g.add_edge("permit_intelligence", "compliance")
    g.add_conditional_edges("compliance", route_after_compliance,
                            {"emergency": "emergency_orchestrator", "advisory": "advisory"})
    g.add_edge("emergency_orchestrator", END)
    g.add_edge("advisory", END)
    return g.compile()


def run_safety_workflow(state: dict[str, Any]) -> dict:
    return build_safety_graph().invoke(state)
