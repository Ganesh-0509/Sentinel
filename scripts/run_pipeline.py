"""End-to-end spine: simulate -> engineer -> train -> evaluate -> scoreboard.

Run from the repo root with the project venv:
    .venv\\Scripts\\python.exe scripts\\run_pipeline.py

Outputs (in ./reports and ./models):
    reports/scoreboard.txt        text scoreboard
    reports/scoreboard.png        baseline-vs-compound bar chart
    reports/episode_results.csv   per-episode detail
    reports/row_metrics.json      row-level ML metrics + feature importances
    models/forecaster.pkl         trained model
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# make the repo root importable regardless of cwd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from sentinel import config as C
from sentinel.sim import generate_dataset
from sentinel.ml.features import build_features, label_rows
from sentinel.ml.forecaster import CompoundRiskForecaster
from sentinel.evaluation.harness import (
    evaluate_episode, aggregate, scoreboard_text, tune_threshold,
)

N_TRAIN = 500
N_VALID = 120
N_TEST = 250

REPORTS = ROOT / "reports"
MODELS = ROOT / "models"
REPORTS.mkdir(exist_ok=True)
MODELS.mkdir(exist_ok=True)


def _feature_table(raw: pd.DataFrame) -> pd.DataFrame:
    frames = [build_features(ep) for _, ep in raw.groupby("episode_id", sort=False)]
    return label_rows(pd.concat(frames, ignore_index=True))


def main():
    print(">> simulating episodes ...")
    train_raw = generate_dataset(N_TRAIN, seed=C.GLOBAL_SEED)
    valid_raw = generate_dataset(N_VALID, seed=C.GLOBAL_SEED + 1)
    test_raw = generate_dataset(N_TEST, seed=C.GLOBAL_SEED + 2)

    print(">> engineering features + labels ...")
    train_df = _feature_table(train_raw)
    valid_df = _feature_table(valid_raw)

    print(f">> training compound forecaster on {len(train_df):,} rows "
          f"(positive rate {train_df['y'].mean():.3f}) ...")
    model = CompoundRiskForecaster().fit(train_df, valid_df)
    # refine the operating point at the episode level (detection + lead, fa-capped)
    tune_threshold(valid_raw, model, fa_cap=0.12)
    model.save(MODELS / "forecaster.pkl")
    print(f"   selected decision threshold = {model.threshold:.2f}")

    # row-level ML metrics on held-out test rows
    test_df = _feature_table(test_raw)
    row_metrics = model.evaluate_rows(test_df)
    row_metrics["top_features"] = model.feature_importance(top=12)
    (REPORTS / "row_metrics.json").write_text(json.dumps(row_metrics, indent=2))

    print(">> evaluating episode-level scoreboard ...")
    results = [evaluate_episode(ep, model)
               for _, ep in test_raw.groupby("episode_id", sort=False)]
    pd.DataFrame(results).to_csv(REPORTS / "episode_results.csv", index=False)
    agg = aggregate(results)

    board = scoreboard_text(agg)
    (REPORTS / "scoreboard.txt").write_text(board, encoding="utf-8")
    print("\n" + board + "\n")

    print("   row-level ML:  "
          f"ROC-AUC={row_metrics['roc_auc']:.3f}  "
          f"PR-AUC={row_metrics['pr_auc']:.3f}  "
          f"recall={row_metrics['recall']:.3f}  precision={row_metrics['precision']:.3f}")
    print("   top features: " +
          ", ".join(f"{k}" for k, _ in row_metrics["top_features"][:6]))

    _plot(agg, REPORTS / "scoreboard.png")
    print(f"\n>> artifacts written to {REPORTS}")


def _plot(agg: dict, path: Path):
    metrics = [
        ("Detection\nrate (%)", 100 * agg["baseline_detection_rate"], 100 * agg["compound_detection_rate"], True),
        ("False-neg\nrate (%)", 100 * agg["baseline_false_negative_rate"], 100 * agg["compound_false_negative_rate"], False),
        ("Lead time\n(matched, min)", agg["matched_baseline_lead_min"], agg["matched_compound_lead_min"], True),
        ("False-alarm\nrate (%)", 100 * agg["baseline_false_alarm_rate"], 100 * agg["compound_false_alarm_rate"], False),
    ]
    labels = [m[0] for m in metrics]
    base = [0 if m[1] != m[1] else m[1] for m in metrics]
    comp = [0 if m[2] != m[2] else m[2] for m in metrics]

    x = range(len(labels))
    w = 0.38
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar([i - w / 2 for i in x], base, w, label="Single-sensor baseline", color="#c0392b")
    ax.bar([i + w / 2 for i in x], comp, w, label="SentinelAI (compound)", color="#1e8449")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_title("SentinelAI vs single-sensor baseline  (green wins where taller for "
                 "detection/lead, shorter for false-neg/alarm)")
    ax.legend()
    for i, (b, c) in enumerate(zip(base, comp)):
        ax.text(i - w / 2, b, f"{b:.0f}", ha="center", va="bottom", fontsize=9)
        ax.text(i + w / 2, c, f"{c:.0f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    main()
