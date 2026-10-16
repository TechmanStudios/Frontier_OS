"""
Frontier_OS: Hippocampal Cognitive Circuit Cache & Consolidation Bridge
File: Frontier_OS/core/metacognition/circuit_cache.py

Provides long-term crystallized topological memory for synthesized Riemannian circuits.
Integrates with the HippocampalMemorySink:
1. Absorbs Carnot dissipative energy from continuous circuit executions.
2. Caches verified circuit geometries for instant O(1) recall during multi-step reasoning.
3. Coordinates Dream Cycle consolidation preserving >= 95% pairwise geodesic correlation.
"""

from dataclasses import dataclass, field
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from sol.kernel.synthesis.circuit_topology import SelfAssembledCircuit
from sol.kernel.synthesis.circuit_synthesizer import TruthTableSpec
from Frontier_OS.core.hippocampal_sink import HippocampalMemorySink, DreamConsolidationReport


@dataclass
class CachedCircuitEntry:
    """Represents a crystallized circuit stored in the Hippocampal memory sink."""
    spec_name: str
    circuit: SelfAssembledCircuit
    creation_timestamp_ms: float
    access_count: int = 0
    total_energy_absorbed: float = 0.0
    is_consolidated: bool = False


class HippocampalCircuitCache:
    """
    Manages long-term crystallized circuit topology and links circuit execution
    telemetry to the HippocampalMemorySink for Dream Cycle consolidation.
    """
    def __init__(
        self,
        hippocampal_sink: Optional[HippocampalMemorySink] = None,
        storage_dir: Optional[Path | str] = None,
        min_geodesic_preservation: float = 0.95
    ):
        self.min_geodesic_preservation = min_geodesic_preservation
        self.sink = hippocampal_sink or HippocampalMemorySink(
            ambient_dim=4,
            compressed_dim=2,
            storage_dir=storage_dir,
            min_preservation_ratio=min_geodesic_preservation,
            enthalpy_limit=300.0,
            auto_dream_flush=False  # Managed explicitly or via threshold
        )
        self.cache: Dict[str, CachedCircuitEntry] = {}
        self.last_consolidation_report: Optional[DreamConsolidationReport] = None

    def store_circuit(
        self,
        spec_name: str,
        circuit: SelfAssembledCircuit
    ) -> CachedCircuitEntry:
        """Stores a verified circuit into the cache and records its nodes in the sink."""
        entry = CachedCircuitEntry(
            spec_name=spec_name,
            circuit=circuit,
            creation_timestamp_ms=time.time() * 1000.0,
            access_count=1,
            is_consolidated=False
        )
        self.cache[spec_name] = entry

        # Register circuit nodes and metrics into hippocampal sink
        for nid, node in circuit.nodes.items():
            # Pad 2D coords to 4D ambient if required by sink
            padded_coords = np.zeros(self.sink.ambient_dim, dtype=np.float64)
            padded_coords[:2] = node.coords

            # 4D metric tensor (block diagonal with local 2x2 metric)
            g_4d = np.eye(self.sink.ambient_dim, dtype=np.float64)
            g_4d[:2, :2] = node.compute_local_metric()

            self.sink.node_coordinates[f"{spec_name}_{nid}"] = padded_coords
            self.sink.node_metrics[f"{spec_name}_{nid}"] = g_4d

        return entry

    def get_circuit(self, spec_name: str) -> Optional[SelfAssembledCircuit]:
        """Retrieves a cached circuit by specification name."""
        if spec_name in self.cache:
            entry = self.cache[spec_name]
            entry.access_count += 1
            return entry.circuit
        return None

    def record_execution_dissipation(
        self,
        spec_name: str,
        dissipated_energy: float
    ) -> None:
        """Records Carnot dissipation from a circuit execution run."""
        if spec_name in self.cache:
            entry = self.cache[spec_name]
            entry.total_energy_absorbed += dissipated_energy
            n_nodes = len(entry.circuit.nodes)
            if n_nodes > 0:
                per_node_e = dissipated_energy / n_nodes
                for nid in entry.circuit.nodes:
                    node_key = f"{spec_name}_{nid}"
                    self.sink.node_absorbed_energy[node_key] = (
                        self.sink.node_absorbed_energy.get(node_key, 0.0) + per_node_e
                    )
        self.sink.record_dissipation(dissipated_energy)

    def trigger_consolidation(self, pair_id: str = "cognitive-orchestrator-dream") -> Optional[DreamConsolidationReport]:
        """
        Executes a Dream Cycle memory consolidation across all cached circuit topologies.
        Verifies the >= 95% geodesic correlation invariant.
        """
        if len(self.sink.node_coordinates) < 3:
            return None

        report = self.sink.execute_dream_cycle(pair_id=pair_id)
        self.last_consolidation_report = report

        for entry in self.cache.values():
            entry.is_consolidated = True

        return report

    def clear(self) -> None:
        """Clears all cached circuits."""
        self.cache.clear()
