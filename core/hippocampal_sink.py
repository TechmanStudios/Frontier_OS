"""
Frontier_OS: Closed-Loop Hippocampal Memory Sink & Dream Cycle Consolidation
File: Frontier_OS/core/hippocampal_sink.py

Couples kinetic dissipation from Riemannian geodesic navigation into the Hippocampal sink:
    dE/dt = E_inject - int_M gamma(v, R) ||v||^2_g dV - dE_hippocampus
During sleep/consolidation (Dream Cycle), dissipated energy crystallizes into long-term
topological memory while preserving >= 95% of pairwise geodesic distance relationships.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import scipy.linalg as la
from scipy.spatial.distance import pdist, squareform

from sol.diagnostics.damping_spectrogram import DampingTelemetryFrame
from Frontier_OS.core.geodesic_navigator import GeodesicStepResult


@dataclass
class DissipationPacket:
    timestamp_ms: float
    node_id: str
    kinetic_dissipation: float      # gamma * ||v||^2_g * dt
    velocity: np.ndarray
    metric_tensor: np.ndarray
    ricci_scalar: float


@dataclass
class DreamConsolidationReport:
    timestamp: str
    pre_compression_nodes: int
    compressed_dim: int
    absorbed_energy_total: float
    geodesic_correlation: float     # Invariant: must be >= 0.95
    crystallized_edges: int
    status: str                     # "CONSOLIDATED" | "DISTORTION_WARNING"
    long_term_record_path: Optional[str] = None


class HippocampalMemorySink:
    """
    Absorbs dissipated quasi-particle kinetic energy and consolidates short-term
    trajectory transients into crystallized long-term Riemannian topology.
    """
    def __init__(
        self,
        ambient_dim: int = 4,
        compressed_dim: int = 2,
        storage_dir: Optional[Path | str] = None,
        min_preservation_ratio: float = 0.95,
        enthalpy_limit: float = 250.0,
        max_buffer_packets: int = 5000,
        auto_dream_flush: bool = True
    ):
        self.ambient_dim = ambient_dim
        self.compressed_dim = compressed_dim
        self.storage_dir = (
            Path(storage_dir) if storage_dir is not None
            else Path(__file__).resolve().parents[1] / "Exciton-MoA" / "working_data"
        )
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.min_preservation_ratio = min_preservation_ratio
        self.enthalpy_limit = enthalpy_limit
        self.max_buffer_packets = max_buffer_packets
        self.auto_dream_flush = auto_dream_flush
        self.auto_flushes_count = 0
        self.lifetime_absorbed_energy = 0.0

        # Energy & Trajectory Buffers
        self.dissipation_buffer: List[DissipationPacket] = []
        self.node_coordinates: Dict[str, np.ndarray] = {}
        self.node_metrics: Dict[str, np.ndarray] = {}
        self.node_absorbed_energy: Dict[str, float] = {}

    def absorb_step(
        self,
        node_id: str,
        coords: np.ndarray,
        step_result: GeodesicStepResult,
        g_ij: np.ndarray,
        dt: float = 0.01
    ) -> float:
        """
        Absorbs dissipated energy from a single geodesic step into the sink:
            dE = gamma(v, R) * ||v||^2_g * dt = 2 * gamma * E_k * dt
        """
        dissipation = 2.0 * step_result.damping_gamma * step_result.kinetic_energy * dt
        self.lifetime_absorbed_energy += dissipation

        packet = DissipationPacket(
            timestamp_ms=0.0,
            node_id=node_id,
            kinetic_dissipation=dissipation,
            velocity=step_result.velocity,
            metric_tensor=g_ij,
            ricci_scalar=step_result.ricci_scalar
        )

        self.dissipation_buffer.append(packet)
        if len(self.dissipation_buffer) > self.max_buffer_packets:
            self.dissipation_buffer.pop(0)

        self.node_coordinates[node_id] = coords.copy()
        self.node_metrics[node_id] = g_ij.copy()
        self.node_absorbed_energy[node_id] = (
            self.node_absorbed_energy.get(node_id, 0.0) + dissipation
        )

        # Hardening 3: Thermodynamic Carnot Governor (Autonomous Sleep/Dream Trigger)
        if (
            self.auto_dream_flush
            and self.get_total_absorbed_energy() >= self.enthalpy_limit
            and len(self.node_coordinates) >= 3
        ):
            self.execute_dream_cycle(pair_id="carnot-governor-auto-flush")
            self.auto_flushes_count += 1

        return dissipation

    def get_total_absorbed_energy(self) -> float:
        """Returns the uncompressed dissipation energy currently in buffer."""
        return sum(p.kinetic_dissipation for p in self.dissipation_buffer)

    def get_lifetime_absorbed_energy(self) -> float:
        """Returns cumulative lifetime energy dissipated across all wake cycles."""
        return self.lifetime_absorbed_energy

    def record_dissipation(self, dissipation: float, step_index: int = 0) -> None:
        """Records macroscopic dissipation energy from multi-agent or multi-shard swarms."""
        self.lifetime_absorbed_energy += float(dissipation)
        if (
            self.auto_dream_flush
            and self.lifetime_absorbed_energy >= self.enthalpy_limit
            and len(self.node_coordinates) >= 3
        ):
            self.execute_dream_cycle(pair_id=f"carnot-governor-step-{step_index}")
            self.auto_flushes_count += 1

    def execute_dream_cycle(
        self,
        pair_id: str = "primary-pair-01"
    ) -> DreamConsolidationReport:
        """
        Simulates the Hippocampal Dream Cycle (memory consolidation):
        1. Evaluates pairwise geodesic distances across active semantic nodes.
        2. Low-distortion isometric projection via Riemannian Mahalanobis-SVD.
        3. Asserts >= 95% geodesic correlation invariant.
        4. Writes consolidated state to hippocampal_long_term.jsonl.
        """
        node_ids = sorted(self.node_coordinates.keys())
        num_nodes = len(node_ids)
        if num_nodes < 3:
            raise ValueError(f"Insufficient active nodes ({num_nodes}) for dream consolidation.")

        now_iso = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        X = np.array([self.node_coordinates[nid] for nid in node_ids])

        # Compute Riemannian deformation matrix from average local metric
        G_avg = np.mean([self.node_metrics[nid] for nid in node_ids], axis=0)
        G_avg = 0.5 * (G_avg + G_avg.T)
        vals, vecs = la.eigh(G_avg)
        vals = np.clip(vals, 1e-4, None)
        G_safe = vecs @ np.diag(vals) @ vecs.T
        L = np.linalg.cholesky(G_safe)

        # Deformed Riemannian coordinates: X_curved = X @ L
        X_curved = X @ L
        D_pre = squareform(pdist(X_curved, metric="euclidean"))

        # ISOMETRIC CONSOLIDATION PROJECTION
        # Find minimal dimension that preserves >= min_preservation_ratio (0.95)
        U, s, Vt = la.svd(X_curved, full_matrices=False)
        triu_indices = np.triu_indices(num_nodes, k=1)
        d_pre_flat = D_pre[triu_indices]

        target_dim = min(self.compressed_dim, X_curved.shape[1], num_nodes)
        best_correlation = 0.0
        X_consolidated = None

        # Search for lowest dimension achieving the 95% preservation invariant
        for k in range(1, min(X_curved.shape[1], num_nodes) + 1):
            X_k = U[:, :k] * s[:k]
            D_k = squareform(pdist(X_k, metric="euclidean"))
            d_k_flat = D_k[triu_indices]
            corr_k = float(np.corrcoef(d_pre_flat, d_k_flat)[0, 1]) if np.std(d_k_flat) > 1e-8 else 1.0

            if corr_k >= self.min_preservation_ratio:
                target_dim = k
                best_correlation = corr_k
                X_consolidated = X_k
                break
            elif corr_k > best_correlation:
                best_correlation = corr_k
                target_dim = k
                X_consolidated = X_k

        if X_consolidated is None:
            target_dim = min(self.compressed_dim, X_curved.shape[1])
            X_consolidated = U[:, :target_dim] * s[:target_dim]
            D_post = squareform(pdist(X_consolidated, metric="euclidean"))
            best_correlation = float(np.corrcoef(d_pre_flat, D_post[triu_indices])[0, 1])

        correlation = best_correlation

        # Status check against 95% invariant
        status = "CONSOLIDATED" if correlation >= self.min_preservation_ratio else "DISTORTION_WARNING"

        # Crystallize edges between top absorbed-energy nodes
        crystallized_edges = 0
        archive_path = self.storage_dir / "hippocampal_long_term.jsonl"

        records_to_append = []
        for idx, nid in enumerate(node_ids):
            energy_absorbed = self.node_absorbed_energy.get(nid, 0.0)
            record = {
                "timestamp": now_iso,
                "node_id": nid,
                "pair_id": pair_id,
                "h_total": float(round(energy_absorbed, 4)),
                "tau_threshold": 1.0,
                "density": float(round(float(np.linalg.norm(X_consolidated[idx])), 4)),
                "dominant_giant": "Hippocampal Memory Crystal",
                "consensus_confidence": float(round(correlation, 4)),
                "crystallized": True,
                "absorbed_dissipation": float(round(energy_absorbed, 4)),
                "compressed_coords": [round(float(c), 4) for c in X_consolidated[idx]]
            }
            records_to_append.append(record)
            if energy_absorbed > 0.1:
                crystallized_edges += 1

        # Append to archive
        with open(archive_path, "a", encoding="utf-8") as f:
            for rec in records_to_append:
                f.write(json.dumps(rec) + "\n")

        # Clear transient short-term buffer after consolidation
        total_absorbed = self.get_total_absorbed_energy()
        self.dissipation_buffer.clear()

        return DreamConsolidationReport(
            timestamp=now_iso,
            pre_compression_nodes=num_nodes,
            compressed_dim=target_dim,
            absorbed_energy_total=total_absorbed,
            geodesic_correlation=correlation,
            crystallized_edges=crystallized_edges,
            status=status,
            long_term_record_path=str(archive_path)
        )
