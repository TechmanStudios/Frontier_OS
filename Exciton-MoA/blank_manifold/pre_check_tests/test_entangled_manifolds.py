# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
import json
from pathlib import Path

import numpy as np
import pytest
from blank_config import BlankManifoldConfig
from entangled_manifolds import (
    EntangledSOLPair,
    EntanglementControls,
    HintGatingPolicy,
    PhononBundle,
    build_controls_from_args,
    build_pair_runtime_parser,
    build_pair_sweep_variants,
    compare_run_checkpoints,
    render_sweep_uncertainty_paper_handoff,
    run_pair_runtime,
    run_pair_runtime_repeated,
    run_pair_runtime_sweep,
)
from hippocampal_replay import HippocampalReplay


def test_entangled_pair_selects_deterministic_wormholes(tmp_path: Path):
    config = BlankManifoldConfig(base_node_count=96, dimensionality=3)
    controls = EntanglementControls(wormhole_count=6, seed=11)

    pair_a = EntangledSOLPair(
        config_a=config, config_b=config, controls=controls, working_dir=tmp_path / "run_a"
    )
    pair_b = EntangledSOLPair(
        config_a=config, config_b=config, controls=controls, working_dir=tmp_path / "run_b"
    )

    assert pair_a.wormhole_nodes == pair_b.wormhole_nodes
    assert len(pair_a.wormhole_nodes) == 6
    assert len(set(pair_a.wormhole_nodes)) == 6
    assert pair_a._build_manifold_checkpoint(pair_a.manifold_a) == pair_b._build_manifold_checkpoint(
        pair_b.manifold_a
    )
    assert pair_a._build_manifold_checkpoint(pair_a.manifold_b) == pair_b._build_manifold_checkpoint(
        pair_b.manifold_b
    )


def test_entangled_pair_records_pair_metrics_and_bounded_flux(tmp_path: Path):
    config = BlankManifoldConfig(base_node_count=96, dimensionality=3)
    controls = EntanglementControls(
        wormhole_count=6, seed=7, aperture=0.22, damping=0.88, phase_offset=0.2, entangler_mode="Stabilizer"
    )
    pair = EntangledSOLPair(config_a=config, config_b=config, controls=controls, working_dir=tmp_path)
    controls_before = (pair.controls.aperture, pair.controls.damping, pair.controls.phase_offset)

    embedding_a = np.linspace(0.2, 1.2, 256)
    embedding_b = np.linspace(0.4, 1.4, 256)
    result = pair.tick(embedding_a=embedding_a, embedding_b=embedding_b)

    pair_snapshots = pair.telemetry_panel.load_pair_snapshots()
    registry = pair.telemetry_panel.render_pair_registry(pair_ids=[pair.pair_id])
    comparative = pair.telemetry_panel.render_pair_comparative(pair_ids=[pair.pair_id])

    assert result["pair_metrics"]["pair_id"] == pair.pair_id
    assert result["pair_metrics"]["shared_locus"]["pair_id"] == pair.pair_id
    assert result["pair_metrics"]["shared_locus"]["pair_clock"] >= 1
    assert result["pair_metrics"]["shared_locus"]["latest_phonon_control_hint"]["status"] == "suppressed"
    assert result["pair_metrics"]["entangler_control"]["controller"] == "Entangler Giant"
    assert result["pair_metrics"]["entangler_control"]["control_mode"] == "active"
    assert result["pair_metrics"]["entangler_control"]["coherence_mode"] == "Stabilizer"
    assert result["pair_metrics"]["entangler_control"]["hint_gate"]["enabled"] is False
    assert result["pair_metrics"]["entangler_control"]["hint_gate"]["rejection_reason"] == "disabled"
    assert result["pair_metrics"]["entangler_control"]["coherence_feedback"]["status"] in {
        "stable",
        "improving",
        "decaying",
    }
    assert result["pair_metrics"]["wormhole_weight_map"]
    assert set(result["pair_metrics"]["wormhole_weight_map"]) == set(pair.wormhole_nodes)
    assert result["pair_metrics"]["local_phonon_bundle_count"] == 4
    assert result["pair_metrics"]["latest_local_phonon_bundle"]["source_tier"].startswith(
        "local_post_injection"
    )
    assert result["pair_metrics"]["phonon_control_hint"]["status"] == "suppressed"
    assert result["pair_metrics"]["phonon_control_hint"]["suppression_reason"] == "insufficient_history"
    assert result["pair_metrics"]["phonon_control_hint"]["decision_reason"] == "insufficient_history"
    assert pair_snapshots
    assert pair_snapshots[-1]["pair_id"] == pair.pair_id
    assert pair_snapshots[-1]["shared_pair_clock"] >= 1
    assert pair_snapshots[-1]["entangler_pair_clock"] >= 1
    assert pair_snapshots[-1]["entangler_mode"] == "Stabilizer"
    assert pair_snapshots[-1]["entangler_hint_gate_state"] == "off"
    assert pair_snapshots[-1]["entangler_coherence_status"] in {"stable", "improving", "decaying"}
    assert pair_snapshots[-1]["phonon_hint_status"] == "suppressed"
    assert np.linalg.norm(pair.shared_flux) < 10.0
    assert (pair.controls.aperture, pair.controls.damping, pair.controls.phase_offset) != controls_before
    assert len(pair.local_phonon_bundles) == 4
    assert len(pair.phonon_control_hints) == 1
    assert {bundle.source_tier for bundle in pair.local_phonon_bundles} == {
        "local_post_giant",
        "local_post_injection",
    }
    assert "local phonon:" in registry
    assert "phonon hint:" in registry
    assert "hint gate: state=off" in registry
    assert "[PAIR REGISTRY] active_pairs=1" in registry
    assert pair.pair_id in registry
    assert "[PAIR COMPARISON] ranked by bilateral bursts, coherence, flux" in comparative
    assert "| gate=off |" in comparative


def test_entangled_pair_uses_previous_tick_candidate_hint_after_pair_state_refresh(tmp_path: Path):
    config = BlankManifoldConfig(base_node_count=96, dimensionality=3)
    controls = EntanglementControls(wormhole_count=6, seed=7)
    pair = EntangledSOLPair(config_a=config, config_b=config, controls=controls, working_dir=tmp_path)
    pair.shared_mediator.publish_pair_state(
        shared_flux=[0.5, 1.4, 0.3],
        phase_coherence=0.55,
        wormhole_nodes=pair.wormhole_nodes,
        bilateral_node_ids=[pair.wormhole_nodes[0]],
        local_consensus={},
    )
    pair.shared_mediator.publish_phonon_control_hint(
        {
            "status": "armed",
            "recommended_bias": "stabilize",
            "confidence": 0.62,
            "age_ticks": 1,
            "stability_window": 6,
            "suppression_reason": "none",
            "source_tier": "local_post_injection",
            "entry_pressure": 1.0,
            "exit_pressure": 0.0,
        }
    )

    captured = {}

    def fake_control(controls, shared_locus_summary, shared_flux_history=None, pair_metrics=None):
        captured["candidate_hint"] = dict((pair_metrics or {}).get("candidate_phonon_control_hint", {}))
        current_mode = controls.entangler_mode
        return {
            "controller": "Entangler Giant",
            "control_mode": "active",
            "coherence_mode": current_mode,
            "next_coherence_mode": current_mode,
            "pair_clock": int(shared_locus_summary.get("pair_clock", 0)),
            "entanglement_strength": 0.42,
            "dominant_giant_consensus": "Entanglement Locus",
            "coherence_feedback": {
                "mode": current_mode,
                "status": "stable",
                "target": 0.88,
                "current": float((pair_metrics or {}).get("phase_coherence", 0.0)),
                "previous": float((pair_metrics or {}).get("phase_coherence", 0.0)),
                "delta": 0.0,
                "trend": 0.0,
                "error": 0.12,
                "history_count": 1,
                "last_control_delta": {"aperture": 0.0, "damping": 0.0, "phase_offset": 0.0},
                "aperture_correction": 0.0,
                "damping_correction": 0.0,
                "phase_correction": 0.0,
            },
            "wormhole_weight_map": {node_id: 1.0 for node_id in pair.wormhole_nodes},
            "wormhole_weight_summary": {"min_weight": 1.0, "max_weight": 1.0, "top_weighted_wormholes": []},
            "controls_before": {
                "aperture": controls.aperture,
                "damping": controls.damping,
                "phase_offset": controls.phase_offset,
            },
            "targets": {
                "aperture": controls.aperture,
                "damping": controls.damping,
                "phase_offset": controls.phase_offset,
            },
            "controls_after": {
                "aperture": controls.aperture,
                "damping": controls.damping,
                "phase_offset": controls.phase_offset,
            },
            "control_delta": {"aperture": 0.0, "damping": 0.0, "phase_offset": 0.0},
            "clamp_flags": {"aperture": False, "damping": False, "phase_offset": False},
            "features": {"coherence_mode": current_mode},
            "hint_gate": {
                "enabled": False,
                "passed": False,
                "applied": False,
                "rejection_reason": "disabled",
            },
            "wormhole_health": {},
            "reasoning_summary": "test candidate hint carry-forward",
        }

    pair.entangler.control = fake_control
    pair.tick(embedding_a=np.linspace(0.2, 1.2, 256), embedding_b=np.linspace(0.4, 1.4, 256))

    assert captured["candidate_hint"]["status"] == "armed"
    assert captured["candidate_hint"]["recommended_bias"] == "stabilize"


