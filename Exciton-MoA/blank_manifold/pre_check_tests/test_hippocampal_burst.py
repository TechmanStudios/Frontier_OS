# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
from pathlib import Path

from blank_config import BlankManifoldConfig
from blank_manifold_core import BlankManifoldCore
from hippocampal import HippocampalTransducer


def test_hippocampal_burst_archive(tmp_path: Path):
    manifold_core = BlankManifoldCore(BlankManifoldConfig())
    manifold_core.generate_manifold()
    manifold_core.graph.nodes["node_0000"]["dominant_giant"] = "The Integrator"
    manifold_core.graph.nodes["node_0000"]["consensus_vector"] = [1.0, 0.5, 0.25]
    manifold_core.graph.nodes["node_0000"]["consensus_sources"] = ["The Integrator"]

    transducer = HippocampalTransducer(output_dir=tmp_path, burst_flush_threshold=1)
    burst_path = transducer.capture_bursts(
        [(
            "node_0000",
            {
                "H_total": 2.0,
                "tau_threshold": 1.75,
                "density": 1.0,
                "density_signal": 0.7,
                "density_contrib": 1.05,
                "shear": 0.5,
                "shear_signal": 0.4,
                "shear_contrib": 0.4,
                "vorticity": 0.25,
                "vorticity_signal": 0.2,
                "vorticity_contrib": 0.15,
            },
        )],
        manifold_core.graph,
    )

    assert burst_path is not None
    assert burst_path.exists()
    assert transducer.long_term_archive.exists()
    assert '"density_contrib": 1.05' in burst_path.read_text(encoding="utf-8")


def test_hippocampal_burst_archive_with_pair_context(tmp_path: Path):
    manifold_core = BlankManifoldCore(BlankManifoldConfig())
    manifold_core.generate_manifold()
    manifold_core.graph.nodes["node_0000"]["dominant_giant"] = "The Integrator"

    transducer = HippocampalTransducer(output_dir=tmp_path, burst_flush_threshold=1)
    burst_path = transducer.capture_bursts(
        [(
            "node_0000",
            {
                "H_total": 2.5,
                "tau_threshold": 2.0,
                "density": 1.1,
                "density_contrib": 1.2,
                "shear": 0.7,
                "shear_contrib": 0.8,
                "vorticity": 0.4,
                "vorticity_contrib": 0.5,
            },
        )],
        manifold_core.graph,
        pair_context={
            "pair_id": "primary-secondary",
            "source_manifold_id": "primary",
            "bilateral_node_ids": ["node_0000"],
            "cross_domain_giant": "Entanglement Locus",
            "phase_coherence": 0.91,
            "shared_flux_norm": 1.4,
            "wormhole_nodes": ["node_0000"],
            "phonon_id": "phonon_primary-secondary_0007",
            "phonon_confidence": 0.64,
            "phonon_entropy": 0.18,
            "phonon_mode": "shear",
            "phonon_predicted_next_mode": "active",
            "phonon_stability_score": 0.74,
            "wormhole_entry_count": 1,
            "wormhole_exit_count": 0,
        },
    )

    text = burst_path.read_text(encoding="utf-8") if burst_path is not None else ""
    assert '"pair_id": "primary-secondary"' in text
    assert '"source_manifold_id": "primary"' in text
    assert '"bilateral_burst": true' in text.lower()
    assert '"wormhole_boundary": true' in text.lower()
    assert '"phonon_id": "phonon_primary-secondary_0007"' in text
    assert '"phonon_mode": "shear"' in text
    assert '"wormhole_entry_count": 1' in text