# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
import numpy as np
from entangler import EntanglerGiant


class _Controls:
    def __init__(self, aperture: float, damping: float, phase_offset: float):
        self.aperture = aperture
        self.damping = damping
        self.phase_offset = phase_offset


def test_entangler_giant_computes_deterministic_control_from_shared_locus():
    entangler = EntanglerGiant()
    controls = _Controls(aperture=0.24, damping=0.86, phase_offset=0.18)
    controls.entangler_mode = "active"
    summary = {
        "pair_clock": 7,
        "shared_flux_vector": [0.9, 2.4, 0.5],
        "shared_flux_norm": 2.61,
        "phase_coherence": 0.68,
        "bilateral_burst_count": 2,
        "bilateral_node_ids": ["node_0001", "node_0008"],
        "wormhole_nodes": ["node_0001", "node_0008", "node_0015", "node_0021"],
        "top_events": [{"manifold_id": "primary", "node_id": "node_0001", "h_total": 7.8}],
        "resolved_channels": {
            "node_0001": {"consensus_confidence": 0.92, "consensus_entropy": 0.12, "dominant_giant": "The Graph Navigator", "vector_clock": 7},
            "node_0008": {"consensus_confidence": 0.88, "consensus_entropy": 0.14, "dominant_giant": "The Graph Navigator", "vector_clock": 7},
            "node_0015": {"consensus_confidence": 0.76, "consensus_entropy": 0.20, "dominant_giant": "The Integrator", "vector_clock": 6},
            "node_0021": {"consensus_confidence": 0.72, "consensus_entropy": 0.18, "dominant_giant": "The Graph Navigator", "vector_clock": 5},
        },
    }
    history = [np.array([0.2, 0.7, 0.1]), np.array([0.5, 1.4, 0.3]), np.array([0.9, 2.4, 0.5])]

    first = entangler.control(controls, summary, history, pair_metrics={"max_h_cross_domain": 7.8})
    second = entangler.control(controls, summary, history, pair_metrics={"max_h_cross_domain": 7.8})
    with_hint = entangler.control(
        controls,
        summary,
        history,
        pair_metrics={
            "max_h_cross_domain": 7.8,
            "phonon_control_hint": {"status": "armed", "recommended_bias": "stabilize", "confidence": 0.52},
        },
    )

    assert first["controls_after"] == second["controls_after"]
    assert first["controls_after"] == with_hint["controls_after"]
    assert first["wormhole_weight_map"] == second["wormhole_weight_map"]
    assert with_hint["hint_gate"]["enabled"] is False
    assert with_hint["hint_gate"]["rejection_reason"] == "disabled"
    assert first["dominant_giant_consensus"] == "The Graph Navigator"
    assert 0.0 <= first["entanglement_strength"] <= 1.0
    assert first["wormhole_weight_map"]["node_0001"] > first["wormhole_weight_map"]["node_0015"]
    assert first["controls_after"]["aperture"] != controls.aperture or first["controls_after"]["phase_offset"] != controls.phase_offset


def test_entangler_giant_clamps_control_outputs_when_targets_run_hot():
    entangler = EntanglerGiant(max_aperture_step=0.05, max_damping_step=0.03, max_phase_step=0.08)
    controls = _Controls(aperture=0.94, damping=0.98, phase_offset=float(2.0 * np.pi) - 0.02)
    controls.entangler_mode = "active"
    summary = {
        "pair_clock": 11,
        "shared_flux_vector": [3.0, 0.2, 2.5],
        "shared_flux_norm": 4.1,
        "phase_coherence": -0.3,
        "bilateral_burst_count": 0,
        "bilateral_node_ids": [],
        "wormhole_nodes": ["node_0001", "node_0008"],
        "resolved_channels": {
            "node_0001": {"consensus_confidence": 0.18, "consensus_entropy": 0.9, "dominant_giant": "The Statistician", "vector_clock": 7},
            "node_0008": {"consensus_confidence": 0.22, "consensus_entropy": 1.1, "dominant_giant": "The Statistician", "vector_clock": 6},
        },
    }
    history = [np.array([0.1, 0.1, 0.1]), np.array([2.8, 0.3, 2.0]), np.array([-2.5, 0.1, -2.4]), np.array([3.0, 0.2, 2.5])]

    report = entangler.control(controls, summary, history, pair_metrics={"max_h_cross_domain": 8.8})

    assert 0.05 <= report["controls_after"]["aperture"] <= 0.95
    assert 0.5 <= report["controls_after"]["damping"] <= 0.99
    assert 0.0 <= report["controls_after"]["phase_offset"] <= float(2.0 * np.pi)
    assert all(0.8 <= value <= 1.5 for value in report["wormhole_weight_map"].values())
    assert report["clamp_flags"]["aperture"] or report["clamp_flags"]["damping"] or report["clamp_flags"]["phase_offset"]


