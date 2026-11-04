# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
from collections.abc import Sequence
from typing import Any

import numpy as np


class StatisticalPrism:
    """
    Acts as the dimensional transducer for the SOL manifold.
    Takes high-dimensional semantic embeddings (e.g., 1536D), extracts their
    statistical moments, and broadcasts them as a 3D probability density shower
    across the entire hyperbolic lattice.
    """

    def __init__(self, manifold_core: Any | None = None):
        self.manifold_core = manifold_core
        if manifold_core is None:
            self.graph = None
        elif hasattr(manifold_core, "graph"):
            self.graph = manifold_core.graph
        else:
            self.graph = manifold_core

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

        # 1. Mean (Central Tendency) -> Base spatial location (two-pass reference-shifted)
        ref = float(arr[0])
        shifted = arr - ref
        mean_shift = float(np.mean(shifted))
        raw_mean = ref + mean_shift
        mu = raw_mean * self.scale_mean

        # 2. Variance (Dispersion) -> Angular spread / uncertainty
        centered = shifted - mean_shift
        raw_var = float(np.mean(centered**2))
        var = raw_var * self.scale_var
        std_dev = float(np.sqrt(max(0.0, raw_var)))
        std_tol = max(1e-30, 1e-14 * abs(raw_mean))

        # 3. Skewness (Asymmetry) -> Phase-shift / Z-axis offset
        if arr.size < 3 or std_dev <= std_tol:
            sk = 0.0
        else:
            normed = centered / std_dev
            raw_sk = float(np.mean(normed**3))
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

        ref = float(arr[0])
        shifted = arr - ref
        mean_shift = float(np.mean(shifted))
        mean = ref + mean_shift
        centered = shifted - mean_shift
        variance = float(np.mean(centered**2))
        std_dev = float(np.sqrt(max(0.0, variance)))
        std_tol = max(1e-30, 1e-14 * abs(mean))

        if arr.size < 2 or std_dev <= std_tol:
            return np.array(
                [mean * self.scale_mean, variance * self.scale_var, 0.0, 0.0, 0.0, 0.0],
                dtype=np.float64,
            )

        normed = centered / std_dev
        if arr.size >= 3:
            raw_sk = float(np.mean(normed**3))
            skewness = (raw_sk * self.scale_skew) if np.isfinite(raw_sk) else 0.0
        else:
            skewness = 0.0
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
                mean * self.scale_mean,
                variance * self.scale_var,
                skewness,
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
        n = max(8, int(dimension))
        n_tiled = (n // 4) * 4
        x = np.zeros(n, dtype=np.float64)
        y = np.zeros(n, dtype=np.float64)
        x[:n_tiled] = np.tile(np.array([1.0, 1.0, -1.0, -1.0], dtype=np.float64), n_tiled // 4)
        y[:n_tiled] = np.tile(np.array([1.0, -1.0, 1.0, -1.0], dtype=np.float64), n_tiled // 4)
        x /= max(float(np.linalg.norm(x)), 1e-12)
        y /= max(float(np.linalg.norm(y)), 1e-12)
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

    def extract_spectral_prism_batch(self, embeddings: np.ndarray) -> np.ndarray:
        """
        Vectorized lockstep (B, N) -> (B, 6) Spectral-Wavelet Prism extractor.
        Computes all 6 spectral-wavelet coordinates across B embedding vectors
        in a single vectorized NumPy pass with < 1e-12 parity against sequential
        `extract_spectral_prism_fingerprint` calls.
        """
        mat = np.asarray(embeddings, dtype=np.float64)
        if mat.ndim == 1:
            mat = mat.reshape(1, -1)
        if mat.ndim != 2 or mat.shape[0] == 0:
            return np.zeros((0, 6), dtype=np.float64)
        b_rows, n_cols = mat.shape
        if n_cols == 0:
            return np.zeros((b_rows, 6), dtype=np.float64)
        mat = np.nan_to_num(mat, nan=0.0, posinf=0.0, neginf=0.0)

        ref = mat[:, :1]
        shifted = mat - ref
        mean_shift = np.mean(shifted, axis=1, keepdims=True)
        means = (ref + mean_shift).ravel()
        centered = shifted - mean_shift
        variances = np.mean(centered**2, axis=1)
        std_devs = np.sqrt(np.maximum(0.0, variances))
        std_tols = np.maximum(1e-30, 1e-14 * np.abs(means))

        out = np.zeros((b_rows, 6), dtype=np.float64)
        out[:, 0] = means * self.scale_mean
        out[:, 1] = variances * self.scale_var

        valid_mask = (n_cols >= 2) & (std_devs > std_tols)
        if not np.any(valid_mask):
            return out

        valid_idx = np.where(valid_mask)[0]
        centered_v = centered[valid_idx]
        std_v = std_devs[valid_idx]
        normed_v = centered_v / std_v[:, None]

        if n_cols >= 3:
            raw_sk = np.mean(normed_v**3, axis=1)
            raw_sk = np.where(np.isfinite(raw_sk), raw_sk * self.scale_skew, 0.0)
            out[valid_idx, 2] = raw_sk

        out[valid_idx, 3] = np.mean(normed_v**4, axis=1) - 3.0

        even_len = (n_cols // 2) * 2
        if even_len >= 2:
            pairs = normed_v[:, :even_len].reshape(len(valid_idx), -1, 2)
            haar_detail = (pairs[:, :, 0] - pairs[:, :, 1]) / np.sqrt(2.0)
            out[valid_idx, 4] = np.mean(haar_detail**2, axis=1)

        fft_vals = np.fft.rfft(normed_v, axis=1)
        power = np.abs(fft_vals[:, 1:]) ** 2
        total_power = np.sum(power, axis=1)
        if power.shape[1] > 0:
            freqs = np.arange(1, power.shape[1] + 1, dtype=np.float64) / float(power.shape[1])
            centroid = np.where(
                total_power > 1e-12,
                np.sum(power * freqs[None, :], axis=1) / np.maximum(total_power, 1e-12),
                0.0,
            )
            out[valid_idx, 5] = centroid

        return out

    def extract_decollided_coords(
        self,
        embedding: np.ndarray,
        *,
        use_spectral_prism: bool = True,
    ) -> np.ndarray:
        """
        Maps an embedding into 3D hyperbolic manifold coordinates in [-2.0, 2.0]^3.
        When `use_spectral_prism=False`, uses legacy 3-moment extraction (`extract_moments`),
        which suffers 3D coordinate collisions (`L2 = 0.0`) on orthogonal Rademacher,
        KV-cache block-pooled, recursive synthetic tail-collapsed, and MoE-aliased pairs.
        When `use_spectral_prism=True`, injects orthogonal spectral-wavelet phase dispersion
        from `[excess_kurtosis, haar_level1_detail_energy, spectral_centroid_ratio]`.
        """
        if not use_spectral_prism:
            return self.extract_moments(embedding)
        fp6 = self.extract_spectral_prism_fingerprint(embedding)
        if fp6[4] == 0.0 and fp6[5] == 0.0:
            return fp6[:3].copy()
        c0 = float(np.clip(fp6[0] + 0.6 * (fp6[4] - 1.0), -2.0, 2.0))
        c1 = float(np.clip(fp6[1] + 0.8 * (fp6[5] - 0.5), -2.0, 2.0))
        c2 = float(np.clip(fp6[2] + 0.15 * np.clip(fp6[3], -3.0, 3.0), -2.0, 2.0))
        return np.array([c0, c1, c2], dtype=np.float64)

    def audit_collapse_and_adversarial_batch(
        self,
        dimension: int = 1536,
        *,
        auto_decollide: bool = True,
        min_prism_separation: float = 0.25,
        quench_factor: float = 0.86,
        quench_steps: int = 30,
    ) -> dict[str, Any]:
        """
        Executes the Venue 4 4-regime training-free audit for hidden model collapse,
        KV-cache compression collapse, MoE router aliasing, and orthogonal adversarial
        collisions in lockstep `(8, dimension)` -> `(8, 6)` batches:
          0. `orthogonal_rademacher_collision`
          1. `kv_cache_block_pooling_collapse`
          2. `synthetic_recursive_tail_collapse`
          3. `moe_router_spectral_aliasing`
        """
        n = max(8, int(dimension))
        n_tiled = (n // 8) * 8
        sep_floor = float(min_prism_separation)
        qf = float(quench_factor)
        q_steps = max(0, int(quench_steps))

        regime_specs = [
            (
                "orthogonal_rademacher_collision",
                [1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0],
                [1.0, 1.0, -1.0, -1.0, 1.0, 1.0, -1.0, -1.0],
            ),
            (
                "kv_cache_block_pooling_collapse",
                [2.0, -2.0, 0.0, 0.0, 1.0, -1.0, 0.0, 0.0],
                [1.0, 1.0, 1.0, 1.0, -1.0, -1.0, -1.0, -1.0],
            ),
            (
                "synthetic_recursive_tail_collapse",
                [3.0, -3.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 1.0, -1.0, -1.0, 0.0, 0.0],
            ),
            (
                "moe_router_spectral_aliasing",
                [2.0, -2.0, 2.0, -2.0, 1.0, -1.0, 1.0, -1.0],
                [2.0, 2.0, -2.0, -2.0, 1.0, 1.0, -1.0, -1.0],
            ),
        ]

        def _norm_tile(tile: list[float]) -> np.ndarray:
            raw = np.zeros(n, dtype=np.float64)
            raw[:n_tiled] = np.tile(np.asarray(tile, dtype=np.float64), n_tiled // 8)
            centered = raw - float(np.mean(raw))
            denom = float(np.std(centered)) * np.sqrt(float(n))
            return centered / max(denom, 1e-12)

        batch_rows: list[np.ndarray] = []
        for _, tile_a, tile_b in regime_specs:
            batch_rows.append(_norm_tile(tile_a))
            batch_rows.append(_norm_tile(tile_b))
        batch_mat = np.vstack(batch_rows)

        prism_batch_6d = self.extract_spectral_prism_batch(batch_mat)
        seq_batch_6d = np.vstack(
            [self.extract_spectral_prism_fingerprint(row) for row in batch_mat]
        )
        max_batch_err = float(np.max(np.abs(prism_batch_6d - seq_batch_6d)))

        raw_attenuation = (qf**q_steps) if auto_decollide else 1.0
        collapsed_retention = (
            0.0
            if (auto_decollide and raw_attenuation < 0.02)
            else float(raw_attenuation)
        )
        stream_supp_db = (
            float(-10.0 * np.log10(max(raw_attenuation, 1e-12)))
            if auto_decollide
            else 0.0
        )

        regimes_out: list[dict[str, Any]] = []
        l2_3d_list: list[float] = []
        l2_6d_list: list[float] = []
        l2_decollided_list: list[float] = []
        s_on_list: list[float] = []
        s_off_list: list[float] = []
        legacy_collisions = 0
        resolved_6d = 0

        for idx, (regime_name, _, _) in enumerate(regime_specs):
            va = batch_mat[2 * idx]
            vb = batch_mat[2 * idx + 1]
            s6_a = prism_batch_6d[2 * idx]
            s6_b = prism_batch_6d[2 * idx + 1]
            m3_a = s6_a[:3]
            m3_b = s6_b[:3]

            cosine = float(
                np.dot(va, vb) / max(float(np.linalg.norm(va) * np.linalg.norm(vb)), 1e-12)
            )
            l2_3d = float(np.linalg.norm(m3_a - m3_b))
            l2_4d = float(np.linalg.norm(s6_a[:4] - s6_b[:4]))
            l2_6d = float(np.linalg.norm(s6_a - s6_b))

            coords_a = self.extract_decollided_coords(
                va, use_spectral_prism=bool(auto_decollide)
            )
            coords_b = self.extract_decollided_coords(
                vb, use_spectral_prism=bool(auto_decollide)
            )
            l2_decollided = float(np.linalg.norm(coords_a - coords_b))

            s_on = float(0.5 * (s6_a[4] / 2.0 + s6_a[5]))
            s_off = float(0.5 * (s6_b[4] / 2.0 + s6_b[5]))

            is_3d_collided = bool(l2_3d < sep_floor)
            is_6d_resolved = bool(l2_6d >= sep_floor)
            if is_3d_collided:
                legacy_collisions += 1
            if is_6d_resolved:
                resolved_6d += 1

            l2_3d_list.append(l2_3d)
            l2_6d_list.append(l2_6d)
            l2_decollided_list.append(l2_decollided)
            s_on_list.append(s_on)
            s_off_list.append(s_off)

            regimes_out.append(
                {
                    "regime_id": idx,
                    "regime": regime_name,
                    "cosine_similarity": round(cosine, 12),
                    "moments_3d_a": [round(float(x), 8) for x in m3_a],
                    "moments_3d_b": [round(float(x), 8) for x in m3_b],
                    "legacy_3d_l2_distance": round(l2_3d, 12),
                    "legacy_3d_collided": is_3d_collided,
                    "kurtosis_4d_l2_distance": round(l2_4d, 8),
                    "spectral_6d_a": [round(float(x), 8) for x in s6_a],
                    "spectral_6d_b": [round(float(x), 8) for x in s6_b],
                    "spectral_6d_l2_distance": round(l2_6d, 8),
                    "resolved_in_6d": is_6d_resolved,
                    "decollided_3d_coords_a": [round(float(x), 6) for x in coords_a],
                    "decollided_3d_coords_b": [round(float(x), 6) for x in coords_b],
                    "decollided_3d_l2_distance": round(l2_decollided, 6),
                    "healthy_prism_score": round(s_on, 6),
                    "collapsed_prism_score": round(s_off, 6),
                    "post_quench_collapsed_weight": round(collapsed_retention, 6),
                    "stream_suppression_db": round(stream_supp_db, 4),
                }
            )

        s_on_min = float(min(s_on_list))
        s_off_max = float(max(s_off_list))
        prism_tau_star = 0.5 * (s_on_min + s_off_max)
        prism_margin = 0.5 * (s_on_min - s_off_max)

        flips = sum(1 for s in s_on_list if s <= prism_tau_star) + sum(
            1 for s in s_off_list if s > prism_tau_star
        )
        total_streams = len(s_on_list) + len(s_off_list)
        accuracy = float(total_streams - flips) / float(max(total_streams, 1))
        legacy_3d_flips = int(legacy_collisions)
        legacy_3d_accuracy = float(total_streams - legacy_3d_flips) / float(
            max(total_streams, 1)
        )

        collapsed_quenched_count = (
            sum(1 for s in s_off_list if s <= prism_tau_star)
            if auto_decollide
            else 0
        )
        surviving_healthy_count = sum(1 for s in s_on_list if s > prism_tau_star)
        spectral_purity = float(surviving_healthy_count) / float(
            max(
                surviving_healthy_count + len(s_off_list) * collapsed_retention,
                1e-12,
            )
        )

        return {
            "dimension": n,
            "batch_shape": [int(batch_mat.shape[0]), int(batch_mat.shape[1])],
            "prism_6d_batch_shape": [
                int(prism_batch_6d.shape[0]),
                int(prism_batch_6d.shape[1]),
            ],
            "auto_decollide": bool(auto_decollide),
            "min_prism_separation": round(sep_floor, 6),
            "quench_factor": round(qf, 6),
            "quench_steps": q_steps,
            "regime_count": len(regimes_out),
            "regimes": regimes_out,
            "legacy_3d_collision_count": legacy_collisions,
            "legacy_3d_max_l2_distance": round(float(max(l2_3d_list)), 12),
            "legacy_3d_min_l2_distance": round(float(min(l2_3d_list)), 12),
            "legacy_3d_classification_accuracy": round(legacy_3d_accuracy, 6),
            "legacy_3d_flip_count": int(legacy_3d_flips),
            "resolved_6d_collision_count": resolved_6d,
            "unresolved_6d_collision_count": len(regimes_out) - resolved_6d,
            "spectral_6d_min_l2_distance": round(float(min(l2_6d_list)), 8),
            "spectral_6d_max_l2_distance": round(float(max(l2_6d_list)), 8),
            "decollided_3d_min_l2_distance": round(float(min(l2_decollided_list)), 6),
            "decollided_3d_max_l2_distance": round(float(max(l2_decollided_list)), 6),
            "lockstep_batch_max_abs_error": max_batch_err,
            "lockstep_parity_verified": bool(max_batch_err < 1e-12),
            "healthy_prism_scores": [round(x, 6) for x in s_on_list],
            "collapsed_prism_scores": [round(x, 6) for x in s_off_list],
            "s_on_min": round(s_on_min, 5),
            "s_off_max": round(s_off_max, 5),
            "prism_tau_star": round(prism_tau_star, 5),
            "prism_minimax_margin": round(prism_margin, 5),
            "minimax_margin_gain_pct": (
                round(((prism_margin - 0.053327) / 0.053327) * 100.0, 2)
                if auto_decollide and prism_margin > 0.053327
                else 0.0
            ),
            "prism_classification_accuracy": round(accuracy, 6),
            "prism_flip_count": int(flips),
            "collapsed_modes_quenched_count": int(collapsed_quenched_count),
            "surviving_healthy_streams_count": int(surviving_healthy_count),
            "raw_quench_attenuation_ratio": round(raw_attenuation, 6),
            "collapsed_stream_retention_ratio": round(collapsed_retention, 6),
            "stream_quench_suppression_db": round(stream_supp_db, 4),
            "post_quench_spectral_purity": round(spectral_purity, 6),
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
        if self.graph is None:
            return target_coords

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
        if self.graph is None or self.manifold_core is None:
            return
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
        if self.graph is None:
            return np.zeros(3, dtype=float)
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
