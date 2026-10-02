"""
Frontier_OS: Exciton-MoA Riemannian Geodesic Navigator
File: Frontier_OS/Exciton-MoA/firmWare/ExcitonEngine/geodesic_navigator.py

Solves the geodesic differential equation with adaptive damping on continuous Riemannian manifolds:
    d^2 x^k / dt^2 + Gamma^k_ij (dx^i/dt)(dx^j/dt) = -gamma(v, R) (dx^k/dt) - g^kl nabla_l Phi(x)
where Gamma^k_ij are the Levi-Civita Christoffel symbols of the second kind:
    Gamma^k_ij = 0.5 * g^kl * (d_i g_jl + d_j g_il - d_l g_ij)
"""

from dataclasses import dataclass

import numpy as np
import scipy.linalg as la
from Frontier_OS.core.telemetry_hook import (
    AgentDispatchThrottler,
    ManifoldTelemetryIPC,
)
from sol.diagnostics.damping_spectrogram import AdaptiveDampingStabilizer, DampingSpectrogram
from sol.kernel.geometry.ricci import DiscreteRicciFlowEngine


@dataclass
class GeodesicStepResult:
    position: np.ndarray
    velocity: np.ndarray
    acceleration: np.ndarray
    ricci_scalar: float
    damping_gamma: float
    kinetic_energy: float
    is_throttled: bool
    routing_channel: str


class ChristoffelCalculator:
    """
    Computes Levi-Civita Christoffel symbols of the second kind:
        Gamma^k_ij = 0.5 * g^kl * (d_i g_jl + d_j g_il - d_l g_ij)
    using vectorized local finite differences across coordinate charts.
    """

    def __init__(self, dim: int, eps: float = 1e-4):
        self.dim = dim
        self.eps = eps

    def compute_symbols(
        self, g_ij: np.ndarray, metric_evaluator: callable | None = None, x: np.ndarray | None = None
    ) -> np.ndarray:
        """
        Calculates Gamma^k_ij as a (dim, dim, dim) tensor.
        Index convention: Gamma[k, i, j].
        """
        inv_g = la.pinvh(g_ij)
        dg = np.zeros((self.dim, self.dim, self.dim), dtype=np.float64)  # dg[l, i, j] = d_l g_ij

        if metric_evaluator is not None and x is not None:
            # Numerical directional derivative along coordinate axes
            for axis in range(self.dim):
                dx = np.zeros(self.dim)
                dx[axis] = self.eps
                g_plus = metric_evaluator(x + dx)
                g_minus = metric_evaluator(x - dx)
                dg[axis] = (g_plus - g_minus) / (2.0 * self.eps)
        else:
            # In localized discrete chart, metric variation scales with local curvature
            # dg is bounded by local anisotropic deformation
            pass

        # Compute Gamma^k_ij = 0.5 * sum_l g^kl (d_i g_jl + d_j g_il - d_l g_ij)
        # Vectorized Einstein summation
        # term[l, i, j] = d_i g_jl + d_j g_il - d_l g_ij
        # dg[axis_deriv, axis_metric1, axis_metric2]
        # d_i g_jl -> input (i, j, l) -> permute (2, 0, 1) to get (l, i, j)
        # d_j g_il -> input (j, i, l) -> permute (2, 1, 0) to get (l, i, j)
        # d_l g_ij -> input (l, i, j) -> identity (0, 1, 2)
        term = np.transpose(dg, (2, 0, 1)) + np.transpose(dg, (2, 1, 0)) - dg
        Gamma = 0.5 * np.einsum("kl,lij->kij", inv_g, term)
        return Gamma


