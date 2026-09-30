"""
Frontier_OS: Multi-Cluster Distributed Swarm Sharding & Mesh Coordinator
File: Frontier_OS/core/sharding/distributed_swarm.py

Implements spatial and semantic domain decomposition for massive-scale Exciton swarms
and 7 Giants MoA operators across distributed compute shards:
1. ShardDomain: Bounding box partition with halo margins and dynamic boundary adjustment.
2. SwarmShardNode: Autonomous compute shard simulating local excitons with ghost particle coupling.
3. SwarmMeshCoordinator: Central mesh coordinator managing halo exchange, transit routing,
   global Kuramoto/Jeans reduction, dynamic load balancing, and Hippocampal memory sink consolidation.
4. DistributedSwarmCluster: High-level cluster facade with uniform grid and 1D strip partitioning.
"""

from dataclasses import dataclass, field
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import scipy.linalg as la

from Frontier_OS.core.hippocampal_sink import HippocampalMemorySink
from Frontier_OS.core.seven_giants import (
    GiantRole,
    GiantProfile,
    GIANT_PROFILES,
    SevenGiantsEnsemble
)
from Frontier_OS.core.sharding.ipc_fabric import (
    EXCITON_DTYPE,
    ExcitonTransitPacket,
    HaloBuffer,
    SharedMemoryMeshBuffer,
    SwarmIPCChannel
)
from Frontier_OS.core.swarm_router import (
    AutonomousSwarmRouter,
    SwarmAgent,
    SwarmCluster,
    SwarmStepReport
)


@dataclass
class ShardDomain:
    """
    Defines the spatial region Ω_k assigned to a shard node on the manifold.
    Coordinates correspond to the primary 2D manifold plane (x_0, x_1) or (x, z).
    """
    shard_id: str
    x_min: float
    x_max: float
    z_min: float
    z_max: float
    halo_margin: float = 1.2

    def contains(self, pos: np.ndarray) -> bool:
        """Checks if a coordinate position lies strictly within the primary domain bounds."""
        x, z = float(pos[0]), float(pos[1])
        return (self.x_min <= x <= self.x_max) and (self.z_min <= z <= self.z_max)

    def in_halo(self, pos: np.ndarray) -> bool:
        """Checks if a coordinate position lies within the expanded halo domain."""
        x, z = float(pos[0]), float(pos[1])
        return (
            (self.x_min - self.halo_margin <= x <= self.x_max + self.halo_margin) and
            (self.z_min - self.halo_margin <= z <= self.z_max + self.halo_margin)
        )

    def is_near_boundary(self, pos: np.ndarray) -> bool:
        """Checks if an agent inside the domain is within the halo margin of any border."""
        if not self.contains(pos):
            return False
        x, z = float(pos[0]), float(pos[1])
        dx = min(abs(x - self.x_min), abs(x - self.x_max))
        dz = min(abs(z - self.z_min), abs(z - self.z_max))
        return min(dx, dz) <= self.halo_margin

    def distance_to_boundary(self, pos: np.ndarray) -> float:
        """Calculates distance from point to the nearest primary domain boundary."""
        x, z = float(pos[0]), float(pos[1])
        dx = min(abs(x - self.x_min), abs(x - self.x_max))
        dz = min(abs(z - self.z_min), abs(z - self.z_max))
        return float(min(dx, dz))

    def shift_boundary_x(self, delta: float, side: str = "max", min_span: float = 1.0) -> None:
        """Adjusts the x boundary for dynamic load balancing."""
        if side == "max":
            if (self.x_max + delta) - self.x_min >= min_span:
                self.x_max += delta
        elif side == "min":
            if self.x_max - (self.x_min + delta) >= min_span:
                self.x_min += delta

    def shift_boundary_z(self, delta: float, side: str = "max", min_span: float = 1.0) -> None:
        """Adjusts the z boundary for dynamic load balancing."""
        if side == "max":
            if (self.z_max + delta) - self.z_min >= min_span:
                self.z_max += delta
        elif side == "min":
            if self.z_max - (self.z_min + delta) >= min_span:
                self.z_min += delta


