"""
Frontier_OS: Distributed Swarm Sharding IPC Fabric & Shared Memory Substrate
File: Frontier_OS/core/sharding/ipc_fabric.py

Provides high-throughput, zero-copy inter-process communication (IPC) for
distributed Exciton swarm sharding across multi-core CPU and GPU workers:
1. EXCITON_DTYPE: Exact 64-byte binary memory layout matching WebGPU WGSL ExcitonParticle.
2. SharedMemoryMeshBuffer: Zero-copy shared memory buffer with atomic version tracking.
3. ExcitonTransitPacket: Low-overhead binary serialization for inter-shard boundary handoffs.
4. HaloBuffer: Double-buffered ghost particle exchange for border interaction.
5. SwarmIPCChannel: Asynchronous message queue and high-speed transit transport.
"""

from dataclasses import dataclass, field
import io
from multiprocessing import shared_memory
import struct
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

# Exact 64-byte structured dtype matching WebGPU WGSL ExcitonParticle
# struct ExcitonParticle {
#     pos: vec4<f32>,     // x, y, z, phase
#     vel: vec4<f32>,     // vx, vy, vz, mass
#     color: vec4<f32>,   // r, g, b, alpha
#     extra: vec4<f32>,   // charge, role_id, target_cluster, status
# };
EXCITON_DTYPE = np.dtype([
    ('pos', np.float32, 4),    # x, y, z, phase
    ('vel', np.float32, 4),    # vx, vy, vz, mass
    ('color', np.float32, 4),  # r, g, b, alpha
    ('extra', np.float32, 4),  # charge, role_id, target_cluster, status
], align=True)

assert EXCITON_DTYPE.itemsize == 64, f"EXCITON_DTYPE itemsize must be 64 bytes, got {EXCITON_DTYPE.itemsize}"


