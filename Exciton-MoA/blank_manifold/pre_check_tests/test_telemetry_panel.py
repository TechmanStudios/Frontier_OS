# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
from pathlib import Path

import numpy as np

from blank_config import BlankManifoldConfig
from blank_manifold_core import BlankManifoldCore
from telemetry import OntologicalOrchestrator
from telemetry_panel import TelemetryPanel


def test_telemetry_panel_records_history_and_renders_latest(tmp_path: Path):
    panel = TelemetryPanel(working_dir=tmp_path, history_limit=4, bar_width=6)

    panel.record_scan(
        "primary",
        adaptive_tau=4.5,
        burst_count=3,
        avg_h=2.7,
        max_h=6.2,
        bursts=[("node_0001", {"H_total": 6.2, "density_contrib": 0.8, "shear_contrib": 3.9, "vorticity_contrib": 0.7})],
    )
    panel.record_scan(
        "primary",
        adaptive_tau=4.7,
        burst_count=5,
        avg_h=3.1,
        max_h=7.4,
        bursts=[("node_0000", {"H_total": 7.4, "density_contrib": 1.1, "shear_contrib": 4.8, "vorticity_contrib": 0.9})],
    )

    rendered = panel.render(
        manifold_id="primary",
        bursts=[
            (
                "node_0000",
                {
                    "H_total": 7.4,
                    "density_contrib": 1.1,
                    "shear_contrib": 4.8,
                    "vorticity_contrib": 0.9,
                },
            )
        ],
    )

    assert panel.history_path.exists()
    assert "[TELEMETRY PANEL] manifold=primary | tau=4.700 | bursts=5" in rendered
    assert "Tau history   : 4.500 4.700" in rendered
    assert "Burst history : 3 5" in rendered
    assert "node_0000 | H=7.40" in rendered
    assert "d [#-----] 1.10" in rendered
    assert "s [######] 4.80" in rendered


def test_telemetry_panel_registry_and_comparative_views(tmp_path: Path):
    panel = TelemetryPanel(working_dir=tmp_path, history_limit=4, bar_width=6)

    panel.record_scan(
        "primary",
        adaptive_tau=4.7,
        burst_count=5,
        avg_h=3.1,
        max_h=7.4,
        bursts=[
            ("node_0000", {"H_total": 7.4, "density_contrib": 1.1, "shear_contrib": 4.8, "vorticity_contrib": 0.9}),
            ("node_0002", {"H_total": 6.8, "density_contrib": 1.0, "shear_contrib": 4.4, "vorticity_contrib": 0.8}),
        ],
    )
    panel.record_scan(
        "secondary",
        adaptive_tau=5.2,
        burst_count=8,
        avg_h=3.9,
        max_h=8.1,
        bursts=[
            ("node_0200", {"H_total": 8.1, "density_contrib": 0.9, "shear_contrib": 5.3, "vorticity_contrib": 1.0}),
            ("node_0201", {"H_total": 7.7, "density_contrib": 0.7, "shear_contrib": 5.1, "vorticity_contrib": 1.1}),
        ],
    )

    registry = panel.render_registry(top_n=2)
    comparative = panel.render_comparative()

    assert "[MANIFOLD REGISTRY] active_manifolds=2" in registry
    assert "- primary | tau=4.700 | bursts=5" in registry
    assert "- secondary | tau=5.200 | bursts=8" in registry
    assert "node_0200 | H=8.10" in registry
    assert "dominant=shear" in registry

    assert "[MANIFOLD COMPARISON] ranked by burst_count, maxH, tau" in comparative
    assert "1. secondary | tau=5.200 | bursts=8" in comparative
    assert "dominant=shear" in comparative