@dataclass
class ShardTelemetryReport:
    """Local performance and physics telemetry snapshot for an individual shard."""
    step_index: int
    shard_id: str
    active_agent_count: int
    order_parameter: float
    order_direction: np.ndarray
    total_kinetic_energy: float
    dissipated_energy: float
    transits_out: int
    transits_in: int
    halo_particles_received: int
    min_pairwise_distance: float
    execution_time_ms: float


class SwarmShardNode:
    """
    Autonomous compute worker executing local geodesic navigation and 7 Giants MoA operators
    over its assigned spatial subdomain Ω_k.
    """
    def __init__(
        self,
        shard_id: str,
        domain: ShardDomain,
        dim: int = 4,
        dt: float = 0.02,
        k_repulsion: float = 1.2,
        r_repulsion: float = 0.8,
        k_alignment: float = 0.85,
        r_alignment: float = 2.5,
        k_cluster: float = 1.5,
        k_crowd: float = 2.0,
        horizon_radius: float = 50.0
    ):
        self.shard_id = shard_id
        self.domain = domain
        self.dim = dim
        self.dt = dt
        self.neighbors: List[str] = []
        self.horizon_radius = horizon_radius

        # Local Swarm Router and 7 Giants MoA Ensemble
        self.router = AutonomousSwarmRouter(
            dim=dim,
            dt=dt,
            k_repulsion=k_repulsion,
            r_repulsion=r_repulsion,
            k_alignment=k_alignment,
            r_alignment=r_alignment,
            k_cluster=k_cluster,
            k_crowd=k_crowd,
            horizon_radius=horizon_radius
        )
        self.seven_giants = SevenGiantsEnsemble(dim=dim)
        self.ipc_channel = SwarmIPCChannel(shard_id=shard_id)

        self._transits_in_count: int = 0
        self._transits_out_count: int = 0
        self._ghost_particles_count: int = 0

    def add_agent(self, agent: SwarmAgent) -> SwarmAgent:
        """Adds an Exciton agent directly into the shard's active population."""
        return self.router.add_agent(
            agent_id=agent.agent_id,
            role=agent.role,
            position=agent.position,
            velocity=agent.velocity,
            mass=agent.mass,
            charge=agent.charge,
            target_cluster=agent.target_cluster
        )

    def add_cluster(self, cluster: SwarmCluster) -> SwarmCluster:
        """Registers a semantic cluster / goal well on this shard."""
        return self.router.add_cluster(
            cluster_id=cluster.cluster_id,
            centroid=cluster.centroid,
            radius=cluster.radius,
            capacity=cluster.capacity,
            semantic_density=cluster.semantic_density
        )

    def ingest_transits(self) -> int:
        """Pops and registers all incoming transit packets from the IPC channel."""
        transits = self.ipc_channel.pop_transits()
        count = len(transits)
        for pkt in transits:
            self.router.add_agent(
                agent_id=pkt.agent_id,
                role=pkt.role,
                position=pkt.position,
                velocity=pkt.velocity,
                mass=pkt.mass,
                charge=pkt.charge,
                target_cluster=pkt.target_cluster
            )
        self._transits_in_count += count
        return count

    def apply_halos(self) -> int:
        """
        Applies smooth inter-shard boundary forces (repulsion & velocity alignment)
        from received neighbor ghost particles onto local border-adjacent agents.
        """
        halos = self.ipc_channel.get_all_halos()
        if not halos or not self.router.agents:
            return 0

        ghost_count = sum(h.count for h in halos)
        self._ghost_particles_count = ghost_count
        if ghost_count == 0:
            return 0

        # Extract local border agents
        local_agents = [
            a for a in self.router.agents.values()
            if self.domain.is_near_boundary(a.position)
        ]
        if not local_agents:
            return ghost_count

        k_rep = self.router.k_repulsion
        r_rep = self.router.r_repulsion
        k_align = self.router.k_alignment
        r_align = self.router.r_alignment
        dt = self.dt

        for halo in halos:
            if halo.count == 0:
                continue
            for a in local_agents:
                # Compute distance to each ghost particle
                diffs = a.position - halo.positions  # (M, dim)
                d_sq = np.sum(diffs**2, axis=-1)
                dist = np.sqrt(np.maximum(d_sq, 1e-12))

                # 1. Ghost Repulsion
                rep_mask = dist < r_rep
                if np.any(rep_mask):
                    idx_rep = np.where(rep_mask)[0]
                    for idx in idx_rep:
                        d = float(dist[idx])
                        u = diffs[idx] / max(d, 1e-6)
                        q_j = float(halo.charges[idx])
                        rep_mag = k_rep * a.charge * q_j * np.exp(-0.5 * (d / (r_rep + 1e-6))**2)
                        a.velocity += (rep_mag / a.mass) * dt * u

                # 2. Ghost Velocity Alignment
                align_mask = dist < r_align
                if np.any(align_mask):
                    idx_align = np.where(align_mask)[0]
                    for idx in idx_align:
                        d = float(dist[idx])
                        weight = np.exp(-0.5 * (d / (r_align + 1e-6))**2)
                        v_diff = halo.velocities[idx] - a.velocity
                        a.velocity += (k_align * weight / (len(self.router.agents) + ghost_count)) * dt * v_diff

        return ghost_count

    def extract_halo_buffer(self, step_index: int) -> HaloBuffer:
        """
        Extracts border-adjacent agents and constructs a HaloBuffer
        to broadcast to neighbor shards.
        """
        border_agents = [
            a for a in self.router.agents.values()
            if self.domain.is_near_boundary(a.position)
        ]
        m = len(border_agents)
        if m == 0:
            return HaloBuffer(
                source_shard_id=self.shard_id,
                step_index=step_index,
                positions=np.zeros((0, self.dim), dtype=np.float32),
                velocities=np.zeros((0, self.dim), dtype=np.float32),
                charges=np.zeros(0, dtype=np.float32),
                masses=np.zeros(0, dtype=np.float32)
            )

        positions = np.array([a.position for a in border_agents], dtype=np.float32)
        velocities = np.array([a.velocity for a in border_agents], dtype=np.float32)
        charges = np.array([a.charge for a in border_agents], dtype=np.float32)
        masses = np.array([a.mass for a in border_agents], dtype=np.float32)

        return HaloBuffer(
            source_shard_id=self.shard_id,
            step_index=step_index,
            positions=positions,
            velocities=velocities,
            charges=charges,
            masses=masses
        )

    def detect_and_evacuate_transits(
        self,
        domain_lookup: Dict[str, ShardDomain]
    ) -> List[ExcitonTransitPacket]:
        """
        Finds all agents that have moved outside this shard's primary domain,
        removes them from local memory, and constructs transit packets for the destination shards.
        """
        transits: List[ExcitonTransitPacket] = []
        evacuate_ids: List[str] = []

        for agent_id, agent in self.router.agents.items():
            if not self.domain.contains(agent.position):
                # Locate destination shard
                dest_id = None
                for nid in self.neighbors:
                    ndomain = domain_lookup.get(nid)
                    if ndomain and ndomain.contains(agent.position):
                        dest_id = nid
                        break

                # If not inside a known neighbor, find closest neighbor
                if dest_id is None:
                    min_dist = float("inf")
                    for nid in self.neighbors:
                        ndomain = domain_lookup.get(nid)
                        if ndomain:
                            d = ndomain.distance_to_boundary(agent.position)
                            if d < min_dist:
                                min_dist = d
                                dest_id = nid

                if dest_id is None and self.neighbors:
                    dest_id = self.neighbors[0]

                if dest_id is not None:
                    pkt = ExcitonTransitPacket(
                        agent_id=agent.agent_id,
                        role=agent.role,
                        position=agent.position.copy(),
                        velocity=agent.velocity.copy(),
                        mass=agent.mass,
                        charge=agent.charge,
                        target_cluster=agent.target_cluster,
                        target_coords=agent.target_coords.copy() if agent.target_coords is not None else None,
                        dwell_time=agent.dwell_time,
                        source_shard_id=self.shard_id,
                        dest_shard_id=dest_id,
                        transit_timestamp=time.time()
                    )
                    transits.append(pkt)
                    evacuate_ids.append(agent_id)

        # Remove evacuated agents from local router
        for aid in evacuate_ids:
            del self.router.agents[aid]

        self._transits_out_count += len(transits)
        return transits

    def step(self, step_index: int) -> Tuple[SwarmStepReport, ShardTelemetryReport]:
        """Executes local integration step for this shard."""
        t0 = time.time()

        # Check for 7 Giants roles and apply specialized differential operators
        giant_roles = {r.value for r in GiantRole}
        has_giants = any(a.role in giant_roles for a in self.router.agents.values())
        if has_giants and len(self.router.agents) > 0:
            metrics = [self.router.compute_local_metric(a.position) for a in self.router.agents.values()]
            extra_accs, _ = self.seven_giants.compute_giant_operators(self.router, metrics)
            for aid, acc in extra_accs.items():
                if aid in self.router.agents:
                    self.router.agents[aid].velocity += acc * self.dt

        # Step local router
        swarm_report = self.router.step_swarm(step_index=step_index)
        t_elapsed = (time.time() - t0) * 1000.0

        telemetry = ShardTelemetryReport(
            step_index=step_index,
            shard_id=self.shard_id,
            active_agent_count=len(self.router.agents),
            order_parameter=swarm_report.order_parameter,
            order_direction=swarm_report.order_direction,
            total_kinetic_energy=swarm_report.total_kinetic_energy,
            dissipated_energy=swarm_report.dissipated_energy,
            transits_out=self._transits_out_count,
            transits_in=self._transits_in_count,
            halo_particles_received=self._ghost_particles_count,
            min_pairwise_distance=swarm_report.min_pairwise_distance,
            execution_time_ms=t_elapsed
        )
        return swarm_report, telemetry