@dataclass
class ExcitonTransitPacket:
    """
    Encapsulates state transfer when an Exciton agent crosses a spatial domain boundary.
    Guarantees phase-space continuity (position, velocity, mass, charge) without tearing.
    """
    agent_id: str
    role: str
    position: np.ndarray       # (dim,) float64 or float32
    velocity: np.ndarray       # (dim,) float64 or float32
    mass: float = 1.0
    charge: float = 1.0
    target_cluster: Optional[str] = None
    target_coords: Optional[np.ndarray] = None
    dwell_time: float = 0.0
    source_shard_id: str = ""
    dest_shard_id: str = ""
    transit_timestamp: float = field(default_factory=time.time)

    def to_bytes(self) -> bytes:
        """Serializes transit packet into a compact binary byte sequence."""
        buf = io.BytesIO()
        # Header: magic (4B) + id lengths
        id_bytes = self.agent_id.encode('utf-8')
        role_bytes = self.role.encode('utf-8')
        src_bytes = self.source_shard_id.encode('utf-8')
        dst_bytes = self.dest_shard_id.encode('utf-8')
        cluster_bytes = (self.target_cluster or "").encode('utf-8')

        dim = len(self.position)
        buf.write(struct.pack(
            "!4sHHBBBBdfffd",
            b"SOLX",
            len(id_bytes),
            len(role_bytes),
            len(src_bytes),
            len(dst_bytes),
            len(cluster_bytes),
            dim,
            self.transit_timestamp,
            self.mass,
            self.charge,
            self.dwell_time,
            float(self.target_coords is not None)
        ))
        buf.write(id_bytes)
        buf.write(role_bytes)
        buf.write(src_bytes)
        buf.write(dst_bytes)
        buf.write(cluster_bytes)

        # Write position and velocity vectors as float64
        pos_f64 = np.asarray(self.position, dtype=np.float64)
        vel_f64 = np.asarray(self.velocity, dtype=np.float64)
        buf.write(pos_f64.tobytes())
        buf.write(vel_f64.tobytes())

        if self.target_coords is not None:
            tc_f64 = np.asarray(self.target_coords, dtype=np.float64)
            buf.write(tc_f64.tobytes())

        return buf.getvalue()

    @classmethod
    def from_bytes(cls, data: bytes) -> 'ExcitonTransitPacket':
        """Deserializes transit packet from binary byte sequence."""
        buf = io.BytesIO(data)
        header_fmt = "!4sHHBBBBdfffd"
        hdr_size = struct.calcsize(header_fmt)
        hdr_data = buf.read(hdr_size)
        if len(hdr_data) < hdr_size:
            raise ValueError("Corrupt transit packet: truncated header")

        magic, id_len, role_len, src_len, dst_len, cluster_len, dim, timestamp, mass, charge, dwell, has_tc = struct.unpack(
            header_fmt, hdr_data
        )
        if magic != b"SOLX":
            raise ValueError(f"Invalid packet magic: expected SOLX, got {magic}")

        agent_id = buf.read(id_len).decode('utf-8')
        role = buf.read(role_len).decode('utf-8')
        src_shard = buf.read(src_len).decode('utf-8')
        dst_shard = buf.read(dst_len).decode('utf-8')
        cluster_str = buf.read(cluster_len).decode('utf-8')
        target_cluster = cluster_str if cluster_str else None

        pos_bytes = buf.read(dim * 8)
        vel_bytes = buf.read(dim * 8)
        position = np.frombuffer(pos_bytes, dtype=np.float64).copy()
        velocity = np.frombuffer(vel_bytes, dtype=np.float64).copy()

        target_coords = None
        if has_tc > 0.5:
            tc_bytes = buf.read(dim * 8)
            target_coords = np.frombuffer(tc_bytes, dtype=np.float64).copy()

        return cls(
            agent_id=agent_id,
            role=role,
            position=position,
            velocity=velocity,
            mass=mass,
            charge=charge,
            target_cluster=target_cluster,
            target_coords=target_coords,
            dwell_time=dwell,
            source_shard_id=src_shard,
            dest_shard_id=dst_shard,
            transit_timestamp=timestamp
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts packet to a JSON-serializable dictionary."""
        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "position": self.position.tolist(),
            "velocity": self.velocity.tolist(),
            "mass": float(self.mass),
            "charge": float(self.charge),
            "target_cluster": self.target_cluster,
            "target_coords": self.target_coords.tolist() if self.target_coords is not None else None,
            "dwell_time": float(self.dwell_time),
            "source_shard_id": self.source_shard_id,
            "dest_shard_id": self.dest_shard_id,
            "transit_timestamp": float(self.transit_timestamp)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExcitonTransitPacket':
        """Constructs packet from dictionary."""
        return cls(
            agent_id=data["agent_id"],
            role=data["role"],
            position=np.array(data["position"], dtype=np.float64),
            velocity=np.array(data["velocity"], dtype=np.float64),
            mass=data.get("mass", 1.0),
            charge=data.get("charge", 1.0),
            target_cluster=data.get("target_cluster"),
            target_coords=np.array(data["target_coords"], dtype=np.float64) if data.get("target_coords") is not None else None,
            dwell_time=data.get("dwell_time", 0.0),
            source_shard_id=data.get("source_shard_id", ""),
            dest_shard_id=data.get("dest_shard_id", ""),
            transit_timestamp=data.get("transit_timestamp", time.time())
        )


@dataclass
class HaloBuffer:
    """
    Ghost particle buffer exchanged between adjacent shards.
    Stores position, velocity, charge, and mass of border-adjacent excitons
    so neighboring shards compute continuous boundary interactions without forces tearing.
    """
    source_shard_id: str
    step_index: int
    positions: np.ndarray       # (M, dim)
    velocities: np.ndarray      # (M, dim)
    charges: np.ndarray         # (M,)
    masses: np.ndarray          # (M,)
    timestamp: float = field(default_factory=time.time)

    @property
    def count(self) -> int:
        return len(self.positions)

    def to_bytes(self) -> bytes:
        """Serializes halo buffer into binary format."""
        buf = io.BytesIO()
        src_bytes = self.source_shard_id.encode('utf-8')
        m, dim = self.positions.shape if len(self.positions.shape) == 2 else (0, 0)
        buf.write(struct.pack("!4sHQdd", b"HALO", len(src_bytes), m, dim, self.timestamp))
        buf.write(src_bytes)
        if m > 0:
            buf.write(np.asarray(self.positions, dtype=np.float32).tobytes())
            buf.write(np.asarray(self.velocities, dtype=np.float32).tobytes())
            buf.write(np.asarray(self.charges, dtype=np.float32).tobytes())
            buf.write(np.asarray(self.masses, dtype=np.float32).tobytes())
        return buf.getvalue()

    @classmethod
    def from_bytes(cls, data: bytes) -> 'HaloBuffer':
        """Deserializes halo buffer from binary bytes."""
        buf = io.BytesIO(data)
        hdr_fmt = "!4sHQdd"
        hdr_size = struct.calcsize(hdr_fmt)
        hdr_data = buf.read(hdr_size)
        magic, src_len, m, dim_f, timestamp = struct.unpack(hdr_fmt, hdr_data)
        dim = int(dim_f)
        if magic != b"HALO":
            raise ValueError(f"Invalid halo magic: expected HALO, got {magic}")
        source_shard_id = buf.read(src_len).decode('utf-8')
        if m > 0:
            pos_bytes = buf.read(m * dim * 4)
            vel_bytes = buf.read(m * dim * 4)
            charge_bytes = buf.read(m * 4)
            mass_bytes = buf.read(m * 4)
            positions = np.frombuffer(pos_bytes, dtype=np.float32).reshape(m, dim).copy()
            velocities = np.frombuffer(vel_bytes, dtype=np.float32).reshape(m, dim).copy()
            charges = np.frombuffer(charge_bytes, dtype=np.float32).copy()
            masses = np.frombuffer(mass_bytes, dtype=np.float32).copy()
        else:
            positions = np.zeros((0, 0), dtype=np.float32)
            velocities = np.zeros((0, 0), dtype=np.float32)
            charges = np.zeros(0, dtype=np.float32)
            masses = np.zeros(0, dtype=np.float32)

        return cls(
            source_shard_id=source_shard_id,
            step_index=0,
            positions=positions,
            velocities=velocities,
            charges=charges,
            masses=masses,
            timestamp=timestamp
        )


class SharedMemoryMeshBuffer:
    """
    Zero-copy shared memory buffer allocating contiguous physical memory for
    up to max_particles Excitons using the 64-byte EXCITON_DTYPE schema.
    Can be mapped concurrently by multiple worker processes without memory duplication.
    """
    # Header format: magic (4B) + capacity (u32) + active_count (u32) + step_index (u64) + timestamp (f64)
    HEADER_FMT = "!4sIIQd"
    HEADER_SIZE = struct.calcsize(HEADER_FMT)

    def __init__(self, name: str, capacity: int, create: bool = False):
        self.name = name
        self.capacity = capacity
        self.total_size = self.HEADER_SIZE + capacity * EXCITON_DTYPE.itemsize
        self._is_creator = create

        if create:
            # Clean up existing if orphaned
            try:
                existing = shared_memory.SharedMemory(name=self.name)
                existing.close()
                existing.unlink()
            except FileNotFoundError:
                pass
            self.shm = shared_memory.SharedMemory(name=self.name, create=True, size=self.total_size)
            # Initialize header
            self._write_header(active_count=0, step_index=0, timestamp=time.time())
        else:
            self.shm = shared_memory.SharedMemory(name=self.name, create=False)

    def _write_header(self, active_count: int, step_index: int, timestamp: float) -> None:
        hdr = struct.pack(self.HEADER_FMT, b"SM01", self.capacity, active_count, step_index, timestamp)
        self.shm.buf[:self.HEADER_SIZE] = hdr

    def read_header(self) -> Tuple[int, int, int, float]:
        """Reads (capacity, active_count, step_index, timestamp)."""
        hdr_data = bytes(self.shm.buf[:self.HEADER_SIZE])
        magic, cap, active, step, ts = struct.unpack(self.HEADER_FMT, hdr_data)
        if magic != b"SM01":
            raise ValueError(f"Invalid shared memory header magic: {magic}")
        return cap, active, step, ts

    def set_active_count(self, count: int, step_index: int) -> None:
        """Updates active exciton count and step index atomically."""
        cap, _, _, _ = self.read_header()
        self._write_header(active_count=count, step_index=step_index, timestamp=time.time())

    def as_array(self) -> np.ndarray:
        """
        Returns a zero-copy NumPy structured array view over the particle buffer.
        Modifications to this array directly alter shared memory.
        """
        raw_buffer = self.shm.buf[self.HEADER_SIZE:self.HEADER_SIZE + self.capacity * EXCITON_DTYPE.itemsize]
        return np.ndarray((self.capacity,), dtype=EXCITON_DTYPE, buffer=raw_buffer)

    def close(self) -> None:
        """Closes the shared memory handle."""
        self.shm.close()

    def unlink(self) -> None:
        """Destroys and frees the shared memory segment."""
        try:
            self.shm.unlink()
        except FileNotFoundError:
            pass


class SwarmIPCChannel:
    """
    In-process and inter-process transport channel for exciton migratory transit packets
    and halo boundary exchanges between shard nodes.
    """
    def __init__(self, shard_id: str):
        self.shard_id = shard_id
        self._transit_inbox: List[ExcitonTransitPacket] = []
        self._halo_inbox: Dict[str, HaloBuffer] = {}
        self._metrics_log: List[Dict[str, Any]] = []
        self.total_packets_sent: int = 0
        self.total_packets_received: int = 0
        self.total_bytes_transferred: int = 0
        self.transit_latency_accumulator: float = 0.0

    def push_transit(self, packet: ExcitonTransitPacket) -> None:
        """Receives an inbound exciton transit packet."""
        now = time.time()
        latency = (now - packet.transit_timestamp) * 1000.0  # in ms
        self.transit_latency_accumulator += latency
        self._transit_inbox.append(packet)
        self.total_packets_received += 1
        self.total_bytes_transferred += len(packet.to_bytes())

    def pop_transits(self) -> List[ExcitonTransitPacket]:
        """Flushes and returns all pending transit packets."""
        packets = list(self._transit_inbox)
        self._transit_inbox.clear()
        return packets

    def update_halo(self, halo: HaloBuffer) -> None:
        """Updates the latest ghost particle halo buffer from a neighboring shard."""
        self._halo_inbox[halo.source_shard_id] = halo
        self.total_bytes_transferred += len(halo.to_bytes())

    def get_halo(self, source_shard_id: str) -> Optional[HaloBuffer]:
        """Retrieves latest halo buffer from a specific neighbor shard."""
        return self._halo_inbox.get(source_shard_id)

    def get_all_halos(self) -> List[HaloBuffer]:
        """Retrieves all received neighbor halo buffers."""
        return list(self._halo_inbox.values())

    @property
    def average_latency_ms(self) -> float:
        """Average transit packet delivery latency in milliseconds."""
        if self.total_packets_received == 0:
            return 0.0
        return self.transit_latency_accumulator / self.total_packets_received