def test_entangler_giant_reverses_phase_bias_when_recent_controls_degrade_coherence():
    entangler = EntanglerGiant()
    controls = _Controls(aperture=0.32, damping=0.78, phase_offset=0.28)
    controls.entangler_mode = "active"
    summary = {
        "pair_clock": 9,
        "shared_flux_vector": [0.3, 1.6, 0.4],
        "shared_flux_norm": 1.68,
        "phase_coherence": 0.46,
        "bilateral_burst_count": 1,
        "bilateral_node_ids": ["node_0001"],
        "wormhole_nodes": ["node_0001", "node_0008"],
        "resolved_channels": {
            "node_0001": {"consensus_confidence": 0.81, "consensus_entropy": 0.18, "dominant_giant": "The Graph Navigator", "vector_clock": 9},
            "node_0008": {"consensus_confidence": 0.69, "consensus_entropy": 0.22, "dominant_giant": "The Integrator", "vector_clock": 8},
        },
    }

    report = entangler.control(
        controls,
        summary,
        shared_flux_history=[np.array([0.2, 0.8, 0.2]), np.array([0.3, 1.6, 0.4])],
        pair_metrics={
            "max_h_cross_domain": 7.4,
            "recent_phase_coherence": [0.82, 0.71, 0.58],
            "recent_control_deltas": [{"aperture": 0.06, "damping": -0.02, "phase_offset": 0.11}],
        },
    )

    feedback = report["coherence_feedback"]

    assert feedback["status"] == "decaying"
    assert report["coherence_mode"] == "active"
    assert feedback["phase_correction"] < 0.0
    assert feedback["damping_correction"] > 0.0
    assert report["controls_after"]["phase_offset"] < controls.phase_offset


def test_entangler_stabilizer_mode_is_more_conservative_during_decay():
    entangler = EntanglerGiant()
    active_controls = _Controls(aperture=0.32, damping=0.78, phase_offset=0.28)
    active_controls.entangler_mode = "active"
    stabilizer_controls = _Controls(aperture=0.32, damping=0.78, phase_offset=0.28)
    stabilizer_controls.entangler_mode = "Stabilizer"
    summary = {
        "pair_clock": 9,
        "shared_flux_vector": [0.3, 1.6, 0.4],
        "shared_flux_norm": 1.68,
        "phase_coherence": 0.46,
        "bilateral_burst_count": 1,
        "bilateral_node_ids": ["node_0001"],
        "wormhole_nodes": ["node_0001", "node_0008"],
        "resolved_channels": {
            "node_0001": {"consensus_confidence": 0.81, "consensus_entropy": 0.18, "dominant_giant": "The Graph Navigator", "vector_clock": 9},
            "node_0008": {"consensus_confidence": 0.69, "consensus_entropy": 0.22, "dominant_giant": "The Integrator", "vector_clock": 8},
        },
    }
    pair_metrics = {
        "max_h_cross_domain": 7.4,
        "recent_phase_coherence": [0.82, 0.71, 0.58],
        "recent_control_deltas": [{"aperture": 0.06, "damping": -0.02, "phase_offset": 0.11}],
    }

    active_report = entangler.control(active_controls, summary, shared_flux_history=[np.array([0.2, 0.8, 0.2]), np.array([0.3, 1.6, 0.4])], pair_metrics=pair_metrics)
    stabilizer_report = entangler.control(stabilizer_controls, summary, shared_flux_history=[np.array([0.2, 0.8, 0.2]), np.array([0.3, 1.6, 0.4])], pair_metrics={**pair_metrics, "entangler_mode": "Stabilizer"})

    assert stabilizer_report["coherence_mode"] == "Stabilizer"
    assert stabilizer_report["coherence_feedback"]["mode"] == "Stabilizer"
    assert stabilizer_report["coherence_feedback"]["damping_correction"] >= active_report["coherence_feedback"]["damping_correction"]
    assert stabilizer_report["coherence_feedback"]["phase_correction"] <= active_report["coherence_feedback"]["phase_correction"]
    active_spread = active_report["wormhole_weight_summary"]["max_weight"] - active_report["wormhole_weight_summary"]["min_weight"]
    stabilizer_spread = stabilizer_report["wormhole_weight_summary"]["max_weight"] - stabilizer_report["wormhole_weight_summary"]["min_weight"]
    assert stabilizer_spread <= active_spread


