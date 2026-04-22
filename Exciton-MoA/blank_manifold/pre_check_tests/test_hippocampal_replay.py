# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
from pathlib import Path

import json
import sys

from blank_config import BlankManifoldConfig
from blank_manifold_core import BlankManifoldCore
from hippocampal import HippocampalTransducer
from hippocampal_replay import HippocampalReplay, main as replay_main
from telemetry_panel import TelemetryPanel


def test_hippocampal_replay_renders_latest_burst(tmp_path: Path):
    manifold_core = BlankManifoldCore(BlankManifoldConfig())
    manifold_core.generate_manifold()
    manifold_core.graph.nodes["node_0000"]["dominant_giant"] = "The Graph Navigator"

    transducer = HippocampalTransducer(output_dir=tmp_path, burst_flush_threshold=1)
    transducer.capture_bursts(
        [
            (
                "node_0000",
                {
                    "H_total": 3.5,
                    "tau_threshold": 2.4,
                    "density": 1.0,
                    "density_contrib": 1.2,
                    "shear": 0.8,
                    "shear_contrib": 0.9,
                    "vorticity": 0.3,
                    "vorticity_contrib": 0.4,
                },
            ),
            (
                "node_0001",
                {
                    "H_total": 2.0,
                    "tau_threshold": 2.4,
                    "density": 0.6,
                    "density_contrib": 0.8,
                    "shear": 0.5,
                    "shear_contrib": 0.5,
                    "vorticity": 0.2,
                    "vorticity_contrib": 0.2,
                },
            ),
        ],
        manifold_core.graph,
    )

    replay = HippocampalReplay(working_dir=tmp_path)
    output = replay.replay(top_n=2)

    assert "Burst count: 2" in output
    assert "Average adaptive tau: 2.400" in output
    assert "node_0000" in output
    assert "Graph Navigator" in output
    assert "d=1.20 s=0.90 v=0.40" in output


def test_hippocampal_replay_pair_summary_from_archive(tmp_path: Path):
    manifold_core = BlankManifoldCore(BlankManifoldConfig())
    manifold_core.generate_manifold()
    manifold_core.graph.nodes["node_0000"]["dominant_giant"] = "The Graph Navigator"
    manifold_core.graph.nodes["node_0001"]["dominant_giant"] = "The Integrator"

    primary_dir = tmp_path / "primary"
    secondary_dir = tmp_path / "secondary"
    transducer_primary = HippocampalTransducer(output_dir=primary_dir, burst_flush_threshold=1)
    transducer_secondary = HippocampalTransducer(output_dir=secondary_dir, burst_flush_threshold=1)

    transducer_primary.capture_bursts(
        [(
            "node_0000",
            {
                "H_total": 3.6,
                "tau_threshold": 2.4,
                "density": 1.0,
                "density_contrib": 1.2,
                "shear": 0.8,
                "shear_contrib": 0.9,
                "vorticity": 0.3,
                "vorticity_contrib": 0.4,
            },
        )],
        manifold_core.graph,
        pair_context={
            "pair_id": "primary-secondary",
            "source_manifold_id": "primary",
            "bilateral_node_ids": ["node_0000"],
            "cross_domain_giant": "Entanglement Locus",
            "phase_coherence": 0.88,
            "shared_flux_norm": 1.2,
            "wormhole_nodes": ["node_0000"],
        },
    )
    transducer_secondary.capture_bursts(
        [(
            "node_0000",
            {
                "H_total": 2.9,
                "tau_threshold": 2.4,
                "density": 0.7,
                "density_contrib": 0.9,
                "shear": 0.7,
                "shear_contrib": 0.8,
                "vorticity": 0.2,
                "vorticity_contrib": 0.3,
            },
        )],
        manifold_core.graph,
        pair_context={
            "pair_id": "primary-secondary",
            "source_manifold_id": "secondary",
            "bilateral_node_ids": ["node_0000"],
            "cross_domain_giant": "Entanglement Locus",
            "phase_coherence": 0.88,
            "shared_flux_norm": 1.2,
            "wormhole_nodes": ["node_0000"],
        },
    )

    replay = HippocampalReplay(working_dir=tmp_path)
    output = replay.replay(pair_id="primary-secondary", top_n=4)

    assert "Pair id: primary-secondary" in output
    assert "Burst count: 2" in output
    assert "Bilateral bursts: 2" in output
    assert "Source manifolds: {'primary': 1, 'secondary': 1}" in output
    assert "Cross-domain giants: {'Entanglement Locus': 2}" in output
    assert "primary:node_0000*" in output


def test_hippocampal_replay_summarizes_weight_drift_and_wormhole_shifts(tmp_path: Path):
    panel = TelemetryPanel(working_dir=tmp_path)
    for pair_clock, min_weight, max_weight, top_wormholes in [
        (1, 0.82, 1.20, [{"node_id": "node_0001", "weight": 1.20}, {"node_id": "node_0008", "weight": 1.10}]),
        (2, 0.84, 1.32, [{"node_id": "node_0008", "weight": 1.32}, {"node_id": "node_0001", "weight": 1.19}]),
        (3, 0.81, 1.41, [{"node_id": "node_0008", "weight": 1.41}, {"node_id": "node_0015", "weight": 1.18}]),
    ]:
        panel.record_pair_scan(
            pair_id="primary-secondary",
            manifold_a_id="primary",
            manifold_b_id="secondary",
            wormhole_nodes=["node_0001", "node_0008", "node_0015"],
            wormhole_aperture=0.28,
            damping=0.82,
            phase_offset=0.15,
            shared_flux=[0.8, 2.9, 0.7],
            phase_coherence=0.73,
            bilateral_burst_count=2,
            max_h_cross_domain=7.9,
            shared_locus_summary={"pair_clock": pair_clock, "cross_domain_giant": "Entanglement Locus"},
            entangler_control={
                "pair_clock": pair_clock,
                "entanglement_strength": 0.74,
                "coherence_mode": "active",
                "controls_before": {"aperture": 0.28, "damping": 0.82, "phase_offset": 0.15},
                "controls_after": {"aperture": 0.34, "damping": 0.79, "phase_offset": 0.21},
                "coherence_feedback": {"status": "stable", "delta": 0.01, "error": 0.10, "target": 0.88},
                "wormhole_weight_summary": {
                    "min_weight": min_weight,
                    "max_weight": max_weight,
                    "top_weighted_wormholes": top_wormholes,
                },
            },
        )

    replay = HippocampalReplay(working_dir=tmp_path)
    drift = replay.summarize_weight_drift(replay.load_pair_telemetry_records(pair_id="primary-secondary"))
    shifts = replay.summarize_top_wormhole_shifts(replay.load_pair_telemetry_records(pair_id="primary-secondary"), top_n=2)
    rendered = replay.render_weight_drift_summary(pair_id="primary-secondary", top_n=2)

    assert drift["tick_count"] == 3
    assert drift["weight_min_range"] == (0.81, 0.84)
    assert drift["weight_max_range"] == (1.2, 1.41)
    assert shifts["node_0008"]["promotions"] >= 1
    assert shifts["node_0015"]["entries"] == 1
    assert "Wormhole weight drift over 3 ticks:" in rendered
    assert "node_0008" in rendered


