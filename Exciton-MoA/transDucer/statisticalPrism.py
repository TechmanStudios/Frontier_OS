# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
from collections.abc import Sequence

import numpy as np
from scipy.stats import skew


class StatisticalPrism:
    """
    Acts as the dimensional transducer for the SOL manifold.
    Takes high-dimensional semantic embeddings (e.g., 1536D), extracts their
    statistical moments, and broadcasts them as a 3D probability density shower
    across the entire hyperbolic lattice.
    """

    def __init__(self, manifold_core):
        self.manifold_core = manifold_core
        self.graph = manifold_core.graph

        # Scaling factors to map statistical moments cleanly onto the
        # [-2.0, 2.0] coordinate limits of the hyperbolic disc.
        self.scale_mean = 5.0
        self.scale_var = 10.0
        self.scale_skew = 2.0

        # The thermodynamic sensitivity of the antenna array
        self.resonance_temperature = 0.5

    def extract_moments(self, embedding: np.ndarray) -> np.ndarray:
        """
        Compresses a high-dimensional vector into a 3D statistical fingerprint.
        [Mean (Radius), Variance (Spread), Skewness (Phase)]
        """
        # 1. Mean (Central Tendency) -> Base spatial location
        mu = np.mean(embedding) * self.scale_mean

        # 2. Variance (Dispersion) -> Angular spread / uncertainty
        var = np.var(embedding) * self.scale_var

        # 3. Skewness (Asymmetry) -> Phase-shift / Z-axis offset
        sk = skew(embedding) * self.scale_skew

        # Ensure it matches the dimensionality of the blank_config (3D)
        return np.array([mu, var, sk])

    def global_resonance_broadcast(self, embedding: np.ndarray):
        """
        The 'Shower'. Computes the statistical fingerprint of the data and
        bathes the 1,024-node lattice in a probability field. Nodes physically
        near the fingerprint in the hyperbolic space experience spontaneous resonance.
        """
        # Extract the 3D target coordinates of the shower
        target_coords = self.extract_moments(embedding)
        print(f"\n[PRISM BROADCAST] Showering manifold at target coordinates: {target_coords}")

        # Apply the thermodynamic forgetting curve (decay) before the new shower hits
        self._apply_ambient_decay()

        max_resonance_spike = 0.0
        epicenter_node = None

        # Bathe the entire antenna array simultaneously
        for node_id, data in self.graph.nodes(data=True):
            node_coords = np.array(data["coords"])

            # Calculate the statistical distance between the node's physical location
            # and the incoming probability density function.
            # (Using Euclidean in the embedded space for speed, mapping to KL divergence conceptually)
            distance = np.linalg.norm(node_coords - target_coords)

            # Spontaneous Resonance: Nodes closer to the target frequency absorb more energy.
            # We use an inverted exponential to simulate a Gaussian probability field.
            resonance_injection = np.exp(-(distance**2) / self.resonance_temperature)

            # Update the node's accumulator
            self.graph.nodes[node_id]["resonance_accumulator"] += resonance_injection

            current_res = self.graph.nodes[node_id]["resonance_accumulator"]
            if current_res > max_resonance_spike:
                max_resonance_spike = current_res
                epicenter_node = node_id

        print(
            f"  -> Broadcast complete. Epicenter at {epicenter_node} with Peak Resonance: {max_resonance_spike:.3f}"
        )
        return target_coords

    def _apply_ambient_decay(self):
        """
        Preserves the topological vacuum. Nodes that do not continuously resonate
        decay back to zero, ensuring maximum capacity for future data waves.
        """
        decay_factor = self.manifold_core.config.base_damping_factor  # e.g., 0.05

        for node_id in self.graph.nodes:
            current_res = self.graph.nodes[node_id].get("resonance_accumulator", 0.0)
            if current_res > 0:
                # Thermodynamic cooling
                new_res = max(0.0, current_res - decay_factor)
                self.graph.nodes[node_id]["resonance_accumulator"] = new_res

    def sample_wormhole_signature(self, node_ids: Sequence[str]) -> np.ndarray:
        """
        Collapse a wormhole boundary into a compact 3-axis signature that can be
        exchanged with another manifold without copying full local state.
        """
        valid_nodes = [node_id for node_id in node_ids if node_id in self.graph]
        if not valid_nodes:
            return np.zeros(3, dtype=float)

        density_values = []
        shear_values = []
        flux_values = []
        for node_id in valid_nodes:
            node = self.graph.nodes[node_id]
            density_values.append(float(node.get("resonance_accumulator", 0.0)))
            shear_values.append(abs(float(node.get("semantic_potential", 0.0))))
            for neighbor in self.graph.neighbors(node_id):
                flux_values.append(abs(float(self.graph[node_id][neighbor].get("residual_flux", 0.0))))

        density = float(np.mean(density_values)) if density_values else 0.0
        shear = float(np.mean(shear_values)) if shear_values else 0.0
        vorticity = float(np.mean(flux_values)) if flux_values else 0.0
        return np.array([density, shear, vorticity], dtype=float)
