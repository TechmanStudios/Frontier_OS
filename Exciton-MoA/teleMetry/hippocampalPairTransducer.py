# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any


class HippocampalPairTransducer:
    def __init__(
        self,
        transducer_a,
        transducer_b,
        pair_id: str,
        manifold_ids: tuple[str, str],
        wormhole_nodes: Sequence[str] | None = None,
    ):
        self.transducer_a = transducer_a
        self.transducer_b = transducer_b
        self.pair_id = pair_id
        self.manifold_ids = manifold_ids
        self.wormhole_nodes = list(wormhole_nodes or [])

    def capture_bilateral_bursts(
        self,
        bursts_a: Iterable[tuple[str, dict[str, Any]]],
        bursts_b: Iterable[tuple[str, dict[str, Any]]],
        manifold_a,
        manifold_b,
        pair_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        burst_list_a = list(bursts_a)
        burst_list_b = list(bursts_b)
        wormhole_set = set(
            pair_metadata.get("wormhole_nodes", self.wormhole_nodes) if pair_metadata else self.wormhole_nodes
        )
        burst_ids_a = {node_id for node_id, _ in burst_list_a}
        burst_ids_b = {node_id for node_id, _ in burst_list_b}
        bilateral_node_ids = burst_ids_a & burst_ids_b
        if wormhole_set:
            bilateral_node_ids &= wormhole_set

        metadata = pair_metadata or {}
        shared_flux = metadata.get("shared_flux", [0.0, 0.0, 0.0])
        shared_flux_norm = sum(float(value) ** 2 for value in shared_flux) ** 0.5
        latest_phonon = dict(metadata.get("phonon_bundle", {}))
        coherence_signature = dict(latest_phonon.get("coherence_signature", {}))

        phonon_context = {}
        if latest_phonon.get("phonon_id"):
            phonon_context = {
                "phonon_id": str(latest_phonon.get("phonon_id")),
                "phonon_confidence": float(latest_phonon.get("confidence", 0.0)),
                "phonon_entropy": float(latest_phonon.get("entropy", 0.0)),
                "phonon_mode": str(latest_phonon.get("mode", "density")),
                "phonon_predicted_next_mode": str(latest_phonon.get("predicted_next_mode", "active")),
                "phonon_stability_score": float(coherence_signature.get("stability_score", 0.0)),
                "wormhole_entry_count": int(len(list(latest_phonon.get("wormhole_entry_nodes", [])))),
                "wormhole_exit_count": int(len(list(latest_phonon.get("wormhole_exit_nodes", [])))),
            }

        context_a = {
            "pair_id": self.pair_id,
            "source_manifold_id": self.manifold_ids[0],
            "bilateral_node_ids": list(bilateral_node_ids),
            "cross_domain_giant": metadata.get("cross_domain_giant", "Entanglement Locus"),
            "phase_coherence": float(metadata.get("phase_coherence", 0.0)),
            "shared_flux_norm": float(shared_flux_norm),
            "wormhole_nodes": list(wormhole_set),
            **phonon_context,
        }
        context_b = {
            "pair_id": self.pair_id,
            "source_manifold_id": self.manifold_ids[1],
            "bilateral_node_ids": list(bilateral_node_ids),
            "cross_domain_giant": metadata.get("cross_domain_giant", "Entanglement Locus"),
            "phase_coherence": float(metadata.get("phase_coherence", 0.0)),
            "shared_flux_norm": float(shared_flux_norm),
            "wormhole_nodes": list(wormhole_set),
            **phonon_context,
        }

        path_a = self.transducer_a.capture_bursts(burst_list_a, manifold_a, pair_context=context_a)
        path_b = self.transducer_b.capture_bursts(burst_list_b, manifold_b, pair_context=context_b)
        return {
            "pair_id": self.pair_id,
            "paths": {self.manifold_ids[0]: path_a, self.manifold_ids[1]: path_b},
            "bilateral_node_ids": sorted(bilateral_node_ids),
        }
