"""
Frontier_OS: The Seven Giants of Massive Data Analysis on Riemannian Manifolds
File: Frontier_OS/core/seven_giants.py

Implements the continuous differential-geometric formulation of the 7 Giants MoA:
1. The Statistician:      Equation of state & semantic pressure regulation p = c * ln(1 + rho/rho_0).
2. The Optimizer:         Riemannian potential gradient carving and steepest geodesic descent.
3. The N-Body Solver:     Jeans Mass gravitational condensation into dense attractor basins.
4. The Graph Navigator:   Divergence-free symplectic magnetic curl circulation for cycle traversal.
5. The Linear Algebraist: Anisotropic metric tensor scaling & gravitational PCA compression.
6. The Aligner:           Kuramoto/Vicsek phase synchronization and flocking velocity consensus.
7. The Integrator:        Volumetric Jacobian expansion sqrt(det(g)) & Bayesian probability normalization.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union
import numpy as np
import scipy.linalg as la

from Frontier_OS.core.swarm_router import (
    AutonomousSwarmRouter,
    SwarmAgent,
    SwarmCluster,
    SwarmStepReport
)
from Frontier_OS.core.hippocampal_sink import HippocampalMemorySink, DreamConsolidationReport


class GiantRole(str, Enum):
    """The Seven Computational Giants of Massive Data Analysis."""
    STATISTICIAN = "The Statistician"
    OPTIMIZER = "The Optimizer"
    N_BODY_SOLVER = "The N-Body Solver"
    GRAPH_NAVIGATOR = "The Graph Navigator"
    LINEAR_ALGEBRAIST = "The Linear Algebraist"
    ALIGNER = "The Aligner"
    INTEGRATOR = "The Integrator"


@dataclass
class GiantProfile:
    """Metadata, styling, and default physical parameters for each Giant."""
    role: GiantRole
    agent_id: str
    color_hex: str
    default_mass: float
    default_charge: float
    description: str


GIANT_PROFILES: Dict[GiantRole, GiantProfile] = {
    GiantRole.STATISTICIAN: GiantProfile(
        role=GiantRole.STATISTICIAN,
        agent_id="G1_Statistician",
        color_hex="#00f0ff",  # Vivid Electric Cyan
        default_mass=1.0,
        default_charge=1.4,
        description="Governs semantic equation of state to regulate crowding and pressure."
    ),
    GiantRole.OPTIMIZER: GiantProfile(
        role=GiantRole.OPTIMIZER,
        agent_id="G2_Optimizer",
        color_hex="#ffb703",  # Radiant Amber Gold
        default_mass=1.1,
        default_charge=0.9,
        description="Carves potential gradient descent towards low-error attractor basins."
    ),
    GiantRole.N_BODY_SOLVER: GiantProfile(
        role=GiantRole.N_BODY_SOLVER,
        agent_id="G3_NBodySolver",
        color_hex="#e056fd",  # Bright Neon Violet/Magenta
        default_mass=2.0,
        default_charge=1.2,
        description="Triggers Jeans Mass gravitational collapse into dense memory crystals."
    ),
    GiantRole.GRAPH_NAVIGATOR: GiantProfile(
        role=GiantRole.GRAPH_NAVIGATOR,
        agent_id="G4_GraphNavigator",
        color_hex="#00ff88",  # Laser Neon Green
        default_mass=1.0,
        default_charge=0.8,
        description="Injects divergence-free symplectic curl for deadlock-free loop traversal."
    ),
    GiantRole.LINEAR_ALGEBRAIST: GiantProfile(
        role=GiantRole.LINEAR_ALGEBRAIST,
        agent_id="G5_LinearAlgebraist",
        color_hex="#818cf8",  # Bright Electric Orchid
        default_mass=1.2,
        default_charge=1.0,
        description="Executes anisotropic tensor scaling and gravitational PCA compression."
    ),
    GiantRole.ALIGNER: GiantProfile(
        role=GiantRole.ALIGNER,
        agent_id="G6_Aligner",
        color_hex="#38bdf8",  # Bright Sky Cyan
        default_mass=1.0,
        default_charge=1.0,
        description="Drives Kuramoto phase synchronization and flocking velocity consensus."
    ),
    GiantRole.INTEGRATOR: GiantProfile(
        role=GiantRole.INTEGRATOR,
        agent_id="G7_Integrator",
        color_hex="#ff3366",  # Hot Radiant Coral Pink
        default_mass=1.3,
        default_charge=1.1,
        description="Computes volumetric Jacobian sqrt(det(g)) and Bayesian normalization."
    )
}


@dataclass
class GiantOperatorReadout:
    """Readout from an individual Giant's differential-geometric operator."""
    role: str
    agent_id: str
    position: List[float]
    velocity: List[float]
    scalar_metric: float       # Role-specific invariant (e.g. pressure, curl, volume, order)
    vector_signal: List[float]       # Acceleration or field force vector
    status: str
    kinetic_energy: float
    color_hex: str


