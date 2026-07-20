"""Sensitivity analysis: is the compound advantage an artefact of one parameter?

The most direct attack on this project is: *"you tuned the sensor attenuation until
the single-sensor baseline lost."* Attenuation controls how much of the true zone gas
the one point sensor actually sees, so it is the parameter that most directly decides
whether the baseline fails. This script sweeps it and reports the answer honestly,
including if the answer is unflattering.

Two arms, because they answer different questions:

    HELD  - one model trained once at the default operating regime, then evaluated at
            every attenuation level. Answers: does the deployed model stay useful when
            sensor quality differs from what it was trained on? (robustness)

    RETRAIN - a fresh model trained at each level. Answers: what is achievable if the
            model is fitted to that plant's own sensor quality? (attainable ceiling)

Both arms compare against the baseline at a MATCHED false-alarm rate, because a low
fixed-threshold alarm can always buy detection by alarming more; comparing at each
system's own operating point would be meaningless.

Run:  .venv\\Scripts\\python.exe scripts\\sensitivity_attenuation.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from sentinel import config as C
from sentinel.evaluation.harness import episode_signals, operating_curve
from sentinel.ml.baseline import baseline_alarm_series
from sentinel.ml.features import build_features, label_rows
from sentinel.ml.forecaster import CompoundRiskForecaster

LEVELS = [0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95]
N_TRAIN, N_TEST = 400, 180
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)


def _feature_table(raw: pd.DataFrame) -> pd.DataFrame:
    frames = [build_features(ep) for _, ep in raw.groupby("episode_id", sort=False)]
    return label_rows(pd.concat(frames, ignore_index=True))


def baseline_stats(raw: pd.DataFrame) -> dict:
    """Detection / false-alarm / lead for the single fixed-threshold gas alarm."""
    det = fa = n_inc = n_safe = 0
    lead_sum = 0.0
    for _, ep in raw.groupby("episode_id", sort=False):
        ep = ep.sort_values("minute").reset_index(drop=True)
        onset = int(ep["incident_onset"].iloc[0])
        had_leak = int(ep["leak_active"].max())
        mask = baseline_alarm_series(ep)
        minutes = ep["minute"].to_numpy()
        at = int(minutes[np.argmax(mask)]) if mask.any() else None
        if onset >= 0:
            n_inc += 1
            if at is not None and at < onset:
                det += 1
                lead_sum += onset - at
        elif had_leak == 0:
            n_safe += 1
            if at is not None:
                fa += 1
    return {
        "detection": det / max(n_inc, 1),
        "false_alarm": fa / max(n_safe, 1),
        "lead": lead_sum / max(det, 1),
        "n_incidents": n_inc,
        "n_safe": n_safe,
    }


def model_at_matched_fa(model, test_raw: pd.DataFrame, target_fa: float) -> dict:
    """Model performance at the operating point matching the baseline's nuisance rate."""
    curve = operating_curve(episode_signals(model, test_raw), n=60)
    row = curve.iloc[(curve["false_alarm"] - target_fa).abs().idxmin()]
    return {
        "detection": float(row["detection"]),
        "false_alarm": float(row["false_alarm"]),
        "lead": float(row["lead"]),
        "threshold": float(row["threshold"]),
    }