def test_entangler_annotation_only_hint_gate_reports_pass_without_changing_controls():
    class _HintGatePolicy:
        enabled = True
        require_armed_status = True
        confidence_threshold = 0.55
        reliability_threshold = 0.60
        max_age_ticks = 2
        min_samples = 3

    entangler = EntanglerGiant()
    controls = _Controls(aperture=0.24, damping=0.86, phase_offset=0.18)
    controls.entangler_mode = "active"
    controls.hint_gate_policy = _HintGatePolicy()
    summary = {
        "pair_clock": 7,
        "shared_flux_vector": [0.9, 2.4, 0.5],
        "shared_flux_norm": 2.61,
        "phase_coherence": 0.68,
        "bilateral_burst_count": 2,
        "bilateral_node_ids": ["node_0001", "node_0008"],
        "wormhole_nodes": ["node_0001", "node_0008", "node_0015", "node_0021"],
        "top_events": [{"manifold_id": "primary", "node_id": "node_0001", "h_total": 7.8}],
        "resolved_channels": {
            "node_0001": {"consensus_confidence": 0.92, "consensus_entropy": 0.12, "dominant_giant": "The Graph Navigator", "vector_clock": 7},
            "node_0008": {"consensus_confidence": 0.88, "consensus_entropy": 0.14, "dominant_giant": "The Graph Navigator", "vector_clock": 7},
            "node_0015": {"consensus_confidence": 0.76, "consensus_entropy": 0.20, "dominant_giant": "The Integrator", "vector_clock": 6},
            "node_0021": {"consensus_confidence": 0.72, "consensus_entropy": 0.18, "dominant_giant": "The Graph Navigator", "vector_clock": 5},
        },
        "latest_phonon_control_hint": {"status": "armed", "recommended_bias": "stabilize", "confidence": 0.83, "age_ticks": 1},
    }
    history = [np.array([0.2, 0.7, 0.1]), np.array([0.5, 1.4, 0.3]), np.array([0.9, 2.4, 0.5])]

    baseline = entangler.control(controls, summary, history, pair_metrics={"max_h_cross_domain": 7.8})
    gated = entangler.control(
        controls,
        summary,
        history,
        pair_metrics={
            "max_h_cross_domain": 7.8,
            "candidate_phonon_control_hint": {"status": "armed", "recommended_bias": "stabilize", "confidence": 0.83, "age_ticks": 1},
            "phonon_hint_reliability": {
                "recommendation_scores": {
                    "stabilize": {"reliability_score": 0.82, "sample_count": 4, "provisional": False}
                }
            },
        },
    )

    assert gated["controls_after"] == baseline["controls_after"]
    assert gated["wormhole_weight_map"] == baseline["wormhole_weight_map"]
    assert gated["hint_gate"]["enabled"] is True
    assert gated["hint_gate"]["passed"] is True
    assert gated["hint_gate"]["applied"] is False
    assert gated["hint_gate"]["rejection_reason"] == "none"
    assert gated["hint_gate"]["considered_recommendation"] == "stabilize"


