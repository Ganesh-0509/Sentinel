"""Render the SentinelAI architecture diagram.

Produces a 16:9 slide-ready PNG plus an SVG. Drawn in code rather than a drawing tool
so it stays in version control and cannot drift from the system it documents.

Layout follows the actual data path top to bottom: sources, ingest, feature store, the
three parallel detectors, fusion, the intelligence layer, agents, delivery.

Vertical layout is computed from an explicit row table rather than hand-placed
constants, because hand-placed constants are how boxes end up overlapping.

Run:  .venv\\Scripts\\python.exe scripts\\make_architecture_diagram.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mp
import matplotlib.pyplot as plt

REPORTS = ROOT / "reports"

# --- palette: matches the product's control-room theme ----------------------
BG = "#0a0e14"
PANEL = "#151d29"
TEXT = "#e2e8f0"
MUTED = "#93a4bd"
DIM = "#5b6b84"

SOURCE = "#64748b"
INGEST = "#0ea5e9"
FEATURE = "#38bdf8"
BASELINE = "#c0392b"
MODEL = "#1e8449"
ANOMALY = "#8b5cf6"
RULES = "#f59e0b"
AGENT = "#ec4899"
DELIVERY = "#14b8a6"

FONT = "DejaVu Sans"
ML = 0.024                 # left margin
MW = 0.952                 # main column width


def box(ax, x, y, w, h, label, sub=None, color=DIM, fill=PANEL,
        fs=10.5, sub_fs=8.0, lw=1.5):
    """Label sits in the upper third, subtitle in the lower — so two-line
    subtitles stay inside the box instead of spilling past its edge."""
    ax.add_patch(mp.FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.005,rounding_size=0.012",
        linewidth=lw, edgecolor=color, facecolor=fill, zorder=3))
    if sub:
        ax.text(x + w / 2, y + h * 0.70, label, ha="center", va="center",
                color=TEXT, fontsize=fs, fontweight="bold", family=FONT, zorder=4)
        ax.text(x + w / 2, y + h * 0.29, sub, ha="center", va="center",
                color=MUTED, fontsize=sub_fs, family=FONT, zorder=4,
                linespacing=1.45)
    else:
        ax.text(x + w / 2, y + h / 2, label, ha="center", va="center",
                color=TEXT, fontsize=fs, fontweight="bold", family=FONT, zorder=4)


CAPTION_CLEARANCE = 0.020   # box pad (0.005) + stroke + breathing room


def caption(ax, row_top, text):
    """Small layer caption in the gap above a row.

    Offset must clear the FancyBboxPatch pad, which extends each box beyond its
    nominal rectangle — otherwise the caption lands on the box edge.
    """
    ax.text(ML, row_top + CAPTION_CLEARANCE, " ".join(text.upper()),
            ha="left", va="bottom", color=DIM, fontsize=6.6,
            fontweight="bold", family=FONT, zorder=2)


def arrow(ax, x1, y1, x2, y2, color=DIM, lw=1.3):
    ax.add_patch(mp.FancyArrowPatch(
        (x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=10,
        linewidth=lw, color=color, zorder=2, shrinkA=1, shrinkB=1))


def main():
    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # ---- explicit row geometry: (bottom_y, height) -------------------------
    R = {
        "sources":      (0.842, 0.078),
        "ingest":       (0.756, 0.050),
        "features":     (0.672, 0.052),
        "detectors":    (0.552, 0.084),
        "fusion":       (0.462, 0.058),
        "intelligence": (0.342, 0.084),
        "agents":       (0.222, 0.084),
        "delivery":     (0.132, 0.052),
    }

    def top(k):
        return R[k][0] + R[k][1]

    # ---------------------------------------------------------------- title
    ax.text(ML, 0.962, "SENTINEL", ha="left", va="center", color=TEXT,
            fontsize=17, fontweight="bold", family=FONT)
    ax.text(ML + 0.126, 0.962, "AI", ha="left", va="center", color=INGEST,
            fontsize=17, fontweight="bold", family=FONT)
    ax.text(ML + 0.158, 0.962,
            "   Compound Industrial Safety Intelligence  —  system architecture",
            ha="left", va="center", color=MUTED, fontsize=10.5, family=FONT)

    # ------------------------------------------------------- 1. sources
    y, h = R["sources"]
    srcs = [
        ("SCADA / IoT", "gas · pressure\ntemp · vibration"),
        ("Permit-to-Work", "hot work · confined\nspace · cold work"),
        ("Maintenance", "work orders\nequipment status"),
        ("Shift roster", "crew · headcount\nchangeover"),
        ("Plant layout", "zones · coordinates\ntopology"),
        ("Regulations", "Factories Act\nDGMS · OISD"),
    ]
    sw = (MW - 5 * 0.012) / 6
    for i, (t, s) in enumerate(srcs):
        x = ML + i * (sw + 0.012)
        box(ax, x, y, sw, h, t, s, color=SOURCE, fs=9.5, sub_fs=7.3)
        arrow(ax, x + sw / 2, y, x + sw / 2, top("ingest"))

    # ------------------------------------------------------- 2. ingest
    y, h = R["ingest"]
    box(ax, ML, y, MW, h, "INGEST & NORMALISE",
        "protocol adapters (REST · CSV · MQTT / simulated stream · document load)   ·   "
        "schema + range validation   ·   units to % LEL   ·   UTC   ·   1-minute grid",
        color=INGEST, fs=10, sub_fs=8.0)
    arrow(ax, 0.5, y, 0.5, top("features"))

    # ------------------------------------------------------- 3. features
    y, h = R["features"]
    box(ax, ML, y, MW, h, "FEATURE STORE",
        "rolling mean / std / trend / rate-of-change   ·   operational context   ·   "
        "cross-signal interaction terms  (gas-trend × hot-work,  gas × maintenance)",
        color=FEATURE, fs=10, sub_fs=8.0)

    # ------------------------------------------------------- 4. detectors
    y, h = R["detectors"]
    dw = (MW - 2 * 0.018) / 3
    dets = [
        ("TIER 0 · BASELINE",
         "single sensor, fixed threshold\nthe control group we measure against", BASELINE),
        ("TIER 1 · COMPOUND FORECASTER",
         "LightGBM · 23 features\nP(incident within 30 min) + lead time", MODEL),
        ("TIER 2 · ANOMALY DETECTOR",
         "Isolation Forest + PCA reconstruction\ntrained on normal operation only", ANOMALY),
    ]
    fusion_cx = ML + (MW * 0.645) / 2
    for i, (t, s, c) in enumerate(dets):
        x = ML + i * (dw + 0.018)
        arrow(ax, x + dw / 2, R["features"][0], x + dw / 2, top("detectors"))
        box(ax, x, y, dw, h, t, s, color=c, fs=9.4, sub_fs=7.6)
        arrow(ax, x + dw / 2, y, fusion_cx, top("fusion"))

    # ------------------------------------------------------- 5. fusion
    # Narrowed so the safety call-out sits beside it rather than on top of it.
    y, h = R["fusion"]
    fw = MW * 0.645
    box(ax, ML, y, fw, h, "FUSION & DECISION LAYER",
        "rule engine holds VETO   ·   calibrated compound risk\n"
        "lead time from observable signals   ·   priority = risk × exposure × urgency",
        color=RULES, fs=10, sub_fs=7.9)

    cx = ML + fw + 0.020
    cw = MW - fw - 0.020
    # Taller than the fusion row so the three-line body clears the lower edge.
    ax.add_patch(mp.FancyBboxPatch(
        (cx, y - 0.026), cw, h + 0.048,
        boxstyle="round,pad=0.005,rounding_size=0.012",
        linewidth=1.6, edgecolor=RULES, facecolor="#1d1608", zorder=3))
    ax.text(cx + cw / 2, y + h + 0.004, "SAFETY CONTRACT", ha="center", va="center",
            color=RULES, fontsize=9.2, fontweight="bold", family=FONT, zorder=4)
    ax.text(cx + cw / 2, y + h / 2 - 0.018,
            "The model may ESCALATE or REJECT work.\n"
            "It can NEVER approve work the deterministic\n"
            "gas / oxygen interlocks have rejected.",
            ha="center", va="center", color=TEXT, fontsize=8.2, family=FONT,
            zorder=4, linespacing=1.5)

    # ------------------------------------------------------- 6. intelligence
    y, h = R["intelligence"]
    iw = (MW - 3 * 0.014) / 4
    intel = [
        ("SHAP", "why this alert\nfeature attribution"),
        ("KNOWLEDGE GRAPH", "blast radius\npermits to suspend"),
        ("INCIDENT PATTERNS", "precursor lift\nprevention priorities"),
        ("RAG COMPLIANCE", "cited clause\nprovenance marked"),
    ]
    for i, (t, s) in enumerate(intel):
        x = ML + i * (iw + 0.014)
        arrow(ax, x + iw / 2, R["fusion"][0], x + iw / 2, top("intelligence"))
        box(ax, x, y, iw, h, t, s, color=DELIVERY, fs=9.2, sub_fs=7.5)

    # ------------------------------------------------------- 7. agents
    y, h = R["agents"]
    aw = (MW - 3 * 0.014) / 4
    agents = [
        ("RISK MONITOR", "deterministic", False),
        ("PERMIT INTELLIGENCE", "deterministic", False),
        ("COMPLIANCE", "LLM + RAG", True),
        ("EMERGENCY ORCHESTRATOR", "LLM-assisted", True),
    ]
    for i, (t, s, is_llm) in enumerate(agents):
        x = ML + i * (aw + 0.014)
        box(ax, x, y, aw, h, t, s, color=AGENT if is_llm else RULES,
            fs=8.9, sub_fs=7.5)
        if i:
            arrow(ax, x - 0.014, y + h / 2, x, y + h / 2, color=AGENT, lw=1.2)
    arrow(ax, ML + aw / 2, R["intelligence"][0], ML + aw / 2, top("agents"))

    # ------------------------------------------------------- 8. delivery
    y, h = R["delivery"]
    arrow(ax, 0.5, R["agents"][0] - 0.020, 0.5, top("delivery"))
    box(ax, ML, y, MW, h, "DELIVERY",
        "FastAPI (typed OpenAPI contract)   ·   React dashboard — plant heatmap · zones · "
        "alerts · analytics · incident patterns · knowledge graph · permits · compliance · evidence",
        color=DELIVERY, fs=10, sub_fs=8.0)

    # ------------------------------------------------------- footer
    ax.text(ML, 0.075,
            "Externally validated —  Tennessee Eastman 84.7% detection @ 1% false alarms   ·   "
            "HAI ROC-AUC 0.966, 5/5 attacks   ·   4,261 zones/sec",
            ha="left", va="center", color=MUTED, fontsize=8.2, family=FONT)
    ax.text(ML, 0.045,
            "LLM chain —  Gemini → Ollama (local, offline) → extractive.   "
            "Nothing on the safety-critical path depends on a language model.",
            ha="left", va="center", color=MUTED, fontsize=8.2, family=FONT)

    for ext in ("png", "svg"):
        fig.savefig(REPORTS / f"architecture.{ext}", dpi=170,
                    facecolor=BG, bbox_inches="tight", pad_inches=0.22)
    plt.close(fig)
    print(f">> architecture.png / architecture.svg written to {REPORTS}")


if __name__ == "__main__":
    main()
