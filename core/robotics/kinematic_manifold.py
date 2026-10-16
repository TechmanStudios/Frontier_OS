"""
Frontier_OS: Embodied Robotic Configuration Space Riemannian Manifold
File: Frontier_OS/core/robotics/kinematic_manifold.py

Formulates the configuration space of physical robotic systems as a Riemannian manifold:
1. Generalized coordinates q ∈ Q ⊂ R^n (e.g. 6-DOF joint angles).
2. Configuration Riemannian metric tensor g(q) ≻ 0 modeling physical inertia and obstacle potential warping.
3. Christoffel symbols Γ^i_{jk}(q) generating Coriolis, centrifugal, and obstacle-repulsion geodesic forces.
4. Forward kinematics, workspace Jacobian J(q), and Yoshikawa manipulability w(q).
"""

from dataclasses import dataclass, field
import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


@dataclass
class Obstacle3D:
    """3D spherical obstacle in robot workspace."""
    obstacle_id: str
    position: np.ndarray        # (3,) [x, y, z] in meters
    radius: float               # Radius in meters
    repulsion_gain: float = 0.5 # Metric warping amplitude alpha


@dataclass
class KinematicState:
    """Kinematic configuration and workspace pose of the robot."""
    joint_angles: np.ndarray            # (n,) q in radians
    joint_velocities: np.ndarray        # (n,) dq/dt in rad/s
    end_effector_pos: np.ndarray        # (3,) [x, y, z] in meters
    end_effector_rot: np.ndarray        # (3, 3) rotation matrix SO(3)
    manipulability: float               # Yoshikawa index w(q)
    min_obstacle_distance: float        # Minimum clearance to nearest obstacle
    metric_determinant: float           # det(g(q))
    metric_condition_number: float      # kappa(g(q))

    def to_dict(self) -> Dict[str, Any]:
        """Serializes kinematic state."""
        return {
            "joint_angles": [round(float(a), 4) for a in self.joint_angles],
            "joint_velocities": [round(float(v), 4) for v in self.joint_velocities],
            "end_effector_pos": [round(float(p), 4) for p in self.end_effector_pos],
            "manipulability": round(float(self.manipulability), 4),
            "min_obstacle_distance": round(float(self.min_obstacle_distance), 4),
            "metric_determinant": round(float(self.metric_determinant), 4),
            "metric_condition_number": round(float(self.metric_condition_number), 2)
        }


