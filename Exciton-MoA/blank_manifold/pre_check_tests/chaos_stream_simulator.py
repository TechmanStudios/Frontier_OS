# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""
Exciton-MoA (Frontier OS) - Chaos Stream Simulator

====================================================================
AGENT INSTRUCTIONS: WHAT TO WATCH FOR DURING EXECUTION
As you execute this continuous flux simulation, explicitly monitor
these three phenomena in the console telemetry:

1. The Thermodynamic Forgetting Curve:
   Observe the 'Global Resonance Load'. Because the signal drifts
   continuously, the focal point of the shower moves across the lattice.
   You should see that the load does not scale to infinity. The ambient
   decay function cools old attractor basins just as fast as new ones form,
   keeping the working memory entirely fluid without crashing the manifold.

2. Black Swan Dilation:
   On every 10th iteration, a massive burst of unstructured noise is injected.
   Watch the Orchestrator's H-Score telemetry instantly spike. You are observing
   the Integrator Exciton violently dilating the local Jacobian volume to absorb
   the shock without shattering the array.

3. Wormhole Accumulation (Long-Term Intuition):
   Watch the 'Gravitational Collapses (Wormholes)' counter slowly increment.
   This tracks the N-Body Solver permanently altering the baseline topology
   by increasing edge weights. You are literally watching the architecture
   build its long-term structural intuition out of the chaos.
====================================================================
"""

import time

import numpy as np
from blank_config import BlankManifoldConfig
from blank_manifold_core import BlankManifoldCore
from excitons import ExcitonEngine
from hippocampal import HippocampalTransducer
from latent_mediator import LatentMediator
from telemetry import OntologicalOrchestrator
from transducer import StatisticalPrism


def run_chaos_stream(iterations: int = 50, sleep_interval: float = 0.5):
    print("=== Initiating Continuous Flux Simulation ===")
    print("WARNING: Injecting chaotic, drifting tensor waves into the hyperbolic vacuum.\n")

    # 1. Boot the Operating System
    config = BlankManifoldConfig(base_node_count=1024, dimensionality=3)
    manifold_core = BlankManifoldCore(config)
    graph = manifold_core.generate_manifold()
    mediator = LatentMediator(manifold_core)
    hippocampal_transducer = HippocampalTransducer()

    prism = StatisticalPrism(manifold_core)
    excitons = ExcitonEngine(manifold_core, mediator=mediator)

    # Use a slightly lower threshold than the default runtime so buildup remains visible
    orchestrator = OntologicalOrchestrator(
        manifold_core, tau_threshold=3.8, mediator=mediator, hippocampal_transducer=hippocampal_transducer
    )

    # 2. Establish the Drifting Signal Baseline
    # We simulate a 1536D embedding whose core meaning shifts over time
    base_signal = np.random.normal(loc=0.0, scale=0.5, size=1536)

    # Trackers for the agent to observe macro-physics
    total_bursts = 0

    for i in range(iterations):
        print(f"\n--- [FLUX WAVE {i + 1}/{iterations}] ---")

        # 3. Mutate the Signal (The 'Concept Drift')
        # We add a geometric random walk to the embedding to simulate shifting intent.
        # The data becomes noisy, stretching the capacity of the manifold.
        drift_vector = np.random.normal(loc=0.05, scale=0.1, size=1536)
        base_signal += drift_vector

        # Introduce occasional 'Black Swan' anomalies (massive flux spikes)
        if i % 10 == 0:
            print("  [!] BLACK SWAN EVENT: Injecting massive unstructured noise.")
            base_signal += np.random.normal(loc=2.0, scale=1.5, size=1536)

        # 4. The Physics Loop
        target_coords = prism.global_resonance_broadcast(base_signal)
        excitons.ignite_excitons(target_coords)
        bursts = orchestrator.scan_manifold()

        total_bursts += len(bursts)

        # 5. Macro-State Observation
        # Calculate how much the manifold has healed/cooled vs how much it is stressed
        active_resonance = sum(d.get("resonance_accumulator", 0.0) for n, d in graph.nodes(data=True))
        collapsed_edges = sum(1 for u, v, d in graph.edges(data=True) if d.get("collapsed", False))

        print(f"  -> Macro-State | Global Resonance Load: {active_resonance:.2f}")
        print(f"  -> Topology    | Gravitational Collapses (Wormholes): {collapsed_edges}")

        time.sleep(sleep_interval)

    print("\n=== Flux Simulation Terminated ===")
    print(f"Total Threshold Bursts Captured: {total_bursts}")
    print("Manifold returning to ambient thermodynamic decay.")


if __name__ == "__main__":
    # Run 50 continuous waves, pausing for half a second between each
    # so the VS Code agent can read the telemetry output in the terminal.
    run_chaos_stream(iterations=50, sleep_interval=0.5)
