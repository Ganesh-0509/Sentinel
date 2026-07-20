# SentinelAI

**Compound industrial safety intelligence for heavy industry.**

Indian heavy industry does not lack sensors — it lacks an intelligence layer that connects
them. Gas detectors, permit-to-work systems, maintenance logs and SCADA all exist, and all
operate independently. The recurring failure mode is *data present, but unacted upon*.

SentinelAI is a software layer above those existing systems. It fuses gas, pressure,
temperature and vibration with operational context (active permits, maintenance, staffing)
into a **forward-looking risk forecast**, explains every alert, enforces deterministic permit
interlocks, and coordinates the response.

---

## The core claim, and the evidence for it

A conventional single-sensor gas alarm is the control group. On 300 held-out episodes:

| Metric | Single-sensor baseline | SentinelAI |
|---|---:|---:|
| Incident detection rate | 73.4 % | **98.4 %** |
| False-negative rate (missed incidents) | 26.6 % | **1.6 %** |
| False-alarm rate (safe zones) | 54.9 % | **10.5 %** |
| Nuisance alarm-minutes | 195 | **21** |
| **Incidents the baseline missed entirely** | — | **17 caught** |

Compared at the **baseline's own false-alarm rate**, SentinelAI reaches **100 % detection with
64.6 min lead time**, against the baseline's 73.4 % and 27.3 min — it dominates on every axis
simultaneously, not just at a favourable operating point.

Model quality: ROC-AUC 0.931, PR-AUC 0.446 (row-level, held-out).

> **Why the baseline fails honestly.** It reads one point sensor, which can be attenuated by
> placement or disturbed airflow — common during maintenance. SentinelAI fuses pressure,
> temperature, vibration and operational context, so it sees hazards the point sensor cannot.
> In the demo replay the point sensor reads **4.5 % LEL while true zone gas is 8.9 % LEL**.

Reproduce: `python scripts/run_pipeline.py` → `reports/scoreboard.txt`.

---

## Safety contract

> The machine-learning layer may **escalate or reject** work.
> It can **never approve** work that the deterministic gas/oxygen interlocks have rejected.

Anything that can stop or clear work is plain, auditable logic — never a model decision.
LLMs are used only for language (compliance retrieval, notification drafting), after the
safety verdict has already been reached deterministically. If every LLM tier is unavailable,
the interlocks still enforce.

---

## Architecture

```
   SCADA / IoT ─┐
   Permits ─────┤
   Maintenance ─┼──▶ ingest ─▶ normalise ─▶ FEATURE STORE ─┬─▶ Baseline detector (control)
   Shift roster ┤     (% LEL, UTC, 1-min grid)             ├─▶ Compound forecaster (LightGBM)
   Plant layout ┘                                          └─▶ Anomaly detector (IF + PCA)
                                                                       │
                                    ┌──────────────────────────────────┘
                                    ▼
                        FUSION + DECISION LAYER
        rule engine (VETO) · risk × exposure × urgency · lead time · SHAP
                                    │
              ┌─────────────────────┼──────────────────────┐
              ▼                     ▼                      ▼
      Agentic workflow      Geospatial heatmap        REST API
   (risk → permit →      (zone risk + workers        (FastAPI, OpenAPI)
    compliance → ERO)         exposed)                     │
                                    └─────────▶ React dashboard
```

Full detail: [`09_Ingestion_Pipeline.md`](09_Ingestion_Pipeline.md) documents every
ingestion stream, the model that consumes it, and the output it produces.
Strategy and model rationale: [`08_Solution_Roadmap.md`](08_Solution_Roadmap.md).

---

## Quick start

**Prerequisites:** Python 3.12, Node 20+. Optional: [Ollama](https://ollama.com) with
`llama3.1:8b` for the offline LLM path.

```bash
# 1. backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe scripts/run_pipeline.py          # trains + writes reports/
.venv/Scripts/python.exe -m uvicorn sentinel.api.app:app --port 8000

# 2. frontend (separate terminal)
cd frontend && npm install && npm run dev
```

Dashboard → `http://localhost:5173` · API docs → `http://localhost:8000/docs`

### Demonstrations

| Command | Shows |
|---|---|
| `scripts/run_pipeline.py` | Baseline-vs-compound scoreboard + chart |
| `scripts/phase2_demo.py` | Single-incident replay with SHAP + permit veto |
| `scripts/phase3_demo.py` | Full agentic workflow on a compound event |
| `scripts/ablation_shift.py` | Feature ablation study (see below) |

---

## Design decisions worth reading

**Labels come from simulated physics, not from hand-written rules.** The simulator models gas
accumulation dynamics; an *incident* is a physical threshold crossing that emerges from those
dynamics. The model is trained to predict that future event from present observables, and
never sees the hidden true-gas variable. It therefore learns genuine leading indicators
rather than re-learning a rule we wrote.

**Shift/roster features were tested and deliberately excluded from the model.** After
modelling shift changeover properly (operator detection latency, handover information loss),
shift state became genuinely causal — night-shift leaks escalate 49.5 % vs 28.7 % on day
shift. But an ablation showed that feeding those features to the risk model *cost 17.8 points
of detection*: the model learned "day shift, no changeover → someone will probably catch this"
and under-alerted. **A safety alert must reflect the hazard, not the odds that somebody else
fixes it.** Those signals now live in the decision layer as consequence/urgency multipliers
(`sentinel/decision/priority.py`). Run `scripts/ablation_shift.py` to reproduce.

---

## Regulatory corpus and licensing

`data/regulations/` contains the **Factories Act, 1948** (Indian statute, reproducible under
s.52(1)(q)(i) of the Copyright Act, 1957) and our own SOP templates.

**OISD-STD-105 is not reproduced here.** It is marked *FOR RESTRICTED CIRCULATION* and may
not be copied without written consent from OISD. The repository ships a *reference index*
(section names and topics, no standard text) so citations point to the correct clause
location. Place your organisation's licensed copy in `data/regulations_local/` — git-ignored —
and the retriever loads it automatically, upgrading citations to `OFFICIAL`.

Every citation carries its provenance, and the UI visibly marks non-official sources.
Numeric gas/oxygen thresholds in code are **site-configurable engineering defaults**,
deliberately conservative — not quoted legal limits.

---

## Project layout

```
sentinel/
  sim/          scenario simulator (physics-lite; labels emerge from dynamics)
  ml/           features · baseline · forecaster · SHAP · anomaly detection
  rules/        deterministic gas/oxygen interlocks (veto authority)
  decision/     alert prioritisation (risk × exposure × urgency)
  rag/          regulation retrieval with provenance-aware citations
  llm/          Gemini → Ollama → extractive provider chain
  agents/       LangGraph multi-agent safety workflow
  api/          FastAPI service + Pydantic schemas
  evaluation/   baseline-vs-compound scoreboard and operating curves
frontend/       React + TypeScript + Tailwind dashboard
scripts/        pipeline, demos, ablation
data/           regulation corpus (see licensing above)
```

---

## Status and limitations

- Results are **simulator-derived**. They demonstrate that the reasoning and the
  measurement methodology are sound; they are not a claim about a specific real plant.
  External validation against the TEP and HAI datasets is documented in
  [`DATASETS.md`](DATASETS.md) and is not yet run.
- The regulation corpus is partly stand-in (see licensing above).
- Decision-support only. This system does not actuate plant equipment.
