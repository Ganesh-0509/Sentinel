"""Ablation: do the shift/roster features actually earn their place?

Trains two identical forecasters on identical data -- one with the full feature
set, one with the shift/roster feature group removed -- and compares them:

  1. THRESHOLD-FREE (ROC-AUC / PR-AUC): does the feature group add information
     at all? This cannot be gamed by a lucky operating point.
  2. MATCHED FALSE-ALARM RATE: episode detection + lead time compared at the
     SAME nuisance level, which is the only fair operating-point comparison.

Run:  .venv\\Scripts\\python.exe scripts\\ablation_shift.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from sentinel import config as C
from sentinel.sim import generate_dataset
from sentinel.ml.features import (
    build_features, label_rows, FEATURE_COLUMNS, ALL_FEATURE_COLUMNS,
)
from sentinel.ml.forecaster import CompoundRiskForecaster
N_TRAIN, N_VALID, N_TEST = 400, 100, 200
TARGET_FA = 0.10          # common operating point for the matched comparison


def _feature_table(raw):
    frames = [build_features(ep) for _, ep in raw.groupby("episode_id", sort=False)]
    return label_rows(pd.concat(frames, ignore_index=True))


def causality_check(raw: pd.DataFrame):
    """Did shift state actually become causal?"""
    eps = raw.groupby("episode_id").agg(
        night=("night_shift", "first"),
        incident=("incident_onset", lambda s: int(s.iloc[0]) >= 0),
        had_leak=("leak_active", "max"),
        changeover=("in_changeover", "max"),
    )
    leaks = eps[eps["had_leak"] == 1]
    if not len(leaks):
        return
    print("\n  -- causality check (leak episodes only) --")
    for label, sub in [
        ("day shift    ", leaks[leaks["night"] == 0]),
        ("night shift  ", leaks[leaks["night"] == 1]),
        ("w/ changeover", leaks[leaks["changeover"] == 1]),
        ("no changeover", leaks[leaks["changeover"] == 0]),
    ]:
        if len(sub):
            print(f"     {label}: incident rate {sub['incident'].mean():6.1%}  (n={len(sub)})")


def episode_signals(model, test_raw):
    out = []
    for _, ep in test_raw.groupby("episode_id", sort=False):
        ep = ep.sort_values("minute").reset_index(drop=True)
        feats = build_features(ep)
        out.append({
            "proba": model.predict_proba(feats),
            "minutes": feats["minute"].to_numpy(),
            "onset": int(ep["incident_onset"].iloc[0]),
            "had_leak": int(ep["leak_active"].max()),
        })
    return out


def sweep(signals) -> pd.DataFrame:
    rows = []
    for t in np.linspace(0.05, 0.995, 80):
        det = fa = n_inc = n_safe = 0
        lead_sum = 0.0
        for e in signals:
            mask = e["proba"] >= t
            at = int(e["minutes"][np.argmax(mask)]) if mask.any() else None
            if e["onset"] >= 0:
                n_inc += 1
                if at is not None and at < e["onset"]:
                    det += 1
                    lead_sum += e["onset"] - at
            elif e["had_leak"] == 0:      # only truly safe zones count as false alarms
                n_safe += 1
                if at is not None:
                    fa += 1
        rows.append({"t": t, "det": det / max(n_inc, 1),
                     "fa": fa / max(n_safe, 1), "lead": lead_sum / max(det, 1)})
    return pd.DataFrame(rows)


def main():
    print(">> generating shared datasets ...")
    train_raw = generate_dataset(N_TRAIN, seed=C.GLOBAL_SEED)
    valid_raw = generate_dataset(N_VALID, seed=C.GLOBAL_SEED + 1)
    test_raw = generate_dataset(N_TEST, seed=C.GLOBAL_SEED + 2)
    train_df, valid_df = _feature_table(train_raw), _feature_table(valid_raw)
    test_df = _feature_table(test_raw)
    causality_check(train_raw)

    full = list(ALL_FEATURE_COLUMNS)      # hazard features + shift/roster group
    reduced = list(FEATURE_COLUMNS)       # hazard features only (shipped model)

    results = {}
    for name, cols in [("WITH shift", full), ("WITHOUT shift", reduced)]:
        print(f">> training: {name} ({len(cols)} features) ...")
        m = CompoundRiskForecaster()
        m.feature_columns = list(cols)
        m.fit(train_df, valid_df)
        rows = m.evaluate_rows(test_df)
        sw = sweep(episode_signals(m, test_raw))
        at = sw.iloc[(sw["fa"] - TARGET_FA).abs().idxmin()]
        results[name] = {"rows": rows, "at": at}

    a, b = results["WITH shift"], results["WITHOUT shift"]
    print("\n" + "=" * 72)
    print("  ABLATION -- do shift/roster features earn their place?")
    print("=" * 72)
    print("  [1] THRESHOLD-FREE (does the feature group add information?)")
    print(f"  {'metric':<34}{'WITH shift':>18}{'WITHOUT shift':>18}")
    print("-" * 72)
    print(f"  {'ROC-AUC':<34}{a['rows']['roc_auc']:>18.4f}{b['rows']['roc_auc']:>18.4f}")
    print(f"  {'PR-AUC':<34}{a['rows']['pr_auc']:>18.4f}{b['rows']['pr_auc']:>18.4f}")
    print("-" * 72)
    print(f"  [2] AT MATCHED FALSE-ALARM RATE (~{TARGET_FA:.0%})")
    print(f"  {'actual false-alarm rate':<34}{a['at']['fa']:>17.1%}{b['at']['fa']:>18.1%}")
    print(f"  {'incident detection rate':<34}{a['at']['det']:>17.1%}{b['at']['det']:>18.1%}")
    print(f"  {'mean lead time (min)':<34}{a['at']['lead']:>18.1f}{b['at']['lead']:>18.1f}")
    print("=" * 72)

    d_roc = a["rows"]["roc_auc"] - b["rows"]["roc_auc"]
    d_pr = a["rows"]["pr_auc"] - b["rows"]["pr_auc"]
    d_det = a["at"]["det"] - b["at"]["det"]
    print(f"  delta (with - without):  ROC-AUC {d_roc:+.4f}   PR-AUC {d_pr:+.4f}"
          f"   detection {d_det:+.1%}")
    verdict = ("shift features EARN their place" if (d_pr > 0.01 or d_det > 0.02)
               else "shift features do NOT earn their place")
    print(f"  >> {verdict}")
    print("\n  NOTE: this measures PREDICTION only. `workers_in_zone` also drives")
    print("  alert PRIORITISATION / evacuation (consequence, not probability),")
    print("  which no prediction metric can capture.\n")


if __name__ == "__main__":
    main()
