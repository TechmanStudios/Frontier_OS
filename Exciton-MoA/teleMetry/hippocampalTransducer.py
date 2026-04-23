# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np


class HippocampalTransducer:
    def __init__(self, output_dir: Path | None = None, burst_flush_threshold: int = 1):
        self.output_dir = Path(output_dir) if output_dir is not None else Path(__file__).resolve().parents[1] / "working_data"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.sequence_buffer: list[dict[str, Any]] = []
        self.long_term_archive = self.output_dir / "hippocampal_long_term.jsonl"
        self.burst_flush_threshold = max(int(burst_flush_threshold), 1)

    def capture_bursts(
        self,
        bursts: Iterable[tuple[str, dict[str, Any]]],
        manifold,
        pair_context: dict[str, Any] | None = None,
    ) -> Path | None:
        batch: list[dict[str, Any]] = []
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        bilateral_node_ids = set(pair_context.get("bilateral_node_ids", [])) if pair_context is not None else set()
        wormhole_nodes = set(pair_context.get("wormhole_nodes", [])) if pair_context is not None else set()

        for node_id, metrics in bursts:
            node = manifold.nodes[node_id]
            record = {
                "timestamp": timestamp,
                "node_id": node_id,
                "h_total": float(metrics.get("H_total", 0.0)),
                "tau_threshold": float(metrics.get("tau_threshold", 0.0)),
                "density": float(metrics.get("density", metrics.get("density_grad", 0.0))),
                "density_signal": float(metrics.get("density_signal", 0.0)),
                "density_contrib": float(metrics.get("density_contrib", 0.0)),
                "shear": float(metrics.get("shear", metrics.get("shear_grad", 0.0))),
                "shear_signal": float(metrics.get("shear_signal", 0.0)),
                "shear_contrib": float(metrics.get("shear_contrib", 0.0)),
                "vorticity": float(metrics.get("vorticity", 0.0)),
                "vorticity_signal": float(metrics.get("vorticity_signal", 0.0)),
                "vorticity_contrib": float(metrics.get("vorticity_contrib", 0.0)),
                "dominant_giant": node.get("dominant_giant") or "Ambient Basin",
                "consensus_clock": node.get("consensus_clock"),
                "consensus_entropy": float(node.get("consensus_entropy", 0.0)),
                "consensus_confidence": float(node.get("consensus_confidence", 0.0)),
                "consensus_vector": self._serialize_vector(node.get("consensus_vector")),
                "consensus_sources": list(node.get("consensus_sources", [])),
            }
            if pair_context is not None:
                record.update(
                    {
                        "pair_id": pair_context.get("pair_id"),
                        "source_manifold_id": pair_context.get("source_manifold_id"),
                        "bilateral_burst": node_id in bilateral_node_ids,
                        "cross_domain_giant": pair_context.get("cross_domain_giant", "Entanglement Locus"),
                        "phase_coherence": float(pair_context.get("phase_coherence", 0.0)),
                        "shared_flux_norm": float(pair_context.get("shared_flux_norm", 0.0)),
                        "wormhole_boundary": node_id in wormhole_nodes,
                    }
                )
                phonon_id = pair_context.get("phonon_id")
                if phonon_id is not None:
                    record.update(
                        {
                            "phonon_id": str(phonon_id),
                            "phonon_confidence": float(pair_context.get("phonon_confidence", 0.0)),
                            "phonon_entropy": float(pair_context.get("phonon_entropy", 0.0)),
                            "phonon_mode": str(pair_context.get("phonon_mode", "density")),
                            "phonon_predicted_next_mode": str(pair_context.get("phonon_predicted_next_mode", "active")),
                            "phonon_stability_score": float(pair_context.get("phonon_stability_score", 0.0)),
                            "wormhole_entry_count": int(pair_context.get("wormhole_entry_count", 0)),
                            "wormhole_exit_count": int(pair_context.get("wormhole_exit_count", 0)),
                        }
                    )
            batch.append(record)

        if not batch:
            return None

        self.sequence_buffer.extend(batch)
        if len(self.sequence_buffer) < self.burst_flush_threshold:
            return None

        burst_path = self.output_dir / f"hippocampal_burst_{timestamp}.json"
        burst_path.write_text(json.dumps(self.sequence_buffer, indent=2), encoding="utf-8")

        with self.long_term_archive.open("a", encoding="utf-8") as archive:
            for record in self.sequence_buffer:
                archive.write(json.dumps(record) + "\n")

        self.sequence_buffer = []
        return burst_path

    def _serialize_vector(self, vector: Any) -> list[float]:
        if vector is None:
            return []
        return [float(value) for value in np.asarray(vector, dtype=float).reshape(-1)]