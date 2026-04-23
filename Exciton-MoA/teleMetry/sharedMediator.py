# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
from teleMetry.latentMediator import ThoughtProjection


class SharedMediator:
    def __init__(
        self,
        pair_id: str,
        manifold_ids: Sequence[str],
        max_entries_per_channel: int = 64,
        state_path: Path | None = None,
    ):
        self.pair_id = str(pair_id)
        self.manifold_ids = tuple(str(manifold_id) for manifold_id in manifold_ids)
        self.max_entries_per_channel = max(int(max_entries_per_channel), 1)
        self.state_path = (
            Path(state_path)
            if state_path is not None
            else Path(__file__).resolve().parents[1] / "working_data" / f"shared_entanglement_locus_{self.pair_id}.json"
        )
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._pair_clock = 0
        self._blackboard: dict[str, list[ThoughtProjection]] = {}
        self._resolved_channels: dict[str, dict[str, Any]] = {}
        self._latest_summary: dict[str, Any] = {}
        self.loaded_state_metadata: dict[str, Any] = {
            "loaded": False,
            "state_path": str(self.state_path),
            "pair_clock_before_load": 0,
            "channel_count": 0,
            "projection_count": 0,
        }
        self._load_state()

    def project(
        self,
        channel_id: str,
        giant_name: str,
        vector: np.ndarray,
        confidence: float,
        metadata: dict[str, Any] | None = None,
    ) -> ThoughtProjection:
        normalized = self._pad_vector(vector)
        entropy = self._estimate_entropy(normalized)
        self._pair_clock += 1

        projection = ThoughtProjection(
            node_id=channel_id,
            giant_name=str(giant_name),
            vector=normalized,
            confidence=max(float(confidence), 0.0),
            entropy=entropy,
            vector_clock=self._pair_clock,
            metadata=self._to_jsonable(metadata or {}),
        )

        channel_entries = self._blackboard.setdefault(channel_id, [])
        channel_entries.append(projection)
        if len(channel_entries) > self.max_entries_per_channel:
            del channel_entries[0 : len(channel_entries) - self.max_entries_per_channel]

        return projection

    def resolve_channel(self, channel_id: str) -> dict[str, Any] | None:
        entries = self._blackboard.get(channel_id, [])
        if not entries:
            return None

        weights = np.array([max(entry.confidence / (1.0 + entry.entropy), 1e-6) for entry in entries], dtype=float)
        weights /= weights.sum()
        stacked = np.vstack([entry.vector for entry in entries])
        consensus_vector = np.average(stacked, axis=0, weights=weights)
        dominant_entry = entries[int(np.argmax(weights))]

        return {
            "channel_id": channel_id,
            "consensus_vector": consensus_vector,
            "consensus_entropy": float(np.average([entry.entropy for entry in entries], weights=weights)),
            "consensus_confidence": float(np.max(weights)),
            "dominant_giant": dominant_entry.giant_name,
            "vector_clock": max(entry.vector_clock for entry in entries),
            "source_giants": [entry.giant_name for entry in entries],
            "projection_count": len(entries),
        }

    def publish_consensus(self, channel_id: str) -> dict[str, Any] | None:
        consensus = self.resolve_channel(channel_id)
        if consensus is None:
            return None
        self._resolved_channels[channel_id] = consensus
        return consensus

    def publish_pair_state(
        self,
        shared_flux: Sequence[float],
        phase_coherence: float,
        wormhole_nodes: Sequence[str],
        bilateral_node_ids: Sequence[str],
        top_events: Sequence[dict[str, Any]] | None = None,
        cross_domain_giant: str = "Entanglement Locus",
        local_consensus: dict[str, dict[str, dict[str, Any]]] | None = None,
        pair_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        flux_vector = self._pad_vector(shared_flux)
        phase_value = float(phase_coherence)
        wormhole_list = [str(node_id) for node_id in wormhole_nodes]
        bilateral_ids = sorted({str(node_id) for node_id in bilateral_node_ids})
        local_payload = self._to_jsonable(local_consensus or {})
        metadata = self._to_jsonable(pair_metadata or {})
        top_event_list = self._to_jsonable(list(top_events or []))
        flux_norm = float(np.linalg.norm(flux_vector))
        locus_confidence = float(np.clip((phase_value + 1.0) * 0.5, 0.0, 1.0))
        previous_summary = self._to_jsonable(self._latest_summary)

        self.project(
            channel_id="entanglement_locus",
            giant_name=cross_domain_giant,
            vector=flux_vector,
            confidence=locus_confidence,
            metadata={
                "pair_id": self.pair_id,
                "manifold_ids": list(self.manifold_ids),
                "wormhole_nodes": wormhole_list,
                "bilateral_node_ids": bilateral_ids,
                "phase_coherence": phase_value,
                "shared_flux_norm": flux_norm,
                "top_events": top_event_list,
                "local_consensus": local_payload,
                **metadata,
            },
        )
        locus_consensus = self.publish_consensus("entanglement_locus")

        for node_id in wormhole_list:
            projection = self._build_wormhole_projection(
                node_id=node_id,
                shared_flux=flux_vector,
                phase_coherence=phase_value,
                bilateral=node_id in bilateral_ids,
                cross_domain_giant=cross_domain_giant,
                local_consensus=local_payload,
            )
            self.project(
                channel_id=node_id,
                giant_name=projection["giant_name"],
                vector=np.asarray(projection["vector"], dtype=float),
                confidence=float(projection["confidence"]),
                metadata=projection["metadata"],
            )
            self.publish_consensus(node_id)

        local_clock_max = max(
            [int(node_payload.get("consensus_clock", 0)) for channels in local_payload.values() for node_payload in channels.values()]
            or [0]
        )
        dominant_channel = self._dominant_channel(
            np.asarray(locus_consensus["consensus_vector"] if locus_consensus is not None else flux_vector, dtype=float)
        )
        self._latest_summary = {
            "pair_id": self.pair_id,
            "manifold_ids": list(self.manifold_ids),
            "pair_clock": self._pair_clock,
            "shared_flux_vector": flux_vector.tolist(),
            "shared_flux_norm": flux_norm,
            "phase_coherence": phase_value,
            "dominant_channel": dominant_channel,
            "cross_domain_giant": str(cross_domain_giant),
            "bilateral_burst_count": len(bilateral_ids),
            "bilateral_node_ids": bilateral_ids,
            "wormhole_count": len(wormhole_list),
            "wormhole_nodes": wormhole_list,
            "local_clock_max": local_clock_max,
            "top_events": top_event_list,
            "resolved_channels": {
                channel_id: self._serialize_resolved_payload(resolved)
                for channel_id, resolved in self._resolved_channels.items()
                if channel_id == "entanglement_locus" or channel_id == "entangler_control" or channel_id in wormhole_list
            },
        }
        self._preserve_latest_summary_fields(previous_summary)
        self.persist_state()
        return self.get_latest_summary()

    def publish_entangler_control(self, control_report: dict[str, Any]) -> dict[str, Any]:
        report = self._to_jsonable(control_report)
        controls_after = dict(report.get("controls_after", {}))
        control_vector = self._pad_vector(
            [
                controls_after.get("aperture", 0.0),
                controls_after.get("damping", 0.0),
                controls_after.get("phase_offset", 0.0),
            ]
        )
        confidence = max(float(report.get("entanglement_strength", 0.0)), 1e-6)
        self.project(
            channel_id="entangler_control",
            giant_name="Entangler Giant",
            vector=control_vector,
            confidence=confidence,
            metadata={
                "pair_id": self.pair_id,
                "manifold_ids": list(self.manifold_ids),
                **report,
            },
        )
        consensus = self.publish_consensus("entangler_control")
        entangler_summary = {
            "pair_id": self.pair_id,
            "controller": "Entangler Giant",
            "control_mode": str(report.get("control_mode", "active")),
            "coherence_mode": str(report.get("coherence_mode", "active")),
            "next_coherence_mode": str(report.get("next_coherence_mode", report.get("coherence_mode", "active"))),
            "pair_clock": self._pair_clock,
            "entanglement_strength": float(report.get("entanglement_strength", 0.0)),
            "dominant_giant_consensus": str(report.get("dominant_giant_consensus", "Entanglement Locus")),
            "coherence_feedback": dict(report.get("coherence_feedback", {})),
            "mode_transition": dict(report.get("mode_transition", {})),
            "mode_decay_streak": int(report.get("mode_decay_streak", 0)),
            "mode_improving_streak": int(report.get("mode_improving_streak", 0)),
            "stabilizer_dwell_ticks": int(report.get("stabilizer_dwell_ticks", 0)),
            "wormhole_weight_map": dict(report.get("wormhole_weight_map", {})),
            "wormhole_weight_summary": dict(report.get("wormhole_weight_summary", {})),
            "controls_before": dict(report.get("controls_before", {})),
            "controls_after": dict(report.get("controls_after", {})),
            "control_delta": dict(report.get("control_delta", {})),
            "targets": dict(report.get("targets", {})),
            "clamp_flags": dict(report.get("clamp_flags", {})),
            "features": dict(report.get("features", {})),
            "hint_gate": dict(report.get("hint_gate", {})),
            "wormhole_health": dict(report.get("wormhole_health", {})),
            "reasoning_summary": str(report.get("reasoning_summary", "")),
            "consensus_vector": control_vector.tolist() if consensus is None else self._pad_vector(consensus.get("consensus_vector", [])).tolist(),
            "consensus_confidence": confidence if consensus is None else float(consensus.get("consensus_confidence", confidence)),
        }

        if not self._latest_summary:
            self._latest_summary = {
                "pair_id": self.pair_id,
                "manifold_ids": list(self.manifold_ids),
                "pair_clock": self._pair_clock,
                "resolved_channels": {},
            }

        self._latest_summary["pair_clock"] = self._pair_clock
        self._latest_summary.setdefault("resolved_channels", {})["entangler_control"] = self._serialize_resolved_payload(
            self._resolved_channels["entangler_control"]
        )
        self._latest_summary["entangler_control"] = entangler_summary
        self.persist_state()
        return self.get_latest_summary().get("entangler_control", entangler_summary)

    def publish_phonon_bundle(self, phonon_bundle: dict[str, Any]) -> dict[str, Any]:
        bundle = self._to_jsonable(phonon_bundle)
        bundles = list(self._latest_summary.get("phonon_bundles", []))
        bundles.append(bundle)
        bundles = bundles[-self.max_entries_per_channel :]

        if not self._latest_summary:
            self._latest_summary = {
                "pair_id": self.pair_id,
                "manifold_ids": list(self.manifold_ids),
                "pair_clock": self._pair_clock,
                "resolved_channels": {},
            }

        self._latest_summary["pair_clock"] = max(int(bundle.get("pair_clock", 0)), int(self._latest_summary.get("pair_clock", 0)))
        self._latest_summary["phonon_bundles"] = bundles
        self._latest_summary["latest_phonon_bundle"] = bundle
        self.persist_state()
        return bundle

    def publish_phonon_control_hint(self, phonon_control_hint: dict[str, Any]) -> dict[str, Any]:
        hint = self._to_jsonable(phonon_control_hint)
        hints = list(self._latest_summary.get("phonon_control_hints", []))
        hints.append(hint)
        hints = hints[-self.max_entries_per_channel :]

        if not self._latest_summary:
            self._latest_summary = {
                "pair_id": self.pair_id,
                "manifold_ids": list(self.manifold_ids),
                "pair_clock": self._pair_clock,
                "resolved_channels": {},
            }

        self._latest_summary["pair_clock"] = max(int(self._latest_summary.get("pair_clock", 0)), self._pair_clock)
        self._latest_summary["phonon_control_hints"] = hints
        self._latest_summary["latest_phonon_control_hint"] = hint
        self.persist_state()
        return hint

    def get_latest_summary(self) -> dict[str, Any]:
        return self._to_jsonable(self._latest_summary)

    def get_state_load_metadata(self) -> dict[str, Any]:
        return dict(self.loaded_state_metadata)

    def persist_state(self) -> None:
        serialized = {
            "pair_id": self.pair_id,
            "manifold_ids": list(self.manifold_ids),
            "pair_clock": self._pair_clock,
            "max_entries_per_channel": self.max_entries_per_channel,
            "blackboard": {
                channel_id: [self._serialize_projection(entry) for entry in entries]
                for channel_id, entries in self._blackboard.items()
            },
            "resolved_channels": {
                channel_id: self._serialize_resolved_payload(resolved)
                for channel_id, resolved in self._resolved_channels.items()
            },
            "latest_summary": self.get_latest_summary(),
        }
        self.state_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")

    def _load_state(self) -> None:
        if not self.state_path.exists():
            return

        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        self._pair_clock = int(payload.get("pair_clock", 0))
        blackboard = payload.get("blackboard", {})
        self.loaded_state_metadata = {
            "loaded": True,
            "state_path": str(self.state_path),
            "pair_clock_before_load": self._pair_clock,
            "channel_count": len(blackboard),
            "projection_count": int(sum(len(entries) for entries in blackboard.values())),
        }
        for channel_id, entries in blackboard.items():
            self._blackboard[channel_id] = [self._deserialize_projection(channel_id, entry) for entry in entries]
        for channel_id, resolved in payload.get("resolved_channels", {}).items():
            self._resolved_channels[channel_id] = self._deserialize_resolved_payload(resolved)
        self._latest_summary = self._to_jsonable(payload.get("latest_summary", {}))

    def _build_wormhole_projection(
        self,
        node_id: str,
        shared_flux: np.ndarray,
        phase_coherence: float,
        bilateral: bool,
        cross_domain_giant: str,
        local_consensus: dict[str, dict[str, dict[str, Any]]],
    ) -> dict[str, Any]:
        vectors: list[np.ndarray] = []
        confidences: list[float] = []
        dominant_weights: dict[str, float] = {}
        per_manifold: dict[str, dict[str, Any]] = {}

        for manifold_id in self.manifold_ids:
            node_payload = dict(local_consensus.get(manifold_id, {}).get(node_id, {}))
            if not node_payload:
                continue

            vector = self._pad_vector(node_payload.get("consensus_vector", shared_flux))
            confidence = max(float(node_payload.get("consensus_confidence", 0.0)), 0.0)
            vectors.append(vector)
            confidences.append(confidence)

            dominant_giant = str(node_payload.get("dominant_giant") or cross_domain_giant)
            dominant_weights[dominant_giant] = dominant_weights.get(dominant_giant, 0.0) + max(confidence, 1e-6)
            per_manifold[manifold_id] = {
                "consensus_vector": vector.tolist(),
                "consensus_confidence": confidence,
                "consensus_entropy": float(node_payload.get("consensus_entropy", 0.0)),
                "consensus_clock": int(node_payload.get("consensus_clock", 0)),
                "dominant_giant": dominant_giant,
            }

        combined_vector = np.mean(vectors, axis=0) if vectors else shared_flux
        average_confidence = float(sum(confidences) / len(confidences)) if confidences else 0.0
        projected_confidence = float(np.clip(((phase_coherence + 1.0) * 0.5) * (0.5 + (0.5 * average_confidence)), 0.0, 1.0))
        giant_name = max(dominant_weights.items(), key=lambda item: item[1])[0] if dominant_weights else cross_domain_giant

        return {
            "giant_name": giant_name,
            "vector": combined_vector.tolist(),
            "confidence": projected_confidence,
            "metadata": {
                "pair_id": self.pair_id,
                "manifold_ids": list(self.manifold_ids),
                "wormhole_node": node_id,
                "bilateral_burst": bool(bilateral),
                "phase_coherence": float(phase_coherence),
                "shared_flux_norm": float(np.linalg.norm(shared_flux)),
                "local_consensus": per_manifold,
            },
        }

    def _serialize_projection(self, projection: ThoughtProjection) -> dict[str, Any]:
        return {
            "giant_name": projection.giant_name,
            "vector": projection.vector.tolist(),
            "confidence": projection.confidence,
            "entropy": projection.entropy,
            "vector_clock": projection.vector_clock,
            "metadata": self._to_jsonable(projection.metadata),
        }

    def _deserialize_projection(self, channel_id: str, payload: dict[str, Any]) -> ThoughtProjection:
        return ThoughtProjection(
            node_id=channel_id,
            giant_name=str(payload.get("giant_name", "Entanglement Locus")),
            vector=self._pad_vector(payload.get("vector", [])),
            confidence=float(payload.get("confidence", 0.0)),
            entropy=float(payload.get("entropy", 0.0)),
            vector_clock=int(payload.get("vector_clock", 0)),
            metadata=self._to_jsonable(payload.get("metadata", {})),
        )

    def _serialize_resolved_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        serialized = dict(payload)
        serialized["consensus_vector"] = self._pad_vector(payload.get("consensus_vector", [])).tolist()
        serialized["source_giants"] = list(payload.get("source_giants", []))
        return self._to_jsonable(serialized)

    def _deserialize_resolved_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        deserialized = dict(payload)
        deserialized["consensus_vector"] = self._pad_vector(payload.get("consensus_vector", []))
        deserialized["source_giants"] = list(payload.get("source_giants", []))
        return deserialized

    def _preserve_latest_summary_fields(self, previous_summary: dict[str, Any]) -> None:
        for key in (
            "entangler_control",
            "latest_phonon_bundle",
            "phonon_bundles",
            "latest_phonon_control_hint",
            "phonon_control_hints",
        ):
            if key in previous_summary and key not in self._latest_summary:
                self._latest_summary[key] = self._to_jsonable(previous_summary[key])

    def _dominant_channel(self, vector: np.ndarray) -> str:
        padded = self._pad_vector(vector)
        labels = ("density", "shear", "vorticity")
        return labels[int(np.argmax(np.abs(padded[:3])))]

    def _pad_vector(self, vector: Any) -> np.ndarray:
        raw = np.asarray(vector, dtype=float).reshape(-1)
        padded = np.zeros(3, dtype=float)
        padded[: min(raw.size, 3)] = raw[: min(raw.size, 3)]
        return padded

    def _estimate_entropy(self, vector: np.ndarray) -> float:
        magnitude = np.abs(vector)
        total = float(np.sum(magnitude))
        if total <= 0.0:
            return 0.0
        probabilities = magnitude / total
        probabilities = np.clip(probabilities, 1e-12, 1.0)
        return float(-np.sum(probabilities * np.log(probabilities)))

    def _to_jsonable(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, dict):
            return {str(key): self._to_jsonable(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._to_jsonable(item) for item in value]
        return value