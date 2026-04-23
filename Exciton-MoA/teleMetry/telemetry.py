# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
import hashlib

import numpy as np


class OntologicalOrchestrator:
    """
    The Metacognitive Spotlight for the Blank SOL Manifold.
    Continuously monitors the topology for mathematical stress, 
    triggering Threshold Bursts when the Hotspot Functional (H) exceeds tau.
    """
    def __init__(self, manifold_core, tau_threshold: float = 4.5, mediator=None, hippocampal_transducer=None, telemetry_panel=None, manifold_id: str = "primary"):
        self.manifold = manifold_core.graph
        self.base_tau = tau_threshold
        self.tau = tau_threshold
        self.mediator = mediator
        self.hippocampal_transducer = hippocampal_transducer
        self.telemetry_panel = telemetry_panel
        self.manifold_id = manifold_id
        self.adaptive_tau_enabled = True
        self.tau_floor = max(1.0, tau_threshold * 0.75)
        self.tau_percentile = 88.0
        self.tau_mad_scale = 2.0
        self.tau_smoothing = 0.35
        self.last_scan_order: list[str] = []
        self.last_scan_order_preview: list[str] = []
        self.last_scan_order_fingerprint = "none"
        
        # Functional Weights over response-compressed channels.
        self.alphas = {"density": 1.5, "shear": 1.0, "vorticity": 0.75}

    def compute_local_hotspot(self, node_id: str) -> dict[str, float]:
        """
        Calculates the 3-part Hotspot Functional H(x,t) for a specific node 
        by analyzing its immediate geodesic neighborhood.
        """
        node_data = self.manifold.nodes[node_id]
        neighbors = list(self.manifold.neighbors(node_id))
        
        if not neighbors:
            return {
                "H_total": 0.0,
                "density": 0.0,
                "density_grad": 0.0,
                "shear": 0.0,
                "shear_grad": 0.0,
                "vorticity": 0.0,
            }

        # 1. Density Gradient (Jeans Mass Collapse)
        # Measures how rapidly semantic resonance is pooling compared to neighbors
        local_res = node_data.get("resonance_accumulator", 0.0)
        neighbor_res = [self.manifold.nodes[n].get("resonance_accumulator", 0.0) for n in neighbors]
        density_grad = float(np.linalg.norm([local_res - nr for nr in neighbor_res]))
        
        # 2. Potential Shear (Epistemic Friction)
        # Prefer the solved scalar semantic potential; fall back to state-vector tension
        local_potential = float(node_data.get("semantic_potential", 0.0))
        shear_deltas = []
        for n in neighbors:
            neighbor_potential = float(self.manifold.nodes[n].get("semantic_potential", 0.0))
            shear_deltas.append(local_potential - neighbor_potential)

        shear_grad = float(np.linalg.norm(shear_deltas)) if shear_deltas else 0.0

        if shear_grad == 0.0:
            local_state = np.array(node_data.get("state_vector", np.zeros(3)))
            state_deltas = []
            for n in neighbors:
                n_state = np.array(self.manifold.nodes[n].get("state_vector", np.zeros(3)))
                state_deltas.append(float(np.linalg.norm(local_state - n_state)))

            shear_grad = float(np.linalg.norm(state_deltas)) if state_deltas else 0.0
            
        # 3. Topological Vorticity (Recursive Logic proxy)
        # For a graph, we approximate curl by checking flow imbalance around triangles/cycles
        # (Simplified to edge-weight momentum flux for real-time telemetry)
        vorticity = self._compute_local_vorticity(node_id, neighbors)

        density_signal = float(np.log1p(density_grad))
        shear_signal = float(np.log1p(shear_grad))
        vorticity_signal = float(np.log1p(vorticity))

        # The Epistemic Field Equation combines compressed tensor responses so
        # one channel cannot dominate H purely by raw scale.
        H_total = (self.alphas["density"] * density_signal) + \
                  (self.alphas["shear"] * shear_signal) + \
                  (self.alphas["vorticity"] * vorticity_signal)

        density_contrib = self.alphas["density"] * density_signal
        shear_contrib = self.alphas["shear"] * shear_signal
        vorticity_contrib = self.alphas["vorticity"] * vorticity_signal

        return {
            "H_total": float(H_total),
            "density": float(density_grad),
            "density_grad": float(density_grad),
            "density_signal": density_signal,
            "density_contrib": float(density_contrib),
            "shear": float(shear_grad),
            "shear_grad": float(shear_grad),
            "shear_signal": shear_signal,
            "shear_contrib": float(shear_contrib),
            "vorticity": float(vorticity),
            "vorticity_signal": vorticity_signal,
            "vorticity_contrib": float(vorticity_contrib),
        }

    def scan_manifold(self):
        """
        Sweeps the spotlight across the 1,024-node lattice to detect localized threshold events.
        """
        active_bursts = []

        manifold_metrics = []
        node_scan_order = [str(node_id) for node_id in self.manifold.nodes]
        self.last_scan_order = list(node_scan_order)
        self.last_scan_order_preview = list(node_scan_order[:8])
        self.last_scan_order_fingerprint = hashlib.sha256("|".join(node_scan_order).encode("utf-8")).hexdigest()[:16] if node_scan_order else "none"
        for node_id in node_scan_order:
            metrics = self.compute_local_hotspot(node_id)
            manifold_metrics.append((node_id, metrics))

        h_values = [metrics["H_total"] for _, metrics in manifold_metrics]
        self.tau = self._compute_adaptive_tau(h_values)
        self.manifold.graph["adaptive_tau"] = self.tau
        self.manifold.graph["manifold_id"] = self.manifold_id

        for node_id, metrics in manifold_metrics:
            metrics["tau_threshold"] = self.tau
            if metrics["H_total"] >= self.tau:
                active_bursts.append((node_id, metrics))
                
        if active_bursts:
            self._enrich_bursts(active_bursts)
            self._trigger_threshold_burst(active_bursts)

        self._render_telemetry_panel(active_bursts, h_values)
            
        return active_bursts

    def _trigger_threshold_burst(self, bursts: list[tuple[str, dict]]):
        """
        The Holographic UI Event. Routes rendering compute to the collapsing 
        basins and signals the Hippocampal transducer to unroll the n+1 tape.
        """
        print(f"\n[ORCHESTRATOR ALERT] {len(bursts)} Threshold Bursts Detected! | Adaptive Tau: {self.tau:.3f}")
        
        for node_id, metrics in bursts:
            print(f"  -> Spotlighting Node {node_id} | H-Score: {metrics['H_total']:.3f}")
            print(f"     * Gravity Well (Density): {metrics['density_grad']:.3f}")
            print(f"     * Chromatic Shear (Friction): {metrics['shear_grad']:.3f}")
            print(f"     * Magnetic Flux (Vorticity): {metrics['vorticity']:.3f}")
            print(
                "     * Contribution Vector: "
                f"density={metrics['density_contrib']:.3f} "
                f"shear={metrics['shear_contrib']:.3f} "
                f"vorticity={metrics['vorticity_contrib']:.3f}"
            )
            print(
                "     * Signal Vector: "
                f"density={metrics['density_signal']:.3f} "
                f"shear={metrics['shear_signal']:.3f} "
                f"vorticity={metrics['vorticity_signal']:.3f}"
            )
            
            # Here we would fire the callback to the Hippocampal sequence buffer
            # to begin transcribing the output tape for this specific node cluster.

        if self.hippocampal_transducer is not None:
            burst_path = self.hippocampal_transducer.capture_bursts(bursts, self.manifold)
            if burst_path is not None:
                print(f"  -> Hippocampal burst archived to {burst_path}")

    def _compute_local_vorticity(self, node_id: str, neighbors: list[str]) -> float:
        vorticity = 0.0
        cycle_count = 0
        for index, left_neighbor in enumerate(neighbors):
            for right_neighbor in neighbors[index + 1:]:
                if not self.manifold.has_edge(left_neighbor, right_neighbor):
                    continue

                cycle_edges = [
                    (node_id, left_neighbor),
                    (left_neighbor, right_neighbor),
                    (right_neighbor, node_id),
                ]
                cycle_flux = 0.0
                for edge_start, edge_end in cycle_edges:
                    cycle_flux += abs(float(self.manifold[edge_start][edge_end].get("residual_flux", 0.0)))

                vorticity += cycle_flux / len(cycle_edges)
                cycle_count += 1

        if cycle_count == 0:
            return 0.0

        return float(np.log1p(vorticity / cycle_count))

    def _enrich_bursts(self, bursts: list[tuple[str, dict]]):
        for node_id, metrics in bursts:
            if self.mediator is not None:
                self.mediator.publish_consensus(node_id)

            node = self.manifold.nodes[node_id]
            metrics["dominant_giant"] = node.get("dominant_giant")
            metrics["consensus_clock"] = node.get("consensus_clock")
            metrics["consensus_entropy"] = float(node.get("consensus_entropy", 0.0))

    def _compute_adaptive_tau(self, h_values: list[float]) -> float:
        if not h_values:
            return self.base_tau

        values = np.asarray(h_values, dtype=float)
        median = float(np.median(values))
        mad = float(np.median(np.abs(values - median)))
        robust_sigma = 1.4826 * mad
        percentile_tau = float(np.percentile(values, self.tau_percentile))
        robust_tau = median + (self.tau_mad_scale * robust_sigma)
        target_tau = max(self.tau_floor, self.base_tau, percentile_tau, robust_tau)

        if not self.adaptive_tau_enabled:
            return self.base_tau

        if self.tau is None:
            return target_tau

        return float(((1.0 - self.tau_smoothing) * self.tau) + (self.tau_smoothing * target_tau))

    def _render_telemetry_panel(self, bursts: list[tuple[str, dict]], h_values: list[float]):
        if self.telemetry_panel is None:
            return

        avg_h = float(np.mean(h_values)) if h_values else 0.0
        max_h = float(np.max(h_values)) if h_values else 0.0
        self.telemetry_panel.record_scan(
            manifold_id=self.manifold_id,
            adaptive_tau=self.tau,
            burst_count=len(bursts),
            avg_h=avg_h,
            max_h=max_h,
            bursts=bursts,
        )
        recent_history = self.telemetry_panel.load_recent_history(self.manifold_id)
        print(self.telemetry_panel.render(self.manifold_id, bursts, history=recent_history))