# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
import numpy as np
from blank_config import BlankManifoldConfig
from blank_manifold_core import BlankManifoldCore
from excitons import ExcitonEngine
from hippocampal import HippocampalTransducer
from latent_mediator import LatentMediator
from telemetry import OntologicalOrchestrator
from telemetry_panel import TelemetryPanel
from transducer import StatisticalPrism


def main():
    print("=== Booting Exciton-MoA Operating System ===")
    
    # 1. Initialize the pristine vacuum
    config = BlankManifoldConfig(base_node_count=1024, dimensionality=3)
    manifold = BlankManifoldCore(config)
    manifold.generate_manifold()
    mediator = LatentMediator(manifold)
    hippocampal_transducer = HippocampalTransducer()
    telemetry_panel = TelemetryPanel()

    # 2. Boot up the engines
    prism = StatisticalPrism(manifold)
    excitons = ExcitonEngine(manifold, mediator=mediator)
    orchestrator = OntologicalOrchestrator(
        manifold,
        mediator=mediator,
        hippocampal_transducer=hippocampal_transducer,
        telemetry_panel=telemetry_panel,
        manifold_id="primary",
    )

    print("\n=== Simulating Incoming 'Hello World' Data Wave ===")
    # Simulating a noisy, 1536-dimensional incoming embedding vector
    noisy_hello_world_vector = np.random.normal(loc=0.5, scale=0.2, size=1536)

    # 3. Shower the manifold with the probability field
    target_coords = prism.global_resonance_broadcast(noisy_hello_world_vector)

    # 4. Excitons physically warp the topology where the rain hits
    excitons.ignite_excitons(target_coords)

    # 5. Orchestrator looks for the Jeans Mass collapses to render the UI telemetry
    bursts = orchestrator.scan_manifold()
    
    print("\n=== Engine Cycle Complete ===")

    return bursts

if __name__ == "__main__":
    main()