def test_entangler_bounded_nudge_applies_within_policy_rails():
    class _HintGatePolicy:
        enabled = True
        require_armed_status = True
        confidence_threshold = 0.0
        reliability_threshold = 0.0
        max_age_ticks = 2
        min_samples = 1
        enable_bounded_nudges = True
        nudge_aperture_max_step = 0.02
        nudge_damping_max_step = 0.015
        nudge_phase_max_step = 0.04
        nudge_reliability_floor = 0.0
        nudge_requires_stability = False
        nudge_stability_window = 1

    entangler = EntanglerGiant()
    baseline_controls = _Controls(aperture=0.24, damping=0.86, phase_offset=0.18)
    baseline_controls.entangler_mode = "active"
    baseline_controls.hint_gate_policy = _HintGatePolicy()
    nudge_controls = _Controls(aperture=0.24, damping=0.86, phase_offset=0.18)
    nudge_controls.entangler_mode = "active"
    nudge_controls.hint_gate_policy = _HintGatePolicy()
    summary = {
        "pair_clock": 7,
        "shared_flux_vector": [0.9, 2.4, 0.5],
        "shared_flux_norm": 2.61,
        "phase_coherence": 0.68,
        "bilateral_burst_count": 2,
        "bilateral_node_ids": ["node_0001", "node_0008"],
        "wormhole_nodes": ["node_0001", "node_0008", "node_0015", "node_0021"],
        "resolved_channels": {
            "node_0001": {"consensus_confidence": 0.92, "consensus_entropy": 0.12, "dominant_giant": "The Graph Navigator", "vector_clock": 7},
            "node_0008": {"consensus_confidence": 0.88, "consensus_entropy": 0.14, "dominant_giant": "The Graph Navigator", "vector_clock": 7},
            "node_0015": {"consensus_confidence": 0.76, "consensus_entropy": 0.20, "dominant_giant": "The Integrator", "vector_clock": 6},
            "node_0021": {"consensus_confidence": 0.72, "consensus_entropy": 0.18, "dominant_giant": "The Graph Navigator", "vector_clock": 5},
        },
    }
    history = [np.array([0.2, 0.7, 0.1]), np.array([0.5, 1.4, 0.3]), np.array([0.9, 2.4, 0.5])]
    pair_metrics = {
        "max_h_cross_domain": 7.8,
        "recent_phase_coherence": [0.62],
        "recent_control_deltas": [{"aperture": 0.0, "damping": 0.0, "phase_offset": -0.02}],
        "candidate_phonon_control_hint": {"status": "armed", "recommended_bias": "stabilize", "confidence": 0.84, "age_ticks": 1},
        "phonon_hint_reliability": {
            "recommendation_scores": {
                "stabilize": {"reliability_score": 0.88, "sample_count": 4, "provisional": False}
            }
        },
    }

    baseline_controls.hint_gate_policy.enable_bounded_nudges = False
    baseline = entangler.control(baseline_controls, summary, history, pair_metrics=pair_metrics)
    nudged = entangler.control(nudge_controls, summary, history, pair_metrics=pair_metrics)

    assert nudged["hint_gate"]["nudge_enabled"] is True
    assert nudged["hint_gate"]["nudge_applied"] is True
    assert nudged["hint_gate"]["nudge_reason"] == "stabilize_via_hint"
    assert abs(nudged["hint_gate"]["nudge_delta"]["aperture"]) <= 0.02
    assert abs(nudged["hint_gate"]["nudge_delta"]["damping"]) <= 0.015
    assert abs(nudged["hint_gate"]["nudge_delta"]["phase_offset"]) <= 0.04
    assert nudged["controls_after"]["damping"] >= baseline["controls_after"]["damping"]
    assert nudged["controls_after"]["aperture"] <= baseline["controls_after"]["aperture"]


