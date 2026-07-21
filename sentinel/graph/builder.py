"""Build the safety knowledge graph from live plant state.

Plant topology lives here as data, not as hard-coded logic. `ZONE_TOPOLOGY` describes
which zones share a physical path — a gas header, a shared duct, a common wall. That is
the information a per-zone dashboard structurally cannot represent, and it is what turns
"COB-B is critical" into "COB-B is critical and there is an open hot-work permit two
zones downwind of it".

Adjacency is derived from the same floor-plan coordinates the map renders from, so the
graph and the geospatial view cannot silently disagree.
"""
from __future__ import annotations

import math

from sentinel.graph.knowledge_graph import GraphNode, SafetyKnowledgeGraph

# Explicit process connections: zones sharing a gas header or duct run.
# Physical connection, not proximity — gas travels along these regardless of distance.
ZONE_TOPOLOGY = [
    ("COB-A", "COB-B", "coke oven gas main"),
    ("COB-B", "BYP-1", "crude gas line to by-product plant"),
    ("BYP-1", "GAS-H", "cleaned gas to holder"),
    ("GAS-H", "PWR-1", "fuel gas to power station"),
    ("GAS-H", "BLF-2", "fuel gas to blast furnace stoves"),
    ("BLF-2", "SIN-1", "shared dust extraction"),
    ("TNK-3", "BYP-1", "tar and benzol transfer"),
]

ADJACENCY_RADIUS = 28.0     # floor-plan units; zones closer than this share an atmosphere

# Which standard governs which permit type. Kept explicit so a compliance officer can
# audit the mapping rather than infer it from code paths.
PERMIT_REGULATIONS = {
    "Hot Work": [("OISD-105-HW", "OISD-STD-105", "Hot work"),
                 ("FA-41H", "Factories Act 1948", "Section 41H - imminent danger")],
    "Confined Space": [("OISD-105-CS", "OISD-STD-105", "Confined space entry"),
                       ("FA-41C", "Factories Act 1948", "Section 41C - hazardous process")],
    "Cold Work": [("OISD-105-WP", "OISD-STD-105", "Work permit")],
    "Electrical": [("OISD-105-EL", "OISD-STD-105", "Electrical isolation")],
}


def build_graph(zone_states: list[dict]) -> SafetyKnowledgeGraph:
    """Construct the graph from the current zone snapshot."""
    g = SafetyKnowledgeGraph()
    g.add_node(GraphNode("PLANT", "Plant", "Visakhapatnam Works"))

    by_id = {z["zone_id"]: z for z in zone_states}

    # --- zones, their sensors, and any active permit -------------------------
    for z in zone_states:
        zid = z["zone_id"]
        g.add_node(GraphNode(zid, "Zone", z["name"], attrs={
            "risk": z["risk"],
            "risk_band": z["risk_band"],
            "gas_lel": z["gas_lel"],
            "workers_in_zone": z["workers_in_zone"],
            "hot_work_active": z["hot_work_active"],
            "maintenance_active": z["maintenance_active"],
            "x": z["x"], "y": z["y"],
        }))
        g.add_edge("PLANT", zid, "CONTAINS")

        sid = f"{zid}-GAS"
        g.add_node(GraphNode(sid, "Sensor", f"{z['name']} gas detector", attrs={
            "reading_lel": z["gas_lel"],
            "sensor_type": "combustible gas",
        }))
        g.add_edge(zid, sid, "MONITORED_BY")

        if z["hot_work_active"]:
            _attach_permit(g, zid, "Hot Work")
        if z["maintenance_active"]:
            _attach_permit(g, zid, "Cold Work")

        if z["workers_in_zone"] > 0:
            wid = f"{zid}-CREW"
            g.add_node(GraphNode(wid, "Worker", f"{z['workers_in_zone']} personnel",
                                 attrs={"headcount": z["workers_in_zone"]}))
            g.add_edge(zid, wid, "STAFFED_BY")

        if z["risk"] >= 0.6:
            hid = f"{zid}-HAZ"
            g.add_node(GraphNode(hid, "Hazard", "Compound gas hazard", attrs={
                "risk": z["risk"], "band": z["risk_band"],
            }))
            g.add_edge(zid, hid, "EXPOSES_TO")

    # --- process connections (explicit topology) ----------------------------
    for a, b, via in ZONE_TOPOLOGY:
        if a in by_id and b in by_id:
            g.add_edge(a, b, "CONNECTED_TO", via=via)

    # --- spatial adjacency (derived from the same coords the map uses) -------
    ids = list(by_id)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            za, zb = by_id[a], by_id[b]
            d = math.dist((za["x"], za["y"]), (zb["x"], zb["y"]))
            if d <= ADJACENCY_RADIUS:
                g.add_edge(a, b, "ADJACENT_TO", distance=round(d, 1))

    return g


def _attach_permit(g: SafetyKnowledgeGraph, zone_id: str, permit_type: str) -> None:
    pid = f"{zone_id}-PTW-{permit_type.replace(' ', '').upper()}"
    g.add_node(GraphNode(pid, "Permit", f"{permit_type} — {zone_id}",
                         attrs={"permit_type": permit_type, "zone_id": zone_id}))
    g.add_edge(zone_id, pid, "HAS_PERMIT")

    for rid, standard, section in PERMIT_REGULATIONS.get(permit_type, []):
        if rid not in g.nodes:
            g.add_node(GraphNode(rid, "Regulation", f"{standard} — {section}",
                                 attrs={"standard": standard, "section": section}))
        g.add_edge(pid, rid, "GOVERNED_BY")
