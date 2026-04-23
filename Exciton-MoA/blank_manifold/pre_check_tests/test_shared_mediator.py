# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
from pathlib import Path

import numpy as np
from shared_mediator import SharedMediator


def test_shared_mediator_persists_and_reloads_pair_state(tmp_path: Path):
    state_path = tmp_path / "shared_entanglement_locus_primary-secondary.json"
    mediator = SharedMediator(
        pair_id="primary-secondary", manifold_ids=("primary", "secondary"), state_path=state_path
    )

    summary = mediator.publish_pair_state(
        shared_flux=np.array([0.8, 2.4, 0.5]),
        phase_coherence=0.72,
        wormhole_nodes=["node_0001", "node_0008"],
        bilateral_node_ids=["node_0001"],
        top_events=[{"manifold_id": "primary", "node_id": "node_0001", "h_total": 7.3}],
        local_consensus={
            "primary": {
                "node_0001": {
                    "consensus_vector": [1.0, 2.0, 0.3],
                    "consensus_confidence": 0.9,
                    "consensus_entropy": 0.1,
                    "consensus_clock": 3,
                    "dominant_giant": "The Graph Navigator",
                }
            },
            "secondary": {
                "node_0001": {
                    "consensus_vector": [0.9, 2.2, 0.4],
                    "consensus_confidence": 0.8,
                    "consensus_entropy": 0.2,
                    "consensus_clock": 2,
                    "dominant_giant": "The Graph Navigator",
                },
                "node_0008": {
                    "consensus_vector": [0.5, 1.5, 0.2],
                    "consensus_confidence": 0.7,
                    "consensus_entropy": 0.3,
                    "consensus_clock": 2,
                    "dominant_giant": "The Integrator",
                },
            },
        },
    )

    assert state_path.exists()
    assert summary["pair_id"] == "primary-secondary"
    assert summary["pair_clock"] == 3
    assert summary["dominant_channel"] == "shear"
    assert summary["cross_domain_giant"] == "Entanglement Locus"
    assert summary["resolved_channels"]["entanglement_locus"]["dominant_giant"] == "Entanglement Locus"

    reloaded = SharedMediator(
        pair_id="primary-secondary", manifold_ids=("primary", "secondary"), state_path=state_path
    )
    restored = reloaded.get_latest_summary()

    assert restored["pair_clock"] == 3
    assert restored["bilateral_node_ids"] == ["node_0001"]
    assert restored["resolved_channels"]["node_0001"]["dominant_giant"] == "The Graph Navigator"