def test_entangler_bounded_nudge_is_blocked_by_reliability_floor():
    class _HintGatePolicy:
        enabled = True
        require_armed_status = True
        confidence_threshold = 0.0
        reliability_threshold = 0.0
        max_age_ticks = 2
        min_samples = 1
        enable_bounded_nudges = True
        nudge_aperture_max_step = 0.02
        nudge_damping_max_step = 0.015
        nudge_phase_max_step = 0.04
        nudge_reliability_floor = 0.90
        nudge_requires_stability = False
        nudge_stability_window = 1

    entangler = EntanglerGiant()
    controls = _Controls(aperture=0.24, damping=0.86, phase_offset=0.18)
    controls.entangler_mode = "active"
    controls.hint_gate_policy = _HintGatePolicy()
    summary = {
        "pair_clock": 7,
        "shared_flux_vector": [0.9, 2.4, 0.5],
        "shared_flux_norm": 2.61,
        "phase_coherence": 0.68,
        "bilateral_burst_count": 2,
        "bilateral_node_ids": ["node_0001", "node_0008"],
        "wormhole_nodes": ["node_0001", "node_0008", "node_0015", "node_0021"],
        "resolved_channels": {
            "node_0001": {"consensus_confidence": 0.92, "consensus_entropy": 0.12, "dominant_giant": "The Graph Navigator", "vector_clock": 7},
            "node_0008": {"consensus_confidence": 0.88, "consensus_entropy": 0.14, "dominant_giant": "The Graph Navigator", "vector_clock": 7},
        },
    }
    report = entangler.control(
        controls,
        summary,
        [np.array([0.2, 0.7, 0.1]), np.array([0.5, 1.4, 0.3]), np.array([0.9, 2.4, 0.5])],
        pair_metrics={
            "max_h_cross_domain": 7.8,
            "recent_phase_coherence": [0.62],
            "recent_control_deltas": [{"aperture": 0.0, "damping": 0.0, "phase_offset": -0.02}],
            "candidate_phonon_control_hint": {"status": "armed", "recommended_bias": "stabilize", "confidence": 0.84, "age_ticks": 1},
            "phonon_hint_reliability": {
                "recommendation_scores": {
                    "stabilize": {"reliability_score": 0.82, "sample_count": 4, "provisional": False}
                }
            },
        },
    )

    assert report["hint_gate"]["passed"] is True
    assert report["hint_gate"]["nudge_enabled"] is True
    assert report["hint_gate"]["nudge_applied"] is False
    assert report["hint_gate"]["nudge_rejection_reason"] == "low_reliability"