def test_hippocampal_replay_summarizes_coherence_trend_and_mode(tmp_path: Path):
    panel = TelemetryPanel(working_dir=tmp_path)
    for pair_clock, coherence, status, mode, changed, previous_mode, next_mode, reason in [
        (1, 0.61, "decaying", "active", False, "active", "active", "none"),
        (2, 0.59, "decaying", "active", True, "active", "Stabilizer", "decaying_x2_after_history3"),
        (3, 0.69, "improving", "Stabilizer", False, "Stabilizer", "Stabilizer", "stabilizer_dwell_1of2"),
        (4, 0.76, "improving", "Stabilizer", True, "Stabilizer", "active", "improving_x3_after_dwell2"),
    ]:
        panel.record_pair_scan(
            pair_id="primary-secondary",
            manifold_a_id="primary",
            manifold_b_id="secondary",
            wormhole_nodes=["node_0001", "node_0008"],
            wormhole_aperture=0.24,
            damping=0.85,
            phase_offset=0.15,
            shared_flux=[0.4, 1.2, 0.2],
            phase_coherence=coherence,
            bilateral_burst_count=1,
            max_h_cross_domain=6.8,
            shared_locus_summary={"pair_clock": pair_clock, "cross_domain_giant": "Entanglement Locus"},
            entangler_control={
                "pair_clock": pair_clock,
                "coherence_mode": mode,
                "next_coherence_mode": next_mode,
                "controls_before": {"aperture": 0.24, "damping": 0.85, "phase_offset": 0.15},
                "controls_after": {"aperture": 0.22, "damping": 0.89, "phase_offset": 0.11},
                "coherence_feedback": {"status": status, "delta": 0.05, "error": 0.12, "target": 0.88},
                "mode_transition": {"changed": changed, "previous_mode": previous_mode, "next_mode": next_mode, "reason": reason, "decay_streak": 2 if status == "decaying" else 0, "improving_streak": 3 if reason.startswith("improving") else 0, "stabilizer_dwell_ticks": 2 if mode == "Stabilizer" else 0},
                "wormhole_weight_summary": {"min_weight": 0.92, "max_weight": 1.08, "top_weighted_wormholes": []},
            },
        )

    replay = HippocampalReplay(working_dir=tmp_path)
    trend = replay.summarize_coherence_trend(replay.load_pair_telemetry_records(pair_id="primary-secondary"))
    switching = replay.summarize_mode_switching(replay.load_pair_telemetry_records(pair_id="primary-secondary"))
    rendered = replay.render_coherence_summary(pair_id="primary-secondary")
    switching_rendered = replay.render_mode_switching_summary(pair_id="primary-secondary")

    assert trend["tick_count"] == 4
    assert trend["coherence_range"] == (0.59, 0.76)
    assert trend["coherence_delta"] > 0.0
    assert trend["latest_status"] == "improving"
    assert trend["mode_counts"]["active"] == 2
    assert trend["mode_counts"]["Stabilizer"] == 2
    assert switching["transition_total"] == 2
    assert switching["transition_counts"]["active->Stabilizer"] == 1
    assert switching["transition_counts"]["Stabilizer->active"] == 1
    assert switching["reason_counts"]["decaying_x2_after_history3"] == 1
    assert switching["reason_counts"]["improving_x3_after_dwell2"] == 1
    assert "Coherence trend over 4 ticks:" in rendered
    assert "mode=active" in rendered
    assert "Mode switching over 4 ticks:" in switching_rendered
    assert "Switch reasons: decaying_x2_after_history3=1, improving_x3_after_dwell2=1" in switching_rendered


