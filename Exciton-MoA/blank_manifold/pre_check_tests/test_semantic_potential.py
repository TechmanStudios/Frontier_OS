# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
import numpy as np

from blank_config import BlankManifoldConfig
from blank_manifold_core import BlankManifoldCore


def test_semantic_potential_solver_enforces_zero_mean_gauge():
    manifold_core = BlankManifoldCore(BlankManifoldConfig())
    manifold_core.generate_manifold()

    graph = manifold_core.graph
    edge = next(iter(graph.edges))
    graph[edge[0]][edge[1]]["residual_flux"] = 1.0

    potentials = manifold_core.solve_semantic_potential()

    assert len(potentials) == graph.number_of_nodes()
    assert abs(sum(potentials.values())) < 1e-6
    assert graph.graph["semantic_potential_gauge"] == "mean_zero"
    assert graph.nodes[edge[0]]["semantic_potential"] != graph.nodes[edge[1]]["semantic_potential"]