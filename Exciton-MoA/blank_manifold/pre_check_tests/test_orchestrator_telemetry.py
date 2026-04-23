# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""
Exciton-MoA: Ontological Orchestrator Telemetry Diagnostics

====================================================================
AGENT INSTRUCTIONS: WHAT TO WATCH FOR DURING EXECUTION
As you execute this macroscopic observation test, explicitly monitor:

1. Precision Isolation:
  We are injecting a massive anomaly at a specific coordinate (node_0042).
  The Orchestrator's scan must isolate this exact node without throwing
  false positives across the rest of the 1,024-node lattice.

2. The H-Score Tensor Computation:
  Verify that the Hotspot Functional (H) correctly decomposes into its
  sub-components. The 'density' (gravity gradient) and 'shear' (epistemic
  friction) must compute as non-zero values that push the total H-Score
  above the retuned tau threshold (4.5). This confirms the UI telemetry is armed.
====================================================================
"""

import numpy as np
from blank_config import BlankManifoldConfig
from blank_manifold_core import BlankManifoldCore
from telemetry import OntologicalOrchestrator


def test_telemetry_thresholding():
  print("Running Pre-Check: Macroscopic Telemetry & Hotspot Detection...")

  manifold_core = BlankManifoldCore(BlankManifoldConfig())
  graph = manifold_core.generate_manifold()

  orchestrator = OntologicalOrchestrator(manifold_core, tau_threshold=4.5)

  test_node = "node_0042"
  graph.nodes[test_node]["resonance_accumulator"] = 5.0
  graph.nodes[test_node]["state_vector"] = np.array([5.0, 5.0, 5.0])

  bursts = orchestrator.scan_manifold()

  assert len(bursts) > 0, "FAIL: Orchestrator failed to detect the massive anomaly."

  detected_nodes = [burst[0] for burst in bursts]
  assert test_node in detected_nodes, f"FAIL: Orchestrator missed the epicenter {test_node}."

  metrics = orchestrator.compute_local_hotspot(test_node)
  assert metrics["H_total"] > 0.0, f"FAIL: H-Score {metrics['H_total']} failed to compute."
  assert metrics["density"] > 0.0, "FAIL: Z-Axis gravity gradient failed to compute."
  assert metrics["shear"] > 0.0, "FAIL: Epistemic friction failed to compute."
  assert metrics["density_contrib"] > 0.0, "FAIL: Density contribution failed to compute."
  assert metrics["shear_contrib"] > 0.0, "FAIL: Shear contribution failed to compute."
  assert metrics["H_total"] >= orchestrator.tau, "FAIL: Adaptive tau exceeded the anomaly response."
  assert orchestrator.tau >= orchestrator.base_tau, "FAIL: Adaptive tau should not fall below the base calibration."

  print(f"PASS: Telemetry functional H(x,t) successfully caught Threshold Burst at {test_node}.")


if __name__ == "__main__":
  test_telemetry_thresholding()