def test_telemetry_panel_pair_registry_and_comparative_views(tmp_path: Path):
    panel = TelemetryPanel(working_dir=tmp_path, history_limit=4, bar_width=6)

    panel.record_pair_scan(
        pair_id="primary-secondary",
        manifold_a_id="primary",
        manifold_b_id="secondary",
        wormhole_nodes=["node_0001", "node_0008"],
        wormhole_aperture=0.28,
        damping=0.82,
        phase_offset=0.15,
        shared_flux=[0.8, 2.9, 0.7],
        phase_coherence=0.73,
        bilateral_burst_count=4,
        max_h_cross_domain=7.9,
        bilateral_node_ids=["node_0001"],
        top_events=[
            {"manifold_id": "primary", "node_id": "node_0001", "h_total": 7.9, "density_contrib": 1.0, "shear_contrib": 4.7, "vorticity_contrib": 0.8},
            {"manifold_id": "secondary", "node_id": "node_0008", "h_total": 7.3, "density_contrib": 0.9, "shear_contrib": 4.3, "vorticity_contrib": 0.7},
        ],
        shared_locus_summary={"pair_clock": 5, "dominant_channel": "shear", "cross_domain_giant": "Entanglement Locus", "shared_flux_norm": 3.09},
        entangler_control={
            "pair_clock": 6,
            "entanglement_strength": 0.74,
            "dominant_giant_consensus": "The Graph Navigator",
            "coherence_mode": "Stabilizer",
            "next_coherence_mode": "Stabilizer",
            "coherence_feedback": {"status": "decaying", "delta": -0.09, "error": 0.15, "target": 0.88},
            "mode_transition": {"changed": True, "previous_mode": "active", "next_mode": "Stabilizer", "reason": "decaying_x2_after_history3", "decay_streak": 2, "improving_streak": 0, "stabilizer_dwell_ticks": 0},
            "mode_decay_streak": 2,
            "mode_improving_streak": 0,
            "stabilizer_dwell_ticks": 0,
            "wormhole_weight_summary": {"min_weight": 0.82, "max_weight": 1.44, "top_weighted_wormholes": [{"node_id": "node_0001", "weight": 1.44}, {"node_id": "node_0008", "weight": 1.18}]},
            "controls_before": {"aperture": 0.28, "damping": 0.82, "phase_offset": 0.15},
            "controls_after": {"aperture": 0.34, "damping": 0.79, "phase_offset": 0.21},
            "clamp_flags": {"aperture": False, "damping": False, "phase_offset": False},
            "reasoning_summary": "coherent bilateral rise",
        },
    )

    snapshots = panel.load_pair_snapshots()
    registry = panel.render_pair_registry(pair_ids=["primary-secondary"], top_n=2)
    comparative = panel.render_pair_comparative(pair_ids=["primary-secondary"])

    assert snapshots[-1]["shared_pair_clock"] == 5
    assert snapshots[-1]["shared_locus_giant"] == "Entanglement Locus"
    assert snapshots[-1]["entangler_strength"] == 0.74
    assert snapshots[-1]["entangler_aperture_after"] == 0.34
    assert snapshots[-1]["entangler_weight_max"] == 1.44
    assert snapshots[-1]["entangler_coherence_status"] == "decaying"
    assert snapshots[-1]["entangler_mode"] == "Stabilizer"
    assert snapshots[-1]["entangler_next_mode"] == "Stabilizer"
    assert snapshots[-1]["entangler_mode_changed"] is True
    assert snapshots[-1]["entangler_previous_mode"] == "active"
    assert snapshots[-1]["entangler_transition_reason"] == "decaying_x2_after_history3"
    assert "[PAIR REGISTRY] active_pairs=1" in registry
    assert "- primary-secondary | aperture=0.280 | damping=0.820 | coherence=0.730 | bilateral=4" in registry
    assert "| clock=5 | locus=Entanglement Locus | mode=Stabilizer" in registry
    assert "| ent=0.740 | ctrl=a0.340/d0.790/p0.210 | w=0.82-1.44 | fb=decaying | gate=off | nudge=off" in registry
    assert "| ph=none:0.00 | tx=active->Stabilizer" in registry
    assert "transition reason: decaying_x2_after_history3" in registry
    assert "weighted wormholes:" in registry
    assert "node_0001 | weight=1.44" in registry
    assert "primary:node_0001 | H=7.90" in registry
    assert "[PAIR COMPARISON] ranked by bilateral bursts, coherence, flux" in comparative
    assert "1. primary-secondary | aperture=0.280 | damping=0.820 | coherence=0.730 | bilateral=4 | dominant=shear | clock=5 | mode=Stabilizer | ent=0.740 | ctrl=a0.340/d0.790/p0.210 | w=0.82-1.44 | fb=decaying | gate=off | nudge=off | lph=none:0.00 | hint=observe:0.00" in comparative
    assert "| tx=active->Stabilizer" in comparative


def test_telemetry_panel_records_and_renders_phonon_summary(tmp_path: Path):
    panel = TelemetryPanel(working_dir=tmp_path, history_limit=4, bar_width=6)

    panel.record_pair_scan(
        pair_id="primary-secondary",
        manifold_a_id="primary",
        manifold_b_id="secondary",
        wormhole_nodes=["node_0001", "node_0008"],
        wormhole_aperture=0.28,
        damping=0.82,
        phase_offset=0.15,
        shared_flux=[0.4, 1.8, 0.2],
        phase_coherence=0.69,
        bilateral_burst_count=2,
        max_h_cross_domain=6.4,
        bilateral_node_ids=["node_0001"],
        top_events=[
            {"manifold_id": "primary", "node_id": "node_0001", "h_total": 6.4, "density_contrib": 0.9, "shear_contrib": 3.8, "vorticity_contrib": 0.6},
        ],
        shared_locus_summary={
            "pair_clock": 7,
            "dominant_channel": "shear",
            "cross_domain_giant": "Entanglement Locus",
            "shared_flux_norm": 1.86,
            "phonon_bundles": [{"phonon_id": "phonon_primary-secondary_0007"}],
            "latest_phonon_bundle": {
                "phonon_id": "phonon_primary-secondary_0007",
                "mode": "shear",
                "amplitude": 0.31,
                "confidence": 0.64,
                "decay_rate": 0.18,
                "predicted_next_mode": "active",
                "wormhole_entry_nodes": ["node_0008"],
                "wormhole_exit_nodes": ["node_0003"],
                "coherence_signature": {"status": "stable", "stability_score": 0.74},
            },
        },
        entangler_control={
            "pair_clock": 7,
            "entanglement_strength": 0.71,
            "dominant_giant_consensus": "Entanglement Locus",
            "coherence_mode": "active",
            "next_coherence_mode": "active",
            "coherence_feedback": {"status": "stable", "delta": 0.02, "error": 0.09, "target": 0.88},
            "wormhole_weight_summary": {"min_weight": 0.90, "max_weight": 1.20, "top_weighted_wormholes": [{"node_id": "node_0008", "weight": 1.20}]},
            "controls_before": {"aperture": 0.28, "damping": 0.82, "phase_offset": 0.15},
            "controls_after": {"aperture": 0.30, "damping": 0.81, "phase_offset": 0.18},
            "clamp_flags": {"aperture": False, "damping": False, "phase_offset": False},
            "reasoning_summary": "stable phonon packet",
        },
        latest_local_phonon_bundle={
            "phonon_id": "phonon_primary-secondary_local_post_injection_primary_0007",
            "source_tier": "local_post_injection",
            "carrier_giant": "The Graph Navigator",
            "mode": "density",
            "amplitude": 0.22,
            "confidence": 0.58,
            "decay_rate": 0.18,
            "source_nodes": ["node_0001", "node_0008"],
            "wormhole_entry_nodes": ["node_0008"],
            "wormhole_exit_nodes": [],
            "coherence_signature": {"status": "local_post_injection", "stability_score": 0.62},
        },
        local_phonon_bundle_count=4,
        phonon_control_hint={
            "status": "armed",
            "recommended_bias": "stabilize",
            "confidence": 0.41,
            "age_ticks": 1,
            "stability_window": 6,
            "suppression_reason": "none",
            "decision_reason": "stabilize_pressure_or_low_stability",
            "source_tier": "local_post_injection",
            "entry_pressure": 1.0,
            "exit_pressure": 0.0,
            "pair_stability": 0.38,
            "local_stability": 0.44,
            "pair_decay": 0.12,
            "amplitude_trend": -0.06,
        },
    )

    snapshots = panel.load_pair_snapshots()
    registry = panel.render_pair_registry(pair_ids=["primary-secondary"], top_n=1)
    comparative = panel.render_pair_comparative(pair_ids=["primary-secondary"])

    assert snapshots[-1]["phonon_bundle_count"] == 1
    assert snapshots[-1]["phonon_id"] == "phonon_primary-secondary_0007"
    assert snapshots[-1]["phonon_mode"] == "shear"
    assert snapshots[-1]["phonon_confidence"] == 0.64
    assert snapshots[-1]["phonon_entry_count"] == 1
    assert snapshots[-1]["phonon_exit_count"] == 1
    assert snapshots[-1]["phonon_status"] == "stable"
    assert snapshots[-1]["local_phonon_bundle_count"] == 4
    assert snapshots[-1]["local_phonon_tier"] == "local_post_injection"
    assert snapshots[-1]["local_phonon_mode"] == "density"
    assert snapshots[-1]["phonon_hint_status"] == "armed"
    assert snapshots[-1]["phonon_hint_recommendation"] == "stabilize"
    assert snapshots[-1]["phonon_hint_decision_reason"] == "stabilize_pressure_or_low_stability"
    assert snapshots[-1]["phonon_hint_pair_stability"] == 0.38
    assert snapshots[-1]["entangler_hint_gate_state"] == "off"
    assert snapshots[-1]["entangler_nudge_applied"] is False
    assert "| gate=off | nudge=off | ph=shear:0.64" in registry
    assert "phonon summary: status=stable | amp=0.310 | stable=0.740 | in=1 | out=1 | next=active" in registry
    assert "local phonon: tier=local_post_injection | carrier=The Graph Navigator | mode=density:0.58 | amp=0.220 | in=1 | out=0" in registry
    assert "phonon hint: status=armed | bias=stabilize | conf=0.41 | age=1 | window=6 | why=none | decide=stabilize_pressure_or_low_stability" in registry
    assert "hint gate: state=off | bias=observe | conf=0.00 | rel=0.00 | n=0 | why=disabled" in registry
    assert "nudge: applied=False | reason=none | rel=0.00 | d=a+0.000/d+0.000/p+0.000 | why=disabled" in registry
    assert "| gate=off | nudge=off | lph=density:0.58 | hint=stabilize:0.41" in comparative


def test_orchestrator_emits_telemetry_panel_and_history(tmp_path: Path, capsys):
    manifold_core = BlankManifoldCore(BlankManifoldConfig())
    manifold_core.generate_manifold()
    panel = TelemetryPanel(working_dir=tmp_path, history_limit=3)
    orchestrator = OntologicalOrchestrator(manifold_core, tau_threshold=4.5, telemetry_panel=panel, manifold_id="primary")

    test_node = "node_0042"
    manifold_core.graph.nodes[test_node]["resonance_accumulator"] = 5.0
    manifold_core.graph.nodes[test_node]["state_vector"] = np.array([5.0, 5.0, 5.0])

    bursts = orchestrator.scan_manifold()
    output = capsys.readouterr().out
    history = panel.load_recent_history("primary")

    assert bursts
    assert history
    assert history[-1]["burst_count"] == len(bursts)
    assert history[-1]["dominant_channel"] in {"density", "shear", "vorticity", "ambient"}
    assert "[TELEMETRY PANEL] manifold=primary" in output
    assert "Top contributions:" in output