def test_entangled_pair_archives_pair_context_for_replay(tmp_path: Path):
    config = BlankManifoldConfig(base_node_count=96, dimensionality=3)
    controls = EntanglementControls(wormhole_count=6, seed=5, aperture=0.2, damping=0.86, phase_offset=0.18)
    pair = EntangledSOLPair(config_a=config, config_b=config, controls=controls, working_dir=tmp_path)

    wormhole_node = pair.wormhole_nodes[0]
    pair.manifold_a.graph.nodes[wormhole_node]["resonance_accumulator"] = 5.0
    pair.manifold_b.graph.nodes[wormhole_node]["resonance_accumulator"] = 4.8
    pair.manifold_a.graph.nodes[wormhole_node]["state_vector"] = np.array([5.0, 5.0, 5.0])
    pair.manifold_b.graph.nodes[wormhole_node]["state_vector"] = np.array([4.5, 4.5, 4.5])

    pair.tick(embedding_a=np.linspace(0.2, 1.2, 256), embedding_b=np.linspace(0.4, 1.4, 256))
    replay = HippocampalReplay(working_dir=tmp_path)
    output = replay.replay(pair_id=pair.pair_id, top_n=6)
    shared_locus_path = tmp_path / f"shared_entanglement_locus_{pair.pair_id}.json"

    assert "Pair id: primary-secondary" in output
    assert "Cross-domain giants:" in output
    assert "Entanglement Locus" in output
    assert "Entangler control summary:" in output
    assert "Coherence trend over" in output
    assert shared_locus_path.exists()
    assert pair.last_pair_metrics["shared_locus"]["cross_domain_giant"] == "Entanglement Locus"
    assert (
        pair.last_pair_metrics["shared_locus"]["latest_phonon_control_hint"]
        == pair.last_pair_metrics["phonon_control_hint"]
    )
    assert pair.last_pair_metrics["entangler_control"]["controller"] == "Entangler Giant"
    assert pair.last_pair_metrics["entangler_control"]["hint_gate"]["enabled"] is False
    assert "Wormhole weight summary:" in output


def test_entangled_pair_promotes_negative_amplitude_collapse_to_stabilize(tmp_path: Path):
    config = BlankManifoldConfig(base_node_count=64, dimensionality=3)
    controls = EntanglementControls(
        wormhole_count=4,
        seed=17,
        hint_gate_policy=HintGatingPolicy(enable_negative_collapse_stabilize=True),
    )
    pair = EntangledSOLPair(config_a=config, config_b=config, controls=controls, working_dir=tmp_path)

    pair.phonon_bundles = [
        PhononBundle(
            phonon_id=f"pair-{index}",
            pair_clock=index,
            source_tier="pair",
            carrier_giant="Entanglement Locus",
            source_nodes=("n1",),
            mode="active",
            state_vector=(0.1, 0.2, 0.3),
            amplitude=0.4,
            phase_coherence=0.8,
            decay_rate=0.01,
            confidence=0.9,
            entropy=0.1,
            predicted_next_mode="active",
            wormhole_entry_nodes=("n1",),
            wormhole_exit_nodes=(),
            weight_delta_map={},
            coherence_signature={"stability_score": 0.88},
        )
        for index in (1, 2, 3, 4)
    ]
    pair.local_phonon_bundles = [
        PhononBundle(
            phonon_id=f"local-{index}",
            pair_clock=index,
            source_tier="local_post_injection",
            carrier_giant="Entanglement Locus",
            source_nodes=("n1",),
            mode="active",
            state_vector=(0.2, 0.1, 0.0),
            amplitude=amplitude,
            phase_coherence=0.75,
            decay_rate=0.01,
            confidence=0.9,
            entropy=0.1,
            predicted_next_mode="active",
            wormhole_entry_nodes=("n1",),
            wormhole_exit_nodes=(),
            weight_delta_map={},
            coherence_signature={"stability_score": local_stability},
        )
        for index, amplitude, local_stability in (
            (1, 0.85, 0.46),
            (2, 0.72, 0.44),
            (3, 0.56, 0.42),
            (4, 0.38, 0.41),
        )
    ]

    hint = pair._derive_phonon_control_hint(current_pair_tick=5)

    assert hint["status"] == "armed"
    assert hint["recommended_bias"] == "stabilize"
    assert hint["decision_reason"] == "stabilize_negative_amplitude_collapse"
    assert hint["pair_decay"] < 0.16
    assert hint["pair_stability"] > 0.70
    assert hint["local_stability"] < 0.50
    assert hint["amplitude_trend"] < -0.35


def test_entangled_flux_injection_respects_per_node_weighting(tmp_path: Path):
    config = BlankManifoldConfig(base_node_count=96, dimensionality=3)
    controls = EntanglementControls(wormhole_count=6, seed=9, aperture=0.24, damping=0.84, phase_offset=0.15)
    pair = EntangledSOLPair(config_a=config, config_b=config, controls=controls, working_dir=tmp_path)

    emphasized = pair.wormhole_nodes[0]
    reduced = pair.wormhole_nodes[1]
    pair.wormhole_weight_map = {node_id: 1.0 for node_id in pair.wormhole_nodes}
    pair.wormhole_weight_map[emphasized] = 1.5
    pair.wormhole_weight_map[reduced] = 0.8

    pair.excitons_a.inject_entangled_flux(
        pair.wormhole_nodes,
        np.array([1.0, 0.5, 0.25]),
        injection_scale=0.05,
        per_node_scale=pair.wormhole_weight_map,
    )

    emphasized_resonance = pair.manifold_a.graph.nodes[emphasized]["resonance_accumulator"]
    reduced_resonance = pair.manifold_a.graph.nodes[reduced]["resonance_accumulator"]

    assert emphasized_resonance >= reduced_resonance
    assert max(pair.wormhole_weight_map.values()) <= 1.5
    assert min(pair.wormhole_weight_map.values()) >= 0.8