def main():
    print(">> training the HELD model once at the default regime ...")
    held_train = _feature_table(__import__("sentinel.sim", fromlist=["generate_dataset"])
                               .generate_dataset(N_TRAIN, seed=C.GLOBAL_SEED))
    held_model = CompoundRiskForecaster().fit(held_train, held_train)

    from sentinel.sim import generate_dataset

    rows = []
    for level in LEVELS:
        print(f">> attenuation = {level:.2f}")
        test_raw = generate_dataset(N_TEST, seed=C.GLOBAL_SEED + 2,
                                    attenuation_override=level)
        base = baseline_stats(test_raw)

        held = model_at_matched_fa(held_model, test_raw, base["false_alarm"])

        train_raw = generate_dataset(N_TRAIN, seed=C.GLOBAL_SEED,
                                     attenuation_override=level)
        retrain_model = CompoundRiskForecaster()
        tr = _feature_table(train_raw)
        retrain_model.fit(tr, tr)
        retrain = model_at_matched_fa(retrain_model, test_raw, base["false_alarm"])

        rows.append({
            "attenuation": level,
            "n_incidents": base["n_incidents"],
            "baseline_detection": base["detection"],
            "baseline_false_alarm": base["false_alarm"],
            "baseline_lead": base["lead"],
            "held_detection": held["detection"],
            "held_lead": held["lead"],
            "retrain_detection": retrain["detection"],
            "retrain_lead": retrain["lead"],
            "advantage_held": held["detection"] - base["detection"],
            "advantage_retrain": retrain["detection"] - base["detection"],
        })
        r = rows[-1]
        print(f"   baseline {r['baseline_detection']:.1%} | held {r['held_detection']:.1%} "
              f"| retrain {r['retrain_detection']:.1%} "
              f"(fa matched at {base['false_alarm']:.1%})")

    df = pd.DataFrame(rows)
    df.to_csv(REPORTS / "sensitivity_attenuation.csv", index=False)

    # ---- verdict ---------------------------------------------------------
    holds = df[df["advantage_retrain"] > 0.05]
    verdict = {
        "levels_tested": LEVELS,
        "levels_where_advantage_exceeds_5pts": holds["attenuation"].tolist(),
        "min_advantage_retrain": float(df["advantage_retrain"].min()),
        "max_advantage_retrain": float(df["advantage_retrain"].max()),
        "advantage_holds_at_high_attenuation": bool(
            df[df["attenuation"] >= 0.85]["advantage_retrain"].min() > 0.05
        ) if len(df[df["attenuation"] >= 0.85]) else None,
    }
    (REPORTS / "sensitivity_verdict.json").write_text(json.dumps(verdict, indent=2))

    print("\n" + "=" * 78)
    print("  SENSITIVITY VERDICT -- does the advantage survive across sensor quality?")
    print("=" * 78)
    print(df.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print("-" * 78)
    print(f"  advantage (retrained) ranges "
          f"{verdict['min_advantage_retrain']:+.1%} to {verdict['max_advantage_retrain']:+.1%}")
    print(f"  holds (>5 pts) at attenuation levels: "
          f"{verdict['levels_where_advantage_exceeds_5pts']}")
    print(f"  survives at well-placed sensors (>=0.85): "
          f"{verdict['advantage_holds_at_high_attenuation']}")
    print("=" * 78)

    _plot(df, REPORTS / "sensitivity_attenuation.png")
    print(f"\n>> artifacts -> {REPORTS}")


def _plot(df: pd.DataFrame, path: Path):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.6))

    ax1.plot(df["attenuation"], df["baseline_detection"] * 100, "o-",
             color="#c0392b", label="single-sensor baseline")
    ax1.plot(df["attenuation"], df["held_detection"] * 100, "s--",
             color="#2980b9", label="SentinelAI (trained once)")
    ax1.plot(df["attenuation"], df["retrain_detection"] * 100, "^-",
             color="#1e8449", label="SentinelAI (retrained per level)")
    ax1.set_xlabel("point-sensor attenuation (fraction of true gas seen)")
    ax1.set_ylabel("incident detection (%)")
    ax1.set_title("Detection vs sensor quality\n(compared at matched false-alarm rate)")
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.2)

    ax2.axhline(0, color="#888", lw=1)
    ax2.axhline(5, color="#1e8449", ls=":", lw=1, label="5 pt advantage")
    ax2.plot(df["attenuation"], df["advantage_retrain"] * 100, "^-",
             color="#1e8449", label="advantage (retrained)")
    ax2.plot(df["attenuation"], df["advantage_held"] * 100, "s--",
             color="#2980b9", label="advantage (trained once)")
    ax2.set_xlabel("point-sensor attenuation")
    ax2.set_ylabel("detection advantage over baseline (pts)")
    ax2.set_title("Where does the compound advantage survive?")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.2)

    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    main()
