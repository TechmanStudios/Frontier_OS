"""
Frontier_OS: Core Manifold Intercept & Agent Dispatch Throttling
File: Frontier_OS/core/telemetry_hook.py
"""

from collections import deque
from dataclasses import dataclass
import threading
import time
from typing import Callable, Deque, Optional, Tuple
import numpy as np


@dataclass
class CurvatureTelemetryPacket:
    node_id: int
    ricci_scalar: float
    curvature_gradient: np.ndarray  # grad(R) in coordinate chart
    metric_condition_number: float
    timestamp: float


class ManifoldTelemetryIPC:
    """
    High-frequency non-blocking IPC hook.
    Polls the SOL kernel geometry state every 10ms (100 Hz).
    """
    def __init__(
        self,
        poll_interval_sec: float = 0.010,  # 10ms
        max_queue_len: int = 500
    ):
        self.poll_interval = poll_interval_sec
        self._queue: Deque[CurvatureTelemetryPacket] = deque(maxlen=max_queue_len)
        self._lock = threading.Lock()
        self._atomic_latest: Optional[CurvatureTelemetryPacket] = None
        self._running = False
        self._poll_thread: Optional[threading.Thread] = None
        self._manifold_sampler: Optional[Callable[[], CurvatureTelemetryPacket]] = None

    def register_sampler(self, sampler_func: Callable[[], CurvatureTelemetryPacket]):
        self._manifold_sampler = sampler_func

    def start(self):
        if self._running:
            return
        self._running = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def stop(self):
        self._running = False
        if self._poll_thread:
            self._poll_thread.join(timeout=0.2)

    def _poll_loop(self):
        while self._running:
            start_t = time.perf_counter()
            if self._manifold_sampler:
                try:
                    packet = self._manifold_sampler()
                    # Atomic reference update for lockless readers
                    self._atomic_latest = packet
                    with self._lock:
                        self._queue.append(packet)
                except Exception:
                    pass
            elapsed = time.perf_counter() - start_t
            sleep_time = max(0.0, self.poll_interval - elapsed)
            time.sleep(sleep_time)

    def get_latest_telemetry(self) -> Optional[CurvatureTelemetryPacket]:
        """Lock-free atomic telemetry read for zero reader contention."""
        latest = self._atomic_latest
        if latest is not None:
            return latest
        with self._lock:
            return self._queue[-1] if self._queue else None


class AgentDispatchThrottler:
    """
    Intercepts and shapes Exciton agent dispatch based on live Riemannian telemetry.
    Diverts agents to orthogonal subspaces if curvature diverges.
    """
    def __init__(
        self,
        ipc: ManifoldTelemetryIPC,
        curvature_safety_limit: float = 15.0,
        condition_limit: float = 50.0
    ):
        self.ipc = ipc
        self.curvature_safety_limit = curvature_safety_limit
        self.condition_limit = condition_limit

    def evaluate_and_route(
        self,
        proposed_velocity: np.ndarray,
        current_node_id: int
    ) -> Tuple[np.ndarray, bool, str]:
        """
        Evaluates proposed agent trajectory against local geometry.

        Returns:
            adjusted_velocity: Scaled or orthogonally projected velocity vector
            throttled: True if dispatch was modified/throttled
            routing_channel: 'DIRECT', 'DIVERTED_ORTHOGONAL', or 'THROTTLED_RADIAL'
        """
        packet = self.ipc.get_latest_telemetry()
        if packet is None:
            return proposed_velocity, False, "DIRECT"

        # Check for geometric singularity or coordinate collapse
        is_singular = (
            abs(packet.ricci_scalar) > self.curvature_safety_limit or
            packet.metric_condition_number > self.condition_limit
        )

        if not is_singular:
            return proposed_velocity, False, "DIRECT"

        # Curvature Divergence Detected: Project onto orthogonal tangent subspace
        grad_R = np.asarray(packet.curvature_gradient, dtype=np.float64).reshape(-1, 1)
        grad_norm_sq = float((grad_R.T @ grad_R)[0, 0])

        if grad_norm_sq < 1e-10:
            # Gradient is isotropic; apply radial deceleration throttle
            v_damped = proposed_velocity * 0.1
            return v_damped, True, "THROTTLED_RADIAL"

        # Projection operator: P_orth = I - (n n^T) / (n^T n)
        n = grad_R / np.sqrt(grad_norm_sq)
        dim = len(proposed_velocity)
        P_orth = np.eye(dim) - (n @ n.T)

        v_in = np.asarray(proposed_velocity, dtype=np.float64).reshape(-1, 1)
        v_diverted = (P_orth @ v_in).ravel()

        # Check if projected velocity is degenerate
        if np.linalg.norm(v_diverted) < 1e-6:
            # Generate deterministic orthogonal null-vector
            null_vec = np.zeros(dim, dtype=np.float64)
            min_idx = int(np.argmin(np.abs(n.ravel())))
            null_vec[min_idx] = 1.0
            v_diverted = (P_orth @ null_vec.reshape(-1, 1)).ravel()

        # Attenuate magnitude to prevent secondary shockwaves
        v_diverted = v_diverted * 0.5
        return v_diverted, True, "DIVERTED_ORTHOGONAL"