@dataclass
class DistributedSwarmReport:
    """Consolidated telemetry snapshot across all cluster shards."""
    step_index: int
    total_active_agents: int
    global_order_parameter: float           # Global Kuramoto alignment r in [0, 1]
    global_order_direction: np.ndarray
    global_jeans_centroid: np.ndarray       # Center of mass
    total_kinetic_energy: float
    total_dissipated_energy: float
    total_transits_occurred: int
    max_load_imbalance: float
    shard_allocations: Dict[str, int]
    shard_reports: Dict[str, ShardTelemetryReport]
    mesh_step_time_ms: float


class SwarmMeshCoordinator:
    """
    Coordinates an ensemble of distributed SwarmShardNode workers.
    Manages halo buffer exchange, inter-shard transit routing,
    global 7 Giants operator reduction, and dynamic load balancing.
    """
    def __init__(
        self,
        shards: List[SwarmShardNode],
        topology: Optional[Dict[str, List[str]]] = None,
        hippocampal_sink: Optional[HippocampalMemorySink] = None,
        shared_memory_buffer: Optional[SharedMemoryMeshBuffer] = None,
        rebalance_threshold: float = 0.40,
        rebalance_rate: float = 0.05
    ):
        self.shards: Dict[str, SwarmShardNode] = {s.shard_id: s for s in shards}
        self.topology: Dict[str, List[str]] = topology or {}
        self.sink = hippocampal_sink
        self.shared_memory = shared_memory_buffer
        self.rebalance_threshold = rebalance_threshold
        self.rebalance_rate = rebalance_rate

        self.total_transits_cumulative: int = 0
        self.step_index: int = 0

        # Wire neighbor adjacencies into shard nodes
        for shard_id, neighbors in self.topology.items():
            if shard_id in self.shards:
                self.shards[shard_id].neighbors = neighbors

    @property
    def domain_lookup(self) -> Dict[str, ShardDomain]:
        return {sid: s.domain for sid, s in self.shards.items()}

    def step_mesh(self) -> DistributedSwarmReport:
        """
        Executes a synchronized distributed step across the entire cluster mesh:
        Phase 1: Halo Buffer Extraction & Neighbor Exchange
        Phase 2: Halo Force Application & Local Geodesic Steps
        Phase 3: Boundary Detection & Transit Routing
        Phase 4: Global Reduction (Kuramoto, Jeans, Carnot Sink)
        Phase 5: Dynamic Load Balancing
        Phase 6: Shared Memory Buffer Synchronization
        """
        t0 = time.time()
        self.step_index += 1

        # Phase 1: Halo Extraction & Neighbor Dispatch
        halo_buffers: Dict[str, HaloBuffer] = {}
        for sid, shard in self.shards.items():
            halo_buffers[sid] = shard.extract_halo_buffer(self.step_index)

        for sid, shard in self.shards.items():
            for nid in shard.neighbors:
                if nid in halo_buffers:
                    shard.ipc_channel.update_halo(halo_buffers[nid])

        # Phase 2: Ingest Halos & Local Step
        shard_telemetries: Dict[str, ShardTelemetryReport] = {}
        for sid, shard in self.shards.items():
            # Ingest previous transits
            shard.ingest_transits()
            # Apply halo interaction forces
            shard.apply_halos()
            # Execute local step
            _, telem = shard.step(self.step_index)
            shard_telemetries[sid] = telem

        # Phase 3: Detect & Route Transits
        domain_map = self.domain_lookup
        all_transits: List[ExcitonTransitPacket] = []
        for sid, shard in self.shards.items():
            transits = shard.detect_and_evacuate_transits(domain_map)
            all_transits.extend(transits)

        # Route transits to destination shard IPC inboxes
        for pkt in all_transits:
            dst = pkt.dest_shard_id
            if dst in self.shards:
                self.shards[dst].ipc_channel.push_transit(pkt)
            else:
                # Fallback to source shard if destination unknown
                self.shards[pkt.source_shard_id].ipc_channel.push_transit(pkt)

        # Immediately ingest transits into destination shards for exact agent conservation
        for shard in self.shards.values():
            shard.ingest_transits()

        self.total_transits_cumulative += len(all_transits)

        # Phase 4: Global Reduction & Consensus
        all_agents: List[SwarmAgent] = []
        for shard in self.shards.values():
            all_agents.extend(shard.router.agents.values())

        total_active = len(all_agents)
        if total_active > 0:
            # Global Kuramoto consensus order parameter r in [0, 1]
            vels = np.array([a.velocity for a in all_agents], dtype=np.float64)
            speeds = np.linalg.norm(vels, axis=1, keepdims=True)
            unit_vels = vels / np.maximum(speeds, 1e-12)
            mean_unit_vel = np.mean(unit_vels, axis=0)
            global_r = float(np.linalg.norm(mean_unit_vel))
            global_dir = mean_unit_vel / max(global_r, 1e-12)

            # Global Jeans Center of Mass
            masses = np.array([a.mass for a in all_agents], dtype=np.float64)
            positions = np.array([a.position for a in all_agents], dtype=np.float64)
            jeans_centroid = np.sum(positions * masses[:, np.newaxis], axis=0) / np.maximum(np.sum(masses), 1e-12)

            total_ke = float(np.sum(0.5 * masses * (speeds[:, 0]**2)))
        else:
            dim = list(self.shards.values())[0].dim
            global_r = 0.0
            global_dir = np.zeros(dim)
            jeans_centroid = np.zeros(dim)
            total_ke = 0.0

        total_dissipation = sum(t.dissipated_energy for t in shard_telemetries.values())

        # Consolidate dissipation into Hippocampal Memory Sink
        if self.sink is not None and total_dissipation > 0:
            self.sink.record_dissipation(total_dissipation, step_index=self.step_index)

        # Shard allocations & load imbalance
        allocs = {sid: len(s.router.agents) for sid, s in self.shards.items()}
        counts = list(allocs.values())
        mean_count = max(float(np.mean(counts)), 1.0)
        imbalance = float((max(counts) - min(counts)) / mean_count) if len(counts) > 1 else 0.0

        # Phase 5: Dynamic Load Balancing
        if imbalance > self.rebalance_threshold and len(self.shards) > 1:
            self._rebalance_shards()

        # Phase 6: Shared Memory Buffer Sync
        if self.shared_memory is not None and total_active > 0:
            self._sync_shared_memory(all_agents)

        elapsed_ms = (time.time() - t0) * 1000.0

        return DistributedSwarmReport(
            step_index=self.step_index,
            total_active_agents=total_active,
            global_order_parameter=global_r,
            global_order_direction=global_dir,
            global_jeans_centroid=jeans_centroid,
            total_kinetic_energy=total_ke,
            total_dissipated_energy=total_dissipation,
            total_transits_occurred=len(all_transits),
            max_load_imbalance=imbalance,
            shard_allocations=allocs,
            shard_reports=shard_telemetries,
            mesh_step_time_ms=elapsed_ms
        )

    def _rebalance_shards(self) -> None:
        """
        Dynamically shifts shard boundaries between adjacent pairs
        to re-distribute agent densities proportionally.
        """
        # Iterate over adjacent shard pairs in topology
        for sid, neighbors in self.topology.items():
            count_i = len(self.shards[sid].router.agents)
            domain_i = self.shards[sid].domain
            for nid in neighbors:
                if sid >= nid:
                    continue  # Process each pair once
                count_j = len(self.shards[nid].router.agents)
                domain_j = self.shards[nid].domain

                # Check if shards share an X boundary: domain_i.x_max == domain_j.x_min
                if abs(domain_i.x_max - domain_j.x_min) < 1e-4:
                    diff = count_i - count_j
                    if abs(diff) > 2:
                        shift = np.clip(diff * self.rebalance_rate, -1.0, 1.0)
                        # Overloaded shard i shrinks boundary: x_max moves left
                        # Underloaded shard j expands boundary: x_min moves left
                        if (domain_i.x_max - shift) - domain_i.x_min >= 1.0 and domain_j.x_max - (domain_j.x_min - shift) >= 1.0:
                            domain_i.x_max -= shift
                            domain_j.x_min -= shift

    def _sync_shared_memory(self, agents: List[SwarmAgent]) -> None:
        """Writes current multi-shard agent states into zero-copy shared memory."""
        arr = self.shared_memory.as_array()
        count = min(len(agents), self.shared_memory.capacity)
        for i in range(count):
            a = agents[i]
            # pos (x, y, z, phase)
            p = a.position
            arr[i]['pos'][0] = p[0] if len(p) > 0 else 0.0
            arr[i]['pos'][1] = p[1] if len(p) > 1 else 0.0
            arr[i]['pos'][2] = p[2] if len(p) > 2 else 0.0
            arr[i]['pos'][3] = p[3] if len(p) > 3 else 0.0

            # vel (vx, vy, vz, mass)
            v = a.velocity
            arr[i]['vel'][0] = v[0] if len(v) > 0 else 0.0
            arr[i]['vel'][1] = v[1] if len(v) > 1 else 0.0
            arr[i]['vel'][2] = v[2] if len(v) > 2 else 0.0
            arr[i]['vel'][3] = a.mass

            # extra (charge, role_id, target_cluster_id, status)
            arr[i]['extra'][0] = a.charge
            arr[i]['extra'][1] = 0.0  # role_id
            arr[i]['extra'][2] = 0.0
            arr[i]['extra'][3] = 1.0 if a.status == "converged" else 0.0

        self.shared_memory.set_active_count(count, self.step_index)


