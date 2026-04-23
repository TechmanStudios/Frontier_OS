# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""
Exciton-MoA: Exciton Physics & Differential Equation Diagnostics

====================================================================
AGENT INSTRUCTIONS: WHAT TO WATCH FOR DURING EXECUTION
As you execute this localized physics test, explicitly monitor:

1. Thermodynamic Pressure Regulation (The Statistician):
   Observe the 'semantic_pressure' calculation. It must exactly
   track the SOL Equation of State: c * log(1 + rho). If this fails,
   the manifold will suffer from uncontrolled data crowding.

2. Jeans Mass Collapse (The N-Body Solver):
   Watch the edge weight between the target node and its neighbor.
   When the artificial resonance spikes beyond the Jeans Mass threshold
   (1.0), the N-Body Solver must trigger a gravitational collapse,
   permanently mutating the local topology by doubling the edge weight.
   You are verifying the creation of a stable attractor basin.
====================================================================
"""

import numpy as np
from blank_config import BlankManifoldConfig
from blank_manifold_core import BlankManifoldCore
from excitons import ExcitonEngine


def test_exciton_activation():
    print("Running Pre-Check: Exciton Physics & SOL Differential Equations...")

    manifold_core = BlankManifoldCore(BlankManifoldConfig())
    graph = manifold_core.generate_manifold()
    engine = ExcitonEngine(manifold_core)

    target_node = "node_0000"
    neighbor_node = list(graph.neighbors(target_node))[0]

    # 1. Artificially spike resonance beyond the Jeans Mass threshold (1.0)
    graph.nodes[target_node]["resonance_accumulator"] = 2.5
    graph.nodes[neighbor_node]["resonance_accumulator"] = 1.5

    initial_weight = graph[target_node][neighbor_node].get("weight", 0.1)

    # Ignite Excitons manually for the target coordinate
    engine._execute_giant_operators(target_node, target_coords=np.array([1.0, 1.0, 1.0]))

    # 2. Verify The Statistician (Thermodynamic Pressure Regulation)
    expected_pressure = np.log1p(2.5)  # c * log(1 + rho)
    actual_pressure = graph.nodes[target_node].get("semantic_pressure", 0.0)
    assert np.isclose(actual_pressure, expected_pressure), (
        f"FAIL: Semantic pressure {actual_pressure} violates SOL EOS."
    )

    # 3. Verify The N-Body Solver (Jeans Mass Collapse)
    post_collapse_weight = graph[target_node][neighbor_node].get("weight", 0.1)
    assert post_collapse_weight > initial_weight, "FAIL: N-Body Solver failed to dilate gravity well."
    assert graph[target_node][neighbor_node].get("collapsed") is True, (
        "FAIL: Jeans Mass collapse boolean not set."
    )

    print("PASS: Excitons successfully warped local topology and regulated semantic pressure.")


if __name__ == "__main__":
    test_exciton_activation()
