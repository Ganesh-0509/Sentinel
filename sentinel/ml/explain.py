"""SHAP explainability -- turns a risk score into 'why'.

Every compound-risk alert must be defensible to a safety officer and an auditor.
We use SHAP over the LightGBM forecaster to attribute each prediction to its
strongest drivers, then translate the feature names into plain language.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

_READABLE = {
    "gas_now": "gas level", "gas_mean": "average gas", "gas_max": "peak gas",
    "gas_std": "gas volatility", "gas_trend": "gas trend", "gas_roc": "gas rate-of-change",
    "pressure_now": "pressure", "pressure_trend": "pressure trend", "pressure_roc": "pressure rate",
    "temp_now": "temperature", "temp_trend": "temperature trend",
    "vib_now": "vibration", "vib_mean": "average vibration",
    "maintenance_active": "active maintenance", "hot_work_permit": "active hot-work permit",
    "confined_space_permit": "confined-space permit", "night_shift": "night shift",
    "workers_in_zone": "workers in zone",
    "time_since_maint": "maintenance duration", "time_since_permit": "permit duration",
    "gas_trend_x_hotwork": "gas rising during hot work",
    "pressure_trend_x_hotwork": "pressure rising during hot work",
    "gas_now_x_maint": "gas level during maintenance",
    "gas_roc_x_maint": "gas surge during maintenance",
    "pressure_trend_x_maint": "pressure rising during maintenance",
}


class RiskExplainer:
    def __init__(self, forecaster):
        import shap
        self.forecaster = forecaster
        self.explainer = shap.TreeExplainer(forecaster.model)
        self.features = forecaster.feature_columns

    def _shap_for_positive(self, X: pd.DataFrame) -> np.ndarray:
        raw = self.explainer.shap_values(X)
        if isinstance(raw, list):                 # [neg, pos]
            return np.asarray(raw[-1])
        raw = np.asarray(raw)
        if raw.ndim == 3:                         # (n, features, classes)
            return raw[:, :, -1]
        return raw

    def explain_row(self, feature_row: pd.DataFrame, top: int = 5) -> list[tuple[str, float]]:
        """Top signed SHAP contributions for a single row (positive class)."""
        X = feature_row[self.features]
        vals = self._shap_for_positive(X)[0]
        pairs = sorted(zip(self.features, vals), key=lambda kv: abs(kv[1]), reverse=True)
        return [(k, float(v)) for k, v in pairs[:top]]

    def explanation_text(self, feature_row: pd.DataFrame, top: int = 5) -> str:
        contribs = self.explain_row(feature_row, top=top)
        parts = []
        for name, val in contribs:
            label = _READABLE.get(name, name)
            arrow = "increases" if val > 0 else "reduces"
            parts.append(f"{label} ({arrow} risk)")
        return "; ".join(parts)
