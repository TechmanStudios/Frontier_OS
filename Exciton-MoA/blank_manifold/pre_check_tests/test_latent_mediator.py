# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
from pathlib import Path

import numpy as np
from blank_config import BlankManifoldConfig
from blank_manifold_core import BlankManifoldCore
from latent_mediator import LatentMediator


def test_latent_mediator_consensus_tracks_dominant_signal(tmp_path: Path):
    manifold_core = BlankManifoldCore(BlankManifoldConfig())
    manifold_core.generate_manifold()
    mediator = LatentMediator(manifold_core, state_path=tmp_path / "latent_mediator_state.json")

    mediator.project("node_0000", "The Statistician", np.array([1.0, 1.0, 0.0]), 0.9)
    mediator.project("node_0000", "The Linear Algebraist", np.array([0.1, 0.1, 1.0]), 0.2)

    consensus = mediator.publish_consensus("node_0000")

    assert consensus is not None
    assert consensus["dominant_giant"] == "The Statistician"
    assert consensus["vector_clock"] == 2
    assert consensus["consensus_vector"][0] > consensus["consensus_vector"][2]


def test_latent_mediator_persists_across_reloads(tmp_path: Path):
    state_path = tmp_path / "latent_mediator_state.json"

    manifold_core = BlankManifoldCore(BlankManifoldConfig())
    manifold_core.generate_manifold()
    mediator = LatentMediator(manifold_core, state_path=state_path)
    mediator.project("node_0000", "The Integrator", np.array([0.2, 0.5, 0.8]), 0.7)
    mediator.publish_consensus("node_0000")
    mediator.persist_state()

    fresh_manifold = BlankManifoldCore(BlankManifoldConfig())
    fresh_manifold.generate_manifold()
    LatentMediator(fresh_manifold, state_path=state_path)

    node_data = fresh_manifold.graph.nodes["node_0000"]
    assert node_data["dominant_giant"] == "The Integrator"
    assert node_data["consensus_clock"] == 1
    assert len(node_data["consensus_vector"]) == 3
