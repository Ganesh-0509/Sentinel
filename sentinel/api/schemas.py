"""Pydantic v2 request/response models.

Every field is typed, bounded and documented so the generated OpenAPI contract is
usable as the integration spec for a plant IT team -- not just a debug page.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PermitType = Literal["Hot Work", "Confined Space", "Cold Work", "Electrical"]
PermitStatus = Literal["APPROVED", "CONDITIONAL", "REJECTED"]
Priority = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    model_loaded: bool
    llm_backend: str = Field(description="gemini | ollama | extractive")
    regulation_chunks: int


class ZoneReading(BaseModel):
    """A single point in a zone's live telemetry."""
    model_config = ConfigDict(json_schema_extra={"example": {
        "minute": 58, "gas_lel": 4.5, "pressure": 8.4,
        "temperature": 57.2, "vibration": 1.8, "risk": 0.96,
    }})

    minute: int = Field(ge=0, description="Minutes since episode start")
    gas_lel: float = Field(ge=0, description="Point-sensor combustible gas, % LEL")
    pressure: float = Field(description="Line pressure, bar")
    temperature: float = Field(description="Zone temperature, degrees C")
    vibration: float = Field(ge=0, description="Equipment vibration index")
    risk: float = Field(ge=0, le=1, description="P(incident within forecast horizon)")


class ShapDriver(BaseModel):
    feature: str
    label: str = Field(description="Human-readable feature name")
    contribution: float = Field(description="Signed SHAP value; >0 increases risk")


class ZoneState(BaseModel):
    """Everything the dashboard needs to render one zone."""
    zone_id: str
    name: str
    x: float = Field(description="Floor-plan X coordinate (0-100)")
    y: float = Field(description="Floor-plan Y coordinate (0-100)")
    risk: float = Field(ge=0, le=1)
    risk_band: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    gas_lel: float
    gas_trend: float = Field(description="% LEL per minute; >0 is rising")
    pressure: float
    temperature: float
    anomaly_score: float
    workers_in_zone: int = Field(ge=0)
    maintenance_active: bool
    hot_work_active: bool
    night_shift: bool
    in_changeover: bool
    lead_time_min: int | None = Field(
        default=None, description="Predicted minutes to threshold crossing")
    baseline_alarm: bool = Field(
        description="Would a conventional single-sensor alarm be firing right now?")
    drivers: list[ShapDriver] = Field(default_factory=list)


class AlertItem(BaseModel):
    alert_id: str
    zone_id: str
    zone_name: str
    priority: Priority
    score: float
    risk: float
    lead_time_min: int | None = None
    drivers: list[str] = Field(default_factory=list)
    raised_at: datetime


class PermitDecisionResponse(BaseModel):
    status: PermitStatus
    reasons: list[str]
    citations: list[str]


class PermitRequestBody(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {
        "permit_type": "Hot Work", "zone_id": "COB-B",
        "machine_id": "COB-B-07", "use_ai_risk": True,
    }})

    permit_type: PermitType
    zone_id: str
    machine_id: str = ""
    use_ai_risk: bool = Field(
        default=True,
        description="Allow the compound-risk model to escalate the decision. "
                    "It can only make the outcome stricter, never more permissive.")


class ComplianceQuery(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {
        "question": "Can hot work continue if gas readings are rising?"}})
    question: str = Field(min_length=5, max_length=500)
    top_k: int = Field(default=4, ge=1, le=10)


class Citation(BaseModel):
    standard: str
    section: str
    provenance: Literal["STATUTE", "OFFICIAL", "SUMMARY", "REFERENCE_ONLY"]
    is_official: bool
    score: float


class ComplianceResponse(BaseModel):
    question: str
    answer: str
    citations: list[Citation]
    backend: str
    grounded: bool = Field(
        description="False when no passage was relevant; the assistant then declines "
                    "to answer rather than drawing on model memory.")


class WorkflowResponse(BaseModel):
    zone_id: str
    trace: list[str] = Field(description="Ordered agent execution trace")
    priority: Priority | None = None
    permit_decision: PermitDecisionResponse | None = None
    interlocks: list[str] = Field(default_factory=list)
    compliance: ComplianceResponse | None = None
    actions: list[str] = Field(default_factory=list)
    report: str | None = Field(default=None, description="Draft regulatory notification")


class ScoreboardResponse(BaseModel):
    """Baseline vs compound engine — the evaluation evidence."""
    n_episodes: int
    n_incident_episodes: int
    n_safe_episodes: int
    baseline_detection_rate: float
    compound_detection_rate: float
    baseline_false_negative_rate: float
    compound_false_negative_rate: float
    baseline_false_alarm_rate: float
    compound_false_alarm_rate: float
    matched_baseline_lead_min: float | None = None
    matched_compound_lead_min: float | None = None
    incidents_missed_by_baseline_caught_by_compound: int