class ArticulatedManipulator6DOF:
    """
    6-DOF Articulated Robotic Manipulator with forward kinematics,
    geometric Jacobian, and configuration space metrics.
    """
    def __init__(
        self,
        link_lengths: Optional[List[float]] = None,
        link_masses: Optional[List[float]] = None,
        joint_limits: Optional[List[Tuple[float, float]]] = None
    ):
        # Default link lengths (meters) [base_h, l1, l2, l3, l4, l5]
        self.link_lengths = link_lengths or [0.25, 0.35, 0.30, 0.15, 0.10, 0.08]
        # Link masses (kg)
        self.link_masses = link_masses or [3.5, 3.0, 2.2, 1.2, 0.8, 0.5]
        # Joint angle limits (radians)
        self.joint_limits = joint_limits or [
            (-math.pi, math.pi),
            (-math.pi * 0.75, math.pi * 0.75),
            (-math.pi * 0.85, math.pi * 0.85),
            (-math.pi, math.pi),
            (-math.pi * 0.75, math.pi * 0.75),
            (-math.pi, math.pi)
        ]
        self.num_joints = 6
        # Base diagonal rotor inertia
        self.rotor_inertia = np.array([0.45, 0.38, 0.25, 0.12, 0.08, 0.04], dtype=np.float64)

    def forward_kinematics(self, q: np.ndarray) -> Tuple[np.ndarray, np.ndarray, List[np.ndarray]]:
        """
        Computes forward kinematics for 6-DOF manipulator.
        Returns:
            end_effector_position: (3,)
            end_effector_rotation: (3, 3)
            joint_positions: List of 3D positions for each link joint (base to end-effector)
        """
        q = np.asarray(q, dtype=np.float64)
        l = self.link_lengths

        # Base frame T_0
        T = np.eye(4, dtype=np.float64)
        joint_positions = [T[:3, 3].copy()]

        # Joint 1: Rotation around Z (Waist)
        c1, s1 = math.cos(q[0]), math.sin(q[0])
        R1 = np.array([[c1, -s1, 0, 0], [s1, c1, 0, 0], [0, 0, 1, l[0]], [0, 0, 0, 1]])
        T = T @ R1
        joint_positions.append(T[:3, 3].copy())

        # Joint 2: Rotation around Y (Shoulder)
        c2, s2 = math.cos(q[1]), math.sin(q[1])
        R2 = np.array([[c2, 0, s2, 0], [0, 1, 0, 0], [-s2, 0, c2, l[1]], [0, 0, 0, 1]])
        T = T @ R2
        joint_positions.append(T[:3, 3].copy())

        # Joint 3: Rotation around Y (Elbow)
        c3, s3 = math.cos(q[2]), math.sin(q[2])
        R3 = np.array([[c3, 0, s3, 0], [0, 1, 0, 0], [-s3, 0, c3, l[2]], [0, 0, 0, 1]])
        T = T @ R3
        joint_positions.append(T[:3, 3].copy())

        # Joint 4: Rotation around Z (Forearm roll)
        c4, s4 = math.cos(q[3]), math.sin(q[3])
        R4 = np.array([[c4, -s4, 0, 0], [s4, c4, 0, 0], [0, 0, 1, l[3]], [0, 0, 0, 1]])
        T = T @ R4
        joint_positions.append(T[:3, 3].copy())

        # Joint 5: Rotation around Y (Wrist pitch)
        c5, s5 = math.cos(q[4]), math.sin(q[4])
        R5 = np.array([[c5, 0, s5, 0], [0, 1, 0, 0], [-s5, 0, c5, l[4]], [0, 0, 0, 1]])
        T = T @ R5
        joint_positions.append(T[:3, 3].copy())

        # Joint 6: Rotation around Z (Tool roll)
        c6, s6 = math.cos(q[5]), math.sin(q[5])
        R6 = np.array([[c6, -s6, 0, 0], [s6, c6, 0, 0], [0, 0, 1, l[5]], [0, 0, 0, 1]])
        T = T @ R6
        joint_positions.append(T[:3, 3].copy())

        ee_pos = T[:3, 3]
        ee_rot = T[:3, :3]
        return ee_pos, ee_rot, joint_positions

    def compute_jacobian(self, q: np.ndarray, eps: float = 1e-6) -> np.ndarray:
        """
        Computes the geometric translational Jacobian J_v(q) = ∂p/∂q ∈ R^{3 x 6}
        via central difference numerical differentiation.
        """
        q = np.asarray(q, dtype=np.float64)
        J_v = np.zeros((3, self.num_joints), dtype=np.float64)

        for i in range(self.num_joints):
            q_plus = q.copy()
            q_plus[i] += eps
            pos_plus, _, _ = self.forward_kinematics(q_plus)

            q_minus = q.copy()
            q_minus[i] -= eps
            pos_minus, _, _ = self.forward_kinematics(q_minus)

            J_v[:, i] = (pos_plus - pos_minus) / (2.0 * eps)

        return J_v

    def compute_manipulability(self, q: np.ndarray) -> float:
        """
        Computes the Yoshikawa manipulability index w(q) = sqrt(det(J J^T)).
        Measures distance to kinematic singularities.
        """
        J_v = self.compute_jacobian(q)
        A = J_v @ J_v.T
        det_A = float(np.linalg.det(A))
        return math.sqrt(max(0.0, det_A))