def test_hippocampal_replay_pair_output_includes_weight_summary_and_back_compat(tmp_path: Path):
    archive_dir = tmp_path / "primary"
    archive_dir.mkdir(parents=True, exist_ok=True)
    (archive_dir / "hippocampal_long_term.jsonl").write_text(
        json.dumps(
            {
                "pair_id": "primary-secondary",
                "source_manifold_id": "primary",
                "node_id": "node_0000",
                "h_total": 3.6,
                "tau_threshold": 2.4,
                "density_contrib": 1.2,
                "shear_contrib": 0.9,
                "vorticity_contrib": 0.4,
                "dominant_giant": "The Graph Navigator",
                "bilateral_burst": True,
                "cross_domain_giant": "Entanglement Locus",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    history_path = tmp_path / "adaptive_tau_history.jsonl"
    history_path.write_text(
        json.dumps({"record_type": "pair", "pair_id": "primary-secondary", "shared_pair_clock": 1}) + "\n",
        encoding="utf-8",
    )

    replay = HippocampalReplay(working_dir=tmp_path)
    output = replay.replay(pair_id="primary-secondary", top_n=4)

    assert "Pair id: primary-secondary" in output
    assert "Entangler control summary:" in output
    assert "Local phonon summary:" in output
    assert "No local phonon telemetry available for replay." in output
    assert "Advisory hint summary:" in output
    assert "No advisory phonon hint telemetry available for replay." in output
    assert "Predictive phonon summary:" in output
    assert "No predictive phonon correlation telemetry available for replay." in output
    assert "Hint reliability summary:" in output
    assert "No hint reliability evidence available for replay." in output
    assert "Hint calibration summary:" in output
    assert "No hint calibration evidence available for replay." in output
    assert "Hint gate summary:" in output
    assert "No hint gate telemetry available for replay." in output
    assert "Nudge outcome summary:" in output
    assert "No nudge outcome telemetry available for replay." in output
    assert "Wormhole weight summary:" in output
    assert "No wormhole weight telemetry available for replay." in output
    assert "No coherence telemetry available for replay." in output
    assert "No mode switching telemetry available for replay." in output


def test_hippocampal_replay_summarizes_local_phonons_and_advisory_hints(tmp_path: Path):
    panel = TelemetryPanel(working_dir=tmp_path)
    for pair_clock, amplitude, confidence, recommendation, status in [
        (1, 0.18, 0.36, "observe", "suppressed"),
        (2, 0.26, 0.44, "stabilize", "armed"),
        (3, 0.31, 0.52, "stabilize", "armed"),
    ]:
        panel.record_pair_scan(
            pair_id="primary-secondary",
            manifold_a_id="primary",
            manifold_b_id="secondary",
            wormhole_nodes=["node_0001", "node_0008"],
            wormhole_aperture=0.24,
            damping=0.85,
            phase_offset=0.15,
            shared_flux=[0.4, 1.1, 0.2],
            phase_coherence=0.67,
            bilateral_burst_count=1,
            max_h_cross_domain=6.8,
            shared_locus_summary={"pair_clock": pair_clock, "cross_domain_giant": "Entanglement Locus"},
            entangler_control={
                "pair_clock": pair_clock,
                "coherence_mode": "active",
                "next_coherence_mode": "active",
                "controls_before": {"aperture": 0.24, "damping": 0.85, "phase_offset": 0.15},
                "controls_after": {"aperture": 0.23, "damping": 0.86, "phase_offset": 0.14},
                "coherence_feedback": {"status": "stable", "delta": 0.02, "error": 0.10, "target": 0.88},
                "mode_transition": {"changed": False, "previous_mode": "active", "next_mode": "active", "reason": "none"},
                "wormhole_weight_summary": {"min_weight": 0.95, "max_weight": 1.05, "top_weighted_wormholes": []},
            },
            latest_local_phonon_bundle={
                "phonon_id": f"phonon_primary-secondary_local_post_injection_primary_{pair_clock:04d}",
                "source_tier": "local_post_injection",
                "carrier_giant": "The Graph Navigator",
                "mode": "shear",
                "amplitude": amplitude,
                "confidence": confidence,
                "decay_rate": 0.15,
                "source_nodes": ["node_0001", "node_0008"],
                "wormhole_entry_nodes": ["node_0008"],
                "wormhole_exit_nodes": [] if pair_clock > 1 else ["node_0003"],
                "coherence_signature": {"status": "local_post_injection", "stability_score": 0.55 + (0.05 * pair_clock)},
            },
            local_phonon_bundle_count=pair_clock * 2,
            phonon_control_hint={
                "status": status,
                "recommended_bias": recommendation,
                "confidence": confidence,
                "age_ticks": 1,
                "stability_window": 4 + pair_clock,
                "suppression_reason": "none" if status == "armed" else "low_confidence",
                "source_tier": "local_post_injection",
                "entry_pressure": 1.0,
                "exit_pressure": 0.0 if pair_clock > 1 else 1.0,
            },
        )

    replay = HippocampalReplay(working_dir=tmp_path)
    local_summary = replay.summarize_local_phonons(replay.load_pair_telemetry_records(pair_id="primary-secondary"))
    hint_summary = replay.summarize_advisory_hints(replay.load_pair_telemetry_records(pair_id="primary-secondary"))
    local_rendered = replay.render_local_phonon_summary(pair_id="primary-secondary")
    hint_rendered = replay.render_advisory_hint_summary(pair_id="primary-secondary")

    assert local_summary["tick_count"] == 3
    assert local_summary["latest_tier"] == "local_post_injection"
    assert local_summary["mode_counts"]["shear"] == 3
    assert hint_summary["tick_count"] == 3
    assert hint_summary["armed_count"] == 2
    assert hint_summary["latest_recommendation"] == "stabilize"
    assert "Local phonons over 3 ticks:" in local_rendered
    assert "latest=local_post_injection:shear" in local_rendered
    assert "Advisory phonon hints over 3 ticks:" in hint_rendered
    assert "latest=armed:stabilize" in hint_rendered


def test_hippocampal_replay_summarizes_predictive_phonon_correlations(tmp_path: Path):
    panel = TelemetryPanel(working_dir=tmp_path)
    for pair_clock, coherence, tier, recommendation, next_mode in [
        (1, 0.40, "local_post_giant", "observe", "active"),
        (2, 0.48, "local_post_injection", "stabilize", "active"),
        (3, 0.61, "local_post_injection", "stabilize", "Stabilizer"),
        (4, 0.57, "local_post_giant", "observe", "active"),
    ]:
        panel.record_pair_scan(
            pair_id="primary-secondary",
            manifold_a_id="primary",
            manifold_b_id="secondary",
            wormhole_nodes=["node_0001", "node_0008"],
            wormhole_aperture=0.24,
            damping=0.85,
            phase_offset=0.15,
            shared_flux=[0.4, 1.1, 0.2],
            phase_coherence=coherence,
            bilateral_burst_count=1,
            max_h_cross_domain=6.8,
            shared_locus_summary={"pair_clock": pair_clock, "cross_domain_giant": "Entanglement Locus"},
            entangler_control={
                "pair_clock": pair_clock,
                "coherence_mode": "active" if pair_clock < 3 else next_mode,
                "next_coherence_mode": next_mode,
                "controls_before": {"aperture": 0.24, "damping": 0.85, "phase_offset": 0.15},
                "controls_after": {"aperture": 0.23, "damping": 0.86, "phase_offset": 0.14},
                "coherence_feedback": {"status": "improving" if pair_clock < 3 else "stable", "delta": 0.04, "error": 0.10, "target": 0.88},
                "mode_transition": {"changed": False, "previous_mode": "active", "next_mode": next_mode, "reason": "none"},
                "wormhole_weight_summary": {"min_weight": 0.95, "max_weight": 1.05, "top_weighted_wormholes": []},
            },
            latest_local_phonon_bundle={
                "phonon_id": f"phonon_primary-secondary_{pair_clock:04d}",
                "source_tier": tier,
                "carrier_giant": "The Graph Navigator",
                "mode": "shear",
                "amplitude": 0.20 + (0.05 * pair_clock),
                "confidence": 0.44 + (0.04 * pair_clock),
                "decay_rate": 0.15,
                "source_nodes": ["node_0001", "node_0008"],
                "wormhole_entry_nodes": ["node_0008"],
                "wormhole_exit_nodes": [],
                "coherence_signature": {"status": tier, "stability_score": 0.55 + (0.04 * pair_clock)},
            },
            local_phonon_bundle_count=pair_clock * 2,
            phonon_control_hint={
                "status": "armed",
                "recommended_bias": recommendation,
                "confidence": 0.44 + (0.04 * pair_clock),
                "age_ticks": 1,
                "stability_window": 4 + pair_clock,
                "suppression_reason": "none",
                "source_tier": tier,
                "entry_pressure": 1.0,
                "exit_pressure": 0.0,
            },
        )

    replay = HippocampalReplay(working_dir=tmp_path)
    predictive = replay.summarize_predictive_phonon_correlations(
        replay.load_pair_telemetry_records(pair_id="primary-secondary"),
        forward_window=2,
    )
    rendered = replay.render_predictive_phonon_summary(pair_id="primary-secondary", forward_window=2)

    assert predictive["sample_count"] == 3
    assert predictive["tier_correlations"]["local_post_injection"]["mean_future_delta"] > 0.0
    assert predictive["recommendation_correlations"]["stabilize"]["recovery_rate"] == 0.5
    assert predictive["recommendation_correlations"]["stabilize"]["stabilizer_entry_rate"] > 0.0
    assert "Predictive phonon correlations over 3 samples with +2-tick lookahead:" in rendered
    assert "recommendations:" in rendered
    assert "stabilize d=" in rendered


def test_hippocampal_replay_scores_hint_reliability(tmp_path: Path):
    replay = HippocampalReplay(working_dir=tmp_path)
    reliability = replay.score_hint_reliability(
        {
            "sample_count": 7,
            "forward_window": 2,
            "recommendation_correlations": {
                "stabilize": {"count": 4, "mean_future_delta": 0.07, "recovery_rate": 0.75, "stabilizer_entry_rate": 0.50},
                "observe": {"count": 3, "mean_future_delta": 0.01, "recovery_rate": 0.33, "stabilizer_entry_rate": 0.00},
            },
            "tier_correlations": {
                "local_post_injection": {"count": 4, "mean_future_delta": 0.07, "recovery_rate": 0.75, "stabilizer_entry_rate": 0.50},
                "local_post_giant": {"count": 3, "mean_future_delta": 0.01, "recovery_rate": 0.33, "stabilizer_entry_rate": 0.00},
            },
        },
        min_samples=3,
    )

    assert reliability["best_recommendation"] == "stabilize"
    assert reliability["recommendation_scores"]["stabilize"]["provisional"] is False
    assert reliability["recommendation_scores"]["stabilize"]["reliability_score"] > reliability["recommendation_scores"]["observe"]["reliability_score"]
    assert reliability["tier_scores"]["local_post_injection"]["evidence_status"] == "established"


def test_hippocampal_replay_summarizes_hint_calibration(tmp_path: Path):
    panel = TelemetryPanel(working_dir=tmp_path)
    for pair_clock, coherence, recommendation, confidence, next_mode in [
        (1, 0.40, "stabilize", 0.92, "active"),
        (2, 0.41, "stabilize", 0.88, "active"),
        (3, 0.58, "observe", 0.36, "Stabilizer"),
        (4, 0.66, "observe", 0.34, "Stabilizer"),
    ]:
        panel.record_pair_scan(
            pair_id="primary-secondary",
            manifold_a_id="primary",
            manifold_b_id="secondary",
            wormhole_nodes=["node_0001", "node_0008"],
            wormhole_aperture=0.24,
            damping=0.85,
            phase_offset=0.15,
            shared_flux=[0.4, 1.1, 0.2],
            phase_coherence=coherence,
            bilateral_burst_count=1,
            max_h_cross_domain=6.8,
            shared_locus_summary={"pair_clock": pair_clock, "cross_domain_giant": "Entanglement Locus"},
            entangler_control={
                "pair_clock": pair_clock,
                "coherence_mode": next_mode,
                "next_coherence_mode": next_mode,
                "controls_before": {"aperture": 0.24, "damping": 0.85, "phase_offset": 0.15},
                "controls_after": {"aperture": 0.23, "damping": 0.86, "phase_offset": 0.14},
                "coherence_feedback": {"status": "stable", "delta": 0.02, "error": 0.10, "target": 0.88},
                "mode_transition": {"changed": False, "previous_mode": next_mode, "next_mode": next_mode, "reason": "none"},
                "wormhole_weight_summary": {"min_weight": 0.95, "max_weight": 1.05, "top_weighted_wormholes": []},
            },
            phonon_control_hint={
                "status": "armed",
                "recommended_bias": recommendation,
                "confidence": confidence,
                "age_ticks": 1,
                "stability_window": 4 + pair_clock,
                "suppression_reason": "none",
                "source_tier": "local_post_injection",
                "entry_pressure": 1.0,
                "exit_pressure": 0.0,
            },
        )

    replay = HippocampalReplay(working_dir=tmp_path)
    records = replay.load_pair_telemetry_records(pair_id="primary-secondary")
    calibration = replay.summarize_hint_calibration(records, forward_window=2, min_samples=1)
    rendered = replay.render_hint_calibration_summary(pair_id="primary-secondary", forward_window=2, min_samples=1)

    assert calibration["tick_count"] == 4
    assert "stabilize" in calibration["recommendation_calibration"]
    assert abs(calibration["recommendation_calibration"]["stabilize"]["calibration_gap"]) > 0.0
    assert calibration["recommendation_calibration"]["observe"]["sample_count"] >= 1
    assert "Hint calibration over 4 hint ticks:" in rendered
    assert "stabilize conf=" in rendered


def test_hippocampal_replay_summarizes_nudge_outcomes(tmp_path: Path):
    panel = TelemetryPanel(working_dir=tmp_path)
    for pair_clock, coherence, mode, hint_gate in [
        (
            1,
            0.50,
            "active",
            {
                "enabled": True,
                "passed": True,
                "applied": True,
                "rejection_reason": "none",
                "nudge_enabled": True,
                "nudge_applied": True,
                "nudge_reason": "stabilize_via_hint",
                "nudge_rejection_reason": "none",
                "nudge_reliability": 0.86,
                "nudge_sample_count": 4,
                "nudge_stability_score": 0.83,
                "nudge_delta": {"aperture": -0.010, "damping": 0.008, "phase_offset": 0.012},
                "nudge_clamped": False,
                "nudge_clamp_flags": {"aperture": False, "damping": False, "phase_offset": False},
            },
        ),
        (
            2,
            0.58,
            "active",
            {
                "enabled": True,
                "passed": True,
                "applied": True,
                "rejection_reason": "none",
                "nudge_enabled": True,
                "nudge_applied": True,
                "nudge_reason": "stabilize_via_hint",
                "nudge_rejection_reason": "none",
                "nudge_reliability": 0.88,
                "nudge_sample_count": 5,
                "nudge_stability_score": 0.85,
                "nudge_delta": {"aperture": -0.012, "damping": 0.010, "phase_offset": 0.014},
                "nudge_clamped": True,
                "nudge_clamp_flags": {"aperture": True, "damping": False, "phase_offset": False},
            },
        ),
        (
            3,
            0.63,
            "Stabilizer",
            {
                "enabled": True,
                "passed": True,
                "applied": False,
                "rejection_reason": "none",
                "nudge_enabled": True,
                "nudge_applied": False,
                "nudge_reason": "none",
                "nudge_rejection_reason": "low_reliability",
                "nudge_reliability": 0.41,
                "nudge_sample_count": 2,
                "nudge_stability_score": 0.80,
                "nudge_delta": {"aperture": 0.0, "damping": 0.0, "phase_offset": 0.0},
                "nudge_clamped": False,
                "nudge_clamp_flags": {"aperture": False, "damping": False, "phase_offset": False},
            },
        ),
        (
            4,
            0.61,
            "Stabilizer",
            {
                "enabled": True,
                "passed": True,
                "applied": False,
                "rejection_reason": "none",
                "nudge_enabled": True,
                "nudge_applied": False,
                "nudge_reason": "none",
                "nudge_rejection_reason": "unstable",
                "nudge_reliability": 0.78,
                "nudge_sample_count": 5,
                "nudge_stability_score": 0.31,
                "nudge_delta": {"aperture": 0.0, "damping": 0.0, "phase_offset": 0.0},
                "nudge_clamped": False,
                "nudge_clamp_flags": {"aperture": False, "damping": False, "phase_offset": False},
            },
        ),
    ]:
        panel.record_pair_scan(
            pair_id="primary-secondary",
            manifold_a_id="primary",
            manifold_b_id="secondary",
            wormhole_nodes=["node_0001", "node_0008"],
            wormhole_aperture=0.24,
            damping=0.85,
            phase_offset=0.15,
            shared_flux=[0.4, 1.1, 0.2],
            phase_coherence=coherence,
            bilateral_burst_count=1,
            max_h_cross_domain=6.8,
            shared_locus_summary={"pair_clock": pair_clock, "cross_domain_giant": "Entanglement Locus"},
            entangler_control={
                "pair_clock": pair_clock,
                "coherence_mode": mode,
                "next_coherence_mode": mode,
                "controls_before": {"aperture": 0.24, "damping": 0.85, "phase_offset": 0.15},
                "controls_after": {"aperture": 0.23, "damping": 0.86, "phase_offset": 0.14},
                "coherence_feedback": {"status": "stable", "delta": 0.02, "error": 0.10, "target": 0.88},
                "mode_transition": {"changed": False, "previous_mode": mode, "next_mode": mode, "reason": "none"},
                "wormhole_weight_summary": {"min_weight": 0.95, "max_weight": 1.05, "top_weighted_wormholes": []},
                "hint_gate": hint_gate,
            },
            phonon_control_hint={
                "status": "armed",
                "recommended_bias": "stabilize",
                "confidence": 0.61,
                "age_ticks": 1,
                "stability_window": 5,
                "suppression_reason": "none",
                "decision_reason": "stabilize_pressure_or_low_stability",
                "source_tier": "local_post_injection",
                "entry_pressure": 1.0,
                "exit_pressure": 0.0,
            },
        )

    replay = HippocampalReplay(working_dir=tmp_path)
    records = replay.load_pair_telemetry_records(pair_id="primary-secondary")
    summary = replay.summarize_nudge_outcomes(records, forward_window=2)
    rendered = replay.render_nudge_outcome_summary(pair_id="primary-secondary", forward_window=2)

    assert summary["tick_count"] == 4
    assert summary["attempt_count"] == 4
    assert summary["applied_count"] == 2
    assert summary["rejection_count"] == 2
    assert summary["positive_coherence_windows"] >= 1
    assert summary["stabilizer_entry_windows"] >= 1
    assert summary["clamp_count"] == 1
    assert summary["reason_counts"]["stabilize_via_hint"] == 2
    assert summary["decision_reason_counts"]["stabilize_pressure_or_low_stability"] == 2
    assert summary["rejection_counts"]["low_reliability"] == 1
    assert summary["delta_abs_mean"]["aperture"] > 0.0
    assert "Nudge outcomes over 4 ticks:" in rendered
    assert "attempts=4, applied=2, rejected=2" in rendered
    assert "stabilize_via_hint" in rendered
    assert "stabilize_pressure_or_low_stability" in rendered


def test_hippocampal_replay_summarizes_hint_gate_decisions(tmp_path: Path):
    panel = TelemetryPanel(working_dir=tmp_path)
    for pair_clock, coherence, gate_passed, gate_reason, gate_status, confidence, reliability, sample_count, provisional, nudge_enabled, nudge_applied, nudge_rejection in [
        (1, 0.58, False, "not_armed", "suppressed", 0.44, 0.62, 2, True, True, False, "gate_blocked"),
        (2, 0.61, False, "low_confidence", "armed", 0.41, 0.71, 3, False, True, False, "gate_blocked"),
        (3, 0.65, False, "low_reliability", "armed", 0.67, 0.42, 2, True, True, False, "gate_blocked"),
        (4, 0.69, True, "none", "armed", 0.73, 0.81, 4, False, True, False, "observe_only"),
    ]:
        panel.record_pair_scan(
            pair_id="primary-secondary",
            manifold_a_id="primary",
            manifold_b_id="secondary",
            wormhole_nodes=["node_0001", "node_0008"],
            wormhole_aperture=0.24,
            damping=0.85,
            phase_offset=0.15,
            shared_flux=[0.4, 1.1, 0.2],
            phase_coherence=coherence,
            bilateral_burst_count=1,
            max_h_cross_domain=6.8,
            shared_locus_summary={"pair_clock": pair_clock, "cross_domain_giant": "Entanglement Locus"},
            entangler_control={
                "pair_clock": pair_clock,
                "coherence_mode": "active",
                "next_coherence_mode": "active",
                "controls_before": {"aperture": 0.24, "damping": 0.85, "phase_offset": 0.15},
                "controls_after": {"aperture": 0.23, "damping": 0.86, "phase_offset": 0.14},
                "coherence_feedback": {"status": "stable", "delta": 0.02, "error": 0.10, "target": 0.88},
                "mode_transition": {"changed": False, "previous_mode": "active", "next_mode": "active", "reason": "none"},
                "wormhole_weight_summary": {"min_weight": 0.95, "max_weight": 1.05, "top_weighted_wormholes": []},
                "hint_gate": {
                    "enabled": True,
                    "passed": gate_passed,
                    "applied": gate_passed,
                    "rejection_reason": gate_reason,
                    "considered_recommendation": "stabilize",
                    "considered_status": gate_status,
                    "considered_confidence": confidence,
                    "considered_reliability": reliability,
                    "considered_sample_count": sample_count,
                    "reliability_provisional": provisional,
                    "nudge_enabled": nudge_enabled,
                    "nudge_applied": nudge_applied,
                    "nudge_reason": "stabilize_via_hint" if nudge_applied else "none",
                    "nudge_rejection_reason": nudge_rejection,
                    "nudge_reliability": reliability,
                    "nudge_sample_count": sample_count,
                    "nudge_stability_score": 0.35,
                    "nudge_delta": {"aperture": 0.0, "damping": 0.0, "phase_offset": 0.0},
                    "nudge_clamped": False,
                    "nudge_clamp_flags": {"aperture": False, "damping": False, "phase_offset": False},
                },
            },
            phonon_control_hint={
                "status": gate_status,
                "recommended_bias": "stabilize",
                "confidence": confidence,
                "age_ticks": 1,
                "stability_window": 5,
                "suppression_reason": "low_confidence" if gate_status != "armed" else "none",
                "decision_reason": "low_confidence" if gate_reason == "low_confidence" else ("stabilize_pressure_or_low_stability" if gate_status == "armed" else "low_confidence"),
                "source_tier": "local_post_injection",
                "entry_pressure": 1.0,
                "exit_pressure": 0.0,
                "pair_stability": 0.42 if gate_status == "armed" else 0.63,
                "local_stability": 0.41 if gate_status == "armed" else 0.28,
                "pair_decay": 0.11,
                "amplitude_trend": -0.04 if gate_status == "armed" else 0.02,
            },
        )

    replay = HippocampalReplay(working_dir=tmp_path)
    records = replay.load_pair_telemetry_records(pair_id="primary-secondary")
    summary = replay.summarize_hint_gate_decisions(records)
    rendered = replay.render_hint_gate_decision_summary(pair_id="primary-secondary")

    assert summary["tick_count"] == 4
    assert summary["enabled_count"] == 4
    assert summary["passed_count"] == 1
    assert summary["blocked_count"] == 3
    assert summary["reason_counts"] == {"not_armed": 1, "low_confidence": 1, "low_reliability": 1}
    assert summary["status_counts"]["armed"] == 3
    assert summary["status_counts"]["suppressed"] == 1
    assert summary["passed_but_nudge_blocked_count"] == 1
    assert summary["near_pass_count"] == 1
    assert summary["first_pass_tick"] == 4
    assert summary["first_block_tick"] == 1
    assert summary["first_near_pass_tick"] == 2
    assert summary["first_near_pass_reason"] == "low_confidence"
    assert summary["first_near_pass_decision_reason"] == "low_confidence"
    assert round(summary["first_near_pass_confidence_gap"], 2) == 0.14
    assert summary["first_near_pass_reliability_gap"] == 0.0
    assert summary["first_near_pass_sample_gap"] == 0
    assert summary["first_pass_decision_reason"] == "stabilize_pressure_or_low_stability"
    assert summary["longest_block_streak"] == 3
    assert "Hint gate decisions over 4 ticks:" in rendered
    assert "enabled=4, passed=1, blocked=3" in rendered
    assert "not_armed=1, low_confidence=1, low_reliability=1" in rendered
    assert "near_pass=1" in rendered
    assert "first_pass=4/stabilize_pressure_or_low_stability/p0.42/l0.41/d0.11/a-0.04" in rendered
    assert "first_near_pass=tick 2 (low_confidence, cgap=0.14, rgap=0.00, ngap=0, decide=low_confidence, signal=p0.42/l0.41/d0.11/a-0.04)" in rendered
    assert "pass_but_nudge_blocked=1" in rendered


def test_hippocampal_replay_summarizes_paper_diagnostic_proxies(tmp_path: Path):
    panel = TelemetryPanel(working_dir=tmp_path)
    for pair_clock, coherence, gate_passed, gate_reason, gate_status, confidence, reliability, sample_count, provisional, nudge_rejection in [
        (1, 0.54, False, "not_armed", "suppressed", 0.44, 0.62, 2, True, "gate_blocked"),
        (2, 0.55, False, "low_confidence", "armed", 0.41, 0.71, 3, False, "gate_blocked"),
        (3, 0.56, False, "low_reliability", "armed", 0.67, 0.42, 2, True, "gate_blocked"),
        (4, 0.56, True, "none", "armed", 0.73, 0.81, 4, False, "observe_only"),
    ]:
        panel.record_pair_scan(
            pair_id="primary-secondary",
            manifold_a_id="primary",
            manifold_b_id="secondary",
            wormhole_nodes=["node_0001", "node_0008"],
            wormhole_aperture=0.24,
            damping=0.85,
            phase_offset=0.15,
            shared_flux=[0.4, 1.1, 0.2],
            phase_coherence=coherence,
            bilateral_burst_count=1,
            max_h_cross_domain=6.8,
            shared_locus_summary={"pair_clock": pair_clock, "cross_domain_giant": "Entanglement Locus"},
            entangler_control={
                "pair_clock": pair_clock,
                "coherence_mode": "active",
                "next_coherence_mode": "active",
                "controls_before": {"aperture": 0.24, "damping": 0.85, "phase_offset": 0.15},
                "controls_after": {"aperture": 0.23, "damping": 0.86, "phase_offset": 0.14},
                "coherence_feedback": {"status": "stable", "delta": 0.01, "error": 0.10, "target": 0.88},
                "mode_transition": {"changed": False, "previous_mode": "active", "next_mode": "active", "reason": "none"},
                "wormhole_weight_summary": {"min_weight": 0.95, "max_weight": 1.05, "top_weighted_wormholes": []},
                "hint_gate": {
                    "enabled": True,
                    "passed": gate_passed,
                    "applied": gate_passed,
                    "rejection_reason": gate_reason,
                    "considered_recommendation": "stabilize",
                    "considered_status": gate_status,
                    "considered_confidence": confidence,
                    "considered_reliability": reliability,
                    "considered_sample_count": sample_count,
                    "reliability_provisional": provisional,
                    "nudge_enabled": True,
                    "nudge_applied": False,
                    "nudge_reason": "none",
                    "nudge_rejection_reason": nudge_rejection,
                    "nudge_reliability": reliability,
                    "nudge_sample_count": sample_count,
                    "nudge_stability_score": 0.35,
                    "nudge_delta": {"aperture": 0.0, "damping": 0.0, "phase_offset": 0.0},
                    "nudge_clamped": False,
                    "nudge_clamp_flags": {"aperture": False, "damping": False, "phase_offset": False},
                },
            },
            phonon_control_hint={
                "status": gate_status,
                "recommended_bias": "stabilize",
                "confidence": confidence,
                "age_ticks": 1,
                "stability_window": 5,
                "suppression_reason": "low_confidence" if gate_status != "armed" else "none",
                "decision_reason": "low_confidence" if gate_reason == "low_confidence" else "stabilize_pressure_or_low_stability",
                "source_tier": "local_post_injection",
                "entry_pressure": 1.0,
                "exit_pressure": 0.0,
                "pair_stability": 0.42,
                "local_stability": 0.41,
                "pair_decay": 0.11,
                "amplitude_trend": -0.04,
            },
        )

    replay = HippocampalReplay(working_dir=tmp_path)
    records = replay.load_pair_telemetry_records(pair_id="primary-secondary")
    summary = replay.summarize_paper_diagnostic_proxies(records)
    rendered = replay.render_paper_diagnostic_summary(pair_id="primary-secondary")

    assert summary["tick_count"] == 4
    assert summary["synchrony_margin"]["label"] == "borderline"
    assert summary["synchrony_margin"]["basis"] == "boundary_led"
    assert summary["synchrony_margin"]["coupling_posture"] == "permissive"
    assert summary["synchrony_margin"]["boundary_state"] == "non_converting"
    assert summary["synchrony_margin"]["contradiction_level"] == "high"
    assert "aperture_damping_permissive" in summary["synchrony_margin"]["coupling_support_signals"]
    assert "phase_offset_aligned" in summary["synchrony_margin"]["coupling_support_signals"]
    assert "coherence_mean_low" in summary["synchrony_margin"]["evidence_signals"]
    assert "coherence_mean_low" in summary["synchrony_margin"]["risk_signals"]
    assert "near_pass_without_resolution" in summary["synchrony_margin"]["contradiction_signals"]
    assert summary["basin_fragility"]["label"] == "broad"
    assert "low_mode_churn" in summary["basin_fragility"]["support_signals"]
    assert "Paper diagnostics over 4 ticks:" in rendered
    assert "synchrony_margin=borderline" in rendered
    assert "basis=boundary_led" in rendered
    assert "coupling=permissive" in rendered
    assert "boundary=non_converting" in rendered
    assert "contradiction=high" in rendered
    assert "basin_fragility=broad" in rendered


def test_hippocampal_replay_renders_uncertainty_paper_recommendation_stub(tmp_path: Path):
    panel = TelemetryPanel(working_dir=tmp_path)
    for pair_clock, coherence, gate_passed, gate_reason, gate_status, confidence, reliability, sample_count, provisional, nudge_rejection in [
        (1, 0.54, False, "not_armed", "suppressed", 0.44, 0.62, 2, True, "gate_blocked"),
        (2, 0.55, False, "low_confidence", "armed", 0.41, 0.71, 3, False, "gate_blocked"),
        (3, 0.56, False, "low_reliability", "armed", 0.67, 0.42, 2, True, "gate_blocked"),
        (4, 0.56, True, "none", "armed", 0.73, 0.81, 4, False, "observe_only"),
    ]:
        panel.record_pair_scan(
            pair_id="primary-secondary",
            manifold_a_id="primary",
            manifold_b_id="secondary",
            wormhole_nodes=["node_0001", "node_0008"],
            wormhole_aperture=0.24,
            damping=0.85,
            phase_offset=0.15,
            shared_flux=[0.4, 1.1, 0.2],
            phase_coherence=coherence,
            bilateral_burst_count=1,
            max_h_cross_domain=6.8,
            shared_locus_summary={"pair_clock": pair_clock, "cross_domain_giant": "Entanglement Locus"},
            entangler_control={
                "pair_clock": pair_clock,
                "coherence_mode": "active",
                "next_coherence_mode": "active",
                "controls_before": {"aperture": 0.24, "damping": 0.85, "phase_offset": 0.15},
                "controls_after": {"aperture": 0.23, "damping": 0.86, "phase_offset": 0.14},
                "coherence_feedback": {"status": "stable", "delta": 0.01, "error": 0.10, "target": 0.88},
                "mode_transition": {"changed": False, "previous_mode": "active", "next_mode": "active", "reason": "none"},
                "wormhole_weight_summary": {"min_weight": 0.95, "max_weight": 1.05, "top_weighted_wormholes": []},
                "hint_gate": {
                    "enabled": True,
                    "passed": gate_passed,
                    "applied": gate_passed,
                    "rejection_reason": gate_reason,
                    "considered_recommendation": "stabilize",
                    "considered_status": gate_status,
                    "considered_confidence": confidence,
                    "considered_reliability": reliability,
                    "considered_sample_count": sample_count,
                    "reliability_provisional": provisional,
                    "nudge_enabled": True,
                    "nudge_applied": False,
                    "nudge_reason": "none",
                    "nudge_rejection_reason": nudge_rejection,
                    "nudge_reliability": reliability,
                    "nudge_sample_count": sample_count,
                    "nudge_stability_score": 0.35,
                    "nudge_delta": {"aperture": 0.0, "damping": 0.0, "phase_offset": 0.0},
                    "nudge_clamped": False,
                    "nudge_clamp_flags": {"aperture": False, "damping": False, "phase_offset": False},
                },
            },
            phonon_control_hint={
                "status": gate_status,
                "recommended_bias": "stabilize",
                "confidence": confidence,
                "age_ticks": 1,
                "stability_window": 5,
                "suppression_reason": "low_confidence" if gate_status != "armed" else "none",
                "decision_reason": "low_confidence" if gate_reason == "low_confidence" else "stabilize_pressure_or_low_stability",
                "source_tier": "local_post_injection",
                "entry_pressure": 1.0,
                "exit_pressure": 0.0,
                "pair_stability": 0.42,
                "local_stability": 0.41,
                "pair_decay": 0.11,
                "amplitude_trend": -0.04,
            },
        )

    replay = HippocampalReplay(working_dir=tmp_path)
    records = replay.load_pair_telemetry_records(pair_id="primary-secondary")
    summary = replay.summarize_uncertainty_paper_recommendation(records)
    rendered = replay.render_uncertainty_paper_recommendation(pair_id="primary-secondary")
    full_output = replay.replay(pair_id="primary-secondary", top_n=4)

    assert summary["triggered"] is True
    assert summary["intervention_class"] == "control policy"
    assert summary["coupling_posture"] == "permissive"
    assert "coupling:permissive" in summary["regimes"]
    assert summary["preferred_search_envelope"] == "one paper"
    assert "UNCERTAINTY TO PAPER RECOMMENDATION" in rendered
    assert "intervention class: control policy" in rendered
    assert "coupling=permissive" in rendered
    assert "preferred search envelope: one paper" in rendered
    assert "Uncertainty paper recommendation:" in full_output
    assert "UNCERTAINTY TO PAPER RECOMMENDATION" in full_output


def test_hippocampal_replay_routes_weak_coupling_uncertainty_to_topology_design(tmp_path: Path):
    panel = TelemetryPanel(working_dir=tmp_path)
    for pair_clock, coherence, status in [
        (1, 0.41, "decaying"),
        (2, 0.39, "decaying"),
        (3, 0.36, "decaying"),
        (4, 0.34, "decaying"),
    ]:
        panel.record_pair_scan(
            pair_id="primary-secondary",
            manifold_a_id="primary",
            manifold_b_id="secondary",
            wormhole_nodes=["node_0001", "node_0008"],
            wormhole_aperture=0.14,
            damping=0.94,
            phase_offset=0.33,
            shared_flux=[0.08, 0.10, 0.05],
            phase_coherence=coherence,
            bilateral_burst_count=1,
            max_h_cross_domain=5.2,
            shared_locus_summary={"pair_clock": pair_clock, "cross_domain_giant": "Entanglement Locus"},
            entangler_control={
                "pair_clock": pair_clock,
                "coherence_mode": "active",
                "next_coherence_mode": "active",
                "controls_before": {"aperture": 0.14, "damping": 0.94, "phase_offset": 0.33},
                "controls_after": {"aperture": 0.14, "damping": 0.94, "phase_offset": 0.33},
                "coherence_feedback": {"status": status, "delta": -0.03, "error": 0.54, "target": 0.88},
                "mode_transition": {"changed": False, "previous_mode": "active", "next_mode": "active", "reason": "none"},
                "wormhole_weight_summary": {"min_weight": 0.95, "max_weight": 1.05, "top_weighted_wormholes": []},
                "hint_gate": {
                    "enabled": True,
                    "passed": False,
                    "applied": False,
                    "rejection_reason": "low_confidence",
                    "considered_recommendation": "observe",
                    "considered_status": "armed",
                    "considered_confidence": 0.31,
                    "considered_reliability": 0.28,
                    "considered_sample_count": 3,
                    "reliability_provisional": False,
                    "nudge_enabled": True,
                    "nudge_applied": False,
                    "nudge_reason": "none",
                    "nudge_rejection_reason": "gate_blocked",
                    "nudge_reliability": 0.28,
                    "nudge_sample_count": 3,
                    "nudge_stability_score": 0.22,
                    "nudge_delta": {"aperture": 0.0, "damping": 0.0, "phase_offset": 0.0},
                    "nudge_clamped": False,
                    "nudge_clamp_flags": {"aperture": False, "damping": False, "phase_offset": False},
                },
            },
            phonon_control_hint={
                "status": "armed",
                "recommended_bias": "observe",
                "confidence": 0.31,
                "age_ticks": 1,
                "stability_window": 5,
                "suppression_reason": "none",
                "decision_reason": "low_confidence",
                "source_tier": "local_post_injection",
                "entry_pressure": 0.2,
                "exit_pressure": 0.8,
                "pair_stability": 0.21,
                "local_stability": 0.18,
                "pair_decay": 0.29,
                "amplitude_trend": -0.18,
            },
        )

    replay = HippocampalReplay(working_dir=tmp_path)
    records = replay.load_pair_telemetry_records(pair_id="primary-secondary")
    proxy = replay.summarize_paper_diagnostic_proxies(records)
    summary = replay.summarize_uncertainty_paper_recommendation(records)
    rendered = replay.render_uncertainty_paper_recommendation(pair_id="primary-secondary")

    assert proxy["synchrony_margin"]["coupling_posture"] == "weak"
    assert summary["triggered"] is True
    assert summary["intervention_class"] == "topology design"
    assert summary["coupling_posture"] == "weak"
    assert summary["desired_paper_role"] == "one paper on topology-aware synchronization feasibility or controllability"
    assert "coupling:weak" in summary["regimes"]
    assert "topology-aware synchronization" in summary["novelty_relative"]
    assert "intervention class: topology design" in rendered
    assert "coupling=weak" in rendered


def test_hippocampal_replay_cli_extracts_paper_section(tmp_path: Path, monkeypatch, capsys):
    panel = TelemetryPanel(working_dir=tmp_path)
    for pair_clock, coherence in [(1, 0.62), (2, 0.70), (3, 0.75)]:
        panel.record_pair_scan(
            pair_id="primary-secondary",
            manifold_a_id="primary",
            manifold_b_id="secondary",
            wormhole_nodes=["node_0001", "node_0008"],
            wormhole_aperture=0.24,
            damping=0.85,
            phase_offset=0.15,
            shared_flux=[0.4, 1.1, 0.2],
            phase_coherence=coherence,
            bilateral_burst_count=1,
            max_h_cross_domain=6.8,
            shared_locus_summary={"pair_clock": pair_clock, "cross_domain_giant": "Entanglement Locus"},
            entangler_control={
                "pair_clock": pair_clock,
                "coherence_mode": "active",
                "next_coherence_mode": "active",
                "controls_before": {"aperture": 0.24, "damping": 0.85, "phase_offset": 0.15},
                "controls_after": {"aperture": 0.23, "damping": 0.86, "phase_offset": 0.14},
                "coherence_feedback": {"status": "improving", "delta": 0.04, "error": 0.10, "target": 0.88},
                "mode_transition": {"changed": False, "previous_mode": "active", "next_mode": "active", "reason": "none"},
                "wormhole_weight_summary": {"min_weight": 0.95, "max_weight": 1.05, "top_weighted_wormholes": []},
                "hint_gate": {
                    "enabled": True,
                    "passed": True,
                    "applied": True,
                    "rejection_reason": "none",
                    "considered_recommendation": "stabilize",
                    "considered_status": "armed",
                    "considered_confidence": 0.73,
                    "considered_reliability": 0.81,
                    "considered_sample_count": 4,
                    "reliability_provisional": False,
                    "nudge_enabled": True,
                    "nudge_applied": True,
                    "nudge_reason": "stabilize_via_hint",
                    "nudge_rejection_reason": "none",
                    "nudge_reliability": 0.81,
                    "nudge_sample_count": 4,
                    "nudge_stability_score": 0.65,
                    "nudge_delta": {"aperture": -0.01, "damping": 0.01, "phase_offset": -0.01},
                    "nudge_clamped": False,
                    "nudge_clamp_flags": {"aperture": False, "damping": False, "phase_offset": False},
                },
            },
            phonon_control_hint={
                "status": "armed",
                "recommended_bias": "stabilize",
                "confidence": 0.73,
                "age_ticks": 1,
                "stability_window": 5,
                "suppression_reason": "none",
                "decision_reason": "stabilize_pressure_or_low_stability",
                "source_tier": "local_post_injection",
                "entry_pressure": 1.0,
                "exit_pressure": 0.0,
                "pair_stability": 0.69,
                "local_stability": 0.65,
                "pair_decay": 0.06,
                "amplitude_trend": 0.03,
            },
        )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "hippocampal_replay.py",
            "--working-dir",
            str(tmp_path),
            "--pair-id",
            "primary-secondary",
            "--section",
            "paper",
        ],
    )

    replay_main()
    output = capsys.readouterr().out

    assert "Pair id: primary-secondary" in output
    assert "Paper diagnostic summary:" in output
    assert "synchrony_margin=" in output
    assert "Uncertainty paper recommendation:" not in output

    def test_hippocampal_replay_summarizes_status_streaks_and_first_stabilizer_tick(tmp_path: Path):
        panel = TelemetryPanel(working_dir=tmp_path)
        for pair_clock, coherence, status, mode in [
            (1, 0.63, "decaying", "active"),
            (2, 0.58, "decaying", "active"),
            (3, 0.57, "stable", "active"),
            (4, 0.62, "improving", "Stabilizer"),
            (5, 0.68, "improving", "Stabilizer"),
        ]:
            panel.record_pair_scan(
                pair_id="primary-secondary",
                manifold_a_id="primary",
                manifold_b_id="secondary",
                wormhole_nodes=["node_0001", "node_0008"],
                wormhole_aperture=0.24,
                damping=0.85,
                phase_offset=0.15,
                shared_flux=[0.4, 1.1, 0.2],
                phase_coherence=coherence,
                bilateral_burst_count=1,
                max_h_cross_domain=6.8,
                shared_locus_summary={"pair_clock": pair_clock, "cross_domain_giant": "Entanglement Locus"},
                entangler_control={
                    "pair_clock": pair_clock,
                    "coherence_mode": mode,
                    "next_coherence_mode": mode,
                    "controls_before": {"aperture": 0.24, "damping": 0.85, "phase_offset": 0.15},
                    "controls_after": {"aperture": 0.23, "damping": 0.86, "phase_offset": 0.14},
                    "coherence_feedback": {"status": status, "delta": 0.04, "error": 0.10, "target": 0.88},
                    "mode_transition": {"changed": False, "previous_mode": mode, "next_mode": mode, "reason": "none"},
                    "wormhole_weight_summary": {"min_weight": 0.95, "max_weight": 1.05, "top_weighted_wormholes": []},
                },
            )

        replay = HippocampalReplay(working_dir=tmp_path)
        streaks = replay.summarize_status_streaks(replay.load_pair_telemetry_records(pair_id="primary-secondary"))

        assert streaks["tick_count"] == 5
        assert streaks["longest_decay_streak"] == 2
        assert streaks["longest_improving_streak"] == 2
        assert streaks["longest_stable_streak"] == 1
        assert streaks["first_stabilizer_tick"] == 4

    def test_hippocampal_replay_diagnoses_low_variance_runs(tmp_path: Path):
        panel = TelemetryPanel(working_dir=tmp_path)
        for pair_clock, coherence, status in [
            (1, 0.84, "stable"),
            (2, 0.85, "improving"),
            (3, 0.86, "stable"),
            (4, 0.85, "stable"),
        ]:
            panel.record_pair_scan(
                pair_id="primary-secondary",
                manifold_a_id="primary",
                manifold_b_id="secondary",
                wormhole_nodes=["node_0001", "node_0008"],
                wormhole_aperture=0.24,
                damping=0.85,
                phase_offset=0.15,
                shared_flux=[0.3, 0.9, 0.1],
                phase_coherence=coherence,
                bilateral_burst_count=1,
                max_h_cross_domain=6.4,
                shared_locus_summary={"pair_clock": pair_clock, "cross_domain_giant": "Entanglement Locus"},
                entangler_control={
                    "pair_clock": pair_clock,
                    "coherence_mode": "active",
                    "next_coherence_mode": "active",
                    "controls_before": {"aperture": 0.24, "damping": 0.85, "phase_offset": 0.15},
                    "controls_after": {"aperture": 0.25, "damping": 0.84, "phase_offset": 0.15},
                    "coherence_feedback": {"status": status, "delta": 0.01, "error": 0.04, "target": 0.88},
                    "mode_transition": {"changed": False, "previous_mode": "active", "next_mode": "active", "reason": "none"},
                    "wormhole_weight_summary": {"min_weight": 0.98, "max_weight": 1.02, "top_weighted_wormholes": []},
                },
            )

        replay = HippocampalReplay(working_dir=tmp_path)
        diagnosis = replay.summarize_sweep_diagnosis(
            replay.load_pair_telemetry_records(pair_id="primary-secondary"),
            min_mode_switch_samples=3,
            enter_decay_streak=2,
            cycle_count=4,
        )

        assert diagnosis["label"] == "low_variance_candidate"
        assert diagnosis["met_entry_policy"] is False
        assert diagnosis["entry_policy_tick"] is None

    def test_hippocampal_replay_diagnoses_threshold_conservative_runs(tmp_path: Path):
        panel = TelemetryPanel(working_dir=tmp_path)
        for pair_clock, coherence, status, decay_streak in [
            (1, 0.74, "decaying", 1),
            (2, 0.66, "decaying", 2),
            (3, 0.61, "stable", 2),
            (4, 0.64, "improving", 0),
        ]:
            panel.record_pair_scan(
                pair_id="primary-secondary",
                manifold_a_id="primary",
                manifold_b_id="secondary",
                wormhole_nodes=["node_0001", "node_0008"],
                wormhole_aperture=0.24,
                damping=0.85,
                phase_offset=0.15,
                shared_flux=[0.5, 1.4, 0.2],
                phase_coherence=coherence,
                bilateral_burst_count=1,
                max_h_cross_domain=6.9,
                shared_locus_summary={"pair_clock": pair_clock, "cross_domain_giant": "Entanglement Locus"},
                entangler_control={
                    "pair_clock": pair_clock,
                    "coherence_mode": "active",
                    "next_coherence_mode": "active",
                    "controls_before": {"aperture": 0.24, "damping": 0.85, "phase_offset": 0.15},
                    "controls_after": {"aperture": 0.22, "damping": 0.87, "phase_offset": 0.13},
                    "coherence_feedback": {"status": status, "delta": -0.07 if status == "decaying" else 0.03, "error": 0.18, "target": 0.88},
                    "mode_transition": {"changed": False, "previous_mode": "active", "next_mode": "active", "reason": "none", "decay_streak": decay_streak},
                    "mode_decay_streak": decay_streak,
                    "wormhole_weight_summary": {"min_weight": 0.92, "max_weight": 1.10, "top_weighted_wormholes": []},
                },
            )

        replay = HippocampalReplay(working_dir=tmp_path)
        diagnosis = replay.summarize_sweep_diagnosis(
            replay.load_pair_telemetry_records(pair_id="primary-secondary"),
            min_mode_switch_samples=2,
            enter_decay_streak=2,
            cycle_count=4,
        )

        assert diagnosis["label"] == "threshold_conservative_candidate"
        assert diagnosis["met_entry_policy"] is True
        assert diagnosis["entry_policy_tick"] == 2

def test_hippocampal_replay_summarizes_real_multi_tick_pair_runs(tmp_path: Path):
    from entangled_manifolds import EntangledSOLPair, EntanglementControls

    pair = EntangledSOLPair(
        config_a=BlankManifoldConfig(base_node_count=64, dimensionality=3),
        config_b=BlankManifoldConfig(base_node_count=64, dimensionality=3),
        controls=EntanglementControls(wormhole_count=4, seed=37),
        working_dir=tmp_path,
    )
    pair.run_live_cycles(
        cycle_count=5,
        embedding_a_loc=0.49,
        embedding_b_loc=0.58,
        embedding_scale=0.07,
        embedding_drift=0.05,
    )

    replay = HippocampalReplay(working_dir=tmp_path)
    output = replay.replay(pair_id=pair.pair_id, top_n=4)

    assert "Entangler control summary:" in output
    assert "Coherence trend over 5 ticks:" in output
    assert "Mode switching over 5 ticks:" in output
    assert "Local phonon summary:" in output
    assert "Advisory hint summary:" in output
    assert "Wormhole weight summary:" in output