def test_shared_mediator_persists_entangler_control_channel(tmp_path: Path):
    state_path = tmp_path / "shared_entanglement_locus_primary-secondary.json"
    mediator = SharedMediator(
        pair_id="primary-secondary", manifold_ids=("primary", "secondary"), state_path=state_path
    )
    mediator.publish_pair_state(
        shared_flux=[0.5, 1.4, 0.3],
        phase_coherence=0.55,
        wormhole_nodes=["node_0001"],
        bilateral_node_ids=["node_0001"],
        local_consensus={
            "primary": {
                "node_0001": {
                    "consensus_vector": [0.5, 1.2, 0.2],
                    "consensus_confidence": 0.8,
                    "consensus_entropy": 0.1,
                    "consensus_clock": 3,
                    "dominant_giant": "The Graph Navigator",
                }
            },
            "secondary": {
                "node_0001": {
                    "consensus_vector": [0.4, 1.0, 0.2],
                    "consensus_confidence": 0.7,
                    "consensus_entropy": 0.2,
                    "consensus_clock": 2,
                    "dominant_giant": "The Graph Navigator",
                }
            },
        },
    )

    control = mediator.publish_entangler_control(
        {
            "pair_clock": 2,
            "entanglement_strength": 0.73,
            "dominant_giant_consensus": "The Graph Navigator",
            "wormhole_weight_map": {"node_0001": 1.32},
            "wormhole_weight_summary": {
                "min_weight": 1.32,
                "max_weight": 1.32,
                "top_weighted_wormholes": [{"node_id": "node_0001", "weight": 1.32}],
            },
            "controls_before": {"aperture": 0.24, "damping": 0.84, "phase_offset": 0.15},
            "controls_after": {"aperture": 0.31, "damping": 0.80, "phase_offset": 0.22},
            "control_delta": {"aperture": 0.07, "damping": -0.04, "phase_offset": 0.07},
            "targets": {"aperture": 0.31, "damping": 0.80, "phase_offset": 0.22},
            "clamp_flags": {"aperture": False, "damping": False, "phase_offset": False},
            "features": {"phase_coherence": 0.55},
            "hint_gate": {
                "enabled": True,
                "annotation_only": True,
                "passed": False,
                "applied": False,
                "rejection_reason": "low_reliability",
                "considered_recommendation": "stabilize",
                "considered_confidence": 0.58,
                "considered_reliability": 0.42,
                "considered_sample_count": 2,
                "reliability_provisional": True,
                "nudge_enabled": True,
                "nudge_applied": False,
                "nudge_reason": "none",
                "nudge_rejection_reason": "low_reliability",
                "nudge_reliability": 0.42,
                "nudge_sample_count": 2,
                "nudge_stability_score": 0.61,
                "nudge_delta": {"aperture": 0.0, "damping": 0.0, "phase_offset": 0.0},
                "nudge_clamp_flags": {"aperture": False, "damping": False, "phase_offset": False},
            },
            "wormhole_health": {"node_0001": 0.81},
            "reasoning_summary": "stable coherent bridge",
        }
    )

    reloaded = SharedMediator(
        pair_id="primary-secondary", manifold_ids=("primary", "secondary"), state_path=state_path
    )
    restored = reloaded.get_latest_summary()

    assert control["controller"] == "Entangler Giant"
    assert restored["entangler_control"]["controls_after"]["aperture"] == 0.31
    assert restored["entangler_control"]["wormhole_weight_map"]["node_0001"] == 1.32
    assert restored["entangler_control"]["hint_gate"]["rejection_reason"] == "low_reliability"
    assert restored["entangler_control"]["hint_gate"]["nudge_rejection_reason"] == "low_reliability"
    assert restored["resolved_channels"]["entangler_control"]["dominant_giant"] == "Entangler Giant"
    assert restored["pair_clock"] >= 3


def test_shared_mediator_pair_clock_advances_with_local_clock_skew(tmp_path: Path):
    mediator = SharedMediator(
        pair_id="primary-secondary",
        manifold_ids=("primary", "secondary"),
        state_path=tmp_path / "shared_entanglement_locus_primary-secondary.json",
    )

    first = mediator.publish_pair_state(
        shared_flux=[0.2, 0.6, 0.1],
        phase_coherence=0.5,
        wormhole_nodes=["node_0002"],
        bilateral_node_ids=[],
        local_consensus={
            "primary": {
                "node_0002": {
                    "consensus_vector": [0.2, 0.6, 0.1],
                    "consensus_confidence": 0.6,
                    "consensus_entropy": 0.2,
                    "consensus_clock": 9,
                    "dominant_giant": "The Statistician",
                }
            },
            "secondary": {
                "node_0002": {
                    "consensus_vector": [0.3, 0.5, 0.1],
                    "consensus_confidence": 0.5,
                    "consensus_entropy": 0.1,
                    "consensus_clock": 1,
                    "dominant_giant": "The Statistician",
                }
            },
        },
    )
    second = mediator.publish_pair_state(
        shared_flux=[0.3, 0.7, 0.1],
        phase_coherence=0.4,
        wormhole_nodes=["node_0002"],
        bilateral_node_ids=["node_0002"],
        local_consensus={
            "primary": {
                "node_0002": {
                    "consensus_vector": [0.1, 0.5, 0.2],
                    "consensus_confidence": 0.5,
                    "consensus_entropy": 0.2,
                    "consensus_clock": 2,
                    "dominant_giant": "The Integrator",
                }
            },
            "secondary": {
                "node_0002": {
                    "consensus_vector": [0.3, 0.7, 0.1],
                    "consensus_confidence": 0.7,
                    "consensus_entropy": 0.1,
                    "consensus_clock": 15,
                    "dominant_giant": "The Integrator",
                }
            },
        },
    )

    assert first["pair_clock"] == 2
    assert second["pair_clock"] == 4
    assert second["pair_clock"] > first["pair_clock"]
    assert first["local_clock_max"] == 9
    assert second["local_clock_max"] == 15
    assert second["bilateral_node_ids"] == ["node_0002"]


