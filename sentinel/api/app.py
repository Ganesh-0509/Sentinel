"""SentinelAI REST API.

Design notes:
  * The safety-critical path (forecaster + deterministic rule engine) never depends
    on the LLM. /compliance and /workflow degrade; /zones and /permits/evaluate do not.
  * Every response is a declared Pydantic model, so /docs is a usable integration
    contract rather than a debug page.
  * Errors return RFC-7807-style problem detail bodies with a stable `type`.
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from sentinel import __version__
from sentinel.api import schemas as S
from sentinel.api.service import plant
from sentinel.llm.provider import get_llm
from sentinel.rules.engine import PermitRequest, ZoneConditions, evaluate_permit

ROOT = Path(__file__).resolve().parents[2]

DESCRIPTION = """
Compound industrial safety intelligence.

Fuses gas, pressure, temperature, vibration and operational context (permits,
maintenance) into a forward-looking risk forecast, explains every alert with SHAP,
enforces deterministic permit interlocks, and coordinates response through a
multi-agent workflow.

**Safety contract:** the machine-learning layer may *escalate or reject* work. It can
never approve work that the deterministic gas/oxygen interlocks have rejected.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    plant.startup()
    yield


app = FastAPI(
    title="SentinelAI",
    version=__version__,
    description=DESCRIPTION,
    lifespan=lifespan,
    contact={"name": "SentinelAI"},
    license_info={"name": "See repository LICENSE"},
    openapi_tags=[
        {"name": "system", "description": "Health and readiness."},
        {"name": "plant", "description": "Live zone telemetry and risk state."},
        {"name": "alerts", "description": "Prioritised alert queue."},
        {"name": "permits", "description": "Deterministic permit interlocks."},
        {"name": "compliance", "description": "RAG-grounded regulatory answers."},
        {"name": "workflow", "description": "Multi-agent safety workflow."},
        {"name": "evaluation", "description": "Baseline-vs-compound evidence."},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api/v1")


def _require_ready() -> None:
    if not plant.ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=plant.error or "service starting",
        )


# ------------------------------------------------------------------- system
@api.get("/health", response_model=S.HealthResponse, tags=["system"])
def health() -> S.HealthResponse:
    return S.HealthResponse(
        status="ok" if plant.ready else "degraded",
        version=__version__,
        model_loaded=plant.model is not None,
        llm_backend=get_llm().backend,
        regulation_chunks=len(plant.store.chunks) if plant.store else 0,
    )


# -------------------------------------------------------------------- plant
@api.get("/zones", response_model=list[S.ZoneState], tags=["plant"])
def zones() -> list[S.ZoneState]:
    _require_ready()
    return [S.ZoneState(**z) for z in plant.zone_states()]


@api.get("/zones/{zone_id}", response_model=S.ZoneState, tags=["plant"])
def zone(zone_id: str) -> S.ZoneState:
    _require_ready()
    try:
        return S.ZoneState(**plant.zone_state(zone_id))
    except KeyError:
        raise HTTPException(404, f"unknown zone '{zone_id}'")


@api.get("/zones/{zone_id}/history", response_model=list[S.ZoneReading], tags=["plant"])
def zone_history(zone_id: str,
                 window: int = Query(90, ge=10, le=240)) -> list[S.ZoneReading]:
    _require_ready()
    try:
        return [S.ZoneReading(**r) for r in plant.zone_history(zone_id, window)]
    except KeyError:
        raise HTTPException(404, f"unknown zone '{zone_id}'")


@api.post("/clock/tick", tags=["plant"])
def tick(steps: int = Query(1, ge=1, le=60)) -> dict:
    _require_ready()
    return {"minute": plant.tick(steps)}


@api.post("/clock/set", tags=["plant"])
def set_clock(minute: int = Query(..., ge=0, le=239)) -> dict:
    _require_ready()
    return {"minute": plant.set_minute(minute)}


@api.get("/clock", tags=["plant"])
def clock() -> dict:
    return {"minute": plant.minute}


# ------------------------------------------------------------------- alerts
@api.get("/alerts", response_model=list[S.AlertItem], tags=["alerts"])
def alerts() -> list[S.AlertItem]:
    _require_ready()
    return [S.AlertItem(**a) for a in plant.alerts()]


# ------------------------------------------------------------------ permits
@api.post("/permits/evaluate", response_model=S.PermitDecisionResponse, tags=["permits"])
def evaluate(body: S.PermitRequestBody) -> S.PermitDecisionResponse:
    """Deterministic interlocks, optionally escalated by the compound-risk model.

    This endpoint does not require the LLM and stays available if it is down.
    """
    _require_ready()
    try:
        s = plant.zone_state(body.zone_id)
    except KeyError:
        raise HTTPException(404, f"unknown zone '{body.zone_id}'")

    cond = ZoneConditions(
        gas_lel=s["gas_lel"], gas_trend=s["gas_trend"],
        maintenance_active=s["maintenance_active"],
        workers_in_zone=s["workers_in_zone"],
    )
    decision = evaluate_permit(
        PermitRequest(body.permit_type, zone=body.zone_id, machine_id=body.machine_id),
        cond,
        compound_risk=s["risk"] if body.use_ai_risk else None,
        lead_time_min=s["lead_time_min"] if body.use_ai_risk else None,
    )
    return S.PermitDecisionResponse(**decision.as_dict())


# --------------------------------------------------------------- compliance
_PROV_OFFICIAL = {"STATUTE", "OFFICIAL"}


@api.post("/compliance/ask", response_model=S.ComplianceResponse, tags=["compliance"])
def ask(body: S.ComplianceQuery) -> S.ComplianceResponse:
    _require_ready()
    from sentinel.rag.assistant import ComplianceAssistant
    ans = ComplianceAssistant(store=plant.store).ask(body.question, k=body.top_k)
    return S.ComplianceResponse(
        question=ans.question, answer=ans.answer, backend=ans.backend,
        grounded=ans.grounded,
        citations=[S.Citation(
            standard=c.standard, section=c.section, provenance=c.provenance,
            is_official=c.provenance in _PROV_OFFICIAL, score=round(c.score, 4),
        ) for c in ans.chunks],
    )


# ----------------------------------------------------------------- workflow
@api.post("/workflow/run/{zone_id}", response_model=S.WorkflowResponse, tags=["workflow"])
def run_workflow(zone_id: str) -> S.WorkflowResponse:
    """Execute the multi-agent safety workflow against a zone's live state."""
    _require_ready()
    try:
        s = plant.zone_state(zone_id)
    except KeyError:
        raise HTTPException(404, f"unknown zone '{zone_id}'")

    from sentinel.agents.graph import run_safety_workflow
    drivers = "; ".join(d["label"] for d in s["drivers"][:4]) or "n/a"
    result = run_safety_workflow({
        "zone": s["name"], "machine_id": zone_id, "risk": s["risk"],
        "lead_time_min": s["lead_time_min"] or 0,
        "anomaly_score": s["anomaly_score"], "explanation": drivers,
        "gas_lel": s["gas_lel"], "gas_trend": s["gas_trend"],
        "maintenance_active": s["maintenance_active"],
        "hot_work_active": s["hot_work_active"],
        "workers_in_zone": s["workers_in_zone"],
        "night_shift": s["night_shift"], "in_changeover": s["in_changeover"],
    })

    comp = result.get("compliance")
    comp_model = None
    if comp:
        comp_model = S.ComplianceResponse(
            question=comp.get("question", ""), answer=comp.get("answer", ""),
            backend=comp.get("backend", "none"), grounded=comp.get("grounded", False),
            citations=[],
        )
    pdec = result.get("permit_decision")
    return S.WorkflowResponse(
        zone_id=zone_id,
        trace=result.get("trace", []),
        priority=(result.get("priority") or {}).get("priority"),
        permit_decision=S.PermitDecisionResponse(**pdec) if pdec else None,
        interlocks=result.get("interlocks", []),
        compliance=comp_model,
        actions=result.get("actions", []),
        report=result.get("report"),
    )


# ------------------------------------------------------------------ analytics
def _scoreboard_dict() -> dict | None:
    path = ROOT / "reports" / "scoreboard.json"
    return json.loads(path.read_text()) if path.exists() else None


@api.get("/analytics/kpis", tags=["analytics"])
def analytics_kpis() -> dict:
    """Headline KPIs tagged leading vs lagging (3:1 ratio is the target)."""
    _require_ready()
    from sentinel.analytics import kpi_summary
    return kpi_summary(plant.zone_states(), _scoreboard_dict())


@api.get("/analytics/tiers", tags=["analytics"])
def analytics_tiers() -> dict:
    """Current conditions classified into the API RP 754 tier structure."""
    _require_ready()
    from sentinel.analytics import tier_events
    return tier_events(plant.zone_states(), _scoreboard_dict())


@api.get("/analytics/alarm-performance", tags=["analytics"])
def analytics_alarms() -> dict:
    """Alarm load benchmarked against EEMUA 191 / ISA-18.2."""
    from sentinel.analytics import alarm_performance
    return alarm_performance(_scoreboard_dict())


@api.get("/analytics/risk-distribution", tags=["analytics"])
def analytics_distribution() -> dict:
    _require_ready()
    from sentinel.analytics import risk_distribution
    return risk_distribution(plant.zone_states())


@api.get("/analytics/trend", tags=["analytics"])
def analytics_trend(window: int = Query(120, ge=20, le=240)) -> list[dict]:
    _require_ready()
    from sentinel.analytics import risk_trend
    series = {z.zone_id: z.proba for z in plant.zones}
    return risk_trend(series, plant.minute, window)


@api.get("/analytics/contributing-factors", tags=["analytics"])
def analytics_factors(top: int = Query(10, ge=3, le=20)) -> list[dict]:
    _require_ready()
    from sentinel.analytics import contributing_factors
    return contributing_factors(plant.model, top=top)


# ---------------------------------------------------------------- evaluation
@api.get("/evaluation/scoreboard", response_model=S.ScoreboardResponse, tags=["evaluation"])
def scoreboard() -> S.ScoreboardResponse:
    """The baseline-vs-compound evidence produced by scripts/run_pipeline.py."""
    path = ROOT / "reports" / "scoreboard.json"
    legacy = ROOT / "reports" / "row_metrics.json"
    if not path.exists():
        raise HTTPException(
            404, "no scoreboard.json — run scripts/run_pipeline.py to generate it"
            + (" (row_metrics.json found, but it is a different report)" if legacy.exists() else "")
        )
    return S.ScoreboardResponse(**json.loads(path.read_text()))


app.include_router(api)


@app.exception_handler(HTTPException)
async def problem_detail(request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"type": f"https://sentinel.ai/errors/{exc.status_code}",
                 "title": exc.detail, "status": exc.status_code,
                 "instance": str(request.url.path)},
    )


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"service": "SentinelAI", "version": __version__, "docs": "/docs"}