class RoboticConfigurationManifold:
    """
    Riemannian Manifold (Q, g(q)) over the robot configuration space.
    Computes metric tensor g(q), Christoffel connection symbols,
    geodesic acceleration, and obstacle potential curvature deformations.
    """
    def __init__(self, robot: ArticulatedManipulator6DOF, obstacles: Optional[List[Obstacle3D]] = None):
        self.robot = robot
        self.obstacles = obstacles or []

    def compute_metric(self, q: np.ndarray) -> np.ndarray:
        """
        Computes the symmetric positive-definite Riemannian metric tensor g(q) ∈ R^{6 x 6}.
        g(q) = g_inertia(q) + g_obstacles(q) + g_limits(q).
        """
        q = np.asarray(q, dtype=np.float64)
        J_v = self.robot.compute_jacobian(q)

        # 1. Base inertial kinetic metric g_0 = J_v^T M_cart J_v + I_rotor
        total_mass = sum(self.robot.link_masses)
        cart_mass_matrix = np.eye(3) * (total_mass * 0.35)
        g_inertia = J_v.T @ cart_mass_matrix @ J_v + np.diag(self.robot.rotor_inertia)

        # 2. Obstacle curvature warping: elevates metric near obstacle boundaries
        ee_pos, _, joint_pos = self.robot.forward_kinematics(q)
        g_obs = np.zeros_like(g_inertia)

        for obs in self.obstacles:
            # Check distance from each joint and end-effector to obstacle
            dists = [float(np.linalg.norm(jp - obs.position)) - obs.radius for jp in joint_pos]
            min_dist = max(1e-3, min(dists))
            # Curvature potential phi = alpha / (dist^2 + eps)
            warp_factor = obs.repulsion_gain / (min_dist**2 + 0.04)
            g_obs += warp_factor * (J_v.T @ J_v)

        # 3. Joint limits metric barrier: prevents joint exceeding physical bounds
        g_limits = np.zeros_like(g_inertia)
        for i in range(self.robot.num_joints):
            q_min, q_max = self.robot.joint_limits[i]
            d_min = max(1e-3, q[i] - q_min)
            d_max = max(1e-3, q_max - q[i])
            limit_barrier = 0.05 * (1.0 / (d_min**2) + 1.0 / (d_max**2))
            g_limits[i, i] += limit_barrier

        g = g_inertia + g_obs + g_limits
        # Ensure exact numerical symmetry
        g = 0.5 * (g + g.T)
        return g

    def compute_christoffel_symbols(self, q: np.ndarray, eps: float = 1e-4) -> np.ndarray:
        """
        Computes Christoffel symbols of the second kind Γ^i_{jk}(q) ∈ R^{n x n x n}.
        Γ^i_{jk} = 1/2 g^{im} (∂_j g_{km} + ∂_k g_{jm} - ∂_m g_{jk}).
        """
        q = np.asarray(q, dtype=np.float64)
        n = self.robot.num_joints
        g = self.compute_metric(q)
        g_inv = np.linalg.inv(g)

        # Numerical partial derivatives ∂_m g_{jk} = dg_dq[m, j, k]
        dg_dq = np.zeros((n, n, n), dtype=np.float64)
        for m in range(n):
            q_plus = q.copy()
            q_plus[m] += eps
            g_plus = self.compute_metric(q_plus)

            q_minus = q.copy()
            q_minus[m] -= eps
            g_minus = self.compute_metric(q_minus)

            dg_dq[m] = (g_plus - g_minus) / (2.0 * eps)

        # Assemble Christoffel symbols
        gamma = np.zeros((n, n, n), dtype=np.float64)
        for i in range(n):
            for j in range(n):
                for k in range(n):
                    term = 0.0
                    for m in range(n):
                        term += g_inv[i, m] * (dg_dq[j, k, m] + dg_dq[k, j, m] - dg_dq[m, j, k])
                    gamma[i, j, k] = 0.5 * term

        return gamma

    def compute_geodesic_acceleration(self, q: np.ndarray, dq: np.ndarray) -> np.ndarray:
        """
        Computes the natural geodesic acceleration on the configuration manifold:
        d²q^i/dt² = - ∑_{j,k} Γ^i_{jk}(q) dq^j dq^k.
        Curves the trajectory naturally around obstacles and joint limits.
        """
        q = np.asarray(q, dtype=np.float64)
        dq = np.asarray(dq, dtype=np.float64)
        n = self.robot.num_joints
        gamma = self.compute_christoffel_symbols(q)

        accel = np.zeros(n, dtype=np.float64)
        for i in range(n):
            val = 0.0
            for j in range(n):
                for k in range(n):
                    val += gamma[i, j, k] * dq[j] * dq[k]
            accel[i] = -val

        return accel

    def get_kinematic_state(self, q: np.ndarray, dq: np.ndarray) -> KinematicState:
        """Evaluates complete kinematic and metric state for configuration (q, dq)."""
        ee_pos, ee_rot, joint_pos = self.robot.forward_kinematics(q)
        manip = self.robot.compute_manipulability(q)
        g = self.compute_metric(q)

        evals = np.linalg.eigvalsh(g)
        det_g = float(np.prod(evals))
        cond_g = float(evals[-1] / max(1e-9, evals[0]))

        # Calculate minimum obstacle clearance
        min_dist = float("inf")
        for obs in self.obstacles:
            for jp in joint_pos:
                d = float(np.linalg.norm(jp - obs.position)) - obs.radius
                if d < min_dist:
                    min_dist = d

        return KinematicState(
            joint_angles=q.copy(),
            joint_velocities=dq.copy(),
            end_effector_pos=ee_pos,
            end_effector_rot=ee_rot,
            manipulability=manip,
            min_obstacle_distance=min_dist,
            metric_determinant=det_g,
            metric_condition_number=cond_g
        )
