"""External validation on the Tennessee Eastman Process benchmark.

Everything else in this project is measured inside a simulator we wrote. This script
takes the components that CAN transfer and runs them, unchanged, on real benchmark
data from a process we did not design.

Dataset: the Braatz-group TEP distribution (University of Illinois).
    d00.dat      500 samples of normal operation   (stored TRANSPOSED, 52 x 500)
    dXX_te.dat   960 samples, fault XX injected at sample 160
    52 variables = XMEAS(1..41) measured + XMV(1..11) manipulated

WHAT THIS VALIDATES, AND WHAT IT CANNOT
---------------------------------------
TEP faults are *injected disturbances* -- a step or random variation switched on at a
known instant. There is no developing precursor before onset, so the information needed
to predict them early does not exist in the data. **TEP therefore cannot validate our
lead-time claim.** Forecasting a hazard that builds over time requires a dataset where
the hazard builds over time; TEP is not that dataset.

What TEP can validate is *detection of process abnormality from multivariate signals*,
which is what our anomaly layer does. So:

    ARM A  our AnomalyDetector, unchanged, trained on TEP normal data only.
           Does the method work outside the simulator it was built in?

    ARM B  our feature-engineering + gradient-boosting approach, trained on faults
           1-10 and tested on faults 11-21 -- fault types it has never seen.
           Does the pipeline generalise to novel failure modes?

Faults 3, 9 and 15 are reported separately: they are long established in the TEP
literature as effectively undetectable (no observable change in mean or variance).
Including them in a headline average would understate any method, including ours.

Run:  .venv\\Scripts\\python.exe scripts\\validate_tep.py
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
from lightgbm import LGBMClassifier
from sklearn.metrics import roc_auc_score

from sentinel import config as C
from sentinel.ml.anomaly import AnomalyDetector

TEP = ROOT / "data" / "external" / "tep"
REPORTS = ROOT / "reports"
FAULT_ONSET = 160          # test files: fault switched on at sample 160
WINDOW = 10                # same look-back we use in the plant pipeline
UNDETECTABLE = {3, 9, 15}  # established in the TEP literature
TARGET_FAR = 0.01          # calibrate the alarm threshold to 1% false alarms


# ------------------------------------------------------------------ loading
def load_normal_train() -> np.ndarray:
    """d00.dat is stored transposed (52 x 500); everything else is samples x 52."""
    a = np.loadtxt(TEP / "d00.dat")
    return a.T if a.shape[0] == 52 else a


def load_test(fault: int) -> np.ndarray:
    name = "d00_te.dat" if fault == 0 else f"d{fault:02d}_te.dat"
    return np.loadtxt(TEP / name)


def load_fault_train(fault: int) -> np.ndarray:
    return np.loadtxt(TEP / f"d{fault:02d}.dat")


# ------------------------------------------------- feature engineering (ours)
def build_features(x: np.ndarray) -> pd.DataFrame:
    """The same feature families used in the plant pipeline, applied to TEP vars.

    Per variable: current value, rolling mean, rolling std, trend (slope) and
    rate-of-change over a WINDOW look-back. No time index is included anywhere --
    the model must not be able to learn 'the fault starts at sample 160'.
    """
    n, k = x.shape
    df = pd.DataFrame(x, columns=[f"v{i}" for i in range(k)])
    out = {}
    idx = np.arange(WINDOW)
    idx = idx - idx.mean()
    denom = (idx * idx).sum()

    for c in df.columns:
        s = df[c]
        roll = s.rolling(WINDOW, min_periods=2)
        out[f"{c}_now"] = s
        out[f"{c}_mean"] = roll.mean()
        out[f"{c}_std"] = roll.std().fillna(0.0)
        out[f"{c}_roc"] = s.diff(5)
        # least-squares slope over the window
        out[f"{c}_trend"] = s.rolling(WINDOW).apply(
            lambda w: float((idx * (w - w.mean())).sum() / denom), raw=True
        )
    feats = pd.DataFrame(out).bfill().fillna(0.0)
    return feats


# ------------------------------------------------------------------- Arm A
def arm_a() -> dict:
    print(">> ARM A - anomaly detector (unchanged) on real TEP data")
    train = build_features(load_normal_train())
    cols = list(train.columns)
    det = AnomalyDetector(features=cols).fit(train)

    # calibrate threshold on the NORMAL test file so false alarms sit at ~1%
    normal_scores = det.score(build_features(load_test(0)))
    thr = float(np.quantile(normal_scores, 1 - TARGET_FAR))
    far_normal = float((normal_scores >= thr).mean())
    print(f"   threshold {thr:.2f} -> false-alarm rate on normal test "
          f"{far_normal:.1%}")

    rows = []
    for f in range(1, 22):
        s = det.score(build_features(load_test(f)))
        pre, post = s[WINDOW:FAULT_ONSET], s[FAULT_ONSET:]
        alarms = post >= thr

        # detection delay: first point where 3 consecutive samples exceed threshold
        delay = None
        run = 0
        for i, a in enumerate(alarms):
            run = run + 1 if a else 0
            if run >= 3:
                delay = i - 2
                break

        rows.append({
            "fault": f,
            "known_undetectable": f in UNDETECTABLE,
            "detection_rate": float(alarms.mean()),
            "false_alarm_rate": float((pre >= thr).mean()),
            "detection_delay_samples": delay,
            "detection_delay_min": None if delay is None else delay * 3,
        })
        r = rows[-1]
        flag = "  (known undetectable)" if r["known_undetectable"] else ""
        d = "never" if delay is None else f"{delay*3} min"
        print(f"   fault {f:>2} | detect {r['detection_rate']:>6.1%} | "
              f"far {r['false_alarm_rate']:>5.1%} | delay {d:>8}{flag}")

    df = pd.DataFrame(rows)
    detectable = df[~df["known_undetectable"]]
    return {
        "threshold": thr,
        "false_alarm_rate_normal": far_normal,
        "mean_detection_detectable": float(detectable["detection_rate"].mean()),
        "mean_detection_all": float(df["detection_rate"].mean()),
        "median_delay_min_detectable": float(
            detectable["detection_delay_min"].dropna().median()
        ),
        "faults_missed": detectable[detectable["detection_rate"] < 0.2]["fault"].tolist(),
        "per_fault": rows,
    }


# ------------------------------------------------------------------- Arm B
def arm_b() -> dict:
    print("\n>> ARM B - feature pipeline + GBM, tested on UNSEEN fault types")
    train_faults = list(range(1, 11))
    test_faults = list(range(11, 22))

    def assemble(faults: list[int]) -> tuple[pd.DataFrame, np.ndarray]:
        """Use the *test* files for training: each carries 160 genuine normal samples
        before onset, so the model actually learns what normal looks like. The
        fault-training files are 96% faulted and gave the model almost no normal
        reference at all."""
        X, y = [], []
        for f in faults:
            feats = build_features(load_test(f))
            lab = np.zeros(len(feats), dtype=int)
            lab[FAULT_ONSET:] = 1
            X.append(feats.iloc[WINDOW:])
            y.append(lab[WINDOW:])
        normal = build_features(load_normal_train())
        X.append(normal)
        y.append(np.zeros(len(normal), dtype=int))
        return pd.concat(X, ignore_index=True), np.concatenate(y)

    Xtr, ytr = assemble(train_faults)
    print(f"   train: {len(Xtr):,} rows from faults {train_faults[0]}-{train_faults[-1]} "
          f"({(ytr == 0).sum():,} normal / {(ytr == 1).sum():,} faulted)")

    model = LGBMClassifier(
        n_estimators=300, learning_rate=0.05, num_leaves=31,
        subsample=0.9, colsample_bytree=0.9, reg_lambda=1.0,
        random_state=C.GLOBAL_SEED, n_jobs=-1, verbosity=-1,
        scale_pos_weight=float((ytr == 0).sum() / max((ytr == 1).sum(), 1)),
    )
    model.fit(Xtr, ytr)

    # Calibrate the decision threshold to ~1% false alarms on held-out normal data,
    # exactly as in Arm A. A fixed 0.5 cut is arbitrary and produced a 51% false-alarm
    # rate, which says nothing about the model and everything about the threshold.
    normal_p = model.predict_proba(build_features(load_test(0)))[:, 1]
    thr = float(np.quantile(normal_p, 1 - TARGET_FAR))
    print(f"   threshold {thr:.3f} -> false-alarm rate on normal test "
          f"{(normal_p >= thr).mean():.1%}")

    rows = []
    for f in test_faults:
        feats = build_features(load_test(f))
        p = model.predict_proba(feats)[:, 1]
        truth = np.zeros(len(feats), dtype=int)
        truth[FAULT_ONSET:] = 1
        valid = slice(WINDOW, len(feats))
        try:
            auc = float(roc_auc_score(truth[valid], p[valid]))
        except ValueError:
            auc = float("nan")
        rows.append({
            "fault": f,
            "known_undetectable": f in UNDETECTABLE,
            "roc_auc": auc,
            "detection_rate": float((p[FAULT_ONSET:] >= thr).mean()),
            "false_alarm_rate": float((p[WINDOW:FAULT_ONSET] >= thr).mean()),
        })
        r = rows[-1]
        flag = "  (known undetectable)" if r["known_undetectable"] else ""
        print(f"   fault {f:>2} | AUC {auc:>5.3f} | detect {r['detection_rate']:>6.1%} | "
              f"far {r['false_alarm_rate']:>5.1%}{flag}")

    df = pd.DataFrame(rows)
    detectable = df[~df["known_undetectable"]]
    return {
        "train_faults": train_faults,
        "test_faults": test_faults,
        "threshold": thr,
        "mean_auc_detectable": float(detectable["roc_auc"].mean()),
        "mean_detection_detectable": float(detectable["detection_rate"].mean()),
        "mean_false_alarm": float(detectable["false_alarm_rate"].mean()),
        "per_fault": rows,
    }


def main():
    if not (TEP / "d00.dat").exists():
        print(f"!! TEP data not found at {TEP}")
        print("   git clone --depth 1 "
              "https://github.com/camaramm/tennessee-eastman-profBraatz.git "
              "data/external/tep")
        return

    a = arm_a()
    b = arm_b()
    result = {
        "dataset": "Tennessee Eastman Process (Braatz distribution)",
        "note": ("TEP faults are injected disturbances with no precursor phase, so this "
                 "benchmark validates DETECTION of process abnormality, not the "
                 "lead-time claim. Faults 3, 9 and 15 are excluded from headline "
                 "averages as established-undetectable."),
        "arm_a_anomaly_detector": a,
        "arm_b_feature_pipeline": b,
    }
    (REPORTS / "tep_validation.json").write_text(json.dumps(result, indent=2))

    print("\n" + "=" * 76)
    print("  TEP EXTERNAL VALIDATION -- summary")
    print("=" * 76)
    print(f"  ARM A  anomaly detector, unchanged, trained on TEP normal only")
    print(f"         mean detection (18 detectable faults) : "
          f"{a['mean_detection_detectable']:.1%}")
    print(f"         false-alarm rate on normal test data   : "
          f"{a['false_alarm_rate_normal']:.1%}")
    print(f"         median detection delay                 : "
          f"{a['median_delay_min_detectable']:.0f} min")
    if a["faults_missed"]:
        print(f"         faults still largely missed            : {a['faults_missed']}")
    print("-" * 76)
    print(f"  ARM B  feature pipeline + GBM, trained faults 1-10, tested 11-21")
    print(f"         mean ROC-AUC on UNSEEN fault types      : "
          f"{b['mean_auc_detectable']:.3f}")
    print(f"         mean detection                          : "
          f"{b['mean_detection_detectable']:.1%}")
    print(f"         mean false-alarm rate                   : "
          f"{b['mean_false_alarm']:.1%}")
    print("=" * 76)

    _plot(a, b, REPORTS / "tep_validation.png")
    print(f"\n>> artifacts -> {REPORTS}")


def _plot(a: dict, b: dict, path: Path):
    da = pd.DataFrame(a["per_fault"])
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.6))

    colors = ["#95a5a6" if u else "#1e8449" for u in da["known_undetectable"]]
    ax1.bar(da["fault"], da["detection_rate"] * 100, color=colors)
    ax1.axhline(a["false_alarm_rate_normal"] * 100, color="#c0392b", ls=":",
                label=f"false-alarm rate ({a['false_alarm_rate_normal']:.1%})")
    ax1.set_xlabel("TEP fault number")
    ax1.set_ylabel("detection rate (%)")
    ax1.set_title("Arm A — anomaly detector on real TEP data\n"
                  "(grey = faults 3/9/15, established undetectable)")
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.2, axis="y")

    db = pd.DataFrame(b["per_fault"])
    colors_b = ["#95a5a6" if u else "#2980b9" for u in db["known_undetectable"]]
    ax2.bar(db["fault"], db["roc_auc"], color=colors_b)
    ax2.axhline(0.5, color="#c0392b", ls=":", label="chance")
    ax2.set_ylim(0, 1)
    ax2.set_xlabel("TEP fault number (unseen during training)")
    ax2.set_ylabel("ROC-AUC")
    ax2.set_title("Arm B — feature pipeline generalising\nto fault types never trained on")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.2, axis="y")

    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    main()