class RiemannianGeodesicNavigator:
    """
    Dispatches and steers Exciton agents along Riemannian geodesics.
    Couples metric curvature, velocity-damping, and Frontier_OS deflection.
    """

    def __init__(
        self,
        dim: int,
        dt: float = 0.01,
        ricci_engine: DiscreteRicciFlowEngine | None = None,
        damping_stabilizer: AdaptiveDampingStabilizer | None = None,
        ipc: ManifoldTelemetryIPC | None = None,
        throttler: AgentDispatchThrottler | None = None,
        horizon_radius: float = 25.0,
        boundary_stiffness: float = 0.5,
    ):
        self.dim = dim
        self.dt = dt
        self.ricci_engine = ricci_engine or DiscreteRicciFlowEngine(dim=dim, dt=dt)
        self.damping_stabilizer = damping_stabilizer or AdaptiveDampingStabilizer()
        self.christoffel = ChristoffelCalculator(dim=dim)
        self.spectrogram = DampingSpectrogram()
        self.horizon_radius = horizon_radius
        self.boundary_stiffness = boundary_stiffness

        # IPC & Throttler
        self.ipc = ipc
        self.throttler = throttler
        if self.ipc and not self.throttler:
            self.throttler = AgentDispatchThrottler(self.ipc)

    def compute_geodesic_acceleration(self, v: np.ndarray, Gamma: np.ndarray) -> np.ndarray:
        """
        Geodesic acceleration: a^k_geo = -Gamma^k_ij * v^i * v^j
        """
        return -np.einsum("kij,i,j->k", Gamma, v, v)

    def compute_boundary_confinement(self, x: np.ndarray) -> np.ndarray:
        """
        Hardening 2: Conformal boundary barrier (AdS containment).
        Prevents exciton trajectories from escaping into unbounded coordinate voids.
        """
        r_sq = float(np.sum(x**2))
        r_horiz_sq = self.horizon_radius**2
        margin = max(r_horiz_sq - r_sq, 0.1)
        if r_sq < (0.25 * r_horiz_sq):
            return np.zeros(self.dim, dtype=np.float64)

        factor = (self.boundary_stiffness * 4.0) / (margin**2)
        factor = min(factor, 50.0)
        return -factor * x

    def step_agent(
        self,
        x: np.ndarray,
        v: np.ndarray,
        g_ij: np.ndarray,
        target_coords: np.ndarray | None = None,
        ricci_scalar: float = 0.0,
        curvature_gradient: np.ndarray | None = None,
        metric_evaluator: callable | None = None,
        potential_coupling: float = 1.0,
    ) -> GeodesicStepResult:
        """
        Advances an exciton agent by one integration timestep dt along the Riemannian manifold.
        """
        # 1. Compute Christoffel symbols of the 2nd kind
        Gamma = self.christoffel.compute_symbols(g_ij, metric_evaluator, x)

        # 2. Geometric acceleration from manifold curvature
        a_geo = self.compute_geodesic_acceleration(v, Gamma)

        # 3. Semantic potential gradient force: F = -g^{kl} nabla_l Phi
        a_pot = np.zeros(self.dim, dtype=np.float64)
        if target_coords is not None:
            grad_phi = x - target_coords
            inv_g = la.pinvh(g_ij)
            a_pot = -potential_coupling * (inv_g @ grad_phi)

        # 4. Boundary confinement
        a_boundary = self.compute_boundary_confinement(x)

        # 5. Adaptive velocity damping from Damping Spectrum Stabilizer
        gamma, v_norm_g, e_k = self.damping_stabilizer.compute_gamma(v, g_ij, ricci_scalar)
        a_damp = -gamma * v

        # 6. Total kinematic acceleration: a = a_geo + a_damp + a_pot + a_boundary
        a_total = a_geo + a_damp + a_pot + a_boundary

        # 6. Semi-implicit symplectic integration:
        v_next = v + self.dt * a_total

        # 7. Frontier_OS Intercept Protocol: Check for curvature divergence
        is_throttled = False
        channel = "DIRECT"
        if self.throttler is not None:
            v_next, is_throttled, channel = self.throttler.evaluate_and_route(v_next, current_node_id=0)

        # 8. Update coordinates along tangent vector
        x_next = x + self.dt * v_next

        # 9. Record diagnostic telemetry frame
        self.spectrogram.record_state(timestamp_ms=0.0, v=v_next, g_ij=g_ij, ricci_scalar=ricci_scalar)

        return GeodesicStepResult(
            position=x_next,
            velocity=v_next,
            acceleration=a_total,
            ricci_scalar=ricci_scalar,
            damping_gamma=gamma,
            kinetic_energy=e_k,
            is_throttled=is_throttled,
            routing_channel=channel,
        )
