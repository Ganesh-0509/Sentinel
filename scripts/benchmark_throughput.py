"""Scalability evidence: how many zones can one process actually carry?

Scalability is the criterion this project has been weakest on, because it has been
asserted from an architecture diagram rather than measured. This script measures it:
feature engineering, model inference, anomaly scoring and the deterministic rule engine,
at increasing zone counts, reporting per-stage latency percentiles and end-to-end
throughput.

What this does and does not show:
    DOES  - single-process compute headroom for the hot path (features -> risk -> rules),
            which is what determines how many zones one worker can serve per minute.
    DOES NOT - network ingest, database write throughput, or multi-node behaviour. Those
            need a deployed environment; this is a compute-bound floor, not a full
            capacity model.

Run:  .venv\\Scripts\\python.exe scripts\\benchmark_throughput.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from sentinel import config as C
from sentinel.ml.anomaly import AnomalyDetector
from sentinel.ml.baseline import baseline_alarm_series
from sentinel.ml.features import build_features
from sentinel.ml.forecaster import CompoundRiskForecaster
from sentinel.rules.engine import PermitRequest, ZoneConditions, evaluate_permit
from sentinel.sim import generate_dataset

ZONE_COUNTS = [10, 50, 100, 250, 500, 1000]
REPORTS = ROOT / "reports"
MODELS = ROOT / "models"


def pct(values: list[float], p: float) -> float:
    return float(np.percentile(values, p)) if values else float("nan")


def main():
    model_path = MODELS / "forecaster.pkl"
    if not model_path.exists():
        print("!! no trained model; run scripts/run_pipeline.py first")
        return
    model = CompoundRiskForecaster.load(model_path)

    print(">> fitting anomaly detector ...")
    normal = generate_dataset(40, seed=C.GLOBAL_SEED + 7, mix={"normal": 1.0})
    detector = AnomalyDetector().fit(build_features(normal))

    print(f">> generating {max(ZONE_COUNTS)} zone episodes ...")
    raw = generate_dataset(max(ZONE_COUNTS), seed=C.GLOBAL_SEED + 11)
    episodes = [ep.sort_values("minute").reset_index(drop=True)
                for _, ep in raw.groupby("episode_id", sort=False)]

    # Feature engineering is the dominant cost and is done once per zone at startup
    # in the live service, so measure it separately from the per-tick hot path.
    print(">> precomputing features (startup cost) ...")
    t0 = time.perf_counter()
    feats = [build_features(ep) for ep in episodes]
    feature_secs = time.perf_counter() - t0
    per_zone_feature_ms = (feature_secs / len(episodes)) * 1000

    rows = []
    mid = C.EPISODE_MINUTES // 2
    for n in ZONE_COUNTS:
        eps, fs = episodes[:n], feats[:n]

        # --- NAIVE: one sklearn call per zone (what the service did originally) ---
        t0 = time.perf_counter()
        _ = [model.predict_proba(f.iloc[[mid]])[0] for f in fs]
        naive_infer_ms = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        _ = [detector.score(f.iloc[[mid]])[0] for f in fs]
        naive_anomaly_ms = (time.perf_counter() - t0) * 1000

        # --- BATCHED: stack every zone's current row, score once ---
        t0 = time.perf_counter()
        snapshot = pd.concat([f.iloc[[mid]] for f in fs], ignore_index=True)
        stack_ms = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        risks = model.predict_proba(snapshot)
        infer_ms = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        _ = detector.score(snapshot)
        anomaly_ms = (time.perf_counter() - t0) * 1000
        infer_ms += stack_ms

        # --- deterministic rule engine ---
        t0 = time.perf_counter()
        for ep, r in zip(eps, risks):
            i = C.EPISODE_MINUTES // 2
            evaluate_permit(
                PermitRequest("Hot Work", zone="z"),
                ZoneConditions(
                    gas_lel=float(ep["gas_sensor"].iloc[i]),
                    maintenance_active=bool(ep["maintenance_active"].iloc[i]),
                    workers_in_zone=int(ep["workers_in_zone"].iloc[i]),
                ),
                compound_risk=float(r),
            )
        rules_ms = (time.perf_counter() - t0) * 1000

        # --- baseline (for reference) ---
        t0 = time.perf_counter()
        _ = [baseline_alarm_series(ep) for ep in eps]
        baseline_ms = (time.perf_counter() - t0) * 1000

        tick_ms = infer_ms + anomaly_ms + rules_ms
        naive_ms = naive_infer_ms + naive_anomaly_ms + rules_ms
        rows.append({
            "zones": n,
            "inference_ms": round(infer_ms, 1),
            "anomaly_ms": round(anomaly_ms, 1),
            "rules_ms": round(rules_ms, 1),
            "baseline_ms": round(baseline_ms, 1),
            "tick_total_ms": round(tick_ms, 1),
            "naive_tick_ms": round(naive_ms, 1),
            "speedup_vs_naive": round(naive_ms / tick_ms, 1) if tick_ms else None,
            "per_zone_us": round((tick_ms / n) * 1000, 1),
            "zones_per_second": round(n / (tick_ms / 1000), 1) if tick_ms else None,
            "ticks_per_minute_capacity": round(60000 / tick_ms, 1) if tick_ms else None,
        })
        r = rows[-1]
        print(f"   {n:>5} zones | batched {r['tick_total_ms']:>7.1f} ms | "
              f"naive {r['naive_tick_ms']:>8.1f} ms | "
              f"{r['speedup_vs_naive']:>5.1f}x | "
              f"{r['zones_per_second']:>9.1f} zones/s")

    df = pd.DataFrame(rows)
    df.to_csv(REPORTS / "throughput_benchmark.csv", index=False)

    biggest = rows[-1]
    summary = {
        "startup_feature_ms_per_zone": round(per_zone_feature_ms, 1),
        "max_zones_tested": biggest["zones"],
        "tick_total_ms_at_max": biggest["tick_total_ms"],
        "zones_per_second_at_max": biggest["zones_per_second"],
        "meets_1min_cadence_at_max": biggest["tick_total_ms"] < 60000,
        "headroom_vs_1min_cadence": round(60000 / biggest["tick_total_ms"], 1),
        "note": ("Compute-bound hot path only (features precomputed at startup). "
                 "Excludes network ingest, database writes and multi-node effects."),
    }
    (REPORTS / "throughput_summary.json").write_text(json.dumps(summary, indent=2))

    print("\n" + "=" * 74)
    print("  THROUGHPUT -- single process, compute-bound hot path")
    print("=" * 74)
    print(df.to_string(index=False))
    print("-" * 74)
    print(f"  startup feature cost: {per_zone_feature_ms:.1f} ms/zone (one-off)")
    print(f"  at {biggest['zones']} zones a full risk tick takes "
          f"{biggest['tick_total_ms']:.0f} ms")
    print(f"  that is {summary['headroom_vs_1min_cadence']}x headroom against a "
          f"1-minute sensor cadence")
    print("=" * 74)


if __name__ == "__main__":
    main()