def test_shared_mediator_persists_latest_phonon_bundle(tmp_path: Path):
    state_path = tmp_path / "shared_entanglement_locus_primary-secondary.json"
    mediator = SharedMediator(
        pair_id="primary-secondary", manifold_ids=("primary", "secondary"), state_path=state_path
    )
    mediator.publish_pair_state(
        shared_flux=[0.5, 1.4, 0.3],
        phase_coherence=0.55,
        wormhole_nodes=["node_0001", "node_0008"],
        bilateral_node_ids=["node_0001"],
        local_consensus={
            "primary": {
                "node_0001": {
                    "consensus_vector": [0.5, 1.2, 0.2],
                    "consensus_confidence": 0.8,
                    "consensus_entropy": 0.1,
                    "consensus_clock": 3,
                    "dominant_giant": "The Graph Navigator",
                }
            },
            "secondary": {
                "node_0001": {
                    "consensus_vector": [0.4, 1.0, 0.2],
                    "consensus_confidence": 0.7,
                    "consensus_entropy": 0.2,
                    "consensus_clock": 2,
                    "dominant_giant": "The Graph Navigator",
                }
            },
        },
    )

    bundle = mediator.publish_phonon_bundle(
        {
            "phonon_id": "phonon_primary-secondary_0007",
            "pair_clock": 7,
            "mode": "shear",
            "confidence": 0.64,
            "amplitude": 0.31,
            "decay_rate": 0.18,
            "predicted_next_mode": "active",
            "wormhole_entry_nodes": ["node_0008"],
            "wormhole_exit_nodes": [],
            "coherence_signature": {"status": "stable", "stability_score": 0.74},
        }
    )

    reloaded = SharedMediator(
        pair_id="primary-secondary", manifold_ids=("primary", "secondary"), state_path=state_path
    )
    restored = reloaded.get_latest_summary()

    assert bundle["phonon_id"] == "phonon_primary-secondary_0007"
    assert restored["pair_clock"] == 7
    assert restored["latest_phonon_bundle"]["mode"] == "shear"
    assert restored["latest_phonon_bundle"]["coherence_signature"]["status"] == "stable"
    assert len(restored["phonon_bundles"]) == 1
    assert restored["phonon_bundles"][0]["wormhole_entry_nodes"] == ["node_0008"]


