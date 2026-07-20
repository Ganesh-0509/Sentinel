"""Phase 2 demo: one Vizag-style compound episode through the full stack.

Shows, on a single timeline:
    * the compound risk trajectory + when SentinelAI raises the alert,
    * SHAP explanation at the moment of alert (why),
    * the deterministic rule-engine permit decision (hot work vs gas),
    * the unsupervised anomaly score.

Run:  .venv\\Scripts\\python.exe scripts\\phase2_demo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from sentinel import config as C
from sentinel.sim.simulator import simulate_episode, generate_dataset
from sentinel.ml.features import build_features, label_rows
from sentinel.ml.forecaster import CompoundRiskForecaster
from sentinel.ml.explain import RiskExplainer
from sentinel.ml.anomaly import AnomalyDetector
from sentinel.rules.engine import PermitRequest, ZoneConditions, evaluate_permit

REPORTS = ROOT / "reports"
MODELS = ROOT / "models"
REPORTS.mkdir(exist_ok=True)


def _load_or_train() -> CompoundRiskForecaster:
    path = MODELS / "forecaster.pkl"
    if path.exists():
        return CompoundRiskForecaster.load(path)
    print("   (no saved model -- training a quick one)")
    raw = generate_dataset(400, seed=C.GLOBAL_SEED)
    frames = [build_features(ep) for _, ep in raw.groupby("episode_id", sort=False)]
    train = label_rows(__import__("pandas").concat(frames, ignore_index=True))
    m = CompoundRiskForecaster().fit(train, train)
    m.save(path)
    return m


def _pick_compound_episode(rng) -> "object":
    for _ in range(200):
        ep = simulate_episode("compound_hidden", rng, episode_id=0)
        if int(ep["incident_onset"].iloc[0]) > 40 and ep["hot_work_permit"].sum() > 0:
            return ep
    return simulate_episode("compound_hidden", rng, episode_id=0)


def main():
    model = _load_or_train()
    rng = np.random.default_rng(C.GLOBAL_SEED + 99)

    # fit the anomaly detector on NORMAL operation only
    normal_raw = generate_dataset(150, seed=C.GLOBAL_SEED + 7, mix={"normal": 1.0})
    anomaly = AnomalyDetector().fit(build_features(normal_raw))
    explainer = RiskExplainer(model)

    ep = _pick_compound_episode(rng)
    onset = int(ep["incident_onset"].iloc[0])
    feats = build_features(ep)
    proba = model.predict_proba(feats)
    anomaly_score = anomaly.score(feats)
    minutes = feats["minute"].to_numpy()

    alert_idx = int(np.argmax(proba >= model.threshold)) if (proba >= model.threshold).any() else None
    alert_t = int(minutes[alert_idx]) if alert_idx is not None else None

    print("\n" + "=" * 70)
    print("  PHASE 2 DEMO  --  compound (hidden) incident replay")
    print("=" * 70)
    print(f"  Incident (explosion/toxic threshold) occurs at minute {onset}.")
    if alert_t is not None:
        lead = onset - alert_t
        print(f"  SentinelAI raises the compound alert at minute {alert_t} "
              f"-> {lead} min lead time.")
        row = feats.iloc[[alert_idx]]
        print(f"\n  WHY (SHAP): {explainer.explanation_text(row, top=5)}")
        print(f"  Anomaly z-score at alert: {anomaly_score[alert_idx]:.1f} "
              f"(>= {anomaly.threshold} = anomalous)")

        # deterministic permit decision at the alert moment
        gtrend = float(row['gas_trend'].iloc[0])
        cond = ZoneConditions(
            gas_lel=float(ep['gas_sensor'].iloc[alert_idx]),
            gas_trend=gtrend,
            maintenance_active=bool(ep['maintenance_active'].iloc[alert_idx]),
            workers_in_zone=int(ep['workers_in_zone'].iloc[alert_idx]),
        )
        decision = evaluate_permit(
            PermitRequest("Hot Work", zone="Coke-Oven-B"), cond,
            compound_risk=float(proba[alert_idx]), lead_time_min=lead,
        )
        print(f"\n  PERMIT AGENT -> Hot Work permit: {decision.status}")
        for r in decision.reasons:
            print(f"     - {r}")
        for c in decision.citations:
            print(f"     [cite] {c}")
    else:
        print("  (model did not alert on this episode -- rerun for another draw)")
    print("=" * 70)

    _plot(minutes, ep, proba, anomaly_score, onset, alert_t, model.threshold,
          REPORTS / "phase2_timeline.png")
    print(f"\n>> timeline chart -> {REPORTS / 'phase2_timeline.png'}\n")


def _plot(minutes, ep, proba, anomaly_score, onset, alert_t, thr, path):
    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.plot(minutes, ep["gas_sensor"].to_numpy(), color="#888", label="gas point-sensor (%LEL)")
    ax1.plot(minutes, ep["gas_true"].to_numpy(), color="#c0392b", ls="--", label="true zone gas (%LEL)")
    ax1.set_xlabel("minute")
    ax1.set_ylabel("gas (% LEL)")
    ax2 = ax1.twinx()
    ax2.plot(minutes, proba, color="#1e8449", lw=2, label="compound risk P(incident)")
    ax2.axhline(thr, color="#1e8449", ls=":", alpha=0.6)
    ax2.set_ylabel("compound risk")
    ax1.axvline(onset, color="black", lw=2, label="incident threshold")
    if alert_t is not None:
        ax1.axvline(alert_t, color="#1e8449", lw=2, ls="--", label="SentinelAI alert")
    ax1.set_title("Compound incident replay: risk rises before the threshold crossing")
    l1, la1 = ax1.get_legend_handles_labels()
    l2, la2 = ax2.get_legend_handles_labels()
    ax1.legend(l1 + l2, la1 + la2, loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    main()