def test_entangled_pair_persists_coherence_feedback_summary(tmp_path: Path):
    config = BlankManifoldConfig(base_node_count=96, dimensionality=3)
    controls = EntanglementControls(
        wormhole_count=6, seed=3, aperture=0.24, damping=0.84, phase_offset=0.19, entangler_mode="Stabilizer"
    )
    pair = EntangledSOLPair(config_a=config, config_b=config, controls=controls, working_dir=tmp_path)
    pair.coherence_history = [0.83, 0.72, 0.61]
    pair.control_delta_history = [{"aperture": 0.05, "damping": -0.02, "phase_offset": 0.09}]

    pair.tick(embedding_a=np.linspace(0.2, 1.2, 256), embedding_b=np.linspace(0.4, 1.4, 256))
    feedback = pair.last_pair_metrics["entangler_control"]["coherence_feedback"]
    restored = json.loads(
        (tmp_path / f"shared_entanglement_locus_{pair.pair_id}.json").read_text(encoding="utf-8")
    )

    assert feedback["history_count"] == 3
    assert feedback["mode"] == "Stabilizer"
    assert restored["latest_summary"]["entangler_control"]["coherence_feedback"]["history_count"] == 3
    assert restored["latest_summary"]["entangler_control"]["coherence_mode"] == "Stabilizer"
    assert pair.last_pair_metrics["entangler_control"]["coherence_feedback"]["target"] == 0.88


def test_entangled_pair_builds_and_serializes_phonon_bundle(tmp_path: Path):
    config = BlankManifoldConfig(base_node_count=96, dimensionality=3)
    controls = EntanglementControls(wormhole_count=6, seed=17, damping=0.82)
    pair = EntangledSOLPair(config_a=config, config_b=config, controls=controls, working_dir=tmp_path)
    previous_weight_map = {
        pair.wormhole_nodes[0]: 1.40,
        pair.wormhole_nodes[1]: 1.32,
        pair.wormhole_nodes[2]: 1.18,
        pair.wormhole_nodes[3]: 1.06,
        pair.wormhole_nodes[4]: 0.98,
        pair.wormhole_nodes[5]: 0.92,
    }
    current_weight_map = {
        pair.wormhole_nodes[0]: 1.44,
        pair.wormhole_nodes[1]: 1.10,
        pair.wormhole_nodes[2]: 1.16,
        pair.wormhole_nodes[3]: 1.30,
        pair.wormhole_nodes[4]: 1.24,
        pair.wormhole_nodes[5]: 0.90,
    }
    current_weight_delta_map = pair._compute_weight_delta_map(previous_weight_map, current_weight_map)
    pair.wormhole_weight_delta_history = [
        {
            pair.wormhole_nodes[0]: 0.02,
            pair.wormhole_nodes[1]: -0.15,
            pair.wormhole_nodes[2]: 0.01,
            pair.wormhole_nodes[3]: 0.18,
            pair.wormhole_nodes[4]: 0.22,
            pair.wormhole_nodes[5]: -0.02,
        },
        {
            pair.wormhole_nodes[0]: 0.04,
            pair.wormhole_nodes[1]: -0.30,
            pair.wormhole_nodes[2]: -0.01,
            pair.wormhole_nodes[3]: 0.20,
            pair.wormhole_nodes[4]: 0.26,
            pair.wormhole_nodes[5]: -0.01,
        },
    ]
    pair.control_delta_history = [
        {"aperture": 0.02, "damping": -0.01, "phase_offset": 0.03},
        {"aperture": 0.01, "damping": 0.00, "phase_offset": -0.02},
    ]

    pair_metrics = {
        "pair_id": pair.pair_id,
        "phase_coherence": 0.64,
        "bilateral_burst_count": 2,
        "bilateral_node_ids": [pair.wormhole_nodes[0], pair.wormhole_nodes[3]],
    }
    shared_locus = {
        "pair_clock": 7,
        "phase_coherence": 0.64,
        "shared_flux_vector": [1.0, 2.0, 2.0],
        "dominant_channel": "shear",
        "cross_domain_giant": "Entanglement Locus",
        "resolved_channels": {
            "entanglement_locus": {
                "consensus_entropy": 0.23,
            }
        },
    }
    entangler_state = {
        "pair_clock": 7,
        "dominant_giant_consensus": "Entanglement Locus",
        "next_coherence_mode": "active",
        "coherence_feedback": {
            "status": "stable",
            "trend": 0.05,
            "delta": 0.03,
        },
    }

    bundle = pair._build_phonon_bundle(
        pair_metrics=pair_metrics,
        shared_locus=shared_locus,
        entangler_state=entangler_state,
        previous_weight_map=previous_weight_map,
        current_weight_map=current_weight_map,
        current_weight_delta_map=current_weight_delta_map,
    )
    serialized = pair._serialize_phonon_bundle(bundle)

    assert bundle.phonon_id == f"phonon_{pair.pair_id}_0007"
    assert bundle.mode == "shear"
    assert bundle.source_nodes == (pair.wormhole_nodes[0], pair.wormhole_nodes[3])
    assert bundle.state_vector == (1.0, 2.0, 2.0)
    assert bundle.amplitude == 3.0
    assert bundle.decay_rate == pytest.approx(0.18)
    assert bundle.confidence == pytest.approx(0.5326666666666667)
    assert bundle.entropy == 0.23
    assert bundle.predicted_next_mode == "active"
    assert bundle.wormhole_entry_nodes == (pair.wormhole_nodes[4],)
    assert bundle.wormhole_exit_nodes == (pair.wormhole_nodes[1],)
    assert bundle.weight_delta_map[pair.wormhole_nodes[1]] == pytest.approx(-0.22)
    assert bundle.weight_delta_map[pair.wormhole_nodes[4]] == pytest.approx(0.26)
    assert bundle.coherence_signature["status"] == "stable"
    assert 0.0 <= bundle.coherence_signature["stability_score"] <= 1.0
    assert serialized["phonon_id"] == bundle.phonon_id
    assert serialized["source_nodes"] == [pair.wormhole_nodes[0], pair.wormhole_nodes[3]]
    assert serialized["wormhole_entry_nodes"] == [pair.wormhole_nodes[4]]
    assert serialized["wormhole_exit_nodes"] == [pair.wormhole_nodes[1]]
    assert serialized["weight_delta_map"][pair.wormhole_nodes[1]] == pytest.approx(-0.22)


def test_entangled_pair_switch_policy_requires_history_streak_and_dwell(tmp_path: Path):
    config = BlankManifoldConfig(base_node_count=64, dimensionality=3)
    controls = EntanglementControls(
        wormhole_count=4,
        seed=13,
        entangler_mode="active",
        min_mode_switch_samples=3,
        stabilizer_enter_decay_streak=2,
        stabilizer_exit_improving_streak=3,
        stabilizer_min_dwell_ticks=2,
    )
    pair = EntangledSOLPair(config_a=config, config_b=config, controls=controls, working_dir=tmp_path)

    first = {
        "coherence_mode": "active",
        "controls_after": {
            "aperture": pair.controls.aperture,
            "damping": pair.controls.damping,
            "phase_offset": pair.controls.phase_offset,
        },
        "coherence_feedback": {"status": "decaying", "history_count": 1},
    }
    pair._apply_entangler_control(first)
    assert pair.controls.entangler_mode == "active"
    assert first["mode_transition"]["changed"] is False
    assert first["mode_transition"]["reason"] == "insufficient_history_2"

    second = {
        "coherence_mode": "active",
        "controls_after": {
            "aperture": pair.controls.aperture,
            "damping": pair.controls.damping,
            "phase_offset": pair.controls.phase_offset,
        },
        "coherence_feedback": {"status": "decaying", "history_count": 2},
    }
    pair._apply_entangler_control(second)
    assert pair.controls.entangler_mode == "Stabilizer"
    assert second["mode_transition"]["changed"] is True
    assert second["mode_transition"]["previous_mode"] == "active"
    assert second["mode_transition"]["next_mode"] == "Stabilizer"
    assert second["mode_transition"]["reason"] == "decaying_x2_after_history3"

    third = {
        "coherence_mode": "Stabilizer",
        "controls_after": {
            "aperture": pair.controls.aperture,
            "damping": pair.controls.damping,
            "phase_offset": pair.controls.phase_offset,
        },
        "coherence_feedback": {"status": "improving", "history_count": 3},
    }
    pair._apply_entangler_control(third)
    assert pair.controls.entangler_mode == "Stabilizer"
    assert third["mode_transition"]["reason"] == "stabilizer_dwell_1of2"

    fourth = {
        "coherence_mode": "Stabilizer",
        "controls_after": {
            "aperture": pair.controls.aperture,
            "damping": pair.controls.damping,
            "phase_offset": pair.controls.phase_offset,
        },
        "coherence_feedback": {"status": "improving", "history_count": 4},
    }
    pair._apply_entangler_control(fourth)
    assert pair.controls.entangler_mode == "Stabilizer"
    assert fourth["mode_transition"]["changed"] is False
    assert fourth["mode_transition"]["improving_streak"] == 2

    fifth = {
        "coherence_mode": "Stabilizer",
        "controls_after": {
            "aperture": pair.controls.aperture,
            "damping": pair.controls.damping,
            "phase_offset": pair.controls.phase_offset,
        },
        "coherence_feedback": {"status": "improving", "history_count": 5},
    }
    pair._apply_entangler_control(fifth)
    assert pair.controls.entangler_mode == "active"
    assert fifth["mode_transition"]["changed"] is True
    assert fifth["mode_transition"]["previous_mode"] == "Stabilizer"
    assert fifth["mode_transition"]["next_mode"] == "active"
    assert fifth["mode_transition"]["reason"] == "improving_x3_after_dwell2"