def test_entangler_observe_hint_applies_small_feedback_nudge():
    class _HintGatePolicy:
        enabled = True
        require_armed_status = True
        confidence_threshold = 0.0
        reliability_threshold = 0.0
        max_age_ticks = 2
        min_samples = 1
        enable_bounded_nudges = True
        nudge_aperture_max_step = 0.02
        nudge_damping_max_step = 0.015
        nudge_phase_max_step = 0.04
        nudge_reliability_floor = 0.90
        nudge_requires_stability = False
        nudge_stability_window = 1
        observe_nudge_feedback_scale = 0.35

    entangler = EntanglerGiant()
    baseline_controls = _Controls(aperture=0.32, damping=0.78, phase_offset=0.28)
    baseline_controls.entangler_mode = "active"
    baseline_controls.hint_gate_policy = _HintGatePolicy()
    observe_controls = _Controls(aperture=0.32, damping=0.78, phase_offset=0.28)
    observe_controls.entangler_mode = "active"
    observe_controls.hint_gate_policy = _HintGatePolicy()
    summary = {
        "pair_clock": 9,
        "shared_flux_vector": [0.3, 1.6, 0.4],
        "shared_flux_norm": 1.68,
        "phase_coherence": 0.46,
        "bilateral_burst_count": 1,
        "bilateral_node_ids": ["node_0001"],
        "wormhole_nodes": ["node_0001", "node_0008"],
        "resolved_channels": {
            "node_0001": {"consensus_confidence": 0.81, "consensus_entropy": 0.18, "dominant_giant": "The Graph Navigator", "vector_clock": 9},
            "node_0008": {"consensus_confidence": 0.69, "consensus_entropy": 0.22, "dominant_giant": "The Integrator", "vector_clock": 8},
        },
    }
    pair_metrics = {
        "max_h_cross_domain": 7.4,
        "recent_phase_coherence": [0.82, 0.71, 0.58],
        "recent_control_deltas": [{"aperture": 0.06, "damping": -0.02, "phase_offset": 0.11}],
        "candidate_phonon_control_hint": {"status": "armed", "recommended_bias": "observe", "confidence": 0.84, "age_ticks": 1},
        "phonon_hint_reliability": {
            "recommendation_scores": {
                "observe": {"reliability_score": 0.44, "sample_count": 4, "provisional": False}
            }
        },
    }

    baseline_controls.hint_gate_policy.enable_bounded_nudges = False
    baseline = entangler.control(
        baseline_controls,
        summary,
        shared_flux_history=[np.array([0.2, 0.8, 0.2]), np.array([0.3, 1.6, 0.4])],
        pair_metrics=pair_metrics,
    )
    observed = entangler.control(
        observe_controls,
        summary,
        shared_flux_history=[np.array([0.2, 0.8, 0.2]), np.array([0.3, 1.6, 0.4])],
        pair_metrics=pair_metrics,
    )

    assert observed["hint_gate"]["passed"] is True
    assert observed["hint_gate"]["nudge_enabled"] is True
    assert observed["hint_gate"]["nudge_applied"] is True
    assert observed["hint_gate"]["nudge_reason"] == "observe_via_feedback"
    assert observed["hint_gate"]["nudge_rejection_reason"] == "none"
    assert abs(observed["hint_gate"]["nudge_delta"]["aperture"]) <= 0.02
    assert abs(observed["hint_gate"]["nudge_delta"]["damping"]) <= 0.015
    assert abs(observed["hint_gate"]["nudge_delta"]["phase_offset"]) <= 0.04
    assert observed["controls_after"] != baseline["controls_after"]


def test_entangler_near_pass_maturity_can_apply_small_observe_override():
    class _HintGatePolicy:
        enabled = True
        require_armed_status = True
        confidence_threshold = 0.55
        reliability_threshold = 0.60
        max_age_ticks = 2
        min_samples = 3
        enable_bounded_nudges = True
        nudge_aperture_max_step = 0.02
        nudge_damping_max_step = 0.015
        nudge_phase_max_step = 0.04
        nudge_reliability_floor = 0.90
        nudge_requires_stability = False
        nudge_stability_window = 1
        observe_nudge_feedback_scale = 0.35
        enable_near_pass_maturity_nudges = True
        near_pass_confidence_gap_max = 0.10
        near_pass_reliability_gap_max = 0.12
        near_pass_sample_gap_max = 0
        near_pass_observe_feedback_scale = 0.20

    entangler = EntanglerGiant()
    controls = _Controls(aperture=0.32, damping=0.78, phase_offset=0.28)
    controls.entangler_mode = "active"
    controls.hint_gate_policy = _HintGatePolicy()
    summary = {
        "pair_clock": 9,
        "shared_flux_vector": [0.3, 1.6, 0.4],
        "shared_flux_norm": 1.68,
        "phase_coherence": 0.46,
        "bilateral_burst_count": 1,
        "bilateral_node_ids": ["node_0001"],
        "wormhole_nodes": ["node_0001", "node_0008"],
        "resolved_channels": {
            "node_0001": {"consensus_confidence": 0.81, "consensus_entropy": 0.18, "dominant_giant": "The Graph Navigator", "vector_clock": 9},
            "node_0008": {"consensus_confidence": 0.69, "consensus_entropy": 0.22, "dominant_giant": "The Integrator", "vector_clock": 8},
        },
    }
    report = entangler.control(
        controls,
        summary,
        shared_flux_history=[np.array([0.2, 0.8, 0.2]), np.array([0.3, 1.6, 0.4])],
        pair_metrics={
            "max_h_cross_domain": 7.4,
            "recent_phase_coherence": [0.82, 0.71, 0.58],
            "recent_control_deltas": [{"aperture": 0.06, "damping": -0.02, "phase_offset": 0.11}],
            "candidate_phonon_control_hint": {"status": "armed", "recommended_bias": "observe", "confidence": 0.49, "age_ticks": 1},
            "phonon_hint_reliability": {
                "recommendation_scores": {
                    "observe": {"reliability_score": 0.58, "sample_count": 3, "provisional": False}
                }
            },
        },
    )

    assert report["hint_gate"]["passed"] is False
    assert report["hint_gate"]["rejection_reason"] == "low_confidence"
    assert report["hint_gate"]["near_pass_candidate"] is True
    assert report["hint_gate"]["nudge_applied"] is True
    assert report["hint_gate"]["nudge_reason"] == "observe_via_near_pass_maturity"
    assert report["hint_gate"]["nudge_override_source"] == "near_pass_maturity"
    assert report["hint_gate"]["nudge_rejection_reason"] == "none"
    assert abs(report["hint_gate"]["nudge_delta"]["aperture"]) <= 0.02
    assert abs(report["hint_gate"]["nudge_delta"]["damping"]) <= 0.015
    assert abs(report["hint_gate"]["nudge_delta"]["phase_offset"]) <= 0.04


