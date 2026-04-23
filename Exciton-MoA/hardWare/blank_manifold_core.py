# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
from typing import Any

import networkx as nx
import numpy as np
from blank_config import BlankManifoldConfig


class BlankManifoldCore:
    """
    Constructs a pristine, unweighted SOL manifold substrate.
    Provides a uniformly distributed lattice (e.g. hyperbolic) with baseline coupling
    and physics, serving as a blank slate for MoA architectures or data streams.
    """
    def __init__(self, config: BlankManifoldConfig | None = None, seed: int | None = None):
        self.config = config or BlankManifoldConfig()
        self.seed = None if seed is None else int(seed)
        self.rng = np.random.default_rng(self.seed)
        self.graph = nx.Graph()
        self.nodes_data: dict[str, dict[str, Any]] = {}
        
    def generate_manifold(self):
        """
        Generates the blank manifold topology according to the config parameters.
        Returns the populated NetworkX graph.
        """
        print(f"Initializing blank manifold substrate with {self.config.base_node_count} nodes...")
        
        # 1. Distribute Nodes
        self._distribute_nodes()
        
        # 2. Establish Baseline Topology (Edges)
        self._build_edges()
        
        print(f"Manifold Generation Complete. Nodes: {self.graph.number_of_nodes()}, Edges: {self.graph.number_of_edges()}")
        return self.graph

    def _distribute_nodes(self):
        """
        Uniformly distributes nodes across the specified topology without semantic weighting.
        """
        if self.config.topology_type == "hyperbolic_uniform":
            # For a Poincare disk/hyperbolic model, we distribute nodes uniformly 
            # with respecting the non-Euclidean expansion (using polar coordinates).
            # Radius (r) mapped exponentially to maintain uniform density in hyperbolic space.
            
            for i in range(self.config.base_node_count):
                node_id = f"node_{i:04d}"
                
                # Random uniform angle
                theta = self.rng.uniform(0.0, 2.0 * np.pi)
                
                # Inverse transform sampling for uniform distribution in hyperbolic disc
                # For radius R = 1, sinh(r) distribution limits
                max_radius_hyperbolic = 2.0  # arbitrary bounding radius in hyperbolic space
                u = self.rng.uniform(0.0, 1.0)
                # Derived from integral of sinh(r)
                r = np.arccosh(1 + u * (np.cosh(max_radius_hyperbolic) - 1))
                
                # Convert back to Cartesian for internal representation if needed
                # (Assuming 2D for simplicity of initialization, can expand to config.dimensionality)
                x = r * np.cos(theta)
                y = r * np.sin(theta)
                
                coords = [x, y]
                # Pad remaining dimensions with 0s or random small variance
                while len(coords) < self.config.dimensionality:
                     coords.append(float(self.rng.normal(0.0, 0.1)))
                     
                self.nodes_data[node_id] = {
                    "coords": coords,
                    "mass": self.config.base_jeans_mass,
                    "state_vector": np.zeros(self.config.dimensionality), # Blank semantic vector
                    "resonance_accumulator": 0.0,
                    "semantic_potential": 0.0,
                    "flux_divergence": 0.0,
                }
                self.graph.add_node(node_id, **self.nodes_data[node_id])
                
        else:
             raise NotImplementedError(f"Topology '{self.config.topology_type}' not yet implemented for Blank Manifold.")

    def _build_edges(self):
        """
        Connects nodes based purely on spatial proximity within the topology.
        Assigns the baseline_coupling strength to all edges.
        """
        # For a substrate, we typically want a k-nearest neighbor (k-NN) or a Delaunay-like structure.
        # We will use a basic spatial threshold to establish connections.
        nodes = list(self.graph.nodes(data=True))
        
        # Simple thresholding calculation (O(N^2) - suitable for 1024 nodes)
        # Calculate max distance to ensure a connected graph, or use a fixed threshold.
        # For hyperbolic uniform with max radius 2.0, a connection distance of ~0.5 usually yields a sensible lattice.
        connection_threshold = 0.5 
        
        for i, (node_a, data_a) in enumerate(nodes):
            coords_a = np.array(data_a["coords"])
            for j in range(i + 1, len(nodes)):
                node_b, data_b = nodes[j]
                coords_b = np.array(data_b["coords"])
                
                # Euclidean distance in embedded space 
                # (True hyperbolic distance is slightly more complex: arccosh(1 + 2*||x-y||^2 / ((1-||x||^2)(1-||y||^2))) )
                # But for initialization seeding, euclidean in the embedding coords is acceptable to build the base mesh
                dist = np.linalg.norm(coords_a - coords_b)
                
                if dist < connection_threshold:
                    self.graph.add_edge(
                        node_a, node_b, 
                        weight=self.config.baseline_coupling,
                        distance=dist
                    )
        
        # Ensure Graph is connected. If we have isolates, we could optionally connect them to nearest neighbor
        isolates = list(nx.isolates(self.graph))
        if isolates:
             print(f"Warning: Connection threshold yielded {len(isolates)} isolated nodes. Repairing connectivity.")
             self._connect_isolates(isolates)

        if not nx.is_connected(self.graph):
            self._connect_components()

    def _connect_isolates(self, isolates: list[str]):
        """
        Ensures isolated nodes are attached to their nearest neighbor so the
        substrate remains traversable for downstream operators and tests.
        """
        for node_id in sorted(isolates):
            coords = np.array(self.graph.nodes[node_id]["coords"])
            nearest_node = None
            nearest_distance = float("inf")

            for candidate_id, data in sorted(self.graph.nodes(data=True), key=lambda item: str(item[0])):
                if candidate_id == node_id:
                    continue

                candidate_coords = np.array(data["coords"])
                distance = float(np.linalg.norm(coords - candidate_coords))
                if distance < nearest_distance or (
                    np.isclose(distance, nearest_distance) and nearest_node is not None and str(candidate_id) < str(nearest_node)
                ):
                    nearest_distance = distance
                    nearest_node = candidate_id

            if nearest_node is not None:
                self.graph.add_edge(
                    node_id,
                    nearest_node,
                    weight=self.config.baseline_coupling,
                    distance=nearest_distance,
                    repaired=True,
                )

    def _connect_components(self):
        """
        Connects disconnected components by linking the closest pair of nodes
        across neighboring components until the graph becomes fully connected.
        """
        components = [sorted(component) for component in nx.connected_components(self.graph)]
        components.sort(key=lambda component: tuple(str(node_id) for node_id in component))
        while len(components) > 1:
            left = components[0]
            right = components[1]
            best_pair: tuple[str, str] | None = None
            best_distance = float("inf")

            for left_node in left:
                left_coords = np.array(self.graph.nodes[left_node]["coords"])
                for right_node in right:
                    right_coords = np.array(self.graph.nodes[right_node]["coords"])
                    distance = float(np.linalg.norm(left_coords - right_coords))
                    candidate_pair = (str(left_node), str(right_node))
                    if distance < best_distance or (
                        np.isclose(distance, best_distance)
                        and best_pair is not None
                        and candidate_pair < (str(best_pair[0]), str(best_pair[1]))
                    ):
                        best_distance = distance
                        best_pair = (left_node, right_node)

            if best_pair is None:
                break

            self.graph.add_edge(
                best_pair[0],
                best_pair[1],
                weight=self.config.baseline_coupling,
                distance=best_distance,
                repaired=True,
            )
            components = [sorted(component) for component in nx.connected_components(self.graph)]
            components.sort(key=lambda component: tuple(str(node_id) for node_id in component))

    def solve_semantic_potential(self, flux_attribute: str = "residual_flux", weight_attribute: str = "weight") -> dict[str, float]:
        """
        Solves the discrete semantic potential on the graph from the current edge flux.

        The weighted graph Laplacian is singular on connected components, so we fix the
        gauge by enforcing a zero-mean potential across all nodes.
        """
        node_ids = list(self.graph.nodes)
        node_count = len(node_ids)
        if node_count == 0:
            return {}

        index_by_node = {node_id: index for index, node_id in enumerate(node_ids)}
        laplacian = np.zeros((node_count, node_count), dtype=float)
        divergence = np.zeros(node_count, dtype=float)

        for left_node, right_node, edge_data in self.graph.edges(data=True):
            weight = float(edge_data.get(weight_attribute, self.config.baseline_coupling))
            weight = max(weight, self.config.baseline_coupling)
            left_index = index_by_node[left_node]
            right_index = index_by_node[right_node]

            laplacian[left_index, left_index] += weight
            laplacian[right_index, right_index] += weight
            laplacian[left_index, right_index] -= weight
            laplacian[right_index, left_index] -= weight

            raw_flux = float(edge_data.get(flux_attribute, 0.0))
            flux = float(np.sign(raw_flux) * np.log1p(abs(raw_flux)))
            tail_node, head_node = sorted((left_node, right_node))
            tail_index = index_by_node[tail_node]
            head_index = index_by_node[head_node]
            divergence[tail_index] += flux
            divergence[head_index] -= flux

        rhs = -divergence
        if np.allclose(rhs, 0.0):
            potentials = np.zeros(node_count, dtype=float)
        else:
            augmented = np.zeros((node_count + 1, node_count + 1), dtype=float)
            augmented[:node_count, :node_count] = laplacian
            augmented[:node_count, node_count] = 1.0
            augmented[node_count, :node_count] = 1.0

            rhs_augmented = np.zeros(node_count + 1, dtype=float)
            rhs_augmented[:node_count] = rhs

            try:
                solution = np.linalg.solve(augmented, rhs_augmented)
            except np.linalg.LinAlgError:
                solution = np.linalg.lstsq(augmented, rhs_augmented, rcond=None)[0]

            potentials = solution[:node_count]

        potential_by_node: dict[str, float] = {}
        for node_id, potential, local_divergence in zip(node_ids, potentials, divergence, strict=False):
            scalar_potential = float(potential)
            self.graph.nodes[node_id]["semantic_potential"] = scalar_potential
            self.graph.nodes[node_id]["flux_divergence"] = float(local_divergence)
            potential_by_node[node_id] = scalar_potential

        self.graph.graph["semantic_potential_gauge"] = "mean_zero"
        self.graph.graph["semantic_potential_flux_attribute"] = flux_attribute
        return potential_by_node

if __name__ == "__main__":
    core = BlankManifoldCore()
    graph = core.generate_manifold()
