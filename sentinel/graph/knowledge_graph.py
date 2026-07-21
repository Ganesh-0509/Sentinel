"""Equipment-permit-hazard-regulation knowledge graph.

Why a graph rather than another table
-------------------------------------
The relational model answers "what is the gas reading in zone COB-B?" perfectly well.
It answers *reachability* questions badly, and reachability is what kills people:

    "Which OTHER zones are endangered by an open hot-work permit in COB-B?"
    "Every zone connected to the same gas header as the one that is leaking — who is in them?"
    "This zone just went critical. Which regulation clauses govern the work happening in it,
     and which permits do I have to suspend, including in adjacent zones?"

Those are traversals. Answering them with joins means one query per hop and a new query
every time the plant topology changes. A graph answers them in one walk, and the plant
topology becomes data instead of code.

Design notes
------------
Deliberately an in-process graph (adjacency dictionaries), not Neo4j. At this scale a
graph database is operational overhead with no query benefit -- the whole plant is a few
hundred nodes and traversals finish in microseconds. The interface below is the part that
matters; swapping the storage for Neo4j later is a `_neighbours()` change, not a redesign.

Node types:  Plant, Zone, Equipment, Sensor, Permit, Hazard, Worker, Regulation
Edge types:  CONTAINS, MONITORED_BY, CONNECTED_TO, HAS_PERMIT, EXPOSES_TO,
             GOVERNED_BY, STAFFED_BY, ADJACENT_TO
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class GraphNode:
    id: str
    kind: str                       # Zone | Equipment | Sensor | Permit | Hazard | ...
    label: str
    attrs: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    relation: str
    attrs: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


class SafetyKnowledgeGraph:
    def __init__(self):
        self.nodes: dict[str, GraphNode] = {}
        self._out: dict[str, list[GraphEdge]] = defaultdict(list)
        self._in: dict[str, list[GraphEdge]] = defaultdict(list)

    # ----------------------------------------------------------------- build
    def add_node(self, node: GraphNode) -> "SafetyKnowledgeGraph":
        self.nodes[node.id] = node
        return self

    def add_edge(self, source: str, target: str, relation: str,
                 **attrs) -> "SafetyKnowledgeGraph":
        edge = GraphEdge(source=source, target=target, relation=relation, attrs=attrs)
        self._out[source].append(edge)
        self._in[target].append(edge)
        return self

    @property
    def edges(self) -> list[GraphEdge]:
        return [e for edges in self._out.values() for e in edges]

    # -------------------------------------------------------------- traverse
    def neighbours(self, node_id: str, relations: set[str] | None = None,
                   undirected: bool = True) -> list[tuple[str, str]]:
        """Return (neighbour_id, relation) pairs, optionally filtered by relation."""
        seen: list[tuple[str, str]] = []
        for e in self._out.get(node_id, []):
            if relations is None or e.relation in relations:
                seen.append((e.target, e.relation))
        if undirected:
            for e in self._in.get(node_id, []):
                if relations is None or e.relation in relations:
                    seen.append((e.source, e.relation))
        return seen

    def reachable(self, start: str, relations: set[str] | None = None,
                  max_hops: int = 3) -> dict[str, int]:
        """Breadth-first reachability with hop distance."""
        dist = {start: 0}
        q = deque([start])
        while q:
            cur = q.popleft()
            if dist[cur] >= max_hops:
                continue
            for nxt, _ in self.neighbours(cur, relations):
                if nxt not in dist:
                    dist[nxt] = dist[cur] + 1
                    q.append(nxt)
        dist.pop(start, None)
        return dist

    def nodes_of_kind(self, kind: str) -> list[GraphNode]:
        return [n for n in self.nodes.values() if n.kind == kind]

    # ------------------------------------------------------ safety questions
    def blast_radius(self, zone_id: str, max_hops: int = 2) -> dict:
        """Which zones share a physical path with this one, and who is in them?

        This is the question a single-zone dashboard cannot answer. A release in one
        zone travels along connected headers and into adjacent areas; the exposure is
        not the zone, it is the reachable set.
        """
        spread = {"CONNECTED_TO", "ADJACENT_TO"}
        reached = self.reachable(zone_id, relations=spread, max_hops=max_hops)

        affected = []
        total_workers = 0
        for zid, hops in sorted(reached.items(), key=lambda kv: kv[1]):
            node = self.nodes.get(zid)
            if not node or node.kind != "Zone":
                continue
            workers = int(node.attrs.get("workers_in_zone", 0))
            total_workers += workers
            affected.append({
                "zone_id": zid,
                "zone": node.label,
                "hops": hops,
                "workers": workers,
                "hot_work_active": bool(node.attrs.get("hot_work_active")),
                "risk": float(node.attrs.get("risk", 0.0)),
            })

        origin = self.nodes.get(zone_id)
        origin_workers = int(origin.attrs.get("workers_in_zone", 0)) if origin else 0
        return {
            "origin": zone_id,
            "origin_zone": origin.label if origin else zone_id,
            "origin_workers": origin_workers,
            "connected_zones": affected,
            "total_workers_at_risk": origin_workers + total_workers,
            "ignition_sources_in_radius": [
                a["zone_id"] for a in affected if a["hot_work_active"]
            ],
        }

    def permits_to_suspend(self, zone_id: str, max_hops: int = 2) -> list[dict]:
        """Every permit that must be reviewed if this zone goes critical.

        Includes permits in connected zones, which is the failure mode a per-zone view
        misses entirely: the permit that kills you is often not in the zone that leaked.
        """
        radius = self.blast_radius(zone_id, max_hops)
        zone_ids = [zone_id] + [z["zone_id"] for z in radius["connected_zones"]]

        out = []
        for zid in zone_ids:
            for nid, rel in self.neighbours(zid, {"HAS_PERMIT"}):
                node = self.nodes.get(nid)
                if not node or node.kind != "Permit":
                    continue
                hops = 0 if zid == zone_id else next(
                    (z["hops"] for z in radius["connected_zones"] if z["zone_id"] == zid), 1
                )
                out.append({
                    "permit_id": nid,
                    "permit_type": node.attrs.get("permit_type", "unknown"),
                    "zone_id": zid,
                    "zone": self.nodes[zid].label if zid in self.nodes else zid,
                    "hops_from_origin": hops,
                    "is_ignition_source": node.attrs.get("permit_type") == "Hot Work",
                })
        out.sort(key=lambda p: (p["hops_from_origin"], not p["is_ignition_source"]))
        return out

    def governing_regulations(self, zone_id: str) -> list[dict]:
        """Which regulation clauses govern the work currently active in this zone."""
        out = []
        for pid, _ in self.neighbours(zone_id, {"HAS_PERMIT"}):
            permit = self.nodes.get(pid)
            if not permit or permit.kind != "Permit":
                continue
            for rid, _ in self.neighbours(pid, {"GOVERNED_BY"}):
                reg = self.nodes.get(rid)
                if reg and reg.kind == "Regulation":
                    out.append({
                        "regulation_id": rid,
                        "standard": reg.attrs.get("standard", ""),
                        "section": reg.attrs.get("section", ""),
                        "via_permit": pid,
                        "permit_type": permit.attrs.get("permit_type", ""),
                    })
        return out

    def explain_path(self, source: str, target: str, max_hops: int = 4) -> list[str] | None:
        """Shortest relationship path, for showing *why* two things are connected."""
        if source not in self.nodes or target not in self.nodes:
            return None
        prev: dict[str, tuple[str, str]] = {}
        q = deque([source])
        seen = {source}
        while q:
            cur = q.popleft()
            if cur == target:
                break
            if len(prev) > max_hops * len(self.nodes):
                break
            for nxt, rel in self.neighbours(cur):
                if nxt not in seen:
                    seen.add(nxt)
                    prev[nxt] = (cur, rel)
                    q.append(nxt)
        if target not in prev and target != source:
            return None

        path, cur = [], target
        while cur != source:
            parent, rel = prev[cur]
            path.append(f"{self.nodes[parent].label} —[{rel}]→ {self.nodes[cur].label}")
            cur = parent
        return list(reversed(path))

    # --------------------------------------------------------------- export
    def to_dict(self) -> dict:
        return {
            "nodes": [n.as_dict() for n in self.nodes.values()],
            "edges": [e.as_dict() for e in self.edges],
            "counts": {
                kind: len(self.nodes_of_kind(kind))
                for kind in sorted({n.kind for n in self.nodes.values()})
            },
        }
