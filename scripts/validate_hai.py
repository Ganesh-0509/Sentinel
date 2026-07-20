"""External validation on the HAI ICS security benchmark.

HAI (HIL-based Augmented ICS) comes from a real industrial control testbed —
steam-turbine and pumped-storage hydropower generation — instrumented with 79 sensor
and actuator tags at 1 Hz. Training files are pure normal operation; test files contain
labelled attacks.

Why run this as well as TEP:
    TEP faults are *process* faults — a valve sticks, a feed composition drifts. HAI
    anomalies are *adversarial manipulations*, deliberately crafted to look like normal
    operation while pushing the process somewhere unsafe. They are stealthy by design.

    That makes HAI a strictly harder and complementary test. TEP asks "does the method
    find process abnormality?" HAI asks "does it find abnormality that is actively trying
    not to be found?" A method that only passes TEP might simply be a good change
    detector.

Same protocol as the TEP run, deliberately:
    * the AnomalyDetector is used unchanged, trained on normal operation only;
    * the alarm threshold is calibrated to a ~1 % false-alarm budget, not chosen post hoc;
    * detection is reported per-sample AND per-episode, because catching each distinct
      event matters more operationally than the raw fraction of flagged samples.

Data (not committed — ~36 MB):
    curl -sSL -o data/external/hai/train1.csv.gz \\
      https://raw.githubusercontent.com/icsdataset/hai/master/hai-21.03/train1.csv.gz
    curl -sSL -o data/external/hai/test1.csv.gz \\
      https://raw.githubusercontent.com/icsdataset/hai/master/hai-21.03/test1.csv.gz

Run:  .venv\\Scripts\\python.exe scripts\\validate_hai.py
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

from sentinel.ml.anomaly import AnomalyDetector
from sentinel.ml.external_features import (
    attack_episodes,
    build_generic_features,
    drop_constant_columns,
)

HAI = ROOT / "data" / "external" / "hai"
REPORTS = ROOT / "reports"

STRIDE = 10          # 1 Hz -> 10 s resolution; attacks last minutes, so nothing is lost
WINDOW = 10          # 100 s look-back, matching the plant pipeline's shape
TARGET_FAR = 0.01
LABEL_COLS = ["attack", "attack_P1", "attack_P2", "attack_P3"]


def load(name: str) -> pd.DataFrame:
    df = pd.read_csv(HAI / name, compression="gzip")
    df.columns = [c.strip() for c in df.columns]
    return df.iloc[::STRIDE].reset_index(drop=True)


def split(df: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    labels = (df["attack"].to_numpy().astype(int)
              if "attack" in df.columns else np.zeros(len(df), dtype=int))
    drop = [c for c in df.columns if c in LABEL_COLS or c.lower() == "time"]
    return df.drop(columns=drop), labels


def main():
    if not (HAI / "train1.csv.gz").exists():
        print(f"!! HAI data not found in {HAI} — see the docstring for the fetch commands")
        return

    print(">> loading HAI 21.03 ...")
    train_df, train_lab = split(load("train1.csv.gz"))
    test_df, test_lab = split(load("test1.csv.gz"))
    print(f"   train {train_df.shape}  (attack samples: {train_lab.sum()})")
    print(f"   test  {test_df.shape}  (attack samples: {test_lab.sum()}, "
          f"{test_lab.mean():.2%})")

    # keep only tags that actually move in training; align both sets to them
    train_df = drop_constant_columns(train_df)
    cols = [c for c in train_df.columns if c in test_df.columns]
    train_df, test_df = train_df[cols], test_df[cols]
    print(f"   using {len(cols)} live tags (constant tags dropped)")

    print(">> engineering features ...")
    Xtr = build_generic_features(train_df, window=WINDOW)
    Xte = build_generic_features(test_df, window=WINDOW)

    print(">> fitting anomaly detector on normal operation only ...")
    det = AnomalyDetector(features=list(Xtr.columns)).fit(Xtr)

    # calibrate on TRAINING normal data — the test set's normal segments are never
    # used to pick the threshold, so this stays an honest held-out measurement
    thr = float(np.quantile(det.score(Xtr), 1 - TARGET_FAR))
    scores = det.score(Xte)
    alarms = scores >= thr

    normal_mask = test_lab == 0
    attack_mask = test_lab == 1
    far = float(alarms[normal_mask].mean())
    sample_detection = float(alarms[attack_mask].mean()) if attack_mask.any() else float("nan")

    # Threshold-free separability. The operating point above was calibrated on TRAINING
    # normals; if the test run's normal operation sits at a different point, that budget
    # will not hold. AUC says whether the score separates attack from normal at all,
    # independent of where the line is drawn.
    from sklearn.metrics import average_precision_score, roc_auc_score
    auc = float(roc_auc_score(test_lab, scores)) if attack_mask.any() else float("nan")
    ap = float(average_precision_score(test_lab, scores)) if attack_mask.any() else float("nan")

    # Oracle reference: the threshold that WOULD have hit the 1% budget on this test run.
    # Selecting it uses test normals, so it is not an honest deployable number — it is
    # reported only to separate "the detector cannot separate" from "the threshold drifted".
    oracle_thr = float(np.quantile(scores[normal_mask], 1 - TARGET_FAR))
    oracle_alarms = scores >= oracle_thr
    oracle_far = float(oracle_alarms[normal_mask].mean())
    oracle_sample_detection = float(oracle_alarms[attack_mask].mean())
    oracle_episode_detection = sum(
        1 for s, e in attack_episodes(test_lab) if oracle_alarms[s:e].any()
    ) / max(len(attack_episodes(test_lab)), 1)

    episodes = attack_episodes(test_lab)
    ep_rows = []
    for i, (s, e) in enumerate(episodes, 1):
        seg = alarms[s:e]
        hit = bool(seg.any())
        delay = int(np.argmax(seg)) * STRIDE if hit else None
        ep_rows.append({
            "episode": i,
            "start_sample": int(s),
            "duration_min": round((e - s) * STRIDE / 60, 1),
            "detected": hit,
            "detection_delay_s": delay,
            "flagged_fraction": float(seg.mean()),
        })

    detected = [r for r in ep_rows if r["detected"]]
    ep_detection = len(detected) / max(len(ep_rows), 1)
    delays = [r["detection_delay_s"] for r in detected if r["detection_delay_s"] is not None]

    result = {
        "dataset": "HAI 21.03 (HIL-based Augmented ICS), train1 / test1",
        "resolution_s": STRIDE,
        "tags_used": len(cols),
        "threshold": thr,
        "false_alarm_rate": far,
        "sample_detection_rate": sample_detection,
        "episode_detection_rate": ep_detection,
        "n_episodes": len(ep_rows),
        "n_detected": len(detected),
        "median_detection_delay_s": float(np.median(delays)) if delays else None,
        "roc_auc": auc,
        "average_precision": ap,
        "oracle_threshold": oracle_thr,
        "oracle_false_alarm_rate": oracle_far,
        "oracle_sample_detection": oracle_sample_detection,
        "oracle_episode_detection": oracle_episode_detection,
        "episodes": ep_rows,
        "note": ("HAI anomalies are adversarial manipulations designed to resemble normal "
                 "operation, so this is a harder test than process-fault detection. "
                 "Like TEP, it validates detection of abnormality, not lead-time "
                 "forecasting — the attacks are injected, not developing hazards."),
    }
    (REPORTS / "hai_validation.json").write_text(json.dumps(result, indent=2))

    print("\n" + "=" * 74)
    print("  HAI EXTERNAL VALIDATION — anomaly detector, unchanged")
    print("=" * 74)
    print(f"  tags used                     : {len(cols)}")
    print(f"  false-alarm rate (normal)     : {far:.2%}")
    print(f"  per-sample detection          : {sample_detection:.1%}")
    print(f"  per-episode detection         : {ep_detection:.1%} "
          f"({len(detected)}/{len(ep_rows)} attacks)")
    if delays:
        print(f"  median detection delay        : {np.median(delays):.0f} s")
    print("-" * 74)
    print(f"  ROC-AUC (threshold-free)      : {auc:.4f}")
    print(f"  average precision             : {ap:.4f}")
    print(f"  [oracle] at a true 1% FAR     : {oracle_sample_detection:.1%} per-sample, "
          f"{oracle_episode_detection:.0%} per-episode")
    print(f"           (threshold picked on test normals — reference only, not deployable)")
    print("-" * 74)
    for r in ep_rows[:12]:
        mark = "OK " if r["detected"] else "MISS"
        d = f"{r['detection_delay_s']:>5}s" if r["detected"] else "    —"
        print(f"   {mark} episode {r['episode']:>2} | {r['duration_min']:>5.1f} min | "
              f"delay {d} | flagged {r['flagged_fraction']:.0%}")
    if len(ep_rows) > 12:
        print(f"   ... and {len(ep_rows) - 12} more")
    print("=" * 74)

    _plot(scores, test_lab, thr, REPORTS / "hai_validation.png")
    print(f"\n>> artifacts -> {REPORTS}")


def _plot(scores: np.ndarray, labels: np.ndarray, thr: float, path: Path):
    fig, ax = plt.subplots(figsize=(13, 4.2))
    t = np.arange(len(scores)) * STRIDE / 3600.0
    ax.plot(t, scores, lw=0.7, color="#2980b9", label="anomaly score")
    ax.axhline(thr, color="#c0392b", ls=":", lw=1.2,
               label=f"threshold (1% false-alarm budget)")

    for s, e in attack_episodes(labels):
        ax.axvspan(t[s], t[min(e, len(t) - 1)], color="#e74c3c", alpha=0.18)

    ax.set_xlabel("time (hours)")
    ax.set_ylabel("anomaly score")
    ax.set_title("HAI 21.03 — anomaly score over the test run "
                 "(red bands = labelled attacks)")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    main()