def test_shared_mediator_persists_latest_phonon_control_hint(tmp_path: Path):
    state_path = tmp_path / "shared_entanglement_locus_primary-secondary.json"
    mediator = SharedMediator(
        pair_id="primary-secondary", manifold_ids=("primary", "secondary"), state_path=state_path
    )
    mediator.publish_pair_state(
        shared_flux=[0.5, 1.4, 0.3],
        phase_coherence=0.55,
        wormhole_nodes=["node_0001", "node_0008"],
        bilateral_node_ids=["node_0001"],
        local_consensus={
            "primary": {
                "node_0001": {
                    "consensus_vector": [0.5, 1.2, 0.2],
                    "consensus_confidence": 0.8,
                    "consensus_entropy": 0.1,
                    "consensus_clock": 3,
                    "dominant_giant": "The Graph Navigator",
                }
            },
            "secondary": {
                "node_0001": {
                    "consensus_vector": [0.4, 1.0, 0.2],
                    "consensus_confidence": 0.7,
                    "consensus_entropy": 0.2,
                    "consensus_clock": 2,
                    "dominant_giant": "The Graph Navigator",
                }
            },
        },
    )

    hint = mediator.publish_phonon_control_hint(
        {
            "status": "armed",
            "recommended_bias": "stabilize",
            "confidence": 0.52,
            "age_ticks": 1,
            "stability_window": 6,
            "suppression_reason": "none",
            "source_tier": "local_post_injection",
            "entry_pressure": 1.0,
            "exit_pressure": 0.0,
        }
    )

    reloaded = SharedMediator(
        pair_id="primary-secondary", manifold_ids=("primary", "secondary"), state_path=state_path
    )
    restored = reloaded.get_latest_summary()

    assert hint["status"] == "armed"
    assert restored["latest_phonon_control_hint"]["recommended_bias"] == "stabilize"
    assert restored["latest_phonon_control_hint"]["confidence"] == 0.52
    assert len(restored["phonon_control_hints"]) == 1
    assert restored["phonon_control_hints"][0]["source_tier"] == "local_post_injection"


def test_shared_mediator_pair_state_refresh_preserves_latest_phonon_control_hint(tmp_path: Path):
    state_path = tmp_path / "shared_entanglement_locus_primary-secondary.json"
    mediator = SharedMediator(
        pair_id="primary-secondary", manifold_ids=("primary", "secondary"), state_path=state_path
    )
    mediator.publish_pair_state(
        shared_flux=[0.5, 1.4, 0.3],
        phase_coherence=0.55,
        wormhole_nodes=["node_0001", "node_0008"],
        bilateral_node_ids=["node_0001"],
        local_consensus={
            "primary": {
                "node_0001": {
                    "consensus_vector": [0.5, 1.2, 0.2],
                    "consensus_confidence": 0.8,
                    "consensus_entropy": 0.1,
                    "consensus_clock": 3,
                    "dominant_giant": "The Graph Navigator",
                }
            },
            "secondary": {
                "node_0001": {
                    "consensus_vector": [0.4, 1.0, 0.2],
                    "consensus_confidence": 0.7,
                    "consensus_entropy": 0.2,
                    "consensus_clock": 2,
                    "dominant_giant": "The Graph Navigator",
                }
            },
        },
    )
    mediator.publish_phonon_control_hint(
        {
            "status": "armed",
            "recommended_bias": "stabilize",
            "confidence": 0.52,
            "age_ticks": 1,
            "stability_window": 6,
            "suppression_reason": "none",
            "source_tier": "local_post_injection",
            "entry_pressure": 1.0,
            "exit_pressure": 0.0,
        }
    )

    refreshed = mediator.publish_pair_state(
        shared_flux=[0.7, 1.8, 0.4],
        phase_coherence=0.61,
        wormhole_nodes=["node_0001", "node_0008"],
        bilateral_node_ids=["node_0001"],
        local_consensus={
            "primary": {
                "node_0001": {
                    "consensus_vector": [0.6, 1.5, 0.2],
                    "consensus_confidence": 0.82,
                    "consensus_entropy": 0.1,
                    "consensus_clock": 4,
                    "dominant_giant": "The Graph Navigator",
                }
            },
            "secondary": {
                "node_0001": {
                    "consensus_vector": [0.5, 1.3, 0.2],
                    "consensus_confidence": 0.74,
                    "consensus_entropy": 0.2,
                    "consensus_clock": 3,
                    "dominant_giant": "The Graph Navigator",
                }
            },
        },
    )

    assert refreshed["latest_phonon_control_hint"]["status"] == "armed"
    assert refreshed["latest_phonon_control_hint"]["recommended_bias"] == "stabilize"
    assert refreshed["phonon_control_hints"][0]["source_tier"] == "local_post_injection"
