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
        arr = np.asarray(embedding, dtype=np.float64).ravel()
        if arr.size == 0:
            return np.zeros(3, dtype=np.float64)
        arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)

        # 1. Mean (Central Tendency) -> Base spatial location
        mu = float(np.mean(arr)) * self.scale_mean

        # 2. Variance (Dispersion) -> Angular spread / uncertainty
        raw_var = float(np.var(arr))
        var = raw_var * self.scale_var

        # 3. Skewness (Asymmetry) -> Phase-shift / Z-axis offset
        if arr.size < 3 or raw_var <= 1e-24:
            sk = 0.0
        else:
            raw_sk = float(skew(arr))
            sk = (raw_sk * self.scale_skew) if np.isfinite(raw_sk) else 0.0

        # Ensure it matches the dimensionality of the blank_config (3D)
        return np.array([mu, var, sk], dtype=np.float64)

    def extract_spectral_prism_fingerprint(self, embedding: np.ndarray) -> np.ndarray:
        """
        Extracts a 6-dimensional Spectral-Wavelet Prism fingerprint:
          [0] scaled_mean (5 * mu)
          [1] scaled_variance (10 * sigma^2)
          [2] scaled_skewness (2 * gamma_1)
          [3] excess_kurtosis (m_4 / sigma^4 - 3)
          [4] haar_level1_detail_energy (normalized adjacent-pair Haar wavelet detail power)
          [5] spectral_centroid_ratio (normalized FFT frequency centroid in [0, 1])

        Resolves the Vector 0 3-moment collision counterexample where orthogonal
        periodic vectors x = [1, 1, -1, -1, ...] and y = [1, -1, 1, -1, ...]
        share identical (mean, variance, skewness) but differ in Haar wavelet
        detail energy (0.0 vs 2.0) and normalized spectral centroid (0.5 vs 1.0).
        """
        arr = np.asarray(embedding, dtype=np.float64).ravel()
        if arr.size == 0:
            return np.zeros(6, dtype=np.float64)
        arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)

        mean = float(np.mean(arr))
        centered = arr - mean
        variance = float(np.var(arr))
        std_dev = float(np.sqrt(max(0.0, variance)))

        if arr.size < 2 or std_dev <= 1e-12:
            return np.array(
                [mean * self.scale_mean, variance * self.scale_var, 0.0, 0.0, 0.0, 0.0],
                dtype=np.float64,
            )

        moments_3d = self.extract_moments(arr)
        normed = centered / std_dev
        kurtosis = float(np.mean(normed**4) - 3.0)

        even_len = (arr.size // 2) * 2
        if even_len >= 2:
            pairs = normed[:even_len].reshape(-1, 2)
            haar_detail = (pairs[:, 0] - pairs[:, 1]) / np.sqrt(2.0)
            haar_energy = float(np.mean(haar_detail**2))
        else:
            haar_energy = 0.0

        fft_vals = np.fft.rfft(normed)
        power = np.abs(fft_vals[1:]) ** 2
        total_power = float(np.sum(power))
        if total_power > 1e-12 and power.size > 0:
            freqs = np.arange(1, power.size + 1, dtype=np.float64) / float(power.size)
            spectral_centroid = float(np.sum(freqs * power) / total_power)
        else:
            spectral_centroid = 0.0

        return np.array(
            [
                float(moments_3d[0]),
                float(moments_3d[1]),
                float(moments_3d[2]),
                kurtosis,
                haar_energy,
                spectral_centroid,
            ],
            dtype=np.float64,
        )

    def verify_orthogonal_counterexample(self, dimension: int = 1536) -> dict:
        """
        Verifies the synThesis Vector 0 orthogonal Rademacher counterexample:
          x = [1, 1, -1, -1, ...] / sqrt(N)
          y = [1, -1, 1, -1, ...] / sqrt(N)
        Shows that 3-moment `extract_moments` collides while 6D
        `extract_spectral_prism_fingerprint` cleanly separates x and y.
        """
        n = max(8, (int(dimension) // 4) * 4)
        scale = 1.0 / np.sqrt(float(n))
        x = np.tile(np.array([1.0, 1.0, -1.0, -1.0], dtype=np.float64), n // 4) * scale
        y = np.tile(np.array([1.0, -1.0, 1.0, -1.0], dtype=np.float64), n // 4) * scale
        cosine = float(np.dot(x, y) / (np.linalg.norm(x) * np.linalg.norm(y)))
        m3_x = self.extract_moments(x)
        m3_y = self.extract_moments(y)
        spec_x = self.extract_spectral_prism_fingerprint(x)
        spec_y = self.extract_spectral_prism_fingerprint(y)
        l2_3d = float(np.linalg.norm(m3_x - m3_y))
        l2_6d = float(np.linalg.norm(spec_x - spec_y))
        return {
            "dimension": n,
            "cosine_similarity": round(cosine, 12),
            "moments_3d_x": [round(float(v), 8) for v in m3_x],
            "moments_3d_y": [round(float(v), 8) for v in m3_y],
            "moments_3d_l2_distance": round(l2_3d, 12),
            "legacy_3moment_l2_distance": round(l2_3d, 12),
            "moments_3d_collided": bool(l2_3d < 1e-9),
            "spectral_6d_x": [round(float(v), 8) for v in spec_x],
            "spectral_6d_y": [round(float(v), 8) for v in spec_y],
            "spectral_6d_l2_distance": round(l2_6d, 8),
            "spectral_prism_distinguishes_orthogonal_vectors": bool(l2_6d > 2.0),
        }

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

        Reproducibility: wormhole node ids are visited in sorted order, neighbor
        iteration is sorted (NetworkX neighbor order is otherwise insertion-order
        dependent), and per-channel value lists are sorted before averaging so
        the floating-point sum order is identical across runs. The returned
        signature is then quantized to 12 decimal places so any sub-ulp drift
        from upstream operators does not compound through the shared-flux loop.
        """
        valid_nodes = sorted(node_id for node_id in node_ids if node_id in self.graph)
        if not valid_nodes:
            return np.zeros(3, dtype=float)

        density_values: list[float] = []
        shear_values: list[float] = []
        flux_values: list[float] = []
        for node_id in valid_nodes:
            node = self.graph.nodes[node_id]
            density_values.append(float(node.get("resonance_accumulator", 0.0)))
            shear_values.append(abs(float(node.get("semantic_potential", 0.0))))
            for neighbor in sorted(self.graph.neighbors(node_id)):
                flux_values.append(abs(float(self.graph[node_id][neighbor].get("residual_flux", 0.0))))

        density = float(np.mean(sorted(density_values))) if density_values else 0.0
        shear = float(np.mean(sorted(shear_values))) if shear_values else 0.0
        vorticity = float(np.mean(sorted(flux_values))) if flux_values else 0.0
        signature = np.array([density, shear, vorticity], dtype=float)
        return np.round(signature, 12)
