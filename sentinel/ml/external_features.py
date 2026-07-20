"""Feature engineering for external benchmark datasets.

The plant pipeline's feature builder is tied to named signals (gas, pressure, permits).
External benchmarks have entirely different variables, so this applies the *same feature
families* — current value, rolling mean, rolling standard deviation, trend and
rate-of-change over a look-back window — to an arbitrary variable set.

That is the point: what transfers to another process is not our feature *names*, it is the
shape of the representation. Keeping this identical across TEP and HAI is what makes the
two validations comparable to each other and to the plant pipeline.

No time or row-index feature is ever produced. On benchmarks where the fault is injected at
a fixed sample, an index feature would let a model memorise the onset position instead of
learning the signal.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_WINDOW = 10
ROC_LAG = 5


def build_generic_features(x: np.ndarray | pd.DataFrame,
                           window: int = DEFAULT_WINDOW,
                           columns: list[str] | None = None) -> pd.DataFrame:
    """Per variable: value, rolling mean, rolling std, least-squares trend, rate-of-change."""
    if isinstance(x, pd.DataFrame):
        df = x.reset_index(drop=True)
    else:
        cols = columns or [f"v{i}" for i in range(x.shape[1])]
        df = pd.DataFrame(x, columns=cols)

    idx = np.arange(window, dtype=float)
    idx -= idx.mean()
    denom = float((idx * idx).sum())

    out: dict[str, pd.Series] = {}
    for c in df.columns:
        s = df[c].astype(float)
        roll = s.rolling(window, min_periods=2)
        out[f"{c}_now"] = s
        out[f"{c}_mean"] = roll.mean()
        out[f"{c}_std"] = roll.std().fillna(0.0)
        out[f"{c}_roc"] = s.diff(ROC_LAG)
        out[f"{c}_trend"] = s.rolling(window).apply(
            lambda w: float((idx * (w - w.mean())).sum() / denom), raw=True
        )

    feats = pd.DataFrame(out)
    return feats.bfill().ffill().fillna(0.0)


def drop_constant_columns(df: pd.DataFrame, tol: float = 1e-12) -> pd.DataFrame:
    """Remove zero-variance columns.

    Industrial captures routinely contain tags that never move over a given run.
    They carry no information, and constant columns degrade PCA reconstruction and
    inflate scaler instability.
    """
    keep = df.columns[df.std(numeric_only=True).fillna(0.0) > tol]
    return df[keep]


def attack_episodes(labels: np.ndarray) -> list[tuple[int, int]]:
    """Contiguous (start, end_exclusive) runs where the label is active.

    Detection is scored per episode as well as per sample: a system that flags one
    sample in a thirty-minute attack has technically 'detected' it, but what matters
    operationally is whether each distinct event was caught, and how quickly.
    """
    episodes: list[tuple[int, int]] = []
    start: int | None = None
    for i, v in enumerate(labels):
        if v and start is None:
            start = i
        elif not v and start is not None:
            episodes.append((start, i))
            start = None
    if start is not None:
        episodes.append((start, len(labels)))
    return episodes
