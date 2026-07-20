# SentinelAI — AI-Powered Industrial Safety Intelligence

Predicts **compound** industrial safety risks (e.g. gas accumulation during an active hot-work
permit) *before* they cross an incident threshold — and proves it against a single-sensor baseline.

See [`08_Solution_Roadmap.md`](08_Solution_Roadmap.md) for the full strategy and
[`DATASETS.md`](DATASETS.md) for data sources.

---

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\run_pipeline.py
```

Outputs land in `reports/` (`scoreboard.txt`, `scoreboard.png`, `episode_results.csv`,
`row_metrics.json`) and `models/forecaster.pkl`.

## What's built (Phase 1 — the spine)

```
sentinel/
  config.py                 shared thresholds / horizons (gas in % LEL)
  sim/simulator.py          physics-lite scenario simulator; incident labels emerge from physics
  ml/features.py            feature engineering (rolling trends + cross-signal interactions)
  ml/baseline.py            single-sensor baseline detector (the control group)
  ml/forecaster.py          LightGBM compound risk forecaster (multi-horizon)
  evaluation/harness.py     baseline-vs-compound episode scoreboard
scripts/run_pipeline.py     end-to-end: simulate -> train -> evaluate -> scoreboard
```

## Latest scoreboard (250 test episodes)

| metric | single-sensor baseline | SentinelAI |
|---|---|---|
| Incident detection rate | 85.6% | **100.0%** |
| False-negative rate (missed incidents) | 14.4% | **0.0%** |
| Lead time (matched incidents) | 41.7 min | 40.3 min |
| False-alarm rate (safe zones) | 41.0% | **15.8%** |
| Incidents baseline MISSED, SentinelAI caught | — | **16** |

Row-level model: ROC-AUC ≈ 0.975, PR-AUC ≈ 0.859.

> Why the baseline fails honestly: it reads **one point sensor**, which can be attenuated by poor
> placement / disturbed airflow (common during maintenance). SentinelAI fuses pressure, temperature,
> vibration and operational context, so it catches the hazard the single sensor cannot see — mirroring
> the Vizag pattern where "the signal existed but was not connected."

## Roadmap (next phases)

- **Phase 2:** SHAP explainability · unsupervised anomaly detector (Isolation Forest + LSTM-AE) ·
  deterministic rule engine (permit-vs-gas veto, OISD-STD-105).
- **Phase 3:** RAG compliance assistant (Gemini + Ollama fallback) · agentic layer (LangGraph:
  Risk / Permit / Compliance / Emergency Orchestrator).
- **Phase 4:** FastAPI backend · React dashboard · geospatial floor-plan heatmap.
