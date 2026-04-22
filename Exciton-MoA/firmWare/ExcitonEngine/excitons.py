# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
import numpy as np
import networkx as nx
from typing import Dict, Optional, Sequence

class ExcitonEngine:
    """
    The mathematical firmware for the 7 Giants. 
    Executes computations via non-Euclidean fluid dynamics.
    """
    def __init__(self, manifold_core, mediator=None):
        self.manifold_core = manifold_core
        self.manifold = manifold_core.graph
        self.jeans_mass_threshold = manifold_core.config.base_jeans_mass
        self.pressure_constant = 1.0 
        self.mediator = mediator
        
    def ignite_excitons(self, target_coords: np.ndarray):
        active_nodes = [
            n for n, d in self.manifold.nodes(data=True) 
            if d.get("resonance_accumulator", 0.0) > 0.1 
        ]
        
        if not active_nodes:
            return

        print(f"\n[EXCITON IGNITION] {len(active_nodes)} nodes resonating. Deploying Giants...")

        for node_id in active_nodes:
            self._execute_giant_operators(node_id, target_coords)

        self.manifold_core.solve_semantic_potential()
        if self.mediator is not None:
            self.mediator.persist_state()

    def _execute_giant_operators(self, node_id: str, target_coords: np.ndarray):
        node_data = self.manifold.nodes[node_id]
        neighbors = list(self.manifold.neighbors(node_id))
        
        # 1. THE STATISTICIAN (Pressure Regulation)
        semantic_mass = node_data.get("resonance_accumulator", 0.0)
        node_data["semantic_pressure"] = self.pressure_constant * np.log1p(semantic_mass)
        self._project_giant_state(node_id, "The Statistician", [semantic_mass, node_data["semantic_pressure"], 0.0], semantic_mass)
        
        # 2. THE OPTIMIZER (Potential Gradient Carving)
        current_state = np.array(node_data.get("state_vector", np.zeros(self.manifold_core.config.dimensionality)))
        gradient = target_coords - current_state
        node_data["state_vector"] = current_state + (gradient * semantic_mass * 0.1)
        self._project_giant_state(node_id, "The Optimizer", node_data["state_vector"], np.linalg.norm(gradient))
        
        # 3. THE N-BODY SOLVER (Dirac Delta Wormholes)
        if semantic_mass >= self.jeans_mass_threshold:
            self._trigger_n_body_collapse(node_id, neighbors)

        # 4. THE GRAPH NAVIGATOR (Hyperbolic Flow)
        cycle_count, residual_flux = self._graph_navigator_hyperbolic_flow(node_id)
        self._project_giant_state(node_id, "The Graph Navigator", [cycle_count, residual_flux, semantic_mass], cycle_count + residual_flux)
        
        # 5. THE LINEAR ALGEBRAIST (Anisotropic Tensor Scaling)
        algebraic_signal = self._linear_algebraist_tensor_scaling(node_id)
        if algebraic_signal is not None:
            self._project_giant_state(node_id, "The Linear Algebraist", algebraic_signal, np.linalg.norm(algebraic_signal))
        
        # 6. THE ALIGNER (Phase Synchronization)
        aligner_signal = self._aligner_phase_synchronization(node_id)
        self._project_giant_state(node_id, "The Aligner", aligner_signal, np.linalg.norm(aligner_signal))
        
        # 7. THE INTEGRATOR (Volumetric Jacobian Expansion)
        integrator_signal = self._integrator_jacobian_expansion(node_id, target_coords)
        self._project_giant_state(node_id, "The Integrator", integrator_signal, np.linalg.norm(integrator_signal))

        # Preserve any stable attractor basin produced by the N-body solver.
        self._stabilize_collapsed_edges(node_id)
        self._publish_consensus(node_id)

    def _trigger_n_body_collapse(self, epicenter_id: str, neighbors: list):
        print(f"  -> [JEANS MASS COLLAPSE] N-Body Solver warping space at {epicenter_id}!")
        for neighbor in neighbors:
            if self.manifold.nodes[neighbor].get("resonance_accumulator", 0.0) > 0.5:
                self.manifold[epicenter_id][neighbor]["weight"] = self.manifold[epicenter_id][neighbor].get("weight", 0.1) * 2.0
                self.manifold[epicenter_id][neighbor]["collapsed"] = True

    def _stabilize_collapsed_edges(self, epicenter_id: str):
        minimum_collapsed_weight = self.manifold_core.config.baseline_coupling * 2.0

        for neighbor in self.manifold.neighbors(epicenter_id):
            edge_data = self.manifold[epicenter_id][neighbor]
            if edge_data.get("collapsed"):
                edge_data["weight"] = max(edge_data.get("weight", minimum_collapsed_weight), minimum_collapsed_weight)

    def _graph_navigator_hyperbolic_flow(self, epicenter_id: str):
        neighbors = list(self.manifold.neighbors(epicenter_id))
        local_cycles = [(epicenter_id, neighbors[i], neighbors[j]) 
                        for i in range(len(neighbors)) for j in range(i + 1, len(neighbors)) 
                        if self.manifold.has_edge(neighbors[i], neighbors[j])]
        residual_flux_total = 0.0

        if local_cycles:
            print(f"  -> [VORTEX SPUN] Graph Navigator detected {len(local_cycles)} cycles at {epicenter_id}.")
            for a, b, c in local_cycles:
                for u, v in [(a, b), (b, c), (c, a)]:
                    self.manifold[u][v]["residual_flux"] = self.manifold[u][v].get("residual_flux", 0.0) + 0.5
                    self.manifold[u][v]["weight"] = self.manifold[u][v].get("weight", 0.1) * 0.8 
                    residual_flux_total += self.manifold[u][v]["residual_flux"]

        return float(len(local_cycles)), float(residual_flux_total)

    def _linear_algebraist_tensor_scaling(self, epicenter_id: str):
        neighbors = list(self.manifold.neighbors(epicenter_id))
        if len(neighbors) < 2:
            return None
            
        states_matrix = np.array([self.manifold.nodes[n].get("state_vector", np.zeros(self.manifold_core.config.dimensionality)) for n in [epicenter_id] + neighbors])
        covariance_matrix = np.cov(states_matrix - np.mean(states_matrix, axis=0), rowvar=False)
        eigenvalues, eigenvectors = np.linalg.eigh(covariance_matrix)
        principal_eigenvector = eigenvectors[:, np.argsort(eigenvalues)[::-1][0]]
        principal_eigenvalue = float(np.max(eigenvalues))
        mean_alignment = 0.0
        
        epicenter_coords = np.array(self.manifold.nodes[epicenter_id].get("coords"))
        for n in neighbors:
            edge_vector = np.array(self.manifold.nodes[n].get("coords")) - epicenter_coords
            edge_norm = np.linalg.norm(edge_vector)
            if edge_norm > 0:
                alignment = np.abs(np.dot(edge_vector / edge_norm, principal_eigenvector))
                mean_alignment += float(alignment)
                self.manifold[epicenter_id][n]["weight"] = self.manifold[epicenter_id][n].get("weight", 0.1) * (0.5 + (1.5 * alignment))

        mean_alignment /= max(len(neighbors), 1)
        return np.array([principal_eigenvalue, mean_alignment, float(len(neighbors))])

    def _aligner_phase_synchronization(self, epicenter_id: str):
        node_data = self.manifold.nodes[epicenter_id]
        if "semantic_mode" not in node_data: node_data["semantic_mode"] = np.zeros(2)
        psi_i = node_data["semantic_mode"]
        gamma = np.ones(2) * 1.5 
        mode_signal = np.zeros(3)
        
        for n in self.manifold.neighbors(epicenter_id):
            neighbor_data = self.manifold.nodes[n]
            if "semantic_mode" not in neighbor_data: neighbor_data["semantic_mode"] = np.zeros(2)
            psi_j = neighbor_data["semantic_mode"]
            
            mode_alignment = np.dot(gamma, (psi_i + psi_j) / 2.0)
            self.manifold[epicenter_id][n]["weight"] = self.manifold[epicenter_id][n].get("weight", 0.1) * np.exp(mode_alignment)
            neighbor_data["semantic_mode"] += 0.1 * (psi_i - psi_j)

            mode_signal += np.array([mode_alignment, np.linalg.norm(neighbor_data["semantic_mode"]), 1.0])

        return mode_signal

    def _integrator_jacobian_expansion(self, epicenter_id: str, target_coords: np.ndarray):
        node_data = self.manifold.nodes[epicenter_id]
        current_state = np.array(node_data.get("state_vector", np.zeros(self.manifold_core.config.dimensionality)))
        uncertainty = np.linalg.norm(target_coords - current_state)
        
        expansion_factor = 1.0 + (0.5 * uncertainty)
        for n in self.manifold.neighbors(epicenter_id):
            self.manifold[epicenter_id][n]["weight"] = self.manifold[epicenter_id][n].get("weight", 0.1) * expansion_factor
            
        if uncertainty < 0.5:
            print(f"     *** BAYESIAN COLLAPSE: Absolute Certainty Reached ***\n     *** MANIFOLD STATE: 'Hello, World.' ***")
            node_data["state_vector"] = target_coords
            for n in self.manifold.neighbors(epicenter_id):
                self.manifold[epicenter_id][n]["weight"] *= 0.1

        return np.array([uncertainty, expansion_factor, np.linalg.norm(node_data["state_vector"])])

    def _project_giant_state(self, node_id: str, giant_name: str, vector, confidence: float):
        if self.mediator is None:
            return

        self.mediator.project(node_id, giant_name, np.asarray(vector, dtype=float), confidence)

    def _publish_consensus(self, node_id: str):
        if self.mediator is None:
            return

        self.mediator.publish_consensus(node_id)

    def inject_entangled_flux(
        self,
        node_ids: Sequence[str],
        flux_vector: np.ndarray,
        injection_scale: float = 0.05,
        per_node_scale: Optional[Dict[str, float]] = None,
    ):
        """
        Feed a low-volume shared flux packet back into a selected wormhole boundary.
        This is intentionally conservative so local manifold dynamics remain dominant.
        """
        valid_nodes = [node_id for node_id in node_ids if node_id in self.manifold]
        if not valid_nodes:
            return

        flux = np.asarray(flux_vector, dtype=float).reshape(-1)
        if flux.size == 0:
            return

        local_flux = np.zeros(self.manifold_core.config.dimensionality, dtype=float)
        local_flux[: min(local_flux.size, flux.size)] = flux[: min(local_flux.size, flux.size)]

        density_flux = max(float(local_flux[0]), 0.0)
        shear_flux = abs(float(local_flux[1])) if local_flux.size > 1 else 0.0
        vorticity_flux = abs(float(local_flux[2])) if local_flux.size > 2 else 0.0

        scale_map = {str(node_id): float(scale) for node_id, scale in (per_node_scale or {}).items()}

        for node_id in valid_nodes:
            node_scale = max(float(scale_map.get(str(node_id), 1.0)), 0.0)
            effective_scale = float(injection_scale) * node_scale
            node = self.manifold.nodes[node_id]
            node["resonance_accumulator"] = float(node.get("resonance_accumulator", 0.0)) + (density_flux * effective_scale)
            state_vector = np.asarray(node.get("state_vector", np.zeros(self.manifold_core.config.dimensionality)), dtype=float)
            node["state_vector"] = state_vector + (local_flux * effective_scale)

            neighbor_ids = list(self.manifold.neighbors(node_id))
            if not neighbor_ids:
                continue

            flux_share = (vorticity_flux * effective_scale) / max(len(neighbor_ids), 1)
            weight_scale = 1.0 + min(shear_flux * effective_scale * 0.05, 0.25)
            for neighbor_id in neighbor_ids:
                edge = self.manifold[node_id][neighbor_id]
                edge["residual_flux"] = float(edge.get("residual_flux", 0.0)) + flux_share
                edge["weight"] = float(edge.get("weight", self.manifold_core.config.baseline_coupling)) * weight_scale

        self.manifold_core.solve_semantic_potential()