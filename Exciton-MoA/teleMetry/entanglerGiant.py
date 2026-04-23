# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np


def _select_coupling_posture_profile(gate_policy: Any, coupling_posture: str) -> Any:
    """Return the matching CouplingPostureGateProfile, or None.

    Match is by exact ``posture_name`` against the live coupling posture.
    Returns None when no profiles are configured, the policy is missing,
    or the posture is ``"unknown"``.
    """
    if gate_policy is None:
        return None
    profiles = getattr(gate_policy, "coupling_posture_profiles", ()) or ()
    posture = str(coupling_posture or "unknown")
    if posture == "unknown":
        return None
    for profile in profiles:
        if str(getattr(profile, "posture_name", "")) == posture:
            return profile
    return None


class EntanglerGiant:
    def __init__(
        self,
        aperture_bounds: tuple[float, float] = (0.05, 0.95),
        damping_bounds: tuple[float, float] = (0.5, 0.99),
        phase_bounds: tuple[float, float] = (0.0, float(2.0 * np.pi)),
        wormhole_weight_bounds: tuple[float, float] = (0.8, 1.5),
        coherence_target: float = 0.88,
        max_aperture_step: float = 0.14,
        max_damping_step: float = 0.08,
        max_phase_step: float = 0.25,
    ):
        self.aperture_bounds = tuple(float(value) for value in aperture_bounds)
        self.damping_bounds = tuple(float(value) for value in damping_bounds)
        self.phase_bounds = tuple(float(value) for value in phase_bounds)
        self.wormhole_weight_bounds = tuple(float(value) for value in wormhole_weight_bounds)
        self.coherence_target = float(coherence_target)
        self.max_aperture_step = float(max_aperture_step)
        self.max_damping_step = float(max_damping_step)
        self.max_phase_step = float(max_phase_step)

    def control(
        self,
        controls: Any,
        shared_locus_summary: dict[str, Any],
        shared_flux_history: Sequence[np.ndarray] | None = None,
        pair_metrics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        pair_metrics = dict(pair_metrics or {})
        mode_name = self._normalize_mode_name(
            pair_metrics.get("entangler_mode", getattr(controls, "entangler_mode", "active"))
        )
        pair_clock = int(shared_locus_summary.get("pair_clock", 0))
        shared_flux_vector = self._vector(shared_locus_summary.get("shared_flux_vector", [0.0, 0.0, 0.0]))
        shared_flux_norm = float(
            shared_locus_summary.get("shared_flux_norm", np.linalg.norm(shared_flux_vector))
        )
        phase_coherence = float(
            shared_locus_summary.get("phase_coherence", pair_metrics.get("phase_coherence", 0.0))
        )
        coherence_strength = float(np.clip((phase_coherence + 1.0) * 0.5, 0.0, 1.0))
        wormhole_nodes = [str(node_id) for node_id in shared_locus_summary.get("wormhole_nodes", [])]
        bilateral_node_ids = [str(node_id) for node_id in shared_locus_summary.get("bilateral_node_ids", [])]
        bilateral_ratio = float(len(bilateral_node_ids) / max(len(wormhole_nodes), 1))
        oscillation = self._compute_oscillation(shared_flux_history or [])
        wormhole_health, dominant_giant_consensus, average_wormhole_health = self._wormhole_health(
            shared_locus_summary, bilateral_node_ids
        )
        coherence_feedback = self._coherence_feedback(
            phase_coherence=phase_coherence,
            recent_phase_coherence=pair_metrics.get("recent_phase_coherence", []),
            recent_control_deltas=pair_metrics.get("recent_control_deltas", []),
            mode_name=mode_name,
        )
        max_h_cross_domain = float(pair_metrics.get("max_h_cross_domain", 0.0))
        h_pressure = float(np.clip(max_h_cross_domain / 8.5, 0.0, 1.0))
        flux_pressure = float(np.clip(shared_flux_norm / 2.5, 0.0, 1.0))
        entanglement_strength = float(
            np.clip(
                (0.45 * coherence_strength) + (0.35 * bilateral_ratio) + (0.20 * average_wormhole_health),
                0.0,
                1.0,
            )
        )

        aperture_before = float(controls.aperture)
        damping_before = float(controls.damping)
        phase_before = float(controls.phase_offset)

        aperture_target = (
            aperture_before
            + (0.22 * (entanglement_strength - 0.45))
            + (0.10 * (bilateral_ratio - 0.25))
            - (0.08 * oscillation)
            - (0.04 * max(0.0, flux_pressure - 0.75))
            + float(coherence_feedback["aperture_correction"])
        )
        damping_target = (
            damping_before
            + (0.12 * oscillation)
            + (0.08 * max(0.0, 0.55 - coherence_strength))
            + (0.05 * h_pressure)
            - (0.10 * max(0.0, entanglement_strength - 0.70))
            + float(coherence_feedback["damping_correction"])
        )

        phase_drive_direction = float(np.sign(shared_flux_vector[1] - shared_flux_vector[0]))
        if phase_drive_direction == 0.0:
            phase_drive_direction = float(np.sign(shared_flux_vector[2])) or 1.0
        phase_pressure = (0.5 - coherence_strength) + (0.5 * (0.35 - bilateral_ratio)) + (0.15 * oscillation)
        phase_target = (
            phase_before
            + (phase_drive_direction * 0.35 * phase_pressure)
            + float(coherence_feedback["phase_correction"])
        )
        hint_gate = self._evaluate_hint_gate(
            controls=controls,
            shared_locus_summary=shared_locus_summary,
            pair_metrics=pair_metrics,
        )
        nudge_summary = self._apply_nudge_if_reliable(
            controls=controls,
            hint_gate=hint_gate,
            coherence_feedback=coherence_feedback,
            recent_phase_coherence=pair_metrics.get("recent_phase_coherence", []),
            coupling_posture=str(
                pair_metrics.get("paper_synchrony_coupling_posture", "unknown")
            ),
        )
        nudge_delta = dict(nudge_summary.get("nudge_delta", {}))
        aperture_target += float(nudge_delta.get("aperture", 0.0))
        damping_target += float(nudge_delta.get("damping", 0.0))
        phase_target += float(nudge_delta.get("phase_offset", 0.0))
        hint_gate.update(nudge_summary)
        hint_gate["annotation_only"] = not bool(nudge_summary.get("nudge_enabled", False))
        hint_gate["applied"] = bool(nudge_summary.get("nudge_applied", False))

        aperture_after, aperture_clamped = self._apply_control(
            aperture_before,
            aperture_target,
            self.aperture_bounds,
            self.max_aperture_step,
        )
        damping_after, damping_clamped = self._apply_control(
            damping_before,
            damping_target,
            self.damping_bounds,
            self.max_damping_step,
        )
        phase_after, phase_clamped = self._apply_control(
            phase_before,
            phase_target,
            self.phase_bounds,
            self.max_phase_step,
        )
        wormhole_weight_map = self._build_wormhole_weight_map(
            wormhole_nodes=wormhole_nodes,
            wormhole_health=wormhole_health,
            bilateral_node_ids=bilateral_node_ids,
            oscillation=oscillation,
            entanglement_strength=entanglement_strength,
            mode_name=mode_name,
        )
        weight_values = list(wormhole_weight_map.values())
        top_weighted_wormholes = [
            {"node_id": node_id, "weight": weight}
            for node_id, weight in sorted(
                wormhole_weight_map.items(), key=lambda item: item[1], reverse=True
            )[:4]
        ]

        reasoning_summary = (
            f"coherence={coherence_strength:.3f}, bilateral={bilateral_ratio:.3f},"
            f" wormhole_health={average_wormhole_health:.3f}, oscillation={oscillation:.3f},"
            f" flux_pressure={flux_pressure:.3f}, h_pressure={h_pressure:.3f},"
            f" weights={min(weight_values or [1.0]):.3f}-{max(weight_values or [1.0]):.3f},"
            f" feedback={coherence_feedback['status']}, mode={mode_name},"
            f" gate={'pass' if hint_gate['passed'] else ('off' if not hint_gate['enabled'] else 'block')}:{hint_gate['rejection_reason']},"
            f" nudge={'apply' if hint_gate.get('nudge_applied') else ('off' if not hint_gate.get('nudge_enabled') else 'skip')}:{hint_gate.get('nudge_rejection_reason', 'disabled')}"
        )

        return {
            "controller": "Entangler Giant",
            "control_mode": "active",
            "coherence_mode": mode_name,
            "pair_clock": pair_clock,
            "entanglement_strength": entanglement_strength,
            "dominant_giant_consensus": dominant_giant_consensus,
            "wormhole_health": wormhole_health,
            "coherence_feedback": coherence_feedback,
            "wormhole_weight_map": wormhole_weight_map,
            "wormhole_weight_summary": {
                "min_weight": float(min(weight_values or [1.0])),
                "max_weight": float(max(weight_values or [1.0])),
                "top_weighted_wormholes": top_weighted_wormholes,
            },
            "controls_before": {
                "aperture": aperture_before,
                "damping": damping_before,
                "phase_offset": phase_before,
            },
            "targets": {
                "aperture": float(aperture_target),
                "damping": float(damping_target),
                "phase_offset": float(phase_target),
            },
            "controls_after": {
                "aperture": aperture_after,
                "damping": damping_after,
                "phase_offset": phase_after,
            },
            "control_delta": {
                "aperture": float(aperture_after - aperture_before),
                "damping": float(damping_after - damping_before),
                "phase_offset": float(phase_after - phase_before),
            },
            "clamp_flags": {
                "aperture": aperture_clamped,
                "damping": damping_clamped,
                "phase_offset": phase_clamped,
            },
            "features": {
                "phase_coherence": phase_coherence,
                "coherence_strength": coherence_strength,
                "bilateral_ratio": bilateral_ratio,
                "bilateral_burst_count": int(
                    shared_locus_summary.get("bilateral_burst_count", len(bilateral_node_ids))
                ),
                "wormhole_count": len(wormhole_nodes),
                "shared_flux_vector": shared_flux_vector.tolist(),
                "shared_flux_norm": shared_flux_norm,
                "flux_pressure": flux_pressure,
                "oscillation": oscillation,
                "max_h_cross_domain": max_h_cross_domain,
                "h_pressure": h_pressure,
                "weight_floor": self.wormhole_weight_bounds[0],
                "weight_ceiling": self.wormhole_weight_bounds[1],
                "coherence_target": self.coherence_target,
                "coherence_mode": mode_name,
                "top_events": list(
                    shared_locus_summary.get("top_events", pair_metrics.get("top_events", []))
                ),
            },
            "hint_gate": hint_gate,
            "reasoning_summary": reasoning_summary,
        }

    def _evaluate_hint_gate(
        self,
        controls: Any,
        shared_locus_summary: dict[str, Any],
        pair_metrics: dict[str, Any],
    ) -> dict[str, Any]:
        gate_policy = getattr(controls, "hint_gate_policy", None)
        enabled = bool(getattr(gate_policy, "enabled", False)) if gate_policy is not None else False
        candidate_hint = dict(
            pair_metrics.get(
                "candidate_phonon_control_hint",
                pair_metrics.get(
                    "phonon_control_hint", shared_locus_summary.get("latest_phonon_control_hint", {})
                ),
            )
        )
        recommendation = str(candidate_hint.get("recommended_bias", "observe"))
        hint_status = str(candidate_hint.get("status", "missing"))
        confidence = float(candidate_hint.get("confidence", 0.0))
        age_ticks = int(candidate_hint.get("age_ticks", 0))
        reliability_summary = dict(pair_metrics.get("phonon_hint_reliability", {}))
        recommendation_scores = dict(reliability_summary.get("recommendation_scores", {}))
        recommendation_summary = dict(recommendation_scores.get(recommendation, {}))
        reliability_score = float(recommendation_summary.get("reliability_score", 0.0))
        sample_count = int(recommendation_summary.get("sample_count", 0))
        provisional = bool(recommendation_summary.get("provisional", True))
        confidence_threshold = (
            float(getattr(gate_policy, "confidence_threshold", 0.55)) if gate_policy is not None else 0.55
        )
        reliability_threshold = (
            float(getattr(gate_policy, "reliability_threshold", 0.60)) if gate_policy is not None else 0.60
        )
        coupling_posture = str(pair_metrics.get("paper_synchrony_coupling_posture", "unknown"))
        active_profile = _select_coupling_posture_profile(gate_policy, coupling_posture)
        profile_used = "none"
        if active_profile is not None:
            profile_used = str(getattr(active_profile, "posture_name", "none"))
            conf_override = getattr(active_profile, "confidence_threshold_override", None)
            if conf_override is not None:
                confidence_threshold = float(conf_override)
            rel_override = getattr(active_profile, "reliability_threshold_override", None)
            if rel_override is not None:
                reliability_threshold = float(rel_override)
        min_samples = int(getattr(gate_policy, "min_samples", 3)) if gate_policy is not None else 3
        confidence_gap = max(confidence_threshold - confidence, 0.0)
        reliability_gap = max(reliability_threshold - reliability_score, 0.0)
        sample_gap = max(min_samples - sample_count, 0)

        evaluation = {
            "enabled": enabled,
            "annotation_only": True,
            "passed": False,
            "applied": False,
            "rejection_reason": "disabled",
            "considered_status": hint_status,
            "considered_recommendation": recommendation,
            "considered_confidence": confidence,
            "considered_age_ticks": age_ticks,
            "considered_reliability": reliability_score,
            "considered_sample_count": sample_count,
            "reliability_provisional": provisional,
            "confidence_gap": confidence_gap,
            "reliability_gap": reliability_gap,
            "sample_gap": sample_gap,
            "near_pass_candidate": False,
            "near_pass_reason": "none",
            "coupling_posture": coupling_posture,
            "coupling_posture_profile_used": profile_used,
            "coupling_posture_profiles_active": bool(
                getattr(gate_policy, "coupling_posture_profiles", ()) or ()
            ),
            "confidence_threshold_effective": confidence_threshold,
            "reliability_threshold_effective": reliability_threshold,
        }
        if not enabled:
            return evaluation
        if not candidate_hint:
            evaluation["rejection_reason"] = "no_hint"
            return evaluation
        if bool(getattr(gate_policy, "require_armed_status", True)) and hint_status != "armed":
            evaluation["rejection_reason"] = "not_armed"
            return evaluation
        if age_ticks > int(getattr(gate_policy, "max_age_ticks", 2)):
            evaluation["rejection_reason"] = "stale"
            return evaluation
        if confidence < confidence_threshold:
            evaluation["rejection_reason"] = "low_confidence"
            self._annotate_near_pass_candidate(evaluation, controls, recommendation)
            return evaluation
        if sample_count < min_samples or provisional:
            evaluation["rejection_reason"] = "insufficient_evidence"
            self._annotate_near_pass_candidate(evaluation, controls, recommendation)
            return evaluation
        if reliability_score < reliability_threshold:
            evaluation["rejection_reason"] = "low_reliability"
            self._annotate_near_pass_candidate(evaluation, controls, recommendation)
            return evaluation
        evaluation["passed"] = True
        evaluation["rejection_reason"] = "none"
        return evaluation

    def _annotate_near_pass_candidate(
        self,
        evaluation: dict[str, Any],
        controls: Any,
        recommendation: str,
    ) -> None:
        gate_policy = getattr(controls, "hint_gate_policy", None)
        if gate_policy is None or not bool(getattr(gate_policy, "enable_near_pass_maturity_nudges", False)):
            return
        if recommendation != "observe":
            return
        reason = str(evaluation.get("rejection_reason", "none"))
        if reason not in {"low_confidence", "low_reliability", "insufficient_evidence"}:
            return
        confidence_gap = float(evaluation.get("confidence_gap", 0.0))
        reliability_gap = float(evaluation.get("reliability_gap", 0.0))
        sample_gap = int(evaluation.get("sample_gap", 0))
        if confidence_gap > float(getattr(gate_policy, "near_pass_confidence_gap_max", 0.10)):
            return
        if reliability_gap > float(getattr(gate_policy, "near_pass_reliability_gap_max", 0.12)):
            return
        if sample_gap > int(getattr(gate_policy, "near_pass_sample_gap_max", 0)):
            return
        evaluation["near_pass_candidate"] = True
        evaluation["near_pass_reason"] = reason

    def _apply_nudge_if_reliable(
        self,
        controls: Any,
        hint_gate: dict[str, Any],
        coherence_feedback: dict[str, Any],
        recent_phase_coherence: Sequence[float] | None = None,
        coupling_posture: str = "unknown",
    ) -> dict[str, Any]:
        gate_policy = getattr(controls, "hint_gate_policy", None)
        nudge_enabled = (
            bool(getattr(gate_policy, "enable_bounded_nudges", False)) if gate_policy is not None else False
        )
        recommendation = str(hint_gate.get("considered_recommendation", "observe"))
        confidence = float(hint_gate.get("considered_confidence", 0.0))
        reliability = float(hint_gate.get("considered_reliability", 0.0))
        sample_count = int(hint_gate.get("considered_sample_count", 0))
        provisional = bool(hint_gate.get("reliability_provisional", True))
        history_count = int(coherence_feedback.get("history_count", 0))
        status = str(coherence_feedback.get("status", "stable"))
        trend = float(coherence_feedback.get("trend", 0.0))
        stability_score = float(
            np.clip(
                1.0
                - max(-trend, 0.0)
                - (0.15 if status == "improving" else (0.0 if status == "stable" else 0.65)),
                0.0,
                1.0,
            )
        )
        profile = _select_coupling_posture_profile(gate_policy, coupling_posture)
        msf_lambda_override = (
            getattr(profile, "msf_lambda_threshold_override", None)
            if profile is not None
            else None
        )
        msf_eval = self._evaluate_msf_guard(
            gate_policy,
            recent_phase_coherence or [],
            lambda_threshold_override=msf_lambda_override,
        )
        result = {
            "nudge_enabled": nudge_enabled,
            "nudge_applied": False,
            "nudge_reason": "none",
            "nudge_rejection_reason": "disabled",
            "nudge_confidence": confidence,
            "nudge_reliability": reliability,
            "nudge_sample_count": sample_count,
            "nudge_stability_score": stability_score,
            "nudge_delta": {"aperture": 0.0, "damping": 0.0, "phase_offset": 0.0},
            "nudge_clamp_flags": {"aperture": False, "damping": False, "phase_offset": False},
            "nudge_override_source": "none",
            "nudge_msf_guard_enabled": msf_eval["enabled"],
            "nudge_msf_lambda_hat": msf_eval["lambda_hat"],
            "nudge_msf_status": msf_eval["status"],
            "nudge_msf_sample_count": msf_eval["sample_count"],
        }
        observe_feedback_scale = (
            float(getattr(gate_policy, "observe_nudge_feedback_scale", 0.35))
            if gate_policy is not None
            else 0.35
        )
        near_pass_observe_feedback_scale = (
            float(getattr(gate_policy, "near_pass_observe_feedback_scale", 0.20))
            if gate_policy is not None
            else 0.20
        )
        observe_feedback_only = recommendation == "observe"
        if not nudge_enabled:
            return result
        near_pass_override = bool(hint_gate.get("near_pass_candidate", False)) and observe_feedback_only
        if not bool(hint_gate.get("passed", False)):
            if not near_pass_override:
                result["nudge_rejection_reason"] = "gate_blocked"
                return result
            result["nudge_override_source"] = "near_pass_maturity"
        if provisional:
            result["nudge_rejection_reason"] = "provisional"
            return result
        if not observe_feedback_only and reliability < float(
            getattr(gate_policy, "nudge_reliability_floor", 0.75)
        ):
            result["nudge_rejection_reason"] = "low_reliability"
            return result
        if bool(getattr(gate_policy, "nudge_requires_stability", True)):
            if history_count < max(int(getattr(gate_policy, "nudge_stability_window", 4)) - 1, 1):
                result["nudge_rejection_reason"] = "insufficient_stability_history"
                return result
            if status == "decaying":
                result["nudge_rejection_reason"] = "unstable"
                return result
        if msf_eval["enabled"] and msf_eval["status"] == "unstable":
            result["nudge_rejection_reason"] = "msf_unstable"
            return result

        strength = float(np.clip((confidence + reliability) * 0.5, 0.0, 1.0))
        aperture_max = min(
            float(getattr(gate_policy, "nudge_aperture_max_step", 0.04)), self.max_aperture_step
        )
        damping_max = min(float(getattr(gate_policy, "nudge_damping_max_step", 0.025)), self.max_damping_step)
        phase_max = min(float(getattr(gate_policy, "nudge_phase_max_step", 0.08)), self.max_phase_step)
        phase_anchor = float(np.sign(float(coherence_feedback.get("phase_correction", 0.0))))
        if phase_anchor == 0.0:
            phase_anchor = 1.0

        raw_delta = {"aperture": 0.0, "damping": 0.0, "phase_offset": 0.0}
        if recommendation == "observe":
            feedback_scale = (
                near_pass_observe_feedback_scale if near_pass_override else observe_feedback_scale
            )
            raw_delta = {
                "aperture": float(coherence_feedback.get("aperture_correction", 0.0))
                * feedback_scale
                * strength,
                "damping": float(coherence_feedback.get("damping_correction", 0.0))
                * feedback_scale
                * strength,
                "phase_offset": float(coherence_feedback.get("phase_correction", 0.0))
                * feedback_scale
                * strength,
            }
            result["nudge_reason"] = (
                "observe_via_near_pass_maturity" if near_pass_override else "observe_via_feedback"
            )
        elif recommendation == "stabilize":
            raw_delta = {
                "aperture": -0.60 * aperture_max * strength,
                "damping": 0.80 * damping_max * strength,
                "phase_offset": 0.35 * phase_max * strength * phase_anchor,
            }
            result["nudge_reason"] = "stabilize_via_hint"
        elif recommendation == "damp":
            raw_delta = {
                "aperture": -0.80 * aperture_max * strength,
                "damping": 0.60 * damping_max * strength,
                "phase_offset": 0.20 * phase_max * strength * phase_anchor,
            }
            result["nudge_reason"] = "damp_via_hint"
        elif recommendation == "loosen":
            raw_delta = {
                "aperture": 0.60 * aperture_max * strength,
                "damping": -0.60 * damping_max * strength,
                "phase_offset": -0.25 * phase_max * strength * phase_anchor,
            }
            result["nudge_reason"] = "loosen_via_hint"
        else:
            result["nudge_rejection_reason"] = "unsupported_recommendation"
            return result

        clipped_delta = {
            "aperture": float(np.clip(raw_delta["aperture"], -aperture_max, aperture_max)),
            "damping": float(np.clip(raw_delta["damping"], -damping_max, damping_max)),
            "phase_offset": float(np.clip(raw_delta["phase_offset"], -phase_max, phase_max)),
        }
        result["nudge_delta"] = clipped_delta
        result["nudge_clamp_flags"] = {
            "aperture": not np.isclose(raw_delta["aperture"], clipped_delta["aperture"]),
            "damping": not np.isclose(raw_delta["damping"], clipped_delta["damping"]),
            "phase_offset": not np.isclose(raw_delta["phase_offset"], clipped_delta["phase_offset"]),
        }
        result["nudge_applied"] = any(not np.isclose(value, 0.0) for value in clipped_delta.values())
        result["nudge_rejection_reason"] = "none" if result["nudge_applied"] else "zero_delta"
        return result

    def _wormhole_health(
        self,
        shared_locus_summary: dict[str, Any],
        bilateral_node_ids: Sequence[str],
    ) -> tuple[dict[str, float], str, float]:
        resolved_channels = dict(shared_locus_summary.get("resolved_channels", {}))
        pair_clock = int(shared_locus_summary.get("pair_clock", 0))
        bilateral_set = {str(node_id) for node_id in bilateral_node_ids}
        dominant_weights: dict[str, float] = {}
        wormhole_health: dict[str, float] = {}

        for node_id in shared_locus_summary.get("wormhole_nodes", []):
            resolved = dict(resolved_channels.get(str(node_id), {}))
            confidence = float(resolved.get("consensus_confidence", 0.0))
            entropy = float(resolved.get("consensus_entropy", 0.0))
            vector_clock = int(resolved.get("vector_clock", pair_clock))
            freshness = max(0.0, 1.0 - (0.2 * max(pair_clock - vector_clock, 0)))
            bilateral_bonus = 1.10 if str(node_id) in bilateral_set else 1.0
            health = float(np.clip((confidence / (1.0 + entropy)) * freshness * bilateral_bonus, 0.0, 1.0))
            wormhole_health[str(node_id)] = health
            dominant_giant = str(resolved.get("dominant_giant", "Entanglement Locus"))
            dominant_weights[dominant_giant] = dominant_weights.get(dominant_giant, 0.0) + max(health, 1e-6)

        if not wormhole_health:
            fallback = str(shared_locus_summary.get("cross_domain_giant", "Entanglement Locus"))
            return {}, fallback, 0.0

        dominant = max(dominant_weights.items(), key=lambda item: item[1])[0]
        average = float(sum(wormhole_health.values()) / len(wormhole_health))
        return wormhole_health, dominant, average

    def _compute_oscillation(self, shared_flux_history: Sequence[np.ndarray]) -> float:
        history = [self._vector(item) for item in shared_flux_history[-4:]]
        if len(history) < 2:
            return 0.0
        diffs = [
            float(np.linalg.norm(current - previous))
            for previous, current in zip(history[:-1], history[1:], strict=False)
        ]
        average_norm = float(np.mean([np.linalg.norm(vector) for vector in history]))
        return float(np.clip(np.mean(diffs) / max(average_norm + 1.0, 1.0), 0.0, 1.0))

    def _evaluate_msf_guard(
        self,
        gate_policy: Any,
        recent_phase_coherence: Sequence[float],
        lambda_threshold_override: float | None = None,
    ) -> dict[str, Any]:
        """Compute the MSFGuard surrogate transverse Lyapunov exponent.

        Discrete-time, observable-only proxy for the master-stability-function
        idea (Pecora & Carroll, PhysRevLett.80.2109): treat ``1 - phase_coherence``
        as a transverse-perturbation magnitude. If it contracts geometrically
        across a short window, the synchronized state is locally transversely
        stable and bounded nudges are safe; if it grows, applying nudges is
        likely to drive the pair away from synchrony.
        """
        enabled = bool(getattr(gate_policy, "enable_msf_guard", False)) if gate_policy else False
        result: dict[str, Any] = {
            "enabled": enabled,
            "lambda_hat": float("nan"),
            "status": "disabled",
            "sample_count": 0,
        }
        if not enabled:
            return result
        window = max(int(getattr(gate_policy, "msf_window", 4)), 2)
        min_samples = max(int(getattr(gate_policy, "msf_min_samples", 3)), 2)
        if lambda_threshold_override is not None:
            threshold = float(lambda_threshold_override)
        else:
            threshold = float(getattr(gate_policy, "msf_lambda_threshold", 0.0))
        history = [float(value) for value in recent_phase_coherence][-window:]
        result["sample_count"] = len(history)
        if len(history) < min_samples:
            result["status"] = "insufficient_history"
            return result
        gaps = [max(1.0 - value, 1e-9) for value in history]
        log_ratios = [
            float(np.log(gaps[idx + 1] / gaps[idx])) for idx in range(len(gaps) - 1)
        ]
        if not log_ratios:
            result["status"] = "insufficient_history"
            return result
        lambda_hat = float(np.mean(log_ratios))
        result["lambda_hat"] = lambda_hat
        result["status"] = "unstable" if lambda_hat > threshold else "stable"
        return result

    def _apply_control(
        self,
        current: float,
        target: float,
        bounds: tuple[float, float],
        max_step: float,
    ) -> tuple[float, bool]:
        delta = float(target - current)
        bounded_delta = float(np.clip(delta, -max_step, max_step))
        stepped = current + bounded_delta
        bounded_value = float(np.clip(stepped, bounds[0], bounds[1]))
        clamped = not np.isclose(delta, bounded_delta) or not np.isclose(stepped, bounded_value)
        return bounded_value, bool(clamped)

    def _build_wormhole_weight_map(
        self,
        wormhole_nodes: Sequence[str],
        wormhole_health: dict[str, float],
        bilateral_node_ids: Sequence[str],
        oscillation: float,
        entanglement_strength: float,
        mode_name: str,
    ) -> dict[str, float]:
        bilateral_set = {str(node_id) for node_id in bilateral_node_ids}
        base_offset = 0.92 + (0.08 * entanglement_strength) - (0.06 * oscillation)
        weight_map: dict[str, float] = {}
        stabilizer_mode = mode_name.lower() == "stabilizer"

        for node_id in wormhole_nodes:
            health = float(wormhole_health.get(str(node_id), 0.0))
            bilateral_bonus = 0.28 if str(node_id) in bilateral_set else -0.04
            raw_weight = base_offset + (0.42 * health) + bilateral_bonus
            if stabilizer_mode:
                raw_weight = 1.0 + ((raw_weight - 1.0) * 0.55)
            bounded_weight = float(
                np.clip(raw_weight, self.wormhole_weight_bounds[0], self.wormhole_weight_bounds[1])
            )
            weight_map[str(node_id)] = bounded_weight

        return weight_map

    def _coherence_feedback(
        self,
        phase_coherence: float,
        recent_phase_coherence: Sequence[float],
        recent_control_deltas: Sequence[dict[str, Any]],
        mode_name: str,
    ) -> dict[str, Any]:
        history = [float(value) for value in recent_phase_coherence]
        previous = history[-1] if history else float(phase_coherence)
        trailing_mean = float(np.mean(history[-3:])) if history else float(phase_coherence)
        coherence_delta = float(phase_coherence - previous)
        coherence_trend = float(phase_coherence - trailing_mean)
        coherence_error = float(np.clip(self.coherence_target - float(phase_coherence), -1.0, 1.0))
        last_control_delta = dict(recent_control_deltas[-1]) if recent_control_deltas else {}
        negative_trend = max(-coherence_trend, 0.0)
        positive_trend = max(coherence_trend, 0.0)
        stabilizer_mode = mode_name.lower() == "stabilizer"

        aperture_reversal = (
            -np.sign(float(last_control_delta.get("aperture", 0.0))) if negative_trend > 0.0 else 0.0
        )
        damping_reversal = (
            -np.sign(float(last_control_delta.get("damping", 0.0))) if negative_trend > 0.0 else 0.0
        )
        phase_reversal = (
            -np.sign(float(last_control_delta.get("phase_offset", 0.0))) if negative_trend > 0.0 else 0.0
        )

        aperture_gain = 0.10
        aperture_reversal_gain = 0.05
        damping_gain = 0.08
        damping_reversal_gain = 0.03
        phase_gain = 0.18
        if stabilizer_mode:
            aperture_gain = 0.06
            aperture_reversal_gain = 0.08
            damping_gain = 0.12
            damping_reversal_gain = 0.05
            phase_gain = 0.26

        aperture_correction = float(
            (aperture_gain * coherence_error) + (aperture_reversal_gain * negative_trend * aperture_reversal)
        )
        damping_correction = float(
            (damping_gain * negative_trend)
            + (damping_reversal_gain * negative_trend * damping_reversal)
            - (0.02 * positive_trend)
        )
        phase_correction = float(phase_gain * negative_trend * phase_reversal)

        if stabilizer_mode and negative_trend > 0.0:
            aperture_correction = min(aperture_correction, 0.0)
            damping_correction = max(damping_correction, 0.02)

        if negative_trend > 0.025:
            status = "decaying"
        elif positive_trend > 0.025:
            status = "improving"
        else:
            status = "stable"

        return {
            "mode": mode_name,
            "status": status,
            "target": self.coherence_target,
            "current": float(phase_coherence),
            "previous": previous,
            "delta": coherence_delta,
            "trend": coherence_trend,
            "error": coherence_error,
            "history_count": len(history),
            "last_control_delta": {
                "aperture": float(last_control_delta.get("aperture", 0.0)),
                "damping": float(last_control_delta.get("damping", 0.0)),
                "phase_offset": float(last_control_delta.get("phase_offset", 0.0)),
            },
            "aperture_correction": aperture_correction,
            "damping_correction": damping_correction,
            "phase_correction": phase_correction,
        }

    def _normalize_mode_name(self, raw_mode: Any) -> str:
        normalized = str(raw_mode or "active").strip().lower()
        if normalized == "stabilizer":
            return "Stabilizer"
        return "active"

    def _vector(self, value: Any) -> np.ndarray:
        raw = np.asarray(value, dtype=float).reshape(-1)
        padded = np.zeros(3, dtype=float)
        padded[: min(raw.size, 3)] = raw[: min(raw.size, 3)]
        return padded