class DistributedSwarmCluster:
    """
    High-level factory and controller for distributed multi-cluster Exciton swarm simulations.
    Supports uniform spatial grids and 1D strip domain decompositions.
    """
    def __init__(
        self,
        coordinator: SwarmMeshCoordinator
    ):
        self.coordinator = coordinator

    @classmethod
    def create_1d_strip(
        cls,
        num_shards: int = 4,
        x_span: Tuple[float, float] = (-20.0, 20.0),
        z_span: Tuple[float, float] = (-20.0, 20.0),
        dim: int = 4,
        dt: float = 0.02,
        halo_margin: float = 1.2,
        hippocampal_sink: Optional[HippocampalMemorySink] = None,
        shared_memory_name: Optional[str] = None,
        shared_memory_capacity: int = 10000
    ) -> 'DistributedSwarmCluster':
        """
        Partitions the manifold into a 1D horizontal strip decomposition along the X-axis.
        Shard k manages [x_k, x_{k+1}] × [z_min, z_max].
        """
        x_min, x_max = x_span
        z_min, z_max = z_span
        dx = (x_max - x_min) / num_shards

        shards: List[SwarmShardNode] = []
        topology: Dict[str, List[str]] = {}

        horizon_radius = max(abs(x_min), abs(x_max), abs(z_min), abs(z_max)) * 2.0
        for k in range(num_shards):
            sid = f"shard-{k}"
            sx_min = x_min + k * dx
            sx_max = x_min + (k + 1) * dx
            domain = ShardDomain(
                shard_id=sid,
                x_min=sx_min,
                x_max=sx_max,
                z_min=z_min,
                z_max=z_max,
                halo_margin=halo_margin
            )
            node = SwarmShardNode(shard_id=sid, domain=domain, dim=dim, dt=dt, horizon_radius=horizon_radius)
            shards.append(node)

            # 1D line topology
            neighbors: List[str] = []
            if k > 0:
                neighbors.append(f"shard-{k-1}")
            if k < num_shards - 1:
                neighbors.append(f"shard-{k+1}")
            topology[sid] = neighbors

        shm = None
        if shared_memory_name is not None:
            shm = SharedMemoryMeshBuffer(
                name=shared_memory_name,
                capacity=shared_memory_capacity,
                create=True
            )

        coordinator = SwarmMeshCoordinator(
            shards=shards,
            topology=topology,
            hippocampal_sink=hippocampal_sink,
            shared_memory_buffer=shm
        )
        return cls(coordinator=coordinator)

    @classmethod
    def create_2d_grid(
        cls,
        grid_x: int = 2,
        grid_z: int = 2,
        x_span: Tuple[float, float] = (-20.0, 20.0),
        z_span: Tuple[float, float] = (-20.0, 20.0),
        dim: int = 4,
        dt: float = 0.02,
        halo_margin: float = 1.2,
        hippocampal_sink: Optional[HippocampalMemorySink] = None,
        shared_memory_name: Optional[str] = None,
        shared_memory_capacity: int = 10000
    ) -> 'DistributedSwarmCluster':
        """
        Partitions the manifold into a 2D Cartesian grid of grid_x × grid_z shards.
        """
        x_min, x_max = x_span
        z_min, z_max = z_span
        dx = (x_max - x_min) / grid_x
        dz = (z_max - z_min) / grid_z

        shards: List[SwarmShardNode] = []
        topology: Dict[str, List[str]] = {}

        horizon_radius = max(abs(x_min), abs(x_max), abs(z_min), abs(z_max)) * 2.0
        for ix in range(grid_x):
            for iz in range(grid_z):
                sid = f"shard-{ix}_{iz}"
                sx_min = x_min + ix * dx
                sx_max = x_min + (ix + 1) * dx
                sz_min = z_min + iz * dz
                sz_max = z_min + (iz + 1) * dz
                domain = ShardDomain(
                    shard_id=sid,
                    x_min=sx_min,
                    x_max=sx_max,
                    z_min=sz_min,
                    z_max=sz_max,
                    halo_margin=halo_margin
                )
                node = SwarmShardNode(shard_id=sid, domain=domain, dim=dim, dt=dt, horizon_radius=horizon_radius)
                shards.append(node)

                # 4-connected 2D grid topology
                neighbors: List[str] = []
                if ix > 0:
                    neighbors.append(f"shard-{ix-1}_{iz}")
                if ix < grid_x - 1:
                    neighbors.append(f"shard-{ix+1}_{iz}")
                if iz > 0:
                    neighbors.append(f"shard-{ix}_{iz-1}")
                if iz < grid_z - 1:
                    neighbors.append(f"shard-{ix}_{iz+1}")
                topology[sid] = neighbors

        shm = None
        if shared_memory_name is not None:
            shm = SharedMemoryMeshBuffer(
                name=shared_memory_name,
                capacity=shared_memory_capacity,
                create=True
            )

        coordinator = SwarmMeshCoordinator(
            shards=shards,
            topology=topology,
            hippocampal_sink=hippocampal_sink,
            shared_memory_buffer=shm
        )
        return cls(coordinator=coordinator)

    def inject_agent(self, agent: SwarmAgent) -> str:
        """
        Injects an agent into the cluster, automatically routing it to the
        appropriate shard containing its initial coordinate position.
        """
        for sid, shard in self.coordinator.shards.items():
            if shard.domain.contains(agent.position):
                shard.add_agent(agent)
                return sid

        # Fallback to closest shard if outside primary domain bounds
        min_dist = float("inf")
        best_sid = list(self.coordinator.shards.keys())[0]
        for sid, shard in self.coordinator.shards.items():
            d = shard.domain.distance_to_boundary(agent.position)
            if d < min_dist:
                min_dist = d
                best_sid = sid

        self.coordinator.shards[best_sid].add_agent(agent)
        return best_sid

    def inject_population(self, agents: List[SwarmAgent]) -> Dict[str, int]:
        """Injects an ensemble of agents across shards and returns allocation counts."""
        allocs: Dict[str, int] = {sid: 0 for sid in self.coordinator.shards}
        for a in agents:
            sid = self.inject_agent(a)
            allocs[sid] += 1
        return allocs

    def add_cluster(
        self,
        cluster_id: str,
        centroid: np.ndarray,
        radius: float = 1.5,
        capacity: int = 4,
        semantic_density: float = 1.0
    ) -> None:
        """Registers a semantic attractor cluster on all shards whose domain overlaps it."""
        cluster = SwarmCluster(
            cluster_id=cluster_id,
            centroid=np.asarray(centroid, dtype=np.float64),
            radius=radius,
            capacity=capacity,
            semantic_density=semantic_density
        )
        for shard in self.coordinator.shards.values():
            shard.add_cluster(cluster)

    def step(self, steps: int = 1) -> List[DistributedSwarmReport]:
        """Executes multiple synchronized distributed mesh steps."""
        reports: List[DistributedSwarmReport] = []
        for _ in range(steps):
            reports.append(self.coordinator.step_mesh())
        return reports

    def get_all_agents(self) -> List[SwarmAgent]:
        """Returns a flat list of all active agents across all shards."""
        agents = []
        for shard in self.coordinator.shards.values():
            agents.extend(shard.router.agents.values())
        return agents

    def close(self) -> None:
        """Cleans up shared memory resources if active."""
        if self.coordinator.shared_memory is not None:
            self.coordinator.shared_memory.close()
            self.coordinator.shared_memory.unlink()
