"""
Sheaf Cohomology Computation Engine
===================================
Computes Sheaf Cohomology groups H^0(X; F) and H^1(X; F), Betti numbers,
harmonic projections, Sheaf Laplacian spectrum, and topological obstructions.

Mathematical Invariants:
------------------------
1. Rank-Nullity on Coboundary delta^0:
    dim C^0(X; F) = D_V = rank(delta^0) + dim ker(delta^0)
    beta_0 = dim H^0(X; F) = dim ker(delta^0) = dim ker(Delta^0)
    beta_1 = dim H^1(X; F) = D_E - rank(delta^0)

2. Orthogonal Harmonic Decomposition:
    For any 0-cochain x in C^0(X; F):
    x = x_{harmonic} + x_{discrepancy}
    where x_{harmonic} in H^0(X; F), delta^0 x_{harmonic} = 0,
    and x_{discrepancy} in (H^0(X; F))^perp.

3. Sheaf Algebraic Connectivity:
    lambda_2(Delta^0) = min_{x perp H^0, ||x||=1} x^T Delta^0 x > 0
    Governs the rate of multi-agent belief consensus diffusion.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import scipy.linalg as la

from .cellular_sheaf import CellularSheaf


@dataclass
class CohomologySpectrum:
    """Stores full spectral analysis of the Sheaf Laplacian."""
    eigenvalues: np.ndarray
    eigenvectors: np.ndarray
    beta_0: int
    beta_1: int
    algebraic_connectivity: float
    spectral_gap: float
    condition_number: float
    harmonic_basis: np.ndarray  # Shape: (D_V, beta_0)


@dataclass
class HarmonicDecomposition:
    """Decomposition of a cochain into consensus and obstruction components."""
    original_energy: float
    harmonic_energy: float  # Identically 0.0
    discrepancy_energy: float
    harmonic_cochain: np.ndarray
    discrepancy_cochain: np.ndarray
    harmonic_ratio: float  # ||x_harmonic||^2 / (||x||^2 + eps)
    obstruction_norm: float  # ||delta^0 x||


class CohomologyEngine:
    """
    Computes cohomology groups, harmonic projections, and topological
    obstructions for Cellular Sheaves.
    """

    def __init__(self, sheaf: CellularSheaf, zero_tolerance: float = 1e-7):
        self.sheaf = sheaf
        self.zero_tolerance = zero_tolerance

    def compute_spectrum(self) -> CohomologySpectrum:
        """
        Compute eigenvalues and eigenvectors of Delta^0, determining
        Betti numbers beta_0, beta_1, and the harmonic basis of H^0(X; F).
        """
        delta = self.sheaf.build_coboundary()
        laplacian = self.sheaf.build_laplacian()
        D_E, D_V = delta.shape

        # SVD of delta^0 to get exact rank and null space
        # delta = U S V^T
        U, s, Vt = la.svd(delta, full_matrices=False)
        rank_delta = int(np.sum(s > self.zero_tolerance))
        
        beta_0 = D_V - rank_delta
        beta_1 = D_E - rank_delta

        # Eigendecomposition of symmetric positive semi-definite Delta^0
        evals, evecs = la.eigh(laplacian)
        # Numerical safety: clip small negative eigenvalues
        evals = np.maximum(evals, 0.0)

        # Sort ascending
        sort_idx = np.argsort(evals)
        evals = evals[sort_idx]
        evecs = evecs[:, sort_idx]

        # Extract harmonic basis spanning ker(Delta^0)
        # Eigenvalues corresponding to ker(Delta^0) are < zero_tolerance
        zero_mask = evals <= self.zero_tolerance
        harmonic_basis = evecs[:, zero_mask]
        
        # If numerical discrepancy in count, take exactly beta_0 smallest
        if harmonic_basis.shape[1] != beta_0:
            harmonic_basis = evecs[:, :beta_0]

        # Algebraic connectivity: smallest non-zero eigenvalue
        non_zero_evals = evals[evals > self.zero_tolerance]
        if len(non_zero_evals) > 0:
            alg_conn = float(non_zero_evals[0])
            max_eval = float(evals[-1])
            cond_num = max_eval / max(alg_conn, 1e-12)
            spec_gap = float(non_zero_evals[0] - (evals[beta_0 - 1] if beta_0 > 0 else 0.0))
        else:
            alg_conn = 0.0
            cond_num = 1.0
            spec_gap = 0.0

        return CohomologySpectrum(
            eigenvalues=evals,
            eigenvectors=evecs,
            beta_0=beta_0,
            beta_1=beta_1,
            algebraic_connectivity=alg_conn,
            spectral_gap=spec_gap,
            condition_number=cond_num,
            harmonic_basis=harmonic_basis
        )

    def harmonic_projector(self, spectrum: Optional[CohomologySpectrum] = None) -> np.ndarray:
        """
        Construct orthogonal projector P_{H^0} onto the space of global sections.
        P_{H^0} = V_0 V_0^T where V_0 is the orthonormal harmonic basis.
        Shape: (D_V, D_V).
        """
        if spectrum is None:
            spectrum = self.compute_spectrum()

        if spectrum.beta_0 == 0:
            return np.zeros((self.sheaf.total_vertex_dim, self.sheaf.total_vertex_dim), dtype=np.float64)

        V0 = spectrum.harmonic_basis  # (D_V, beta_0)
        P = V0 @ V0.T
        return 0.5 * (P + P.T)

    def decompose_cochain(
        self,
        x: np.ndarray,
        spectrum: Optional[CohomologySpectrum] = None
    ) -> HarmonicDecomposition:
        """
        Decompose an arbitrary 0-cochain x into:
        x = x_{harmonic} + x_{discrepancy}
        where x_{harmonic} in H^0(X; F) satisfies delta^0 x_{harmonic} = 0.
        """
        if spectrum is None:
            spectrum = self.compute_spectrum()

        P = self.harmonic_projector(spectrum)
        x_harm = P @ x
        x_disc = x - x_harm

        e_orig = self.sheaf.dirichlet_energy(x)
        e_harm = self.sheaf.dirichlet_energy(x_harm)
        e_disc = self.sheaf.dirichlet_energy(x_disc)

        norm_sq_x = float(np.dot(x, x))
        norm_sq_harm = float(np.dot(x_harm, x_harm))
        harm_ratio = norm_sq_harm / (norm_sq_x + 1e-12) if norm_sq_x > 0 else 1.0

        y = self.sheaf.compute_coboundary_of(x)
        obs_norm = float(np.linalg.norm(y))

        return HarmonicDecomposition(
            original_energy=e_orig,
            harmonic_energy=e_harm,
            discrepancy_energy=e_disc,
            harmonic_cochain=x_harm,
            discrepancy_cochain=x_disc,
            harmonic_ratio=harm_ratio,
            obstruction_norm=obs_norm
        )

    def compute_holonomy(self, cycle_edges: List[Tuple[str, str, bool]]) -> np.ndarray:
        """
        Compute holonomy (parallel transport) around an oriented cycle in X.
        cycle_edges is a list of (edge_id, source_id, is_forward).
        Returns the composed linear transformation matrix around the loop.
        """
        first_edge_id, src, is_fwd = cycle_edges[0]
        first_edge = self.sheaf.edges[first_edge_id]
        dim = self.sheaf.vertex_dims[src]

        T = np.eye(dim, dtype=np.float64)

        for e_id, s_id, fwd in cycle_edges:
            edge = self.sheaf.edges[e_id]
            if fwd:
                # Traversing source -> target:
                # F_{u <= e} x_u = F_{v <= e} x_v  => x_v = (F_{v <= e})^{-1} F_{u <= e} x_u
                # For square maps, pinv computes generalized transport
                tgt_map_inv = la.pinv(edge.target_map)
                step = tgt_map_inv @ edge.source_map
            else:
                # Traversing target -> source:
                src_map_inv = la.pinv(edge.source_map)
                step = src_map_inv @ edge.target_map
            T = step @ T

        return T
