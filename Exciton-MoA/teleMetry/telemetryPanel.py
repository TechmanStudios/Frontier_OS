# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


class TelemetryPanel:
    def __init__(self, working_dir: Optional[Path] = None, history_limit: int = 8, bar_width: int = 8):
        self.working_dir = Path(working_dir) if working_dir is not None else Path(__file__).resolve().parents[1] / "working_data"
        self.working_dir.mkdir(parents=True, exist_ok=True)
        self.history_limit = max(int(history_limit), 1)
        self.bar_width = max(int(bar_width), 4)
        self.history_path = self.working_dir / "adaptive_tau_history.jsonl"

    def record_scan(
        self,
        manifold_id: str,
        adaptive_tau: float,
        burst_count: int,
        avg_h: float,
        max_h: float,
        bursts: Optional[Sequence[Tuple[str, Dict[str, float]]]] = None,
    ) -> Dict[str, object]:
        burst_summary = self._summarize_bursts(bursts or [])
        entry = {
            "schema_version": "1.1",
            "record_type": "manifold",
            "timestamp": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            "manifold_id": manifold_id,
            "adaptive_tau": float(adaptive_tau),
            "burst_count": int(burst_count),
            "avg_h": float(avg_h),
            "max_h": float(max_h),
            "dominant_channel": burst_summary["dominant_channel"],
            "avg_density_contrib": burst_summary["avg_density_contrib"],
            "avg_shear_contrib": burst_summary["avg_shear_contrib"],
            "avg_vorticity_contrib": burst_summary["avg_vorticity_contrib"],
            "top_nodes": burst_summary["top_nodes"],
        }

        with self.history_path.open("a", encoding="utf-8") as history_file:
            history_file.write(json.dumps(entry) + "\n")

        return entry

    def record_pair_scan(
        self,
        pair_id: str,
        manifold_a_id: str,
        manifold_b_id: str,
        wormhole_nodes: Sequence[str],
        wormhole_aperture: float,
        damping: float,
        phase_offset: float,
        shared_flux: Sequence[float],
        phase_coherence: float,
        bilateral_burst_count: int,
        max_h_cross_domain: float,
        bilateral_node_ids: Optional[Sequence[str]] = None,
        top_events: Optional[Sequence[Dict[str, object]]] = None,
        shared_locus_summary: Optional[Dict[str, object]] = None,
        entangler_control: Optional[Dict[str, object]] = None,
        latest_local_phonon_bundle: Optional[Dict[str, object]] = None,
        local_phonon_bundle_count: int = 0,
        phonon_control_hint: Optional[Dict[str, object]] = None,
    ) -> Dict[str, object]:
        flux = list(float(value) for value in shared_flux)
        while len(flux) < 3:
            flux.append(0.0)

        dominant_channel = self._dominant_channel(
            density=float(flux[0]),
            shear=float(flux[1]),
            vorticity=float(flux[2]),
        )
        entry = {
            "schema_version": "2.2",
            "record_type": "pair",
            "timestamp": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            "pair_id": pair_id,
            "manifold_a_id": manifold_a_id,
            "manifold_b_id": manifold_b_id,
            "wormhole_count": len(list(wormhole_nodes)),
            "wormhole_nodes": list(wormhole_nodes),
            "wormhole_aperture": float(wormhole_aperture),
            "damping": float(damping),
            "phase_offset": float(phase_offset),
            "shared_flux_density": float(flux[0]),
            "shared_flux_shear": float(flux[1]),
            "shared_flux_vorticity": float(flux[2]),
            "entanglement_strength": float((flux[0] ** 2 + flux[1] ** 2 + flux[2] ** 2) ** 0.5),
            "phase_coherence": float(phase_coherence),
            "bilateral_burst_count": int(bilateral_burst_count),
            "bilateral_node_ids": list(bilateral_node_ids or []),
            "max_h_cross_domain": float(max_h_cross_domain),
            "dominant_channel": dominant_channel,
            "top_events": list(top_events or []),
            "local_phonon_bundle_count": int(local_phonon_bundle_count),
        }

        if shared_locus_summary is not None:
            entry["shared_pair_clock"] = int(shared_locus_summary.get("pair_clock", 0))
            entry["shared_dominant_channel"] = str(shared_locus_summary.get("dominant_channel", dominant_channel))
            entry["shared_locus_giant"] = str(shared_locus_summary.get("cross_domain_giant", "Entanglement Locus"))
            entry["shared_flux_norm"] = float(shared_locus_summary.get("shared_flux_norm", entry["entanglement_strength"]))
            latest_phonon_bundle = dict(shared_locus_summary.get("latest_phonon_bundle", {}))
            entry["phonon_bundle_count"] = int(len(list(shared_locus_summary.get("phonon_bundles", []))))
            if latest_phonon_bundle:
                coherence_signature = dict(latest_phonon_bundle.get("coherence_signature", {}))
                entry["phonon_id"] = str(latest_phonon_bundle.get("phonon_id", ""))
                entry["phonon_mode"] = str(latest_phonon_bundle.get("mode", dominant_channel))
                entry["phonon_amplitude"] = float(latest_phonon_bundle.get("amplitude", 0.0))
                entry["phonon_confidence"] = float(latest_phonon_bundle.get("confidence", 0.0))
                entry["phonon_decay_rate"] = float(latest_phonon_bundle.get("decay_rate", 0.0))
                entry["phonon_predicted_next_mode"] = str(latest_phonon_bundle.get("predicted_next_mode", "active"))
                entry["phonon_entry_count"] = int(len(list(latest_phonon_bundle.get("wormhole_entry_nodes", []))))
                entry["phonon_exit_count"] = int(len(list(latest_phonon_bundle.get("wormhole_exit_nodes", []))))
                entry["phonon_status"] = str(coherence_signature.get("status", "stable"))
                entry["phonon_stability_score"] = float(coherence_signature.get("stability_score", 0.0))

        local_bundle = dict(latest_local_phonon_bundle or {})
        if local_bundle:
            local_signature = dict(local_bundle.get("coherence_signature", {}))
            entry["local_phonon_id"] = str(local_bundle.get("phonon_id", ""))
            entry["local_phonon_tier"] = str(local_bundle.get("source_tier", "local"))
            entry["local_phonon_carrier"] = str(local_bundle.get("carrier_giant", "Ambient Basin"))
            entry["local_phonon_mode"] = str(local_bundle.get("mode", dominant_channel))
            entry["local_phonon_amplitude"] = float(local_bundle.get("amplitude", 0.0))
            entry["local_phonon_confidence"] = float(local_bundle.get("confidence", 0.0))
            entry["local_phonon_decay_rate"] = float(local_bundle.get("decay_rate", 0.0))
            entry["local_phonon_entry_count"] = int(len(list(local_bundle.get("wormhole_entry_nodes", []))))
            entry["local_phonon_exit_count"] = int(len(list(local_bundle.get("wormhole_exit_nodes", []))))
            entry["local_phonon_source_node_count"] = int(len(list(local_bundle.get("source_nodes", []))))
            entry["local_phonon_status"] = str(local_signature.get("status", "stable"))
            entry["local_phonon_stability_score"] = float(local_signature.get("stability_score", 0.0))

        hint = dict(phonon_control_hint or {})
        if hint:
            entry["phonon_hint_status"] = str(hint.get("status", "suppressed"))
            entry["phonon_hint_recommendation"] = str(hint.get("recommended_bias", "observe"))
            entry["phonon_hint_confidence"] = float(hint.get("confidence", 0.0))
            entry["phonon_hint_age_ticks"] = int(hint.get("age_ticks", 0))
            entry["phonon_hint_stability_window"] = int(hint.get("stability_window", 0))
            entry["phonon_hint_suppression_reason"] = str(hint.get("suppression_reason", "none"))
            entry["phonon_hint_decision_reason"] = str(hint.get("decision_reason", "unknown"))
            entry["phonon_hint_source_tier"] = str(hint.get("source_tier", "none"))
            entry["phonon_hint_entry_pressure"] = float(hint.get("entry_pressure", 0.0))
            entry["phonon_hint_exit_pressure"] = float(hint.get("exit_pressure", 0.0))
            entry["phonon_hint_pair_stability"] = float(hint.get("pair_stability", 0.0))
            entry["phonon_hint_local_stability"] = float(hint.get("local_stability", 0.0))
            entry["phonon_hint_pair_decay"] = float(hint.get("pair_decay", 0.0))
            entry["phonon_hint_amplitude_trend"] = float(hint.get("amplitude_trend", 0.0))

        if entangler_control is not None:
            controls_before = dict(entangler_control.get("controls_before", {}))
            controls_after = dict(entangler_control.get("controls_after", {}))
            clamp_flags = dict(entangler_control.get("clamp_flags", {}))
            weight_summary = dict(entangler_control.get("wormhole_weight_summary", {}))
            coherence_feedback = dict(entangler_control.get("coherence_feedback", {}))
            mode_transition = dict(entangler_control.get("mode_transition", {}))
            hint_gate = dict(
                entangler_control.get(
                    "hint_gate",
                    {
                        "enabled": False,
                        "annotation_only": True,
                        "passed": False,
                        "applied": False,
                        "rejection_reason": "disabled",
                        "considered_recommendation": "observe",
                        "considered_status": "missing",
                        "considered_confidence": 0.0,
                        "considered_reliability": 0.0,
                        "considered_sample_count": 0,
                        "reliability_provisional": True,
                        "nudge_enabled": False,
                        "nudge_applied": False,
                        "nudge_reason": "none",
                        "nudge_rejection_reason": "disabled",
                        "nudge_confidence": 0.0,
                        "nudge_reliability": 0.0,
                        "nudge_sample_count": 0,
                        "nudge_stability_score": 0.0,
                        "nudge_delta": {"aperture": 0.0, "damping": 0.0, "phase_offset": 0.0},
                        "nudge_clamped": False,
                        "nudge_clamp_flags": {"aperture": False, "damping": False, "phase_offset": False},
                    },
                )
            )
            entry["entangler_strength"] = float(entangler_control.get("entanglement_strength", 0.0))
            entry["entangler_dominant_giant"] = str(
                entangler_control.get("dominant_giant_consensus", "Entanglement Locus")
            )
            entry["entangler_mode"] = str(entangler_control.get("coherence_mode", entangler_control.get("control_mode", "active")))
            entry["entangler_next_mode"] = str(entangler_control.get("next_coherence_mode", entry["entangler_mode"]))
            entry["entangler_pair_clock"] = int(entangler_control.get("pair_clock", entry.get("shared_pair_clock", 0)))
            entry["entangler_aperture_before"] = float(controls_before.get("aperture", wormhole_aperture))
            entry["entangler_damping_before"] = float(controls_before.get("damping", damping))
            entry["entangler_phase_before"] = float(controls_before.get("phase_offset", phase_offset))
            entry["entangler_aperture_after"] = float(controls_after.get("aperture", wormhole_aperture))
            entry["entangler_damping_after"] = float(controls_after.get("damping", damping))
            entry["entangler_phase_after"] = float(controls_after.get("phase_offset", phase_offset))
            entry["entangler_clamped"] = bool(any(bool(value) for value in clamp_flags.values()))
            entry["entangler_reasoning_summary"] = str(entangler_control.get("reasoning_summary", ""))
            entry["entangler_weight_min"] = float(weight_summary.get("min_weight", 1.0))
            entry["entangler_weight_max"] = float(weight_summary.get("max_weight", 1.0))
            entry["entangler_top_wormholes"] = list(weight_summary.get("top_weighted_wormholes", []))
            entry["entangler_coherence_status"] = str(coherence_feedback.get("status", "stable"))
            entry["entangler_coherence_delta"] = float(coherence_feedback.get("delta", 0.0))
            entry["entangler_coherence_error"] = float(coherence_feedback.get("error", 0.0))
            entry["entangler_coherence_target"] = float(coherence_feedback.get("target", phase_coherence))
            entry["entangler_mode_changed"] = bool(mode_transition.get("changed", False))
            entry["entangler_previous_mode"] = str(mode_transition.get("previous_mode", entry["entangler_mode"]))
            entry["entangler_transition_reason"] = str(mode_transition.get("reason", "none"))
            entry["entangler_decay_streak"] = int(entangler_control.get("mode_decay_streak", mode_transition.get("decay_streak", 0)))
            entry["entangler_improving_streak"] = int(
                entangler_control.get("mode_improving_streak", mode_transition.get("improving_streak", 0))
            )
            entry["entangler_stabilizer_dwell_ticks"] = int(
                entangler_control.get("stabilizer_dwell_ticks", mode_transition.get("stabilizer_dwell_ticks", 0))
            )
            gate_enabled = bool(hint_gate.get("enabled", False))
            gate_passed = bool(hint_gate.get("passed", False))
            entry["entangler_hint_gate_enabled"] = gate_enabled
            entry["entangler_hint_gate_passed"] = gate_passed
            entry["entangler_hint_gate_applied"] = bool(hint_gate.get("applied", False))
            entry["entangler_hint_gate_state"] = "off" if not gate_enabled else ("pass" if gate_passed else "block")
            entry["entangler_hint_gate_reason"] = str(hint_gate.get("rejection_reason", "disabled"))
            entry["entangler_hint_gate_recommendation"] = str(hint_gate.get("considered_recommendation", "observe"))
            entry["entangler_hint_gate_status"] = str(hint_gate.get("considered_status", "missing"))
            entry["entangler_hint_gate_confidence"] = float(hint_gate.get("considered_confidence", 0.0))
            entry["entangler_hint_gate_reliability"] = float(hint_gate.get("considered_reliability", 0.0))
            entry["entangler_hint_gate_sample_count"] = int(hint_gate.get("considered_sample_count", 0))
            entry["entangler_hint_gate_provisional"] = bool(hint_gate.get("reliability_provisional", True))
            entry["entangler_nudge_enabled"] = bool(hint_gate.get("nudge_enabled", False))
            entry["entangler_nudge_applied"] = bool(hint_gate.get("nudge_applied", False))
            entry["entangler_nudge_reason"] = str(hint_gate.get("nudge_reason", "none"))
            entry["entangler_nudge_rejection_reason"] = str(hint_gate.get("nudge_rejection_reason", "disabled"))
            entry["entangler_nudge_reliability"] = float(hint_gate.get("nudge_reliability", 0.0))
            entry["entangler_nudge_sample_count"] = int(hint_gate.get("nudge_sample_count", 0))
            entry["entangler_nudge_stability_score"] = float(hint_gate.get("nudge_stability_score", 0.0))
            nudge_delta = dict(hint_gate.get("nudge_delta", {}))
            nudge_clamp_flags = dict(hint_gate.get("nudge_clamp_flags", {}))
            entry["entangler_nudge_clamped"] = bool(hint_gate.get("nudge_clamped", any(bool(value) for value in nudge_clamp_flags.values())))
            entry["entangler_nudge_aperture_delta"] = float(nudge_delta.get("aperture", 0.0))
            entry["entangler_nudge_damping_delta"] = float(nudge_delta.get("damping", 0.0))
            entry["entangler_nudge_phase_delta"] = float(nudge_delta.get("phase_offset", 0.0))
            entry["entangler_nudge_aperture_clamped"] = bool(nudge_clamp_flags.get("aperture", False))
            entry["entangler_nudge_damping_clamped"] = bool(nudge_clamp_flags.get("damping", False))
            entry["entangler_nudge_phase_clamped"] = bool(nudge_clamp_flags.get("phase_offset", False))

        with self.history_path.open("a", encoding="utf-8") as history_file:
            history_file.write(json.dumps(entry) + "\n")

        return entry

    def load_recent_history(self, manifold_id: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, object]]:
        if not self.history_path.exists():
            return []

        entries: List[Dict[str, object]] = []
        for line in self.history_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry.get("record_type") == "pair" or "pair_id" in entry:
                continue
            if manifold_id is not None and entry.get("manifold_id") != manifold_id:
                continue
            entries.append(entry)

        history_limit = self.history_limit if limit is None else max(int(limit), 1)
        return entries[-history_limit:]

    def load_latest_bursts(self) -> List[Dict[str, object]]:
        burst_files = sorted(self.working_dir.glob("hippocampal_burst_*.json"))
        if not burst_files:
            return []
        return json.loads(burst_files[-1].read_text(encoding="utf-8"))

    def load_manifold_snapshots(self) -> List[Dict[str, object]]:
        if not self.history_path.exists():
            return []

        latest_by_manifold: Dict[str, Dict[str, object]] = {}
        for line in self.history_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry.get("record_type") == "pair" or "pair_id" in entry:
                continue
            manifold_id = str(entry.get("manifold_id", "primary"))
            latest_by_manifold[manifold_id] = entry

        snapshots = list(latest_by_manifold.values())
        snapshots.sort(key=lambda entry: str(entry.get("manifold_id", "primary")))
        return snapshots

    def load_pair_snapshots(self) -> List[Dict[str, object]]:
        if not self.history_path.exists():
            return []

        latest_by_pair: Dict[str, Dict[str, object]] = {}
        for line in self.history_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            pair_id = entry.get("pair_id")
            if pair_id is None:
                continue
            latest_by_pair[str(pair_id)] = entry

        snapshots = list(latest_by_pair.values())
        snapshots.sort(key=lambda entry: str(entry.get("pair_id", "pair")))
        return snapshots

    def render(
        self,
        manifold_id: str,
        bursts: Sequence[Tuple[str, Dict[str, float]]],
        history: Optional[List[Dict[str, object]]] = None,
        top_n: int = 5,
    ) -> str:
        recent_history = history if history is not None else self.load_recent_history(manifold_id)
        latest = recent_history[-1] if recent_history else {
            "adaptive_tau": 0.0,
            "burst_count": len(bursts),
            "avg_h": 0.0,
            "max_h": max((float(metrics.get("H_total", 0.0)) for _, metrics in bursts), default=0.0),
        }

        tau_history = " ".join(f"{float(entry.get('adaptive_tau', 0.0)):.3f}" for entry in recent_history) or "none"
        burst_history = " ".join(str(int(entry.get("burst_count", 0))) for entry in recent_history) or "none"

        lines = [
            (
                f"[TELEMETRY PANEL] manifold={manifold_id} | tau={float(latest.get('adaptive_tau', 0.0)):.3f}"
                f" | bursts={int(latest.get('burst_count', 0))} | avgH={float(latest.get('avg_h', 0.0)):.3f}"
                f" | maxH={float(latest.get('max_h', 0.0)):.3f}"
            ),
            f"  Tau history   : {tau_history}",
            f"  Burst history : {burst_history}",
            "  Top contributions:",
        ]

        ranked_bursts = sorted(bursts, key=lambda item: float(item[1].get("H_total", 0.0)), reverse=True)[:top_n]
        if not ranked_bursts:
            lines.append("    none")
            return "\n".join(lines)

        for node_id, metrics in ranked_bursts:
            density = float(metrics.get("density_contrib", 0.0))
            shear = float(metrics.get("shear_contrib", 0.0))
            vorticity = float(metrics.get("vorticity_contrib", 0.0))
            scale = max(density, shear, vorticity, 1.0)
            lines.append(
                f"    {node_id} | H={float(metrics.get('H_total', 0.0)):.2f}"
                f" | d [{self._bar(density, scale)}] {density:.2f}"
                f" | s [{self._bar(shear, scale)}] {shear:.2f}"
                f" | v [{self._bar(vorticity, scale)}] {vorticity:.2f}"
            )

        return "\n".join(lines)

    def render_latest(self, manifold_id: str = "primary", top_n: int = 5) -> str:
        records = self.load_latest_bursts()
        bursts = []
        for record in records:
            bursts.append(
                (
                    str(record.get("node_id", "unknown")),
                    {
                        "H_total": float(record.get("h_total", 0.0)),
                        "density_contrib": float(record.get("density_contrib", 0.0)),
                        "shear_contrib": float(record.get("shear_contrib", 0.0)),
                        "vorticity_contrib": float(record.get("vorticity_contrib", 0.0)),
                    },
                )
            )
        return self.render(manifold_id=manifold_id, bursts=bursts, top_n=top_n)

    def render_registry(self, manifold_ids: Optional[Sequence[str]] = None, top_n: int = 3) -> str:
        snapshots = self.load_manifold_snapshots()
        if manifold_ids is not None:
            allowed = {str(manifold_id) for manifold_id in manifold_ids}
            snapshots = [snapshot for snapshot in snapshots if str(snapshot.get("manifold_id")) in allowed]

        if not snapshots:
            return "[MANIFOLD REGISTRY] no manifold snapshots available."

        lines = [f"[MANIFOLD REGISTRY] active_manifolds={len(snapshots)}"]
        for snapshot in snapshots:
            manifold_id = str(snapshot.get("manifold_id", "primary"))
            lines.append(
                f"- {manifold_id} | tau={float(snapshot.get('adaptive_tau', 0.0)):.3f}"
                f" | bursts={int(snapshot.get('burst_count', 0))}"
                f" | avgH={float(snapshot.get('avg_h', 0.0)):.3f}"
                f" | maxH={float(snapshot.get('max_h', 0.0)):.3f}"
                f" | dominant={snapshot.get('dominant_channel', 'ambient')}"
            )

            top_nodes = list(snapshot.get("top_nodes", []))[:top_n]
            if not top_nodes:
                lines.append("  top nodes: none")
                continue

            lines.append("  top nodes:")
            for node in top_nodes:
                density = float(node.get("density_contrib", 0.0))
                shear = float(node.get("shear_contrib", 0.0))
                vorticity = float(node.get("vorticity_contrib", 0.0))
                scale = max(density, shear, vorticity, 1.0)
                lines.append(
                    f"    {node.get('node_id', 'unknown')} | H={float(node.get('h_total', 0.0)):.2f}"
                    f" | d [{self._bar(density, scale)}] {density:.2f}"
                    f" | s [{self._bar(shear, scale)}] {shear:.2f}"
                    f" | v [{self._bar(vorticity, scale)}] {vorticity:.2f}"
                )

        return "\n".join(lines)

    def render_pair_registry(self, pair_ids: Optional[Sequence[str]] = None, top_n: int = 3) -> str:
        snapshots = self.load_pair_snapshots()
        if pair_ids is not None:
            allowed = {str(pair_id) for pair_id in pair_ids}
            snapshots = [snapshot for snapshot in snapshots if str(snapshot.get("pair_id")) in allowed]

        if not snapshots:
            return "[PAIR REGISTRY] no entangled pair snapshots available."

        lines = [f"[PAIR REGISTRY] active_pairs={len(snapshots)}"]
        for snapshot in snapshots:
            pair_id = str(snapshot.get("pair_id", "pair"))
            lines.append(
                f"- {pair_id} | aperture={float(snapshot.get('wormhole_aperture', 0.0)):.3f}"
                f" | damping={float(snapshot.get('damping', 0.0)):.3f}"
                f" | coherence={float(snapshot.get('phase_coherence', 0.0)):.3f}"
                f" | bilateral={int(snapshot.get('bilateral_burst_count', 0))}"
                f" | flux={float(snapshot.get('entanglement_strength', 0.0)):.3f}"
                f" | dominant={snapshot.get('dominant_channel', 'ambient')}"
                f" | clock={int(snapshot.get('shared_pair_clock', 0))}"
                f" | locus={snapshot.get('shared_locus_giant', 'Entanglement Locus')}"
                f" | mode={snapshot.get('entangler_mode', 'active')}"
                f" | ent={float(snapshot.get('entangler_strength', 0.0)):.3f}"
                f" | ctrl=a{float(snapshot.get('entangler_aperture_after', snapshot.get('wormhole_aperture', 0.0))):.3f}"
                f"/d{float(snapshot.get('entangler_damping_after', snapshot.get('damping', 0.0))):.3f}"
                f"/p{float(snapshot.get('entangler_phase_after', snapshot.get('phase_offset', 0.0))):.3f}"
                f" | w={float(snapshot.get('entangler_weight_min', 1.0)):.2f}-{float(snapshot.get('entangler_weight_max', 1.0)):.2f}"
                f" | fb={snapshot.get('entangler_coherence_status', 'stable')}"
                f" | gate={snapshot.get('entangler_hint_gate_state', 'off')}"
                f" | nudge={'on' if bool(snapshot.get('entangler_nudge_applied', False)) else 'off'}"
                f" | ph={snapshot.get('phonon_mode', 'none')}:{float(snapshot.get('phonon_confidence', 0.0)):.2f}"
            )
            if bool(snapshot.get("entangler_clamped", False)):
                lines[-1] += " | clamped"
            if bool(snapshot.get("entangler_mode_changed", False)):
                lines[-1] += (
                    f" | tx={snapshot.get('entangler_previous_mode', 'active')}"
                    f"->{snapshot.get('entangler_next_mode', snapshot.get('entangler_mode', 'active'))}"
                )
                lines.append(f"  transition reason: {snapshot.get('entangler_transition_reason', 'none')}")
            if int(snapshot.get("phonon_bundle_count", 0)) > 0:
                lines.append(
                    f"  phonon summary: status={snapshot.get('phonon_status', 'stable')}"
                    f" | amp={float(snapshot.get('phonon_amplitude', 0.0)):.3f}"
                    f" | stable={float(snapshot.get('phonon_stability_score', 0.0)):.3f}"
                    f" | in={int(snapshot.get('phonon_entry_count', 0))}"
                    f" | out={int(snapshot.get('phonon_exit_count', 0))}"
                    f" | next={snapshot.get('phonon_predicted_next_mode', snapshot.get('entangler_next_mode', 'active'))}"
                )
            if int(snapshot.get("local_phonon_bundle_count", 0)) > 0:
                lines.append(
                    f"  local phonon: tier={snapshot.get('local_phonon_tier', 'local')}"
                    f" | carrier={snapshot.get('local_phonon_carrier', 'Ambient Basin')}"
                    f" | mode={snapshot.get('local_phonon_mode', 'none')}:{float(snapshot.get('local_phonon_confidence', 0.0)):.2f}"
                    f" | amp={float(snapshot.get('local_phonon_amplitude', 0.0)):.3f}"
                    f" | in={int(snapshot.get('local_phonon_entry_count', 0))}"
                    f" | out={int(snapshot.get('local_phonon_exit_count', 0))}"
                )
            if snapshot.get("phonon_hint_status") is not None:
                lines.append(
                    f"  phonon hint: status={snapshot.get('phonon_hint_status', 'suppressed')}"
                    f" | bias={snapshot.get('phonon_hint_recommendation', 'observe')}"
                    f" | conf={float(snapshot.get('phonon_hint_confidence', 0.0)):.2f}"
                    f" | age={int(snapshot.get('phonon_hint_age_ticks', 0))}"
                    f" | window={int(snapshot.get('phonon_hint_stability_window', 0))}"
                    f" | why={snapshot.get('phonon_hint_suppression_reason', 'none')}"
                    f" | decide={snapshot.get('phonon_hint_decision_reason', 'unknown')}"
                )
            if snapshot.get("entangler_hint_gate_state") is not None:
                lines.append(
                    f"  hint gate: state={snapshot.get('entangler_hint_gate_state', 'off')}"
                    f" | bias={snapshot.get('entangler_hint_gate_recommendation', 'observe')}"
                    f" | conf={float(snapshot.get('entangler_hint_gate_confidence', 0.0)):.2f}"
                    f" | rel={float(snapshot.get('entangler_hint_gate_reliability', 0.0)):.2f}"
                    f" | n={int(snapshot.get('entangler_hint_gate_sample_count', 0))}"
                    f" | why={snapshot.get('entangler_hint_gate_reason', 'disabled')}"
                )
            if snapshot.get("entangler_nudge_enabled") is not None:
                lines.append(
                    f"  nudge: applied={bool(snapshot.get('entangler_nudge_applied', False))}"
                    f" | reason={snapshot.get('entangler_nudge_reason', 'none')}"
                    f" | rel={float(snapshot.get('entangler_nudge_reliability', 0.0)):.2f}"
                    f" | d=a{float(snapshot.get('entangler_nudge_aperture_delta', 0.0)):+.3f}"
                    f"/d{float(snapshot.get('entangler_nudge_damping_delta', 0.0)):+.3f}"
                    f"/p{float(snapshot.get('entangler_nudge_phase_delta', 0.0)):+.3f}"
                    f" | why={snapshot.get('entangler_nudge_rejection_reason', 'disabled')}"
                )

            top_events = list(snapshot.get("top_events", []))[:top_n]
            if not top_events:
                lines.append("  top events: none")
                continue

            lines.append("  top events:")
            for event in top_events:
                density = float(event.get("density_contrib", 0.0))
                shear = float(event.get("shear_contrib", 0.0))
                vorticity = float(event.get("vorticity_contrib", 0.0))
                scale = max(density, shear, vorticity, 1.0)
                lines.append(
                    f"    {event.get('manifold_id', 'pair')}:{event.get('node_id', 'unknown')}"
                    f" | H={float(event.get('h_total', 0.0)):.2f}"
                    f" | d [{self._bar(density, scale)}] {density:.2f}"
                    f" | s [{self._bar(shear, scale)}] {shear:.2f}"
                    f" | v [{self._bar(vorticity, scale)}] {vorticity:.2f}"
                )

            top_wormholes = list(snapshot.get("entangler_top_wormholes", []))[:top_n]
            if top_wormholes:
                lines.append("  weighted wormholes:")
                for item in top_wormholes:
                    lines.append(
                        f"    {item.get('node_id', 'unknown')} | weight={float(item.get('weight', 1.0)):.2f}"
                    )

        return "\n".join(lines)

    def render_comparative(self, manifold_ids: Optional[Sequence[str]] = None) -> str:
        snapshots = self.load_manifold_snapshots()
        if manifold_ids is not None:
            allowed = {str(manifold_id) for manifold_id in manifold_ids}
            snapshots = [snapshot for snapshot in snapshots if str(snapshot.get("manifold_id")) in allowed]

        if not snapshots:
            return "[MANIFOLD COMPARISON] no manifold snapshots available."

        ranked = sorted(
            snapshots,
            key=lambda entry: (
                int(entry.get("burst_count", 0)),
                float(entry.get("max_h", 0.0)),
                float(entry.get("adaptive_tau", 0.0)),
            ),
            reverse=True,
        )

        lines = ["[MANIFOLD COMPARISON] ranked by burst_count, maxH, tau"]
        for index, snapshot in enumerate(ranked, start=1):
            density = float(snapshot.get("avg_density_contrib", 0.0))
            shear = float(snapshot.get("avg_shear_contrib", 0.0))
            vorticity = float(snapshot.get("avg_vorticity_contrib", 0.0))
            dominant = str(snapshot.get("dominant_channel", "ambient"))
            scale = max(density, shear, vorticity, 1.0)
            lines.append(
                f"{index}. {snapshot.get('manifold_id', 'primary')}"
                f" | tau={float(snapshot.get('adaptive_tau', 0.0)):.3f}"
                f" | bursts={int(snapshot.get('burst_count', 0))}"
                f" | avgH={float(snapshot.get('avg_h', 0.0)):.3f}"
                f" | maxH={float(snapshot.get('max_h', 0.0)):.3f}"
                f" | dominant={dominant}"
                f" | d [{self._bar(density, scale)}] {density:.2f}"
                f" | s [{self._bar(shear, scale)}] {shear:.2f}"
                f" | v [{self._bar(vorticity, scale)}] {vorticity:.2f}"
            )

        return "\n".join(lines)

    def render_pair_comparative(self, pair_ids: Optional[Sequence[str]] = None) -> str:
        snapshots = self.load_pair_snapshots()
        if pair_ids is not None:
            allowed = {str(pair_id) for pair_id in pair_ids}
            snapshots = [snapshot for snapshot in snapshots if str(snapshot.get("pair_id")) in allowed]

        if not snapshots:
            return "[PAIR COMPARISON] no entangled pair snapshots available."

        ranked = sorted(
            snapshots,
            key=lambda entry: (
                int(entry.get("bilateral_burst_count", 0)),
                float(entry.get("phase_coherence", 0.0)),
                float(entry.get("entanglement_strength", 0.0)),
            ),
            reverse=True,
        )

        lines = ["[PAIR COMPARISON] ranked by bilateral bursts, coherence, flux"]
        for index, snapshot in enumerate(ranked, start=1):
            density = float(snapshot.get("shared_flux_density", 0.0))
            shear = float(snapshot.get("shared_flux_shear", 0.0))
            vorticity = float(snapshot.get("shared_flux_vorticity", 0.0))
            scale = max(density, shear, vorticity, 1.0)
            lines.append(
                f"{index}. {snapshot.get('pair_id', 'pair')}"
                f" | aperture={float(snapshot.get('wormhole_aperture', 0.0)):.3f}"
                f" | damping={float(snapshot.get('damping', 0.0)):.3f}"
                f" | coherence={float(snapshot.get('phase_coherence', 0.0)):.3f}"
                f" | bilateral={int(snapshot.get('bilateral_burst_count', 0))}"
                f" | dominant={snapshot.get('dominant_channel', 'ambient')}"
                f" | clock={int(snapshot.get('shared_pair_clock', 0))}"
                f" | mode={snapshot.get('entangler_mode', 'active')}"
                f" | ent={float(snapshot.get('entangler_strength', 0.0)):.3f}"
                f" | ctrl=a{float(snapshot.get('entangler_aperture_after', snapshot.get('wormhole_aperture', 0.0))):.3f}"
                f"/d{float(snapshot.get('entangler_damping_after', snapshot.get('damping', 0.0))):.3f}"
                f"/p{float(snapshot.get('entangler_phase_after', snapshot.get('phase_offset', 0.0))):.3f}"
                f" | w={float(snapshot.get('entangler_weight_min', 1.0)):.2f}-{float(snapshot.get('entangler_weight_max', 1.0)):.2f}"
                f" | fb={snapshot.get('entangler_coherence_status', 'stable')}"
                f" | gate={snapshot.get('entangler_hint_gate_state', 'off')}"
                f" | nudge={'on' if bool(snapshot.get('entangler_nudge_applied', False)) else 'off'}"
                f" | lph={snapshot.get('local_phonon_mode', 'none')}:{float(snapshot.get('local_phonon_confidence', 0.0)):.2f}"
                f" | hint={snapshot.get('phonon_hint_recommendation', 'observe')}:{float(snapshot.get('phonon_hint_confidence', 0.0)):.2f}"
                f" | d [{self._bar(density, scale)}] {density:.2f}"
                f" | s [{self._bar(shear, scale)}] {shear:.2f}"
                f" | v [{self._bar(vorticity, scale)}] {vorticity:.2f}"
            )
            if bool(snapshot.get("entangler_clamped", False)):
                lines[-1] += " | clamped"
            if bool(snapshot.get("entangler_mode_changed", False)):
                lines[-1] += (
                    f" | tx={snapshot.get('entangler_previous_mode', 'active')}"
                    f"->{snapshot.get('entangler_next_mode', snapshot.get('entangler_mode', 'active'))}"
                )

        return "\n".join(lines)

    def _summarize_bursts(self, bursts: Sequence[Tuple[str, Dict[str, float]]], top_n: int = 3) -> Dict[str, object]:
        ranked_bursts = sorted(bursts, key=lambda item: float(item[1].get("H_total", 0.0)), reverse=True)[:top_n]
        if not ranked_bursts:
            return {
                "dominant_channel": "ambient",
                "avg_density_contrib": 0.0,
                "avg_shear_contrib": 0.0,
                "avg_vorticity_contrib": 0.0,
                "top_nodes": [],
            }

        density_values = [float(metrics.get("density_contrib", 0.0)) for _, metrics in ranked_bursts]
        shear_values = [float(metrics.get("shear_contrib", 0.0)) for _, metrics in ranked_bursts]
        vorticity_values = [float(metrics.get("vorticity_contrib", 0.0)) for _, metrics in ranked_bursts]

        avg_density = sum(density_values) / len(density_values)
        avg_shear = sum(shear_values) / len(shear_values)
        avg_vorticity = sum(vorticity_values) / len(vorticity_values)
        dominant_channel = max(
            (
                ("density", avg_density),
                ("shear", avg_shear),
                ("vorticity", avg_vorticity),
            ),
            key=lambda item: item[1],
        )[0]

        top_nodes = []
        for node_id, metrics in ranked_bursts:
            top_nodes.append(
                {
                    "node_id": node_id,
                    "h_total": float(metrics.get("H_total", 0.0)),
                    "density_contrib": float(metrics.get("density_contrib", 0.0)),
                    "shear_contrib": float(metrics.get("shear_contrib", 0.0)),
                    "vorticity_contrib": float(metrics.get("vorticity_contrib", 0.0)),
                }
            )

        return {
            "dominant_channel": dominant_channel,
            "avg_density_contrib": avg_density,
            "avg_shear_contrib": avg_shear,
            "avg_vorticity_contrib": avg_vorticity,
            "top_nodes": top_nodes,
        }

    def _dominant_channel(self, density: float, shear: float, vorticity: float) -> str:
        return max(
            (("density", abs(float(density))), ("shear", abs(float(shear))), ("vorticity", abs(float(vorticity)))),
            key=lambda item: item[1],
        )[0]

    def _bar(self, value: float, scale: float) -> str:
        filled = int(round((max(value, 0.0) / max(scale, 1.0)) * self.bar_width))
        filled = max(0, min(filled, self.bar_width))
        return ("#" * filled).ljust(self.bar_width, "-")


