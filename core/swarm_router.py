"""
Frontier_OS: Autonomous Exciton Swarm Router
File: Frontier_OS/core/swarm_router.py

Implements decentralized, non-branching swarm routing for Exciton agents across multi-cluster
Riemannian manifolds. Couples:
1. Mutual Swarm Potential: Short-range collision repulsion and medium-range Kuramoto/Vicsek velocity alignment.
2. Dynamic Cluster Load Balancing: Attractive goal wells with soft capacity crowding penalties.
3. Stigmergic Riemannian Trail: Curvature/pheromone footprints accelerating path discovery.
4. Symplectic Energy Conservation: Damping dissipation absorbed into the Hippocampal Memory Sink.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple, Union
import numpy as np
import scipy.linalg as la

from Frontier_OS.core.geodesic_navigator import (
    ChristoffelCalculator,
    GeodesicStepResult,
    RiemannianGeodesicNavigator
)
from Frontier_OS.core.hippocampal_sink import HippocampalMemorySink
from sol.kernel.geometry.ricci import DiscreteRicciFlowEngine, ExcitonTrajectory


@dataclass
class SwarmAgent:
    """Represents an individual Exciton agent participating in collective swarm routing."""
    agent_id: str
    role: str                       # e.g., "The Architect", "The Critic", "Exciton-01"
    position: np.ndarray            # Coordinate in M (dim,)
    velocity: np.ndarray            # Tangent vector in T_x M (dim,)
    mass: float = 1.0               # Inertial mass
    charge: float = 1.0             # Mutual repulsive charge
    target_cluster: Optional[str] = None
    target_coords: Optional[np.ndarray] = None
    status: str = "active"          # "active" | "converged" | "deflected"
    dwell_time: float = 0.0
    path: List[np.ndarray] = field(default_factory=list)


@dataclass
class SwarmCluster:
    """Represents a target semantic cluster or goal destination on the manifold."""
    cluster_id: str
    centroid: np.ndarray            # (dim,)
    radius: float = 1.5             # Convergence basin radius
    capacity: int = 4               # Target capacity before crowding repulsion kicks in
    semantic_density: float = 1.0   # Reward / attraction depth factor
    assigned_agents: List[str] = field(default_factory=list)


@dataclass
class SwarmStepReport:
    """Detailed telemetry snapshot of the swarm state at a given integration step."""
    step_index: int
    order_parameter: float          # Alignment / consensus metric r in [0, 1]
    cluster_allocations: Dict[str, int]
    total_kinetic_energy: float
    dissipated_energy: float
    collision_events_avoided: int
    min_pairwise_distance: float
    converged_agents: int
    metric_condition_number: float
    order_direction: np.ndarray


class AutonomousSwarmRouter:
    """
    Coordinates an ensemble of Exciton agents navigating a continuous Riemannian manifold.
    Enforces collective consensus, collision avoidance, and multi-goal routing without
    discrete symbolic branching.
    """
    def __init__(
        self,
        dim: int = 4,
        dt: float = 0.02,
        k_repulsion: float = 1.2,
        r_repulsion: float = 0.8,
        k_alignment: float = 0.85,
        r_alignment: float = 2.5,
        k_cluster: float = 1.5,
        k_crowd: float = 2.0,
        k_trail: float = 0.4,
        trail_decay: float = 0.05,
        gamma_base: float = 0.12,
        horizon_radius: float = 20.0,
        hippocampal_sink: Optional[HippocampalMemorySink] = None,
        ricci_engine: Optional[DiscreteRicciFlowEngine] = None
    ):
        self.dim = dim
        self.dt = dt
        self.k_repulsion = k_repulsion
        self.r_repulsion = r_repulsion
        self.k_alignment = k_alignment
        self.r_alignment = r_alignment
        self.k_cluster = k_cluster
        self.k_crowd = k_crowd
        self.k_trail = k_trail
        self.trail_decay = trail_decay
        self.gamma_base = gamma_base
        self.horizon_radius = horizon_radius

        self.sink = hippocampal_sink
        self.ricci_engine = ricci_engine
        self.christoffel_calc = ChristoffelCalculator(dim=dim)

        self.agents: Dict[str, SwarmAgent] = {}
        self.clusters: Dict[str, SwarmCluster] = {}
        self.stigmergic_history: List[Tuple[np.ndarray, float]] = []  # (position, intensity)
        self.total_dissipated_energy: float = 0.0

    def add_cluster(
        self,
        cluster_id: str,
        centroid: np.ndarray,
        radius: float = 1.5,
        capacity: int = 3,
        semantic_density: float = 1.0
    ) -> SwarmCluster:
        """Registers a semantic cluster / attractor basin on the manifold."""
        cluster = SwarmCluster(
            cluster_id=cluster_id,
            centroid=np.asarray(centroid, dtype=np.float64).copy(),
            radius=radius,
            capacity=capacity,
            semantic_density=semantic_density
        )
        self.clusters[cluster_id] = cluster
        return cluster

    def add_agent(
        self,
        agent_id: str,
        role: str,
        position: np.ndarray,
        velocity: np.ndarray,
        mass: float = 1.0,
        charge: float = 1.0,
        target_cluster: Optional[str] = None
    ) -> SwarmAgent:
        """Adds an Exciton agent to the active routing swarm."""
        pos = np.asarray(position, dtype=np.float64).copy()
        vel = np.asarray(velocity, dtype=np.float64).copy()
        agent = SwarmAgent(
            agent_id=agent_id,
            role=role,
            position=pos,
            velocity=vel,
            mass=mass,
            charge=charge,
            target_cluster=target_cluster,
            path=[pos.copy()]
        )
        self.agents[agent_id] = agent
        return agent

    def compute_local_metric(self, x: np.ndarray) -> np.ndarray:
        """
        Computes local Riemannian metric tensor g_ij(x) with cluster deformations
        and AdS boundary barrier. Strictly guarantees g_ij >> 0 via Log-Euclidean retractions.
        """
        r_sq = float(np.sum(x**2))
        S = np.zeros((self.dim, self.dim), dtype=np.float64)

        # Cluster metric condensation: space contracts (g > I) inside semantic clusters
        for cluster in self.clusters.values():
            dist_sq = float(np.sum((x - cluster.centroid)**2))
            envelope = np.exp(-dist_sq / (2.0 * (cluster.radius**2) + 1e-6))
            S += 0.35 * cluster.semantic_density * envelope * np.eye(self.dim)

        # Boundary metric stiffening
        if r_sq > (self.horizon_radius - 2.0)**2:
            barrier = 0.5 * ((r_sq - (self.horizon_radius - 2.0)**2) / 4.0)**2
            barrier = min(barrier, 15.0)
            S += barrier * np.eye(self.dim)

        # Retraction to positive-definite cone
        S = np.clip(S, -20.0, 20.0)
        g_ij = la.expm(S)
        g_ij = 0.5 * (g_ij + g_ij.T)
        evals, evecs = la.eigh(g_ij)
        evals = np.clip(evals, 1e-4, 100.0)
        return (evecs * evals) @ evecs.T

    def step_swarm(self, step_index: int = 0) -> SwarmStepReport:
        """
        Executes a single synchronized symplectic step of the entire Exciton swarm:
        1. Pairwise mutual forces (short-range repulsion, flocking alignment).
        2. Cluster attraction & capacity crowding backreaction.
        3. Stigmergic pheromone trail gradient.
        4. Symplectic geodesic integration and Hippocampal energy dissipation.
        """
        agent_list = list(self.agents.values())
        N = len(agent_list)
        if N == 0:
            return SwarmStepReport(
                step_index=step_index,
                order_parameter=0.0,
                cluster_allocations={},
                total_kinetic_energy=0.0,
                dissipated_energy=0.0,
                collision_events_avoided=0,
                min_pairwise_distance=999.0,
                converged_agents=0,
                metric_condition_number=1.0,
                order_direction=np.zeros(self.dim)
            )

        # Precompute positions, velocities, and metrics
        positions = np.array([a.position for a in agent_list], dtype=np.float64)
        velocities = np.array([a.velocity for a in agent_list], dtype=np.float64)
        metrics = [self.compute_local_metric(pos) for pos in positions]
        inv_metrics = [la.pinvh(g) for g in metrics]

        # Count current cluster occupation for dynamic capacity penalties
        cluster_occupancy: Dict[str, int] = {cid: 0 for cid in self.clusters}
        for a in agent_list:
            if a.target_cluster and a.target_cluster in cluster_occupancy:
                cluster_occupancy[a.target_cluster] += 1

        accelerations = np.zeros_like(velocities)
        collision_avoidance_count = 0
        min_pdist = float("inf")

        # 1. Compute Pairwise Swarm Forces (Repulsion & Flocking)
        for i in range(N):
            g_i = metrics[i]
            for j in range(i + 1, N):
                g_j = metrics[j]
                g_avg = 0.5 * (g_i + g_j)
                diff = positions[i] - positions[j]
                # Riemannian distance: d_g = sqrt(diff^T g_avg diff)
                d_sq = float(diff @ g_avg @ diff)
                dist_g = max(float(np.sqrt(d_sq)), 1e-6)
                if dist_g < min_pdist:
                    min_pdist = dist_g

                # Unit tangent vector from j to i
                u_ji = diff / dist_g

                # Short-Range Repulsion (Collision Avoidance)
                if dist_g < self.r_repulsion:
                    collision_avoidance_count += 1
                    rep_mag = self.k_repulsion * agent_list[i].charge * agent_list[j].charge * np.exp(-0.5 * (dist_g / (self.r_repulsion + 1e-6))**2)
                    accelerations[i] += (rep_mag / agent_list[i].mass) * u_ji
                    accelerations[j] -= (rep_mag / agent_list[j].mass) * u_ji

                # Medium-Range Velocity Alignment (Flocking Consensus)
                if dist_g < self.r_alignment:
                    weight = np.exp(-0.5 * (dist_g / (self.r_alignment + 1e-6))**2)
                    # Mutual target affinity factor
                    if agent_list[i].target_cluster == agent_list[j].target_cluster:
                        weight *= 1.5

                    v_diff = velocities[j] - velocities[i]
                    accelerations[i] += (self.k_alignment * weight / N) * v_diff
                    accelerations[j] -= (self.k_alignment * weight / N) * v_diff

        # 2. Cluster Attraction, Overcapacity Crowding, & Geodesics
        step_dissipation = 0.0
        converged_count = 0
        total_ke = 0.0

        for i, a in enumerate(agent_list):
            pos = positions[i]
            vel = velocities[i]
            g = metrics[i]
            inv_g = inv_metrics[i]

            # Christoffel connection acceleration
            Gamma = self.christoffel_calc.compute_symbols(
                g_ij=g,
                metric_evaluator=self.compute_local_metric,
                x=pos
            )
            geodesic_acc = -np.einsum('kij,i,j->k', Gamma, vel, vel)

            # Target Cluster Potential Force
            cluster_acc = np.zeros(self.dim)
            if a.target_cluster and a.target_cluster in self.clusters:
                target_c = self.clusters[a.target_cluster]
                c_diff = pos - target_c.centroid
                c_dist = max(float(np.sqrt(c_diff @ g @ c_diff)), 1e-6)

                if c_dist < target_c.radius:
                    a.status = "converged"
                    converged_count += 1
                else:
                    a.status = "active"

                # Attractive pull toward centroid
                u_to_cluster = -c_diff / c_dist
                pull_mag = self.k_cluster * target_c.semantic_density / (1.0 + 0.3 * c_dist)
                cluster_acc += pull_mag * u_to_cluster

                # Capacity crowding penalty: if cluster is full, repel excess agents
                assigned_count = cluster_occupancy[a.target_cluster]
                if assigned_count > target_c.capacity:
                    excess = assigned_count - target_c.capacity
                    crowd_repulsion = self.k_crowd * excess * np.exp(-0.5 * (c_dist / target_c.radius)**2)
                    cluster_acc += crowd_repulsion * (c_diff / c_dist)

            # Stigmergic trail gradient force
            trail_acc = np.zeros(self.dim)
            if self.stigmergic_history:
                for trail_pos, intensity in self.stigmergic_history[-40:]:
                    t_diff = trail_pos - pos
                    t_dist_sq = float(np.sum(t_diff**2))
                    if t_dist_sq < 9.0:
                        kernel = np.exp(-t_dist_sq / 3.0)
                        trail_acc += self.k_trail * intensity * kernel * t_diff

            # Boundary confinement
            r_curr = float(np.linalg.norm(pos))
            boundary_acc = np.zeros(self.dim)
            if r_curr > (self.horizon_radius - 1.5):
                dr = r_curr - (self.horizon_radius - 1.5)
                boundary_acc = -15.0 * dr * (pos / (r_curr + 1e-8))

            # Adaptive velocity damping
            v_norm_sq = float(vel @ g @ vel)
            damping_gamma = self.gamma_base + 0.05 * v_norm_sq
            drag_acc = -damping_gamma * vel

            # Net acceleration
            total_acc = (
                geodesic_acc +
                inv_g @ (cluster_acc + trail_acc + boundary_acc) +
                accelerations[i] +
                drag_acc
            )

            # Symplectic integration
            vel_next = vel + self.dt * total_acc
            pos_next = pos + self.dt * vel_next

            # Kinetic energy and dissipation
            ke = 0.5 * float(vel_next @ g @ vel_next)
            dE = 2.0 * damping_gamma * ke * self.dt

            total_ke += ke
            step_dissipation += dE

            # Update agent state
            a.position = pos_next
            a.velocity = vel_next
            a.path.append(pos_next.copy())
            a.dwell_time += self.dt

            # Feed dissipation to Hippocampal Sink if connected
            if self.sink is not None:
                step_res = GeodesicStepResult(
                    position=pos_next,
                    velocity=vel_next,
                    acceleration=total_acc,
                    ricci_scalar=0.1,
                    damping_gamma=damping_gamma,
                    kinetic_energy=ke,
                    is_throttled=False,
                    routing_channel=a.target_cluster or "swarm_void"
                )
                self.sink.absorb_step(
                    node_id=a.agent_id,
                    coords=pos_next,
                    step_result=step_res,
                    g_ij=g,
                    dt=self.dt
                )

            # Deposit stigmergic footprint
            if a.status == "converged":
                self.stigmergic_history.append((pos_next.copy(), 1.5))
            else:
                self.stigmergic_history.append((pos_next.copy(), 0.5))

        # Evaporate old stigmergic trails
        self.stigmergic_history = [
            (pos, intensity * (1.0 - self.trail_decay))
            for pos, intensity in self.stigmergic_history
            if intensity * (1.0 - self.trail_decay) > 0.05
        ]

        self.total_dissipated_energy += step_dissipation

        # 3. Flocking / Alignment Order Parameter: r = 1/N || sum v_m / ||v_m|| ||
        unit_vels = []
        for a in agent_list:
            spd = float(np.linalg.norm(a.velocity))
            if spd > 1e-6:
                unit_vels.append(a.velocity / spd)
            else:
                unit_vels.append(np.zeros(self.dim))

        mean_dir = np.mean(unit_vels, axis=0) if unit_vels else np.zeros(self.dim)
        order_param = float(np.linalg.norm(mean_dir))

        # Maximum condition number
        cond_max = max(float(np.linalg.cond(g)) for g in metrics)

        return SwarmStepReport(
            step_index=step_index,
            order_parameter=round(order_param, 4),
            cluster_allocations=cluster_occupancy,
            total_kinetic_energy=round(total_ke, 4),
            dissipated_energy=round(step_dissipation, 4),
            collision_events_avoided=collision_avoidance_count,
            min_pairwise_distance=round(min_pdist if min_pdist != float("inf") else 0.0, 4),
            converged_agents=converged_count,
            metric_condition_number=round(cond_max, 2),
            order_direction=mean_dir
        )

    def run_routing_mission(self, max_steps: int = 80) -> List[SwarmStepReport]:
        """Runs the autonomous swarm routing simulation until convergence or max_steps."""
        reports = []
        for step in range(max_steps):
            report = self.step_swarm(step_index=step)
            reports.append(report)
            # If all agents have converged to target clusters, terminate mission early
            if report.converged_agents == len(self.agents) and len(self.agents) > 0:
                break
        return reports

    def get_consensus_summary(self) -> Dict[str, Union[float, int, str, Dict]]:
        """Returns high-level summary of swarm convergence and load distribution."""
        total_agents = len(self.agents)
        converged = sum(1 for a in self.agents.values() if a.status == "converged")
        cluster_counts = {cid: 0 for cid in self.clusters}
        for a in self.agents.values():
            if a.target_cluster and a.target_cluster in cluster_counts:
                cluster_counts[a.target_cluster] += 1

        return {
            "total_agents": total_agents,
            "converged_agents": converged,
            "convergence_rate": round(converged / max(total_agents, 1), 4),
            "cluster_distribution": cluster_counts,
            "total_dissipated_energy": round(self.total_dissipated_energy, 4),
            "stigmergic_trail_nodes": len(self.stigmergic_history),
            "status": "ALL_CONVERGED" if converged == total_agents and total_agents > 0 else "PARTIAL_ROUTING"
        }