@dataclass
class SevenGiantsMissionReport:
    """Comprehensive telemetry report of a multi-step 7 Giants swarm routing mission."""
    steps_executed: int
    step_reports: List[SwarmStepReport]
    giant_readouts: Dict[str, GiantOperatorReadout]
    order_parameter_history: List[float]
    final_consensus_order: float
    jeans_mass_collapses: int
    volume_invariance_mean: float
    total_dissipated_energy: float
    converged_giants: int
    all_converged: bool
    dream_consolidation: Optional[DreamConsolidationReport] = None


class SevenGiantsEnsemble:
    """
    Coordinates the collective execution of the 7 Giants on a Riemannian manifold.
    Injects specialized differential-geometric operators into each Giant agent.
    """
    def __init__(
        self,
        dim: int = 4,
        pressure_cs: float = 1.2,
        jeans_mass_threshold: float = 1.0,
        curl_vorticity: float = 0.75,
        pca_compression_rate: float = 0.4,
        align_coupling: float = 1.5
    ):
        self.dim = dim
        self.pressure_cs = pressure_cs
        self.jeans_mass_threshold = jeans_mass_threshold
        self.curl_vorticity = curl_vorticity
        self.pca_compression_rate = pca_compression_rate
        self.align_coupling = align_coupling

        # Precompute 4D symplectic curl generator matrix Omega (antisymmetric)
        self.Omega = np.zeros((self.dim, self.dim), dtype=np.float64)
        if self.dim >= 2:
            self.Omega[0, 1] = -self.curl_vorticity
            self.Omega[1, 0] = self.curl_vorticity
        if self.dim >= 4:
            self.Omega[2, 3] = -self.curl_vorticity
            self.Omega[3, 2] = self.curl_vorticity

    def deploy_giants(
        self,
        router: AutonomousSwarmRouter,
        target_cluster: Optional[str] = None,
        base_origin: Optional[np.ndarray] = None,
        spread: float = 2.0
    ) -> Dict[str, SwarmAgent]:
        """
        Deploys all 7 Giants into the router with balanced geometric distribution.
        """
        if base_origin is None:
            base_origin = np.zeros(self.dim, dtype=np.float64)
        else:
            base_origin = np.asarray(base_origin, dtype=np.float64)

        deployed_agents: Dict[str, SwarmAgent] = {}
        roles = list(GiantRole)

        # Distribute the 7 Giants symmetrically around base_origin in the primary plane
        for idx, role in enumerate(roles):
            profile = GIANT_PROFILES[role]
            angle = (2.0 * np.pi * idx) / len(roles)
            pos = base_origin.copy()
            pos[0] += spread * np.cos(angle)
            pos[1] += spread * np.sin(angle)
            if self.dim >= 3 and idx % 2 == 1:
                pos[2] += 0.5 * spread * np.sin(2.0 * angle)

            # Tangential initial velocity for natural orbital flocking
            vel = np.zeros(self.dim, dtype=np.float64)
            vel[0] = -1.2 * np.sin(angle)
            vel[1] = 1.2 * np.cos(angle)

            agent = router.add_agent(
                agent_id=profile.agent_id,
                role=profile.role.value,
                position=pos,
                velocity=vel,
                mass=profile.default_mass,
                charge=profile.default_charge,
                target_cluster=target_cluster
            )
            deployed_agents[profile.agent_id] = agent

        return deployed_agents

    def compute_giant_operators(
        self,
        router: AutonomousSwarmRouter,
        metrics: List[np.ndarray]
    ) -> Tuple[Dict[str, np.ndarray], Dict[str, GiantOperatorReadout]]:
        """
        Computes role-specific differential-geometric accelerations and telemetry readouts.
        """
        agent_list = list(router.agents.values())
        N = len(agent_list)
        positions = np.array([a.position for a in agent_list], dtype=np.float64)
        velocities = np.array([a.velocity for a in agent_list], dtype=np.float64)

        extra_accelerations: Dict[str, np.ndarray] = {}
        readouts: Dict[str, GiantOperatorReadout] = {}

        # Precompute mean center and covariance for Linear Algebraist
        centroid_swarm = np.mean(positions, axis=0) if N > 0 else np.zeros(self.dim)
        centered = positions - centroid_swarm
        cov = (centered.T @ centered) / max(N, 1) + 1e-5 * np.eye(self.dim)
        eigvals, eigvecs = la.eigh(cov)
        # Principal axis is eigenvector with largest eigenvalue
        principal_axis = eigvecs[:, -1]
        minor_axes = eigvecs[:, :-1]

        # Count total collapses detected this step
        collapses_detected = 0

        for i, a in enumerate(agent_list):
            pos = positions[i]
            vel = velocities[i]
            g = metrics[i]
            ke = 0.5 * float(vel @ g @ vel)

            acc_giant = np.zeros(self.dim, dtype=np.float64)
            scalar_metric = 0.0

            # 1. THE STATISTICIAN (Equation of State & Pressure)
            if a.role == GiantRole.STATISTICIAN.value:
                # Estimate local swarm density rho(x)
                dists_sq = np.sum((positions - pos)**2, axis=1)
                rho = float(np.sum(np.exp(-dists_sq / 2.0)))
                # Pressure p = c_s^2 * ln(1 + rho)
                pressure = (self.pressure_cs**2) * np.log1p(rho)
                scalar_metric = pressure

                # Negative pressure gradient force away from dense center
                grad_rho = np.zeros(self.dim)
                for j in range(N):
                    if j != i:
                        grad_rho -= 2.0 * (pos - positions[j]) * np.exp(-dists_sq[j] / 2.0)
                acc_giant = -((self.pressure_cs**2) / (rho + 1.0)) * grad_rho * 0.35

            # 2. THE OPTIMIZER (Potential Gradient Descent)
            elif a.role == GiantRole.OPTIMIZER.value:
                if a.target_cluster and a.target_cluster in router.clusters:
                    c_target = router.clusters[a.target_cluster].centroid
                else:
                    c_target = np.zeros(self.dim)
                grad_phi = pos - c_target
                scalar_metric = float(np.linalg.norm(grad_phi))
                # Steepest descent with metric Riemannian metric weighting
                acc_giant = -1.6 * (la.pinvh(g) @ grad_phi)

            # 3. THE N-BODY SOLVER (Jeans Mass Gravitational Condensation)
            elif a.role == GiantRole.N_BODY_SOLVER.value:
                # Accumulate local gravitational potential from nearby clusters & agents
                grav_pull = np.zeros(self.dim)
                for c in router.clusters.values():
                    diff = c.centroid - pos
                    dist = float(np.linalg.norm(diff)) + 1e-4
                    grav_pull += 2.5 * (diff / (dist**3 + 0.5))

                local_mass = a.mass + 0.4 * float(np.sum([
                    other.mass for j, other in enumerate(agent_list)
                    if j != i and np.linalg.norm(pos - positions[j]) < 1.8
                ]))
                scalar_metric = local_mass

                if local_mass >= self.jeans_mass_threshold:
                    collapses_detected += 1
                    # Intense local attractor well
                    acc_giant = grav_pull * 2.2
                else:
                    acc_giant = grav_pull * 1.1

            # 4. THE GRAPH NAVIGATOR (Symplectic Curl & Loop Traversal)
            elif a.role == GiantRole.GRAPH_NAVIGATOR.value:
                # Magnetic curl acceleration B = Omega * v
                curl_force = self.Omega @ vel
                scalar_metric = float(np.linalg.norm(curl_force))
                acc_giant = curl_force * 1.25

            # 5. THE LINEAR ALGEBRAIST (Anisotropic PCA Subspace Compression)
            elif a.role == GiantRole.LINEAR_ALGEBRAIST.value:
                # Compress along minor dispersion axes, preserving principal manifold direction
                disp_minor = np.zeros(self.dim)
                for col in range(minor_axes.shape[1]):
                    axis = minor_axes[:, col]
                    comp = float(axis @ (pos - centroid_swarm))
                    disp_minor += comp * axis
                scalar_metric = float(eigvals[-1] / (np.sum(eigvals) + 1e-6))
                acc_giant = -self.pca_compression_rate * disp_minor

            # 6. THE ALIGNER (Kuramoto Phase Synchronization)
            elif a.role == GiantRole.ALIGNER.value:
                # Enhanced Vicsek alignment pulling swarm into phase coherence
                v_diff_sum = np.zeros(self.dim)
                for j in range(N):
                    if j != i:
                        v_diff_sum += (velocities[j] - vel)
                acc_giant = (self.align_coupling / max(N, 1)) * v_diff_sum
                # Kuramoto order scalar
                spd = float(np.linalg.norm(vel))
                scalar_metric = spd

            # 7. THE INTEGRATOR (Volumetric Jacobian & Invariance Verification)
            elif a.role == GiantRole.INTEGRATOR.value:
                # Riemannian volume element dV = sqrt(det(g))
                det_g = max(float(la.det(g)), 1e-8)
                vol_element = float(np.sqrt(det_g))
                scalar_metric = vol_element
                # Symplectic Liouville restoring acceleration
                acc_giant = -0.15 * (vol_element - 1.0) * vel

            # Default / Generic fallback
            else:
                scalar_metric = float(np.linalg.norm(vel))
                acc_giant = np.zeros(self.dim)

            extra_accelerations[a.agent_id] = acc_giant

            # Profile lookup for color
            role_enum = next((r for r in GiantRole if r.value == a.role), None)
            color_hex = GIANT_PROFILES[role_enum].color_hex if role_enum else "#38bdf8"

            readouts[a.agent_id] = GiantOperatorReadout(
                role=a.role,
                agent_id=a.agent_id,
                position=[round(float(c), 3) for c in pos],
                velocity=[round(float(v), 3) for v in vel],
                scalar_metric=round(float(scalar_metric), 4),
                vector_signal=[round(float(s), 3) for s in acc_giant],
                status=a.status,
                kinetic_energy=round(float(ke), 4),
                color_hex=color_hex
            )

        return extra_accelerations, readouts

    def run_giants_mission(
        self,
        router: AutonomousSwarmRouter,
        max_steps: int = 60,
        trigger_dream_consolidation: bool = True
    ) -> SevenGiantsMissionReport:
        """
        Executes a complete 7 Giants swarm routing mission with real-time operator injection,
        tracking Kuramoto order, Jeans collapses, volume invariance, and dream consolidation.
        """
        step_reports: List[SwarmStepReport] = []
        last_readouts: Dict[str, GiantOperatorReadout] = {}
        order_history: List[float] = []
        vol_invariance_history: List[float] = []
        total_collapses = 0

        for step in range(max_steps):
            # Compute current metrics
            agent_list = list(router.agents.values())
            metrics = [router.compute_local_metric(a.position) for a in agent_list]

            # Compute specialized operators for the 7 Giants
            extra_accs, readouts = self.compute_giant_operators(router, metrics)
            last_readouts = readouts

            # Apply specialized operator accelerations directly before symplectic step
            for a_id, extra_acc in extra_accs.items():
                if a_id in router.agents:
                    # Accelerate agent velocity by half dt before router step
                    router.agents[a_id].velocity += router.dt * 0.5 * extra_acc

            # Step the autonomous swarm router
            step_rep = router.step_swarm(step_index=step)
            step_reports.append(step_rep)
            order_history.append(step_rep.order_parameter)

            # Volume invariance check: mean sqrt(det(g))
            vol_mean = float(np.mean([np.sqrt(max(la.det(g), 1e-8)) for g in metrics]))
            vol_invariance_history.append(vol_mean)

            # Check Jeans collapse
            nbody_readout = readouts.get(GIANT_PROFILES[GiantRole.N_BODY_SOLVER].agent_id)
            if nbody_readout and nbody_readout.scalar_metric >= self.jeans_mass_threshold:
                total_collapses += 1

            # Termination condition: high consensus and all converged
            if step_rep.converged_agents == len(router.agents) and step_rep.order_parameter >= 0.70:
                break

        # Final consensus order
        final_consensus = order_history[-1] if order_history else 0.0
        converged_count = sum(1 for a in router.agents.values() if a.status == "converged")

        # Optional Hippocampal Dream Cycle consolidation
        dream_rep = None
        if trigger_dream_consolidation and router.sink is not None:
            try:
                dream_rep = router.sink.execute_dream_cycle()
            except Exception:
                pass

        return SevenGiantsMissionReport(
            steps_executed=len(step_reports),
            step_reports=step_reports,
            giant_readouts=last_readouts,
            order_parameter_history=order_history,
            final_consensus_order=round(float(final_consensus), 4),
            jeans_mass_collapses=total_collapses,
            volume_invariance_mean=round(float(np.mean(vol_invariance_history)), 4) if vol_invariance_history else 1.0,
            total_dissipated_energy=round(float(router.total_dissipated_energy), 4),
            converged_giants=converged_count,
            all_converged=(converged_count == len(router.agents) and len(router.agents) > 0),
            dream_consolidation=dream_rep
        )