def test_entangler_near_pass_maturity_stays_blocked_by_default():
    class _HintGatePolicy:
        enabled = True
        require_armed_status = True
        confidence_threshold = 0.55
        reliability_threshold = 0.60
        max_age_ticks = 2
        min_samples = 3
        enable_bounded_nudges = True
        nudge_aperture_max_step = 0.02
        nudge_damping_max_step = 0.015
        nudge_phase_max_step = 0.04
        nudge_reliability_floor = 0.90
        nudge_requires_stability = False
        nudge_stability_window = 1
        observe_nudge_feedback_scale = 0.35
        enable_near_pass_maturity_nudges = False
        near_pass_confidence_gap_max = 0.10
        near_pass_reliability_gap_max = 0.12
        near_pass_sample_gap_max = 0
        near_pass_observe_feedback_scale = 0.20

    entangler = EntanglerGiant()
    controls = _Controls(aperture=0.32, damping=0.78, phase_offset=0.28)
    controls.entangler_mode = "active"
    controls.hint_gate_policy = _HintGatePolicy()
    report = entangler.control(
        controls,
        {
            "pair_clock": 9,
            "shared_flux_vector": [0.3, 1.6, 0.4],
            "shared_flux_norm": 1.68,
            "phase_coherence": 0.46,
            "bilateral_burst_count": 1,
            "bilateral_node_ids": ["node_0001"],
            "wormhole_nodes": ["node_0001", "node_0008"],
            "resolved_channels": {
                "node_0001": {"consensus_confidence": 0.81, "consensus_entropy": 0.18, "dominant_giant": "The Graph Navigator", "vector_clock": 9},
                "node_0008": {"consensus_confidence": 0.69, "consensus_entropy": 0.22, "dominant_giant": "The Integrator", "vector_clock": 8},
            },
        },
        shared_flux_history=[np.array([0.2, 0.8, 0.2]), np.array([0.3, 1.6, 0.4])],
        pair_metrics={
            "max_h_cross_domain": 7.4,
            "recent_phase_coherence": [0.82, 0.71, 0.58],
            "recent_control_deltas": [{"aperture": 0.06, "damping": -0.02, "phase_offset": 0.11}],
            "candidate_phonon_control_hint": {"status": "armed", "recommended_bias": "observe", "confidence": 0.49, "age_ticks": 1},
            "phonon_hint_reliability": {
                "recommendation_scores": {
                    "observe": {"reliability_score": 0.58, "sample_count": 3, "provisional": False}
                }
            },
        },
    )

    assert report["hint_gate"]["passed"] is False
    assert report["hint_gate"]["near_pass_candidate"] is False
    assert report["hint_gate"]["nudge_applied"] is False
    assert report["hint_gate"]["nudge_rejection_reason"] == "gate_blocked"