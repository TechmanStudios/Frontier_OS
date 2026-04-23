# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class ThoughtProjection:
    node_id: str
    giant_name: str
    vector: np.ndarray
    confidence: float
    entropy: float
    vector_clock: int
    metadata: dict[str, Any]


class LatentMediator:
    def __init__(self, manifold_core, max_entries_per_node: int = 64, state_path: Path | None = None):
        self.manifold_core = manifold_core
        self.graph = manifold_core.graph
        self.max_entries_per_node = max_entries_per_node
        self.state_path = (
            Path(state_path)
            if state_path is not None
            else Path(__file__).resolve().parents[1] / "working_data" / "latent_mediator_state.json"
        )
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = 0
        self._blackboard: dict[str, list[ThoughtProjection]] = {}
        self.loaded_state_metadata: dict[str, Any] = {
            "loaded": False,
            "state_path": str(self.state_path),
            "clock_before_load": 0,
            "node_count": 0,
            "projection_count": 0,
        }
        self._load_state()

    def project(
        self,
        node_id: str,
        giant_name: str,
        vector: np.ndarray,
        confidence: float,
        metadata: dict[str, Any] | None = None,
    ) -> ThoughtProjection:
        normalized = np.asarray(vector, dtype=float).reshape(-1)
        entropy = self._estimate_entropy(normalized)
        self._clock += 1

        projection = ThoughtProjection(
            node_id=node_id,
            giant_name=giant_name,
            vector=normalized,
            confidence=max(float(confidence), 0.0),
            entropy=entropy,
            vector_clock=self._clock,
            metadata=metadata or {},
        )

        node_entries = self._blackboard.setdefault(node_id, [])
        node_entries.append(projection)
        if len(node_entries) > self.max_entries_per_node:
            del node_entries[0 : len(node_entries) - self.max_entries_per_node]

        self.graph.nodes[node_id]["latent_projection_count"] = len(node_entries)
        return projection

    def resolve_node(self, node_id: str) -> dict[str, Any] | None:
        entries = self._blackboard.get(node_id, [])
        if not entries:
            return None

        weights = np.array(
            [max(entry.confidence / (1.0 + entry.entropy), 1e-6) for entry in entries],
            dtype=float,
        )
        weights /= weights.sum()
        stacked = np.vstack([entry.vector for entry in entries])
        consensus_vector = np.average(stacked, axis=0, weights=weights)
        dominant_entry = entries[int(np.argmax(weights))]

        return {
            "node_id": node_id,
            "consensus_vector": consensus_vector,
            "consensus_entropy": float(np.average([entry.entropy for entry in entries], weights=weights)),
            "consensus_confidence": float(np.max(weights)),
            "dominant_giant": dominant_entry.giant_name,
            "vector_clock": max(entry.vector_clock for entry in entries),
            "source_giants": [entry.giant_name for entry in entries],
        }

    def publish_consensus(self, node_id: str) -> dict[str, Any] | None:
        consensus = self.resolve_node(node_id)
        if consensus is None:
            return None

        node = self.graph.nodes[node_id]
        node["consensus_vector"] = consensus["consensus_vector"]
        node["consensus_entropy"] = consensus["consensus_entropy"]
        node["consensus_confidence"] = consensus["consensus_confidence"]
        node["consensus_clock"] = consensus["vector_clock"]
        node["consensus_sources"] = consensus["source_giants"]
        node["dominant_giant"] = consensus["dominant_giant"]
        return consensus

    def persist_state(self):
        serialized = {
            "clock": self._clock,
            "max_entries_per_node": self.max_entries_per_node,
            "blackboard": {
                node_id: [self._serialize_projection(entry) for entry in entries]
                for node_id, entries in self._blackboard.items()
            },
        }
        self.state_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")

    def _load_state(self):
        if not self.state_path.exists():
            return

        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        self._clock = int(payload.get("clock", 0))
        blackboard = payload.get("blackboard", {})
        self.loaded_state_metadata = {
            "loaded": True,
            "state_path": str(self.state_path),
            "clock_before_load": self._clock,
            "node_count": len(blackboard),
            "projection_count": int(sum(len(entries) for entries in blackboard.values())),
        }
        for node_id, entries in blackboard.items():
            self._blackboard[node_id] = [self._deserialize_projection(node_id, entry) for entry in entries]
            if node_id in self.graph:
                self.graph.nodes[node_id]["latent_projection_count"] = len(self._blackboard[node_id])
                self.publish_consensus(node_id)

    def get_state_load_metadata(self) -> dict[str, Any]:
        return dict(self.loaded_state_metadata)

    def _serialize_projection(self, projection: ThoughtProjection) -> dict[str, Any]:
        return {
            "giant_name": projection.giant_name,
            "vector": projection.vector.tolist(),
            "confidence": projection.confidence,
            "entropy": projection.entropy,
            "vector_clock": projection.vector_clock,
            "metadata": projection.metadata,
        }

    def _deserialize_projection(self, node_id: str, payload: dict[str, Any]) -> ThoughtProjection:
        return ThoughtProjection(
            node_id=node_id,
            giant_name=payload["giant_name"],
            vector=np.asarray(payload.get("vector", []), dtype=float),
            confidence=float(payload.get("confidence", 0.0)),
            entropy=float(payload.get("entropy", 0.0)),
            vector_clock=int(payload.get("vector_clock", 0)),
            metadata=dict(payload.get("metadata", {})),
        )

    def _estimate_entropy(self, vector: np.ndarray) -> float:
        magnitude = np.abs(vector)
        total = float(np.sum(magnitude))
        if total <= 0.0:
            return 0.0

        probabilities = magnitude / total
        probabilities = np.clip(probabilities, 1e-12, 1.0)
        return float(-np.sum(probabilities * np.log(probabilities)))