def main(argv: Optional[Sequence[str]] = None):
    parser = argparse.ArgumentParser(description="Render telemetry views for the Exciton-MoA manifold runtime.")
    parser.add_argument("--mode", choices=["latest", "registry", "comparative"], default="latest")
    parser.add_argument("--scope", choices=["manifold", "pair", "all"], default="manifold")
    parser.add_argument("--manifold", dest="manifold_id", default="primary")
    parser.add_argument("--top-n", dest="top_n", type=int, default=5)
    args = parser.parse_args(argv)

    panel = TelemetryPanel()
    if args.mode == "registry":
        if args.scope == "pair":
            print(panel.render_pair_registry(top_n=args.top_n))
            return
        if args.scope == "all":
            print(panel.render_registry(top_n=args.top_n))
            print()
            print(panel.render_pair_registry(top_n=args.top_n))
            return
        print(panel.render_registry(top_n=args.top_n))
        return
    if args.mode == "comparative":
        if args.scope == "pair":
            print(panel.render_pair_comparative())
            return
        if args.scope == "all":
            print(panel.render_comparative())
            print()
            print(panel.render_pair_comparative())
            return
        print(panel.render_comparative())
        return
    if args.scope == "pair":
        print(panel.render_pair_registry(top_n=args.top_n))
        return
    print(panel.render_latest(manifold_id=args.manifold_id, top_n=args.top_n))


if __name__ == "__main__":
    main()