def test_entangled_pair_records_mode_transitions_in_runtime_and_replay(tmp_path: Path):
    config = BlankManifoldConfig(base_node_count=64, dimensionality=3)
    controls = EntanglementControls(wormhole_count=4, seed=19)
    pair = EntangledSOLPair(config_a=config, config_b=config, controls=controls, working_dir=tmp_path)
    status_sequence = [
        {"status": "decaying", "history_count": 1},
        {"status": "decaying", "history_count": 2},
        {"status": "improving", "history_count": 3},
        {"status": "improving", "history_count": 4},
        {"status": "improving", "history_count": 5},
    ]

    def fake_control(controls, shared_locus_summary, shared_flux_history=None, pair_metrics=None):
        feedback = status_sequence.pop(0)
        current_mode = controls.entangler_mode
        return {
            "controller": "Entangler Giant",
            "control_mode": "active",
            "coherence_mode": current_mode,
            "pair_clock": int(shared_locus_summary.get("pair_clock", 0)),
            "entanglement_strength": 0.42,
            "dominant_giant_consensus": "Entanglement Locus",
            "coherence_feedback": {
                "mode": current_mode,
                "status": feedback["status"],
                "target": 0.88,
                "current": float(pair_metrics.get("phase_coherence", 0.0)),
                "previous": float(pair_metrics.get("phase_coherence", 0.0)),
                "delta": 0.04 if feedback["status"] == "improving" else -0.04,
                "trend": 0.04 if feedback["status"] == "improving" else -0.04,
                "error": 0.12,
                "history_count": feedback["history_count"],
                "last_control_delta": {"aperture": 0.0, "damping": 0.0, "phase_offset": 0.0},
                "aperture_correction": 0.0,
                "damping_correction": 0.02,
                "phase_correction": 0.0,
            },
            "wormhole_weight_map": {node_id: 1.0 for node_id in pair.wormhole_nodes},
            "wormhole_weight_summary": {"min_weight": 1.0, "max_weight": 1.0, "top_weighted_wormholes": []},
            "controls_before": {
                "aperture": controls.aperture,
                "damping": controls.damping,
                "phase_offset": controls.phase_offset,
            },
            "targets": {
                "aperture": controls.aperture,
                "damping": controls.damping,
                "phase_offset": controls.phase_offset,
            },
            "controls_after": {
                "aperture": controls.aperture,
                "damping": controls.damping,
                "phase_offset": controls.phase_offset,
            },
            "control_delta": {"aperture": 0.0, "damping": 0.0, "phase_offset": 0.0},
            "clamp_flags": {"aperture": False, "damping": False, "phase_offset": False},
            "features": {"coherence_mode": current_mode},
            "wormhole_health": {},
            "reasoning_summary": f"status={feedback['status']}, mode={current_mode}",
        }

    pair.entangler.control = fake_control

    for _ in range(5):
        pair.tick(embedding_a=np.linspace(0.2, 1.2, 256), embedding_b=np.linspace(0.4, 1.4, 256))

    history_records = [
        json.loads(line)
        for line in (tmp_path / "adaptive_tau_history.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    transition_records = [record for record in history_records if record.get("entangler_mode_changed")]
    replay = HippocampalReplay(working_dir=tmp_path)
    output = replay.replay(pair_id=pair.pair_id, top_n=4)
    restored = json.loads(
        (tmp_path / f"shared_entanglement_locus_{pair.pair_id}.json").read_text(encoding="utf-8")
    )

    assert len(transition_records) == 2
    assert transition_records[0]["entangler_previous_mode"] == "active"
    assert transition_records[0]["entangler_next_mode"] == "Stabilizer"
    assert transition_records[0]["entangler_transition_reason"] == "decaying_x2_after_history3"
    assert transition_records[1]["entangler_previous_mode"] == "Stabilizer"
    assert transition_records[1]["entangler_next_mode"] == "active"
    assert transition_records[1]["entangler_transition_reason"] == "improving_x3_after_dwell2"
    assert pair.last_pair_metrics["entangler_mode"] == "active"
    assert pair.last_pair_metrics["entangler_mode_used"] == "Stabilizer"
    assert pair.last_pair_metrics["mode_transition"]["changed"] is True
    assert restored["latest_summary"]["entangler_control"]["mode_transition"]["changed"] is True
    assert "Mode switching over 5 ticks:" in output
    assert "active->Stabilizer=1" in output
    assert "Stabilizer->active=1" in output
    assert "Switch reasons: decaying_x2_after_history3=1, improving_x3_after_dwell2=1" in output


def test_pair_runtime_parser_maps_user_facing_threshold_overrides():
    parser = build_pair_runtime_parser()
    args = parser.parse_args(
        [
            "--cycles",
            "7",
            "--seed",
            "29",
            "--entangler-mode",
            "Stabilizer",
            "--min-history",
            "5",
            "--enter-decay-streak",
            "4",
            "--exit-improving-streak",
            "6",
            "--min-dwell",
            "3",
            "--aperture",
            "0.31",
            "--damping",
            "0.79",
            "--phase-offset",
            "0.22",
            "--max-history",
            "24",
            "--enable-hint-gate",
            "--hint-confidence-threshold",
            "0.61",
            "--hint-reliability-threshold",
            "0.72",
            "--hint-max-age-ticks",
            "4",
            "--hint-min-samples",
            "5",
            "--hint-forward-window",
            "3",
            "--enable-bounded-nudges",
            "--nudge-aperture-max-step",
            "0.02",
            "--nudge-damping-max-step",
            "0.015",
            "--nudge-phase-max-step",
            "0.04",
            "--nudge-reliability-floor",
            "0.81",
            "--no-nudge-requires-stability",
            "--nudge-stability-window",
            "2",
        ]
    )
    controls = build_controls_from_args(args)

    assert args.cycles == 7
    assert controls.seed == 29
    assert controls.entangler_mode == "Stabilizer"
    assert controls.min_mode_switch_samples == 5
    assert controls.stabilizer_enter_decay_streak == 4
    assert controls.stabilizer_exit_improving_streak == 6
    assert controls.stabilizer_min_dwell_ticks == 3
    assert controls.aperture == 0.31
    assert controls.damping == 0.79
    assert controls.phase_offset == 0.22
    assert controls.max_history == 24
    assert controls.hint_gate_policy.enabled is True
    assert controls.hint_gate_policy.confidence_threshold == 0.61
    assert controls.hint_gate_policy.reliability_threshold == 0.72
    assert controls.hint_gate_policy.max_age_ticks == 4
    assert controls.hint_gate_policy.min_samples == 5
    assert controls.hint_gate_policy.forward_window == 3
    assert controls.hint_gate_policy.enable_bounded_nudges is True
    assert controls.hint_gate_policy.nudge_aperture_max_step == 0.02
    assert controls.hint_gate_policy.nudge_damping_max_step == 0.015
    assert controls.hint_gate_policy.nudge_phase_max_step == 0.04
    assert controls.hint_gate_policy.nudge_reliability_floor == 0.81
    assert controls.hint_gate_policy.nudge_requires_stability is False
    assert controls.hint_gate_policy.nudge_stability_window == 2


def test_pair_runtime_parser_applies_best_pocket_preset():
    parser = build_pair_runtime_parser()
    args = parser.parse_args(["--runtime-preset", "best-pocket"])

    assert args.runtime_preset == "best-pocket"
    assert args.cycles == 12
    assert args.seed == 149
    assert args.embedding_a_loc == 0.50
    assert args.embedding_b_loc == 0.57
    assert args.embedding_scale == 0.08
    assert args.embedding_drift == 0.06


def test_pair_runtime_parser_allows_explicit_overrides_after_preset():
    parser = build_pair_runtime_parser()
    args = parser.parse_args(
        [
            "--runtime-preset",
            "best-pocket",
            "--seed",
            "83",
            "--embedding-b-loc",
            "0.58",
            "--cycles",
            "18",
        ]
    )

    assert args.runtime_preset == "best-pocket"
    assert args.seed == 83
    assert args.embedding_b_loc == 0.58
    assert args.cycles == 18
    assert args.embedding_a_loc == 0.50
    assert args.embedding_scale == 0.08
    assert args.embedding_drift == 0.06


def test_pair_runtime_parser_accepts_reproducibility_flags(tmp_path: Path):
    parser = build_pair_runtime_parser()
    args = parser.parse_args(
        [
            "--working-dir",
            str(tmp_path / "repro_run"),
            "--clean-run-reset",
            "--repeat-run-count",
            "2",
        ]
    )

    assert args.clean_run_reset is True
    assert args.repeat_run_count == 2
    assert args.working_dir == str(tmp_path / "repro_run")


def test_entangled_pair_live_cycles_persist_runtime_outputs(tmp_path: Path):
    config = BlankManifoldConfig(base_node_count=64, dimensionality=3)
    controls = EntanglementControls(wormhole_count=4, seed=31)
    pair = EntangledSOLPair(config_a=config, config_b=config, controls=controls, working_dir=tmp_path)

    results = pair.run_live_cycles(
        cycle_count=4,
        embedding_a_loc=0.48,
        embedding_b_loc=0.57,
        embedding_scale=0.08,
        embedding_drift=0.03,
    )
    summaries = pair.render_runtime_outputs(top_n=4)
    output_paths = pair.persist_runtime_outputs(top_n=4)
    replay = HippocampalReplay(working_dir=tmp_path)
    output = replay.replay(pair_id=pair.pair_id, top_n=4)

    assert len(results) == 4
    assert (tmp_path / "adaptive_tau_history.jsonl").exists()
    assert output_paths["replay"].exists()
    assert output_paths["registry"].exists()
    assert output_paths["comparative"].exists()
    assert "Entangler control summary:" in summaries["replay"]
    assert "Mode switching over 4 ticks:" in summaries["replay"]
    assert "[PAIR REGISTRY] active_pairs=1" in summaries["registry"]
    assert "[PAIR COMPARISON] ranked by bilateral bursts, coherence, flux" in summaries["comparative"]
    assert "Coherence trend over 4 ticks:" in output


def test_run_pair_runtime_persists_reproducibility_checkpoint(tmp_path: Path):
    controls = EntanglementControls(wormhole_count=4, seed=31)

    result = run_pair_runtime(
        controls=controls,
        working_dir=tmp_path / "runtime",
        cycles=2,
        top_n=3,
        live_embeddings=True,
        persist_summaries=True,
        embedding_a_loc=0.48,
        embedding_b_loc=0.57,
        embedding_scale=0.08,
        embedding_drift=0.03,
        clean_run_reset=True,
    )

    checkpoint_path = result["output_paths"]["checkpoint"]
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))

    assert checkpoint_path.exists()
    assert checkpoint["seed"] == 31
    assert checkpoint["tick_count"] == 2
    assert checkpoint["state_loads"]["primary"]["loaded"] is False
    assert checkpoint["state_loads"]["secondary"]["loaded"] is False
    assert checkpoint["state_loads"]["shared"]["loaded"] is False
    assert checkpoint["scan_fingerprints"]["primary"]["fingerprint"] != "none"
    assert checkpoint["scan_fingerprints"]["secondary"]["fingerprint"] != "none"
    assert len(checkpoint["tick_trace"]) == 2
    assert len(checkpoint["signature_a_history"]) == 2
    assert len(checkpoint["signature_b_history"]) == 2
    assert len(checkpoint["shared_flux_vector_history"]) == 2
    assert len(checkpoint["primary_wormhole_state_fingerprint_history"]) == 2
    assert len(checkpoint["secondary_wormhole_edge_fingerprint_history"]) == 2
    assert checkpoint["tick_trace"][0]["manifolds"]["primary"]["wormhole_state_fingerprint"]
    assert checkpoint["tick_trace"][0]["manifolds"]["secondary"]["wormhole_edge_fingerprint"]
    assert len(checkpoint["phase_coherence_history"]) == 2
    assert len(checkpoint["gate_reason_history"]) == 2


def test_compare_run_checkpoints_reports_first_divergence():
    left = {
        "seed": 83,
        "wormhole_nodes": ["n1", "n2"],
        "wormhole_fingerprint": "abc",
        "manifolds": {"primary": {"fingerprint": "m1"}},
        "state_loads": {"primary": {"loaded": False}},
        "scan_fingerprints": {"primary": {"fingerprint": "scan-a"}},
        "primary_wormhole_state_fingerprint_history": ["wa1", "wa2", "wa3"],
        "secondary_wormhole_state_fingerprint_history": ["wb1", "wb2", "wb3"],
        "primary_wormhole_edge_fingerprint_history": ["ea1", "ea2", "ea3"],
        "secondary_wormhole_edge_fingerprint_history": ["eb1", "eb2", "eb3"],
        "signature_a_history": [[0.1, 0.2, 0.3], [0.2, 0.3, 0.4], [0.3, 0.4, 0.5]],
        "signature_b_history": [[0.4, 0.5, 0.6], [0.5, 0.6, 0.7], [0.6, 0.7, 0.8]],
        "shared_flux_vector_history": [[0.01, 0.02, 0.03], [0.04, 0.05, 0.06], [0.07, 0.08, 0.09]],
        "control_delta_history": [{"aperture": 0.0}, {"aperture": 0.01}, {"aperture": 0.02}],
        "coherence_feedback_history": [{"status": "stable"}, {"status": "improving"}, {"status": "stable"}],
        "shared_pair_clock_history": [1, 2, 3],
        "phase_coherence_history": [0.1, 0.2, 0.3],
        "mode_history": ["active", "active", "Stabilizer"],
        "hint_status_history": ["suppressed", "armed", "armed"],
        "hint_bias_history": ["observe", "stabilize", "stabilize"],
        "gate_state_history": ["block", "pass", "pass"],
        "gate_reason_history": ["no_hint", "none", "none"],
        "gate_status_history": ["missing", "armed", "armed"],
        "nudge_rejection_history": ["disabled", "observe_only", "applied"],
        "first_tick_phase_coherence": 0.1,
        "final_mode": "Stabilizer",
    }
    right = {
        **left,
        "phase_coherence_history": [0.1, 0.25, 0.3],
    }

    comparison = compare_run_checkpoints(left, right)

    assert comparison["matches"] is False
    assert comparison["sequence_matches"]["phase_coherence_history"] is False
    assert comparison["first_divergence"]["field"] == "phase_coherence_history"
    assert comparison["first_divergence"]["tick_index"] == 2


def test_compare_run_checkpoints_reports_signature_level_divergence_first():
    left = {
        "seed": 83,
        "wormhole_nodes": ["n1", "n2"],
        "wormhole_fingerprint": "abc",
        "manifolds": {"primary": {"fingerprint": "m1"}},
        "state_loads": {"primary": {"loaded": False}},
        "scan_fingerprints": {"primary": {"fingerprint": "scan-a"}},
        "primary_wormhole_state_fingerprint_history": ["wa1", "wa2"],
        "secondary_wormhole_state_fingerprint_history": ["wb1", "wb2"],
        "primary_wormhole_edge_fingerprint_history": ["ea1", "ea2"],
        "secondary_wormhole_edge_fingerprint_history": ["eb1", "eb2"],
        "signature_a_history": [[0.1, 0.2, 0.3], [0.2, 0.3, 0.4]],
        "signature_b_history": [[0.4, 0.5, 0.6], [0.5, 0.6, 0.7]],
        "shared_flux_vector_history": [[0.01, 0.02, 0.03], [0.04, 0.05, 0.06]],
        "control_delta_history": [{"aperture": 0.0}, {"aperture": 0.01}],
        "coherence_feedback_history": [{"status": "stable"}, {"status": "stable"}],
        "shared_pair_clock_history": [1, 2],
        "phase_coherence_history": [0.1, 0.2],
        "mode_history": ["active", "active"],
        "hint_status_history": ["suppressed", "armed"],
        "hint_bias_history": ["observe", "stabilize"],
        "gate_state_history": ["block", "pass"],
        "gate_reason_history": ["no_hint", "none"],
        "gate_status_history": ["missing", "armed"],
        "nudge_rejection_history": ["disabled", "observe_only"],
        "first_tick_phase_coherence": 0.1,
        "final_mode": "active",
    }
    right = {
        **left,
        "signature_a_history": [[0.1, 0.2, 0.3], [0.21, 0.3, 0.4]],
        "phase_coherence_history": [0.1, 0.25],
    }

    comparison = compare_run_checkpoints(left, right)

    assert comparison["matches"] is False
    assert comparison["sequence_matches"]["signature_a_history"] is False
    assert comparison["first_divergence"]["field"] == "signature_a_history"
    assert comparison["first_divergence"]["tick_index"] == 2


def test_run_pair_runtime_repeated_clones_controls_per_attempt(tmp_path: Path):
    controls = EntanglementControls(seed=83)

    result = run_pair_runtime_repeated(
        controls=controls,
        working_dir=tmp_path / "repeated",
        cycles=2,
        top_n=2,
        live_embeddings=False,
        persist_summaries=False,
        embedding_a_loc=0.5,
        embedding_b_loc=0.57,
        embedding_scale=0.08,
        embedding_drift=0.06,
        repeat_run_count=2,
        clean_run_reset=True,
    )

    assert controls.aperture == 0.25
    assert controls.damping == 0.85
    assert controls.phase_offset == 0.15
    assert controls.entangler_mode == "active"
    assert result["comparisons"][0]["matches"] is True


def test_compare_run_checkpoints_ignores_state_load_path_only_differences():
    left = {
        "seed": 83,
        "wormhole_nodes": ["n1", "n2"],
        "wormhole_fingerprint": "abc",
        "manifolds": {"primary": {"fingerprint": "m1"}},
        "state_loads": {
            "primary": {
                "loaded": False,
                "clock_before_load": 0,
                "node_count": 0,
                "projection_count": 0,
                "state_path": "repeat_01/latent.json",
            }
        },
        "scan_fingerprints": {"primary": {"fingerprint": "scan-a"}},
        "shared_pair_clock_history": [1, 2],
        "phase_coherence_history": [0.1, 0.2],
        "mode_history": ["active", "active"],
        "hint_status_history": ["suppressed", "armed"],
        "hint_bias_history": ["observe", "stabilize"],
        "gate_state_history": ["block", "pass"],
        "gate_reason_history": ["no_hint", "none"],
        "gate_status_history": ["missing", "armed"],
        "nudge_rejection_history": ["disabled", "observe_only"],
        "first_tick_phase_coherence": 0.1,
        "final_mode": "active",
    }
    right = {
        **left,
        "state_loads": {
            "primary": {
                "loaded": False,
                "clock_before_load": 0,
                "node_count": 0,
                "projection_count": 0,
                "state_path": "repeat_02/latent.json",
            }
        },
    }

    comparison = compare_run_checkpoints(left, right)

    assert comparison["static_matches"]["state_loads"] is True
    assert comparison["matches"] is True


def test_pair_runtime_parser_accepts_sweep_lists():
    parser = build_pair_runtime_parser()
    args = parser.parse_args(
        [
            "--sweep",
            "--sweep-root-dir",
            "working_data/test_sweep",
            "--sweep-embedding-a-locs",
            "0.47",
            "0.51",
            "--sweep-embedding-b-locs",
            "0.56",
            "0.60",
            "--sweep-embedding-drifts",
            "0.02",
            "0.05",
            "--sweep-cycle-counts",
            "4",
            "7",
            "--sweep-seeds",
            "13",
            "21",
        ]
    )

    assert args.sweep is True
    assert args.sweep_root_dir == "working_data/test_sweep"
    assert args.sweep_embedding_a_locs == [0.47, 0.51]
    assert args.sweep_embedding_b_locs == [0.56, 0.60]
    assert args.sweep_embedding_drifts == [0.02, 0.05]
    assert args.sweep_cycle_counts == [4, 7]
    assert args.sweep_seeds == [13, 21]


def test_build_pair_sweep_variants_is_deterministic_and_isolates_dirs(tmp_path: Path):
    parser = build_pair_runtime_parser()
    args = parser.parse_args(
        [
            "--working-dir",
            str(tmp_path / "single"),
            "--sweep",
            "--sweep-root-dir",
            str(tmp_path / "sweep"),
            "--embedding-scale",
            "0.09",
            "--sweep-embedding-a-locs",
            "0.48",
            "0.50",
            "--sweep-embedding-b-locs",
            "0.57",
            "--sweep-embedding-drifts",
            "0.03",
            "0.05",
            "--sweep-cycle-counts",
            "4",
            "--sweep-seeds",
            "17",
            "29",
        ]
    )

    variants_a = build_pair_sweep_variants(args, tmp_path / "sweep")
    variants_b = build_pair_sweep_variants(args, tmp_path / "sweep")

    assert [variant.variant_id for variant in variants_a] == [variant.variant_id for variant in variants_b]
    assert [variant.working_dir for variant in variants_a] == [variant.working_dir for variant in variants_b]
    assert len(variants_a) == 8
    assert len({variant.working_dir for variant in variants_a}) == 8
    assert all(variant.embedding_scale == 0.09 for variant in variants_a)


def test_pair_runtime_sweep_persists_aggregate_and_variant_outputs(tmp_path: Path):
    parser = build_pair_runtime_parser()
    args = parser.parse_args(
        [
            "--sweep",
            "--sweep-root-dir",
            str(tmp_path / "sweep_runs"),
            "--cycles",
            "2",
            "--top-n",
            "4",
            "--embedding-scale",
            "0.08",
            "--enable-hint-gate",
            "--enable-bounded-nudges",
            "--sweep-embedding-a-locs",
            "0.49",
            "--sweep-embedding-b-locs",
            "0.57",
            "--sweep-embedding-drifts",
            "0.03",
            "--sweep-cycle-counts",
            "2",
            "--sweep-seeds",
            "11",
        ]
    )

    result = run_pair_runtime_sweep(args)
    summary_lines = (tmp_path / "sweep_runs" / "sweep_summary.jsonl").read_text(encoding="utf-8").splitlines()
    csv_text = (tmp_path / "sweep_runs" / "sweep_summary.csv").read_text(encoding="utf-8")
    ranked_summary = (tmp_path / "sweep_runs" / "sweep_ranked_summary.txt").read_text(encoding="utf-8")
    compact_comparison = (tmp_path / "sweep_runs" / "sweep_compact_comparison.txt").read_text(
        encoding="utf-8"
    )
    paper_diagnostics = (tmp_path / "sweep_runs" / "sweep_paper_diagnostics.txt").read_text(encoding="utf-8")
    paper_handoff = (tmp_path / "sweep_runs" / "sweep_uncertainty_paper_handoff.md").read_text(
        encoding="utf-8"
    )
    paper_recommendation = (tmp_path / "sweep_runs" / "paper_finder_recommendation.md").read_text(
        encoding="utf-8"
    )
    record = result["records"][0]

    assert len(result["variants"]) == 1
    assert len(result["records"]) == 1
    assert len(summary_lines) == 1
    assert "variant_id,pair_id,working_dir" in csv_text
    assert "bounded_nudges_enabled" in csv_text
    assert "near_pass_maturity_nudges_enabled" in csv_text
    assert "nudge_attempt_count" in csv_text
    assert "hint_gate_blocked_count" in csv_text
    assert "hint_gate_near_pass_count" in csv_text
    assert "hint_gate_first_near_pass_tick" in csv_text
    assert "paper_synchrony_margin" in csv_text
    assert "paper_synchrony_basis" in csv_text
    assert "paper_synchrony_coupling_posture" in csv_text
    assert "paper_synchrony_evidence" in csv_text
    assert "paper_synchrony_contradiction" in csv_text
    assert "paper_synchrony_boundary_state" in csv_text
    assert "paper_basin_fragility" in csv_text
    assert "paper_uncertainty_triggered" in csv_text
    assert "[PAIR SWEEP] variants=1" in ranked_summary
    assert "Paper-trigger consensus:" in ranked_summary
    assert "Synchrony labels:" in ranked_summary
    assert "Synchrony boundary states:" in ranked_summary
    assert "Coupling postures:" in ranked_summary
    assert "Basin labels:" in ranked_summary
    assert "Ranked variants by natural decay pressure:" in ranked_summary
    assert "| gate=" in ranked_summary
    assert "near@" in ranked_summary or "pass@" in ranked_summary
    assert "| nudge=" in ranked_summary
    assert "| sync=" in ranked_summary
    assert "| basin=" in ranked_summary
    assert "[PAIR SWEEP COMPARISON] variants=1" in compact_comparison
    assert "Best natural entry:" in compact_comparison
    assert "Best paper-triggered uncertainty:" in compact_comparison
    assert "Paper-trigger consensus:" in compact_comparison
    assert "Synchrony boundary states:" in compact_comparison
    assert "Coupling postures:" in compact_comparison
    assert "Diagnosis-grouped leaders:" in compact_comparison
    assert "Parameter pockets:" in compact_comparison
    assert (
        "[cycles] key | runs | entries | mean_span | mean_decay | top_variant | top_reason"
        in compact_comparison
    )
    assert (
        "[drift] key | runs | entries | mean_span | mean_decay | top_variant | top_reason"
        in compact_comparison
    )
    assert (
        "[loc_pair] key | runs | entries | mean_span | mean_decay | top_variant | top_reason"
        in compact_comparison
    )
    assert (
        "rank | variant_id | cycles | seed | locA | locB | drift | mode | a2s | decay" in compact_comparison
    )
    assert (
        "nudges | gate | n+ | sync | basin | paper | policy | switch_tick | policy_tick | diagnosis | rank_reason | working_dir"
        in compact_comparison
    )
    assert (
        "threshold_ready_no_switch" in compact_comparison
        or "too_short" in compact_comparison
        or "calm" in compact_comparison
        or "decay_pressure" in compact_comparison
        or "entered" in compact_comparison
    )
    assert "[PAIR SWEEP PAPER] variants=1" in paper_diagnostics
    assert "Synchrony boundary states:" in paper_diagnostics
    assert "Coupling postures:" in paper_diagnostics
    assert "Variant paper-facing diagnostics:" in paper_diagnostics
    assert "# UNCERTAINTY TO PAPER RECOMMENDATION" in paper_handoff
    assert "# PAPER FINDER RECOMMENDATION" in paper_recommendation
    assert "- source uncertainty handoff:" in paper_recommendation
    assert record["hint_gate_enabled"] is True
    assert record["bounded_nudges_enabled"] is True
    assert record["negative_collapse_stabilize_enabled"] is False
    assert record["hint_gate_tick_count"] >= 1
    assert record["hint_gate_enabled_count"] >= 1
    assert record["hint_gate_near_pass_count"] >= 0
    assert record["paper_synchrony_margin"] in {"favorable", "borderline", "unfavorable", "unknown"}
    assert record["paper_synchrony_basis"] in {
        "response_led",
        "boundary_led",
        "structure_led",
        "mixed",
        "unknown",
    }
    assert record["paper_synchrony_coupling_posture"] in {"permissive", "strained", "weak", "unknown"}
    assert record["paper_synchrony_contradiction"] in {"low", "medium", "high", "unknown"}
    assert record["paper_synchrony_boundary_state"] in {
        "converting",
        "mixed_conversion",
        "non_converting",
        "blocked",
        "clear",
        "unknown",
    }
    assert record["paper_basin_fragility"] in {"broad", "narrow", "fragile", "unknown"}
    assert isinstance(record["paper_uncertainty_triggered"], bool)
    assert isinstance(record["hint_gate_reason_counts"], dict)
    assert record["nudge_tick_count"] >= 1
    assert record["nudge_attempt_count"] >= 1
    assert isinstance(record["nudge_reason_counts"], dict)
    assert isinstance(record["nudge_rejection_counts"], dict)

    for variant in result["variants"]:
        assert variant.working_dir.exists()
        assert (variant.working_dir / "replay_summary.txt").exists()
        assert (variant.working_dir / "registry_summary.txt").exists()
        assert (variant.working_dir / "comparative_summary.txt").exists()
        assert (variant.working_dir / "adaptive_tau_history.jsonl").exists()

    diagnosis_labels = {record["diagnosis_label"] for record in result["records"]}
    assert diagnosis_labels <= {
        "entered_stabilizer",
        "low_variance_candidate",
        "runtime_too_short_candidate",
        "threshold_conservative_candidate",
    }
    assert result["output_paths"]["compact_comparison"].exists()
    assert result["output_paths"]["paper_diagnostics"].exists()
    assert result["output_paths"]["paper_handoff"].exists()
    assert result["output_paths"]["paper_recommendation"].exists()


def test_render_sweep_uncertainty_paper_handoff_selects_best_triggered_variant():
    records = [
        {
            "variant_id": "variant_low",
            "working_dir": "working_data/sweep/variant_low",
            "paper_uncertainty_triggered": False,
            "paper_uncertainty_intervention_class": "diagnostics",
            "paper_uncertainty_desired_paper_role": "one paper on synchronization feasibility diagnostics",
            "paper_uncertainty_summary": "No stable bounded uncertainty.",
            "paper_synchrony_margin": "favorable",
            "paper_basin_fragility": "broad",
            "paper_synchrony_risk_score": 0,
            "paper_basin_risk_score": 0,
            "paper_synchrony_contradiction_count": 0,
            "hint_gate_blocked_count": 0,
            "hint_gate_near_pass_count": 0,
            "hint_gate_first_near_pass_confidence_gap": 1.0,
            "hint_gate_first_near_pass_reliability_gap": 1.0,
            "hint_gate_first_near_pass_sample_gap": 99,
            "diagnosis_label": "low_variance_candidate",
            "coherence_delta": 0.02,
            "longest_decay_streak": 0,
        },
        {
            "variant_id": "variant_mid",
            "working_dir": "working_data/sweep/variant_mid",
            "paper_uncertainty_triggered": True,
            "paper_uncertainty_intervention_class": "control policy",
            "paper_uncertainty_desired_paper_role": "one paper on synchrony-margin diagnostics or conservative gating under ambiguous local evidence",
            "paper_uncertainty_summary": "The pair shows unresolved synchrony uncertainty under repeated blocked and contradictory local evidence.",
            "paper_synchrony_margin": "borderline",
            "paper_basin_fragility": "narrow",
            "paper_synchrony_risk_score": 3,
            "paper_basin_risk_score": 2,
            "paper_synchrony_contradiction_count": 2,
            "hint_gate_blocked_count": 5,
            "hint_gate_near_pass_count": 1,
            "hint_gate_first_near_pass_confidence_gap": 0.18,
            "hint_gate_first_near_pass_reliability_gap": 0.09,
            "hint_gate_first_near_pass_sample_gap": 2,
            "diagnosis_label": "threshold_conservative_candidate",
            "coherence_delta": -0.05,
            "longest_decay_streak": 2,
        },
        {
            "variant_id": "variant_high",
            "working_dir": "working_data/sweep/variant_high",
            "paper_uncertainty_triggered": True,
            "paper_uncertainty_intervention_class": "control policy",
            "paper_uncertainty_desired_paper_role": "one paper on synchrony-margin diagnostics or conservative gating under ambiguous local evidence",
            "paper_uncertainty_summary": "The pair shows unresolved synchrony uncertainty under repeated blocked and contradictory local evidence.",
            "paper_synchrony_margin": "borderline",
            "paper_basin_fragility": "narrow",
            "paper_synchrony_risk_score": 3,
            "paper_basin_risk_score": 2,
            "paper_synchrony_contradiction_count": 2,
            "hint_gate_blocked_count": 4,
            "hint_gate_near_pass_count": 2,
            "hint_gate_first_near_pass_confidence_gap": 0.04,
            "hint_gate_first_near_pass_reliability_gap": 0.02,
            "hint_gate_first_near_pass_sample_gap": 0,
            "diagnosis_label": "threshold_conservative_candidate",
            "coherence_delta": -0.03,
            "longest_decay_streak": 2,
        },
    ]

    rendered = render_sweep_uncertainty_paper_handoff(records)

    assert "# UNCERTAINTY TO PAPER RECOMMENDATION" in rendered
    assert "Selected variant: variant_high" in rendered
    assert "Sweep trigger coverage: 2/3 variants" in rendered
    assert (
        "Selection basis: highest-priority triggered variant chosen by risk, contradiction count, and near-pass maturity"
        in rendered
    )
    assert (
        "Consensus pattern: dominant triggered pattern: intervention=control policy (2/2), sync=borderline (2/2), basin=narrow (2/2), diagnosis=threshold_conservative_candidate (2/2)"
        in rendered
    )
    assert "- intervention class: control policy" in rendered


def test_render_sweep_uncertainty_paper_handoff_reflects_topology_route():
    records = [
        {
            "variant_id": "variant_topology",
            "working_dir": "working_data/sweep/variant_topology",
            "paper_uncertainty_triggered": True,
            "paper_uncertainty_intervention_class": "topology design",
            "paper_uncertainty_desired_paper_role": "one paper on topology-aware synchronization feasibility or controllability",
            "paper_uncertainty_summary": "The pair shows unresolved synchrony uncertainty under weak coupling posture.",
            "paper_synchrony_margin": "borderline",
            "paper_synchrony_coupling_posture": "weak",
            "paper_basin_fragility": "broad",
            "paper_synchrony_risk_score": 3,
            "paper_basin_risk_score": 0,
            "paper_synchrony_contradiction_count": 1,
            "hint_gate_blocked_count": 4,
            "hint_gate_near_pass_count": 0,
            "hint_gate_first_near_pass_confidence_gap": 0.31,
            "hint_gate_first_near_pass_reliability_gap": 0.10,
            "hint_gate_first_near_pass_sample_gap": 3,
            "diagnosis_label": "low_variance_candidate",
            "coherence_delta": 0.12,
            "longest_decay_streak": 0,
        }
    ]

    rendered = render_sweep_uncertainty_paper_handoff(records)

    assert (
        "- key telemetry fields: phase_coherence, entangler_coherence_delta, entangler_coherence_status, wormhole_aperture, damping, phase_offset, entanglement_strength"
        in rendered
    )
    assert (
        "- key replay or sweep signals: coherence trend, coupling posture summary, paper diagnostic summary, sweep ranking"
        in rendered
    )
    assert (
        "- recent regimes or labels involved: borderline, coupling:weak, broad, low_variance_candidate"
        in rendered
    )
    assert (
        "- working hypothesis 1: The pair may sit outside a favorable synchronizable region because the current coupling posture is too weak or misaligned."
        in rendered
    )
    assert "- intervention class: topology design" in rendered
    assert (
        "- novelty relative to current `working_mind`: Extend beyond the current synchrony-margin and basin-stability seeds with a more specific topology-aware synchronization or controllability source."
        in rendered
    )
    assert "- preferred search envelope: one paper" in rendered
    assert (
        "current bottleneck: The pair shows unresolved synchrony uncertainty under weak coupling posture."
        in rendered
    )


def test_render_sweep_uncertainty_paper_handoff_reports_sweepwide_consensus():
    records = [
        {
            "variant_id": "variant_a",
            "working_dir": "working_data/sweep/variant_a",
            "paper_uncertainty_triggered": True,
            "paper_uncertainty_intervention_class": "control policy",
            "paper_uncertainty_desired_paper_role": "one paper on synchrony-margin diagnostics or conservative gating under ambiguous local evidence",
            "paper_uncertainty_summary": "The pair shows unresolved synchrony uncertainty under repeated blocked and contradictory local evidence.",
            "paper_synchrony_margin": "borderline",
            "paper_basin_fragility": "broad",
            "paper_synchrony_risk_score": 1,
            "paper_basin_risk_score": 1,
            "paper_synchrony_contradiction_count": 2,
            "hint_gate_blocked_count": 12,
            "hint_gate_near_pass_count": 3,
            "hint_gate_first_near_pass_confidence_gap": 0.08,
            "hint_gate_first_near_pass_reliability_gap": 0.04,
            "hint_gate_first_near_pass_sample_gap": 0,
            "diagnosis_label": "low_variance_candidate",
            "coherence_delta": 0.50,
            "longest_decay_streak": 0,
        },
        {
            "variant_id": "variant_b",
            "working_dir": "working_data/sweep/variant_b",
            "paper_uncertainty_triggered": True,
            "paper_uncertainty_intervention_class": "control policy",
            "paper_uncertainty_desired_paper_role": "one paper on synchrony-margin diagnostics or conservative gating under ambiguous local evidence",
            "paper_uncertainty_summary": "The pair shows unresolved synchrony uncertainty under repeated blocked and contradictory local evidence.",
            "paper_synchrony_margin": "borderline",
            "paper_basin_fragility": "broad",
            "paper_synchrony_risk_score": 1,
            "paper_basin_risk_score": 1,
            "paper_synchrony_contradiction_count": 2,
            "hint_gate_blocked_count": 11,
            "hint_gate_near_pass_count": 5,
            "hint_gate_first_near_pass_confidence_gap": 0.03,
            "hint_gate_first_near_pass_reliability_gap": 0.01,
            "hint_gate_first_near_pass_sample_gap": 0,
            "diagnosis_label": "low_variance_candidate",
            "coherence_delta": 0.40,
            "longest_decay_streak": 0,
        },
    ]

    rendered = render_sweep_uncertainty_paper_handoff(records)

    assert "Selected variant: variant_b" in rendered
    assert "Sweep trigger coverage: 2/2 variants" in rendered
    assert "Selection basis: representative triggered variant chosen from a sweep-wide consensus" in rendered
    assert (
        "Consensus pattern: unanimous sweep consensus: intervention=control policy (2/2), sync=borderline (2/2), basin=broad (2/2), diagnosis=low_variance_candidate (2/2)"
        in rendered
    )
