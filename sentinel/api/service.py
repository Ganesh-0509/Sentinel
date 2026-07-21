"""Live plant state service.

Holds one running episode per zone, precomputes the model outputs once at startup,
then serves a moving "now" pointer. Swapping the simulator for a live SCADA feed
means replacing `_load_zones` only -- everything downstream is unchanged.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from sentinel import config as C
from sentinel.decision.priority import AlertContext, prioritise
from sentinel.ml.anomaly import AnomalyDetector
from sentinel.ml.baseline import baseline_alarm_series
from sentinel.ml.explain import RiskExplainer
from sentinel.ml.features import build_features
from sentinel.ml.forecaster import CompoundRiskForecaster
from sentinel.sim.simulator import generate_dataset, simulate_episode

ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "models" / "forecaster.pkl"

# Plant layout: floor-plan coordinates on a 0-100 grid.
ZONE_LAYOUT = [
    ("COB-A", "Coke Oven Battery A", 18, 24, "gas_leak_visible"),
    ("COB-B", "Coke Oven Battery B", 38, 24, "compound_hidden"),
    ("BYP-1", "By-Product Plant", 62, 20, "normal"),
    ("GAS-H", "Gas Holder Yard", 84, 30, "normal"),
    ("SIN-1", "Sinter Plant", 20, 58, "maintenance_no_leak"),
    ("BLF-2", "Blast Furnace 2", 46, 62, "compound_hidden"),
    ("PWR-1", "Power & Blowing Stn", 72, 60, "normal"),
    ("TNK-3", "Tank Farm 3", 30, 86, "gas_leak_visible"),
]

RISK_BANDS = [(0.30, "LOW"), (0.60, "MEDIUM"), (0.85, "HIGH")]


def _band(risk: float) -> str:
    for edge, name in RISK_BANDS:
        if risk < edge:
            return name
    return "CRITICAL"


@dataclass
class ZoneRuntime:
    zone_id: str
    name: str
    x: float
    y: float
    episode: pd.DataFrame
    features: pd.DataFrame
    proba: np.ndarray
    anomaly: np.ndarray
    baseline: np.ndarray


class PlantService:
    """Singleton-ish holder for models + live zone state."""

    def __init__(self):
        self._lock = threading.Lock()
        self.minute = 0
        self.model: CompoundRiskForecaster | None = None
        self.explainer: RiskExplainer | None = None
        self.detector: AnomalyDetector | None = None
        self.zones: list[ZoneRuntime] = []
        self.store = None
        self.ready = False
        self.error: str | None = None

    # ------------------------------------------------------------------ setup
    def startup(self) -> None:
        try:
            if not MODEL_PATH.exists():
                self.error = ("no trained model at models/forecaster.pkl -- "
                              "run scripts/run_pipeline.py first")
                return
            self.model = CompoundRiskForecaster.load(MODEL_PATH)
            self.explainer = RiskExplainer(self.model)

            normal = generate_dataset(60, seed=C.GLOBAL_SEED + 7, mix={"normal": 1.0})
            self.detector = AnomalyDetector().fit(build_features(normal))

            self._load_zones()

            from sentinel.rag.store import RegulationStore
            self.store = RegulationStore().build()
            self.ready = True
        except Exception as e:                       # surface, don't crash the API
            self.error = f"{type(e).__name__}: {e}"

    def _load_zones(self) -> None:
        rng = np.random.default_rng(C.GLOBAL_SEED + 31)
        zones = []
        for i, (zid, name, x, y, scenario) in enumerate(ZONE_LAYOUT):
            ep = simulate_episode(scenario, rng, episode_id=i)
            feats = build_features(ep)
            zones.append(ZoneRuntime(
                zone_id=zid, name=name, x=x, y=y,
                episode=ep, features=feats,
                proba=self.model.predict_proba(feats),
                anomaly=self.detector.score(feats),
                baseline=baseline_alarm_series(ep),
            ))
        self.zones = zones

    # ------------------------------------------------------------------ clock
    def tick(self, steps: int = 1) -> int:
        with self._lock:
            horizon = min(len(z.features) for z in self.zones) if self.zones else 1
            self.minute = (self.minute + steps) % horizon
            return self.minute

    def set_minute(self, minute: int) -> int:
        with self._lock:
            horizon = min(len(z.features) for z in self.zones) if self.zones else 1
            self.minute = max(0, min(minute, horizon - 1))
            return self.minute

    # ------------------------------------------------------------------ state
    def _lead_time(self, z: ZoneRuntime, i: int) -> int | None:
        """Projected minutes to threshold, from OBSERVABLE signals only.

        This must never read `incident_onset`. That column is the simulator's hidden
        ground truth; in a live plant the remaining time to an incident is precisely
        the thing nobody knows. Reporting it would make the dashboard look prescient
        while being unimplementable in the field.

        What we can honestly say has two parts:
          1. The model's own claim -- it predicts an incident within PRIMARY_HORIZON,
             so that horizon is the upper bound on the estimate.
          2. A physical extrapolation -- the observed gas reading rising at the observed
             trend reaches the alarm limit in (limit - gas) / trend minutes.

        We report the tighter of the two, floored at one minute. Both inputs are
        available from the sensor feed alone.
        """
        if self.model is None or z.proba[i] < self.model.threshold:
            return None

        gas = float(z.episode["gas_sensor"].iloc[i])
        trend = float(z.features["gas_trend"].iloc[i])      # %LEL per minute, observed

        projected = float(C.PRIMARY_HORIZON)
        if trend > 0.01 and gas < C.GAS_HIGH_ALARM:
            projected = (C.GAS_HIGH_ALARM - gas) / trend

        return int(max(1, min(projected, C.PRIMARY_HORIZON)))

    def zone_states(self) -> list[dict]:
        i = self.minute
        out = []
        for z in self.zones:
            row = z.features.iloc[[i]]
            ep = z.episode
            drivers = []
            if self.explainer is not None and z.proba[i] >= 0.25:
                from sentinel.ml.explain import _READABLE
                for feat, val in self.explainer.explain_row(row, top=5):
                    drivers.append({"feature": feat,
                                    "label": _READABLE.get(feat, feat),
                                    "contribution": round(float(val), 4)})
            out.append({
                "zone_id": z.zone_id, "name": z.name, "x": z.x, "y": z.y,
                "risk": round(float(z.proba[i]), 4),
                "risk_band": _band(float(z.proba[i])),
                "gas_lel": round(float(ep["gas_sensor"].iloc[i]), 2),
                "gas_trend": round(float(row["gas_trend"].iloc[0]), 3),
                "pressure": round(float(ep["pressure"].iloc[i]), 2),
                "temperature": round(float(ep["temperature"].iloc[i]), 2),
                "anomaly_score": round(float(z.anomaly[i]), 2),
                "workers_in_zone": int(ep["workers_in_zone"].iloc[i]),
                "maintenance_active": bool(ep["maintenance_active"].iloc[i]),
                "hot_work_active": bool(ep["hot_work_permit"].iloc[i]),
                "night_shift": bool(ep["night_shift"].iloc[i]),
                "in_changeover": bool(ep["in_changeover"].iloc[i]),
                "lead_time_min": self._lead_time(z, i),
                "baseline_alarm": bool(z.baseline[i]),
                "drivers": drivers,
            })
        return out

    def zone_history(self, zone_id: str, window: int = 90) -> list[dict]:
        z = self._zone(zone_id)
        i = self.minute
        lo = max(0, i - window + 1)
        ep, f = z.episode, z.features
        return [{
            "minute": int(f["minute"].iloc[k]),
            "gas_lel": round(float(ep["gas_sensor"].iloc[k]), 2),
            "pressure": round(float(ep["pressure"].iloc[k]), 2),
            "temperature": round(float(ep["temperature"].iloc[k]), 2),
            "vibration": round(float(ep["vibration"].iloc[k]), 3),
            "risk": round(float(z.proba[k]), 4),
        } for k in range(lo, i + 1)]

    def _zone(self, zone_id: str) -> ZoneRuntime:
        for z in self.zones:
            if z.zone_id == zone_id:
                return z
        raise KeyError(zone_id)

    def alerts(self) -> list[dict]:
        now = datetime.now(timezone.utc)
        items = []
        for s in self.zone_states():
            if s["risk"] < 0.35:
                continue
            pr = prioritise(AlertContext(
                risk=s["risk"], workers_in_zone=s["workers_in_zone"],
                night_shift=s["night_shift"], in_changeover=s["in_changeover"],
                lead_time_min=s["lead_time_min"],
            ))
            items.append({
                "alert_id": f"{s['zone_id']}-{self.minute:04d}",
                "zone_id": s["zone_id"], "zone_name": s["name"],
                "priority": pr["priority"], "score": pr["score"],
                "risk": s["risk"], "lead_time_min": s["lead_time_min"],
                "drivers": pr["drivers"], "raised_at": now,
            })
        order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        items.sort(key=lambda a: (order[a["priority"]], -a["score"]))
        return items

    def zone_state(self, zone_id: str) -> dict:
        for s in self.zone_states():
            if s["zone_id"] == zone_id:
                return s
        raise KeyError(zone_id)


plant = PlantService()
