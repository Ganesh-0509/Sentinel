"""Phase 3 demo: the full agentic pipeline on a Vizag-style compound event.

Chains everything built so far:
    simulator -> features -> compound forecaster -> SHAP -> anomaly
             -> LangGraph agents (risk / permit / compliance / emergency)

Run:  .venv\\Scripts\\python.exe scripts\\phase3_demo.py
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np

from sentinel import config as C
from sentinel.agents.graph import run_safety_workflow
from sentinel.ml.anomaly import AnomalyDetector
from sentinel.ml.explain import RiskExplainer
from sentinel.ml.features import build_features
from sentinel.ml.forecaster import CompoundRiskForecaster
from sentinel.sim.simulator import generate_dataset, simulate_episode

MODELS = ROOT / "models"


def _wrap(text, indent="     "):
    return "\n".join(textwrap.fill(line, 92, initial_indent=indent,
                                   subsequent_indent=indent)
                     for line in text.splitlines() if line.strip())


def _pick_episode(rng):
    for _ in range(400):
        ep = simulate_episode("compound_hidden", rng, episode_id=0)
        if int(ep["incident_onset"].iloc[0]) > 40 and ep["hot_work_permit"].sum() > 0:
            return ep
    return simulate_episode("compound_hidden", rng, episode_id=0)


def main():
    model_path = MODELS / "forecaster.pkl"
    if not model_path.exists():
        print("!! no trained model. Run scripts/run_pipeline.py first.")
        return
    model = CompoundRiskForecaster.load(model_path)
    explainer = RiskExplainer(model)
    rng = np.random.default_rng(C.GLOBAL_SEED + 5)

    print(">> fitting anomaly detector on normal operation ...")
    normal = generate_dataset(120, seed=C.GLOBAL_SEED + 7, mix={"normal": 1.0})
    anomaly = AnomalyDetector().fit(build_features(normal))

    ep = _pick_episode(rng)
    onset = int(ep["incident_onset"].iloc[0])
    feats = build_features(ep)
    proba = model.predict_proba(feats)
    minutes = feats["minute"].to_numpy()

    fired = proba >= model.threshold
    if not fired.any():
        print("!! model did not alert on this draw; rerun.")
        return
    i = int(np.argmax(fired))
    alert_t = int(minutes[i])
    lead = onset - alert_t
    row = feats.iloc[[i]]

    print("\n" + "=" * 96)
    print("  SENTINELAI  --  PHASE 3: AGENTIC SAFETY WORKFLOW")
    print("=" * 96)
    print(f"  Scenario   : hidden compound event (leak + maintenance + hot work, "
          f"attenuated gas sensor)")
    print(f"  Incident   : physical threshold crossed at minute {onset}")
    print(f"  Detection  : compound risk {proba[i]:.0%} at minute {alert_t}  "
          f"-->  {lead} MIN LEAD TIME")
    print(f"  Point sensor reads only {float(ep['gas_sensor'].iloc[i]):.1f} %LEL "
          f"(true zone gas {float(ep['gas_true'].iloc[i]):.1f} %LEL) "
          f"-- a single-sensor alarm stays silent")
    print(f"  Anomaly    : {anomaly.score(row)[0]:.1f}")
    print(f"  SHAP why   : {explainer.explanation_text(row, top=4)}")
    print("-" * 96)

    state = {
        "zone": "Coke-Oven-Battery-B",
        "machine_id": "COB-B-07",
        "risk": float(proba[i]),
        "lead_time_min": int(lead),
        "anomaly_score": float(anomaly.score(row)[0]),
        "explanation": explainer.explanation_text(row, top=4),
        "gas_lel": float(ep["gas_sensor"].iloc[i]),
        "gas_trend": float(row["gas_trend"].iloc[0]),
        "maintenance_active": bool(ep["maintenance_active"].iloc[i]),
        "hot_work_active": bool(ep["hot_work_permit"].iloc[i]),
        "workers_in_zone": int(ep["workers_in_zone"].iloc[i]),
        "night_shift": bool(ep["night_shift"].iloc[i]),
        "in_changeover": bool(ep["in_changeover"].iloc[i]),
    }

    print("  AGENT TRACE")
    result = run_safety_workflow(state)
    for line in result.get("trace", []):
        print(f"   {line}")

    pd_ = result.get("permit_decision", {})
    print("\n  PERMIT DECISION: " + pd_.get("status", "n/a"))
    for r in pd_.get("reasons", []):
        print(_wrap(f"- {r}"))
    for c in pd_.get("citations", []):
        print(f"     [cite] {c}")

    for v in result.get("interlocks", []):
        print(f"\n  !! INTERLOCK: {v}")

    comp = result.get("compliance", {})
    if comp.get("answer"):
        print("\n  COMPLIANCE (RAG-grounded):")
        print(_wrap(comp["answer"]))
        for c in comp.get("citations", []):
            print(f"     [cite] {c}")

    if result.get("actions"):
        print("\n  ACTIONS INITIATED:")
        for a in result["actions"]:
            print(_wrap(f"- {a}"))

    if result.get("report"):
        print("\n  DRAFT REGULATORY NOTIFICATION:")
        print(_wrap(result["report"]))

    print("=" * 96 + "\n")


if __name__ == "__main__":
    main()
