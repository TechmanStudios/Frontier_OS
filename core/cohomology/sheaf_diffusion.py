"""
Continuous Sheaf Heat Diffusion & Consensus Dynamics
====================================================
Simulates continuous heat diffusion and harmonic consensus over Cellular Sheaves.

Mathematical Invariants:
------------------------
1. Continuous Heat Equation on 0-Cochains:
    dx/dt = -alpha * Delta^0 x
    x(t) = exp(-alpha * Delta^0 * t) x(0)

2. Semi-Implicit Backward Euler Integrator (Unconditionally Stable):
    (I + alpha * dt * Delta^0) x^{k+1} = x^k + dt * noise^k

3. Monotonic Energy Dissipation:
    d E_F(x) / dt = -alpha * ||Delta^0 x||^2 <= 0

4. Asymptotic Convergence Rate:
    ||x(t) - x_{harmonic}|| <= ||x(0) - x_{harmonic}|| * exp(-alpha * lambda_2 * t)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
import scipy.linalg as la

from .cellular_sheaf import CellularSheaf
from .cohomology_engine import CohomologyEngine, CohomologySpectrum


@dataclass
class DiffusionStepRecord:
    step: int
    time: float
    dirichlet_energy: float
    obstruction_norm: float
    distance_to_harmonic: float
    semantic_consistency: float


@dataclass
class DiffusionTrajectory:
    total_steps: int
    total_time: float
    initial_energy: float
    final_energy: float
    energy_reduction_ratio: float
    final_semantic_consistency: float
    steps: List[DiffusionStepRecord]
    final_cochain: np.ndarray


class SheafDiffuser:
    """
    Simulates continuous multi-agent belief and metric diffusion over a Cellular Sheaf.
    """

    def __init__(
        self,
        sheaf: CellularSheaf,
        diffusion_rate: float = 1.0,
        dt: float = 0.05
    ):
        self.sheaf = sheaf
        self.diffusion_rate = float(diffusion_rate)
        self.dt = float(dt)
        self.engine = CohomologyEngine(sheaf)

    def step_semi_implicit(
        self,
        x: np.ndarray,
        dt: Optional[float] = None,
        external_forcing: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """
        Execute one semi-implicit backward Euler step:
        (I + alpha * dt * Delta^0) x^{k+1} = x^k + dt * F^k
        Unconditionally stable for all step sizes dt > 0.
        """
        step_dt = self.dt if dt is None else float(dt)
        laplacian = self.sheaf.build_laplacian()
        D_V = laplacian.shape[0]

        A = np.eye(D_V, dtype=np.float64) + (self.diffusion_rate * step_dt) * laplacian
        b = x.copy()
        if external_forcing is not None:
            b += step_dt * np.asarray(external_forcing, dtype=np.float64)

        # Solve linear system A x_next = b
        x_next = la.solve(A, b, assume_a='pos')
        return x_next

    def analytical_solution(self, x_init: np.ndarray, t: float) -> np.ndarray:
        """
        Compute exact closed-form matrix exponential solution at time t:
        x(t) = exp(-alpha * Delta^0 * t) x(0)
        """
        laplacian = self.sheaf.build_laplacian()
        A = -self.diffusion_rate * t * laplacian
        prop = la.expm(A)
        return prop @ x_init

    def run_diffusion(
        self,
        x_init: np.ndarray,
        max_steps: int = 100,
        energy_tolerance: float = 1e-6,
        dt: Optional[float] = None
    ) -> DiffusionTrajectory:
        """
        Run continuous sheaf diffusion until energy dissipates or max_steps reached.
        Records step-by-step telemetry of Dirichlet energy and semantic consistency.
        """
        step_dt = self.dt if dt is None else float(dt)
        spectrum = self.engine.compute_spectrum()
        P_harm = self.engine.harmonic_projector(spectrum)
        x_harm = P_harm @ x_init

        x_current = x_init.copy()
        init_energy = self.sheaf.dirichlet_energy(x_current)
        
        records: List[DiffusionStepRecord] = []
        cur_time = 0.0

        for step in range(max_steps + 1):
            e_dirichlet = self.sheaf.dirichlet_energy(x_current)
            y = self.sheaf.compute_coboundary_of(x_current)
            obs_norm = float(np.linalg.norm(y))
            
            dist_harm = float(np.linalg.norm(x_current - x_harm))
            
            norm_x_sq = float(np.dot(x_current, x_current))
            consist = float(np.exp(- (obs_norm ** 2) / (norm_x_sq + 1e-6)))

            records.append(DiffusionStepRecord(
                step=step,
                time=cur_time,
                dirichlet_energy=e_dirichlet,
                obstruction_norm=obs_norm,
                distance_to_harmonic=dist_harm,
                semantic_consistency=consist
            ))

            if step == max_steps or e_dirichlet <= energy_tolerance:
                break

            x_current = self.step_semi_implicit(x_current, dt=step_dt)
            cur_time += step_dt

        final_energy = records[-1].dirichlet_energy
        reduction = (init_energy - final_energy) / max(init_energy, 1e-12)

        return DiffusionTrajectory(
            total_steps=len(records) - 1,
            total_time=records[-1].time,
            initial_energy=init_energy,
            final_energy=final_energy,
            energy_reduction_ratio=reduction,
            final_semantic_consistency=records[-1].semantic_consistency,
            steps=records,
            final_cochain=x_current
        )
