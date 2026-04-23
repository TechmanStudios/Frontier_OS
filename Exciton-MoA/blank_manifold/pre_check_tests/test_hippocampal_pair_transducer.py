# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
from pathlib import Path

from blank_config import BlankManifoldConfig
from blank_manifold_core import BlankManifoldCore
from hippocampal import HippocampalPairTransducer, HippocampalTransducer


def test_capture_bilateral_bursts_marks_shared_wormhole_nodes(tmp_path: Path):
    manifold_a = BlankManifoldCore(BlankManifoldConfig())
    manifold_a.generate_manifold()
    manifold_b = BlankManifoldCore(BlankManifoldConfig())
    manifold_b.generate_manifold()

    transducer_a = HippocampalTransducer(output_dir=tmp_path / "primary", burst_flush_threshold=1)
    transducer_b = HippocampalTransducer(output_dir=tmp_path / "secondary", burst_flush_threshold=1)
    pair_transducer = HippocampalPairTransducer(
        transducer_a,
        transducer_b,
        pair_id="primary-secondary",
        manifold_ids=("primary", "secondary"),
        wormhole_nodes=["node_0000", "node_0001"],
    )

    result = pair_transducer.capture_bilateral_bursts(
        [
            (
                "node_0000",
                {
                    "H_total": 3.2,
                    "tau_threshold": 2.0,
                    "density_contrib": 1.0,
                    "shear_contrib": 0.9,
                    "vorticity_contrib": 0.4,
                },
            )
        ],
        [
            (
                "node_0000",
                {
                    "H_total": 2.8,
                    "tau_threshold": 2.0,
                    "density_contrib": 0.8,
                    "shear_contrib": 0.7,
                    "vorticity_contrib": 0.3,
                },
            )
        ],
        manifold_a.graph,
        manifold_b.graph,
        pair_metadata={
            "phase_coherence": 0.9,
            "shared_flux": [0.4, 0.8, 0.2],
            "cross_domain_giant": "Entanglement Locus",
            "wormhole_nodes": ["node_0000", "node_0001"],
            "phonon_bundle": {
                "phonon_id": "phonon_primary-secondary_0005",
                "mode": "shear",
                "confidence": 0.62,
                "entropy": 0.14,
                "predicted_next_mode": "active",
                "wormhole_entry_nodes": ["node_0001"],
                "wormhole_exit_nodes": [],
                "coherence_signature": {"stability_score": 0.73},
            },
        },
    )

    assert result["pair_id"] == "primary-secondary"
    assert result["bilateral_node_ids"] == ["node_0000"]
    primary_text = (
        tmp_path
        / "primary"
        / next(path.name for path in (tmp_path / "primary").glob("hippocampal_burst_*.json"))
    ).read_text(encoding="utf-8")
    secondary_text = (
        tmp_path
        / "secondary"
        / next(path.name for path in (tmp_path / "secondary").glob("hippocampal_burst_*.json"))
    ).read_text(encoding="utf-8")
    assert '"bilateral_burst": true' in primary_text.lower()
    assert '"phonon_id": "phonon_primary-secondary_0005"' in primary_text
    assert '"pair_id": "primary-secondary"' in secondary_text
