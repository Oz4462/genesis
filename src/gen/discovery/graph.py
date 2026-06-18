"""graph — the Discovery Graph (build doc 4.6 / Anhang C), the discovery long-term memory.

Every candidate the engine judges — kept AND rejected — becomes a node here, with its
verdict, its gate results, its δ-to-consensus and its provenance. Nodes are keyed by a
deterministic FINGERPRINT of the formula's dimensional signature, so the same law
discovered twice collapses onto one node: the graph is what stops the system from
breathlessly "re-discovering" something it already weighed (the doc's explicit goal —
"verhindert doppelte Neu-Entdeckung verworfener Ideen"). Edges record provenance and
derivation links (``analog_zu`` / ``abgeleitet_aus``), so the graph is a versioned,
searchable record, not a flat list.

It is Ledger-aligned by construction: ``to_ledger_records`` emits the exact Anhang-C JSON
schema (id, timestamp, input_idea, candidate, delta_to_consensus, gates, verdict,
provenance, parent_ids, graph_edges), the same provenance discipline as the core Ledger.
Deterministic and dependency-free (a timestamp, when wanted, is passed in — never minted —
so a run is reproducible).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace

from .engine import DiscoveryResult, DiscoveryVerdict


def _signature(target_name: str, exponents: dict[str, float]) -> str:
    """Canonical, rounded exponent signature of a candidate (target + sorted non-zero
    exponents) — the basis of the dedup fingerprint."""
    terms = sorted((name, round(p, 6)) for name, p in exponents.items() if abs(p) >= 1e-9)
    return f"{target_name}|" + ";".join(f"{n}:{p}" for n, p in terms)


def fingerprint(target_name: str, exponents: dict[str, float]) -> str:
    """A stable 16-hex fingerprint of a candidate's dimensional signature."""
    return hashlib.sha256(_signature(target_name, exponents).encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class GraphNode:
    """One Discovery-Graph node (Anhang-C schema). `id` is the dimensional fingerprint;
    `encounters` counts how often this signature was (re-)proposed — a re-encounter does
    NOT create a duplicate node, it increments this and merges provenance."""

    id: str
    input_idea: str
    candidate: str
    exponent_signature: dict[str, float]
    delta_to_consensus: float
    gates: dict
    verdict: str
    provenance: tuple[str, ...] = ()
    parent_ids: tuple[str, ...] = ()
    graph_edges: tuple[str, ...] = ()
    timestamp: str | None = None
    encounters: int = 1

    def to_record(self) -> dict:
        """The Anhang-C Ledger/Discovery-Graph JSON record for this node (lossless:
        ``from_record`` reconstructs the node exactly, so a graph round-trips through JSON)."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "input_idea": self.input_idea,
            "candidate": self.candidate,
            "exponent_signature": dict(self.exponent_signature),
            "delta_to_consensus": self.delta_to_consensus,
            "gates": self.gates,
            "verdict": self.verdict,
            "provenance": list(self.provenance),
            "parent_ids": list(self.parent_ids),
            "graph_edges": list(self.graph_edges),
            "encounters": self.encounters,
        }

    @staticmethod
    def from_record(record: dict) -> "GraphNode":
        """Reconstruct a node from its Anhang-C record (the inverse of ``to_record``)."""
        return GraphNode(
            id=record["id"],
            input_idea=record["input_idea"],
            candidate=record["candidate"],
            exponent_signature=dict(record.get("exponent_signature", {})),
            delta_to_consensus=record["delta_to_consensus"],
            gates=record["gates"],
            verdict=record["verdict"],
            provenance=tuple(record.get("provenance", ())),
            parent_ids=tuple(record.get("parent_ids", ())),
            graph_edges=tuple(record.get("graph_edges", ())),
            timestamp=record.get("timestamp"),
            encounters=record.get("encounters", 1),
        )


@dataclass
class DiscoveryGraph:
    """A versioned, searchable graph of discovery nodes, deduped by dimensional fingerprint."""

    _nodes: dict[str, GraphNode] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self._nodes)

    def get(self, node_id: str) -> GraphNode | None:
        return self._nodes.get(node_id)

    def nodes(self) -> list[GraphNode]:
        return list(self._nodes.values())

    def is_known(self, target_name: str, exponents: dict[str, float]) -> bool:
        """Has a candidate with this exact dimensional signature already been recorded? The
        rediscovery guard — a True here means 'do not re-explore, look it up'."""
        return fingerprint(target_name, exponents) in self._nodes

    def add_verdict(
        self,
        verdict: DiscoveryVerdict,
        *,
        idea: str,
        target_name: str,
        provenance: tuple[str, ...] = (),
        timestamp: str | None = None,
        parent_ids: tuple[str, ...] = (),
    ) -> GraphNode:
        """Add (or merge) one judged candidate. If its fingerprint already exists, the node
        is NOT duplicated: its encounter count rises and any new provenance is merged.
        Returns the (new or merged) node."""
        node_id = fingerprint(target_name, verdict.candidate.exponents)
        existing = self._nodes.get(node_id)
        if existing is not None:
            merged_prov = tuple(dict.fromkeys((*existing.provenance, *provenance)))
            self._nodes[node_id] = replace(existing, encounters=existing.encounters + 1,
                                           provenance=merged_prov)
            return self._nodes[node_id]
        node = GraphNode(
            id=node_id,
            input_idea=idea,
            candidate=verdict.candidate.expression,
            exponent_signature={k: round(v, 6) for k, v in verdict.candidate.exponents.items()},
            delta_to_consensus=verdict.delta_to_consensus,
            gates=verdict.gates,
            verdict=verdict.verdict,
            provenance=provenance,
            parent_ids=parent_ids,
            timestamp=timestamp,
        )
        self._nodes[node_id] = node
        return node

    def add_result(
        self,
        result: DiscoveryResult,
        *,
        target_name: str,
        provenance: tuple[str, ...] = (),
        timestamp: str | None = None,
    ) -> list[GraphNode]:
        """Record EVERY candidate of a discovery run (kept and rejected) — rejection is
        information. Returns the added/merged nodes in record order."""
        return [
            self.add_verdict(rec, idea=result.problem_idea, target_name=target_name,
                             provenance=provenance, timestamp=timestamp)
            for rec in result.all_records
        ]

    def link(self, from_id: str, to_id: str, relation: str) -> None:
        """Add a provenance/derivation edge (e.g. ``analog_zu`` / ``abgeleitet_aus``) from
        one node to another. Raises KeyError if either endpoint is unknown."""
        node = self._nodes[from_id]
        if to_id not in self._nodes:
            raise KeyError(f"edge target {to_id!r} is not a node")
        self._nodes[from_id] = replace(node, graph_edges=(*node.graph_edges, f"{relation}:{to_id}"))

    def find_by_verdict(self, verdict: str) -> list[GraphNode]:
        return [n for n in self._nodes.values() if n.verdict == verdict]

    def confirmed(self) -> list[GraphNode]:
        """The validated discoveries (verdict 'bestaetigt')."""
        return self.find_by_verdict("bestaetigt")

    def to_ledger_records(self) -> list[dict]:
        """All nodes as Anhang-C JSON records — the Ledger-aligned, serialisable form."""
        return [n.to_record() for n in self._nodes.values()]

    @staticmethod
    def from_records(records: list[dict]) -> "DiscoveryGraph":
        """Rebuild a graph from serialised Anhang-C records — used to resume a checkpointed
        exploration so the live graph contains the pre-checkpoint nodes exactly."""
        g = DiscoveryGraph()
        for rec in records:
            node = GraphNode.from_record(rec)
            g._nodes[node.id] = node
        return g

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_ledger_records(), indent=indent, ensure_ascii=False, sort_keys=True)
