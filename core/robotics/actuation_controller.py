"""
Frontier_OS: Geodesic Robotic Actuation Controller & 7 Giants MoA Guidance
File: Frontier_OS/core/robotics/actuation_controller.py

Implements closed-loop physical actuation along configuration space geodesics:
1. 7 Giants MoA differential operators guiding Cartesian end-effector navigation.
2. Riemannian inverse dynamics torque computation: τ = g(q) a_des + C(q, dq) dq + G(q).
3. Symplectic time-stepping integration with thermodynamic Carnot dissipation accumulation.
4. Singularity avoidance and obstacle repulsion via metric curvature.
"""

from dataclasses import dataclass, field
import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from Frontier_OS.core.robotics.kinematic_manifold import (
    ArticulatedManipulator6DOF,
    RoboticConfigurationManifold,
    KinematicState,
    Obstacle3D
)


@dataclass
class ActuationStepRecord:
    """Telemetry captured at a single discrete actuation step."""
    step_index: int
    time_s: float
    end_effector_pos: List[float]
    distance_to_goal: float
    min_obstacle_dist: float
    manipulability: float
    torque_norm: float
    kinetic_energy: float
    carnot_dissipated_dE: float


@dataclass
class TrajectoryExecutionReport:
    """Full summary of a closed-loop geodesic trajectory execution."""
    success: bool
    total_steps: int
    duration_s: float
    initial_distance: float
    final_distance: float
    min_obstacle_clearance: float
    max_torque_nm: float
    total_carnot_dissipated_j: float
    trajectory: List[ActuationStepRecord] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes trajectory report."""
        return {
            "success": self.success,
            "total_steps": self.total_steps,
            "duration_s": round(self.duration_s, 3),
            "initial_distance": round(self.initial_distance, 4),
            "final_distance": round(self.final_distance, 4),
            "min_obstacle_clearance": round(self.min_obstacle_clearance, 4),
            "max_torque_nm": round(self.max_torque_nm, 2),
            "total_carnot_dissipated_j": round(self.total_carnot_dissipated_j, 4),
            "trajectory_points_count": len(self.trajectory)
        }


class GeodesicActuationController:
    """
    Closed-loop differential-geometric robot controller.
    Synthesizes Riemannian geodesic steering with 7 Giants MoA guidance.
    """
    def __init__(
        self,
        manifold: RoboticConfigurationManifold,
        dt: float = 0.01,
        damping_gamma: float = 0.08
    ):
        self.manifold = manifold
        self.robot = manifold.robot
        self.dt = dt
        self.damping_gamma = damping_gamma

        # Controller gains
        self.kp_cartesian = 18.0
        self.kd_cartesian = 4.5
        self.kp_nullspace = 3.0
        self.kd_nullspace = 1.0

    def compute_gravity_compensation(self, q: np.ndarray) -> np.ndarray:
        """
        Computes the gravitational torque vector G(q) = ∂V/∂q.
        Assumes downward gravity g_acc = 9.81 m/s² along -Z.
        """
        q = np.asarray(q, dtype=np.float64)
        g_acc = 9.81
        n = self.robot.num_joints
        G = np.zeros(n, dtype=np.float64)
        eps = 1e-5

        # Forward kinematics joint positions
        _, _, joint_pos = self.robot.forward_kinematics(q)

        # Potential energy V = sum_i m_i * g * z_i
        def potential(q_vec):
            _, _, jp = self.robot.forward_kinematics(q_vec)
            v_tot = 0.0
            for i, p in enumerate(jp[1:]):
                mass = self.robot.link_masses[min(i, len(self.robot.link_masses) - 1)]
                v_tot += mass * g_acc * p[2]
            return v_tot

        v0 = potential(q)
        for i in range(n):
            q_perturbed = q.copy()
            q_perturbed[i] += eps
            G[i] = (potential(q_perturbed) - v0) / eps

        return G

    def compute_control_torque(
        self,
        q: np.ndarray,
        dq: np.ndarray,
        target_pos: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Computes the motor torques τ and desired joint acceleration using Riemannian mechanics
        and 7 Giants MoA Cartesian steering.
        """
        q = np.asarray(q, dtype=np.float64)
        dq = np.asarray(dq, dtype=np.float64)
        target_pos = np.asarray(target_pos, dtype=np.float64)

        ee_pos, _, _ = self.robot.forward_kinematics(q)
        J_v = self.robot.compute_jacobian(q)
        g = self.manifold.compute_metric(q)
        g_inv = np.linalg.inv(g)

        # 1. 7 Giants MoA Guidance:
        # A. Optimizer (Steepest descent toward target position)
        pos_err = target_pos - ee_pos
        f_attract = self.kp_cartesian * pos_err - self.kd_cartesian * (J_v @ dq)

        # B. Graph Navigator (Curl circulation around obstacle boundaries)
        f_curl = np.zeros(3, dtype=np.float64)
        for obs in self.manifold.obstacles:
            diff = ee_pos - obs.position
            dist = float(np.linalg.norm(diff))
            if dist < (obs.radius + 0.30):
                # Orthogonal curl vector: tangent in XY plane
                curl_tangent = np.array([-diff[1], diff[0], 0.0], dtype=np.float64)
                curl_norm = float(np.linalg.norm(curl_tangent))
                if curl_norm > 1e-5:
                    curl_tangent /= curl_norm
                    f_curl += (0.8 / (dist**2 + 0.01)) * curl_tangent

        total_cart_force = f_attract + f_curl

        # 2. Dynamically Consistent Generalized Inverse J_bar = g^-1 J^T (J g^-1 J^T)^-1
        lambda_inv = J_v @ g_inv @ J_v.T
        # Regularization for kinematic singularities
        lambda_mat = np.linalg.inv(lambda_inv + 1e-4 * np.eye(3))
        J_bar = g_inv @ J_v.T @ lambda_mat

        # Task-space torques: τ_task = J_v^T Total Force
        tau_task = J_v.T @ total_cart_force

        # 3. Nullspace Projection: τ_null = (I - J_v^T J_bar^T) τ_null_posture
        # Statistician joint limit centering & Aligner damping
        null_proj = np.eye(self.robot.num_joints) - J_v.T @ J_bar.T
        q_mid = np.array([(lim[0] + lim[1]) * 0.5 for lim in self.robot.joint_limits], dtype=np.float64)
        tau_null_posture = self.kp_nullspace * (q_mid - q) - self.kd_nullspace * dq
        tau_null = null_proj @ tau_null_posture

        # 4. Geodesic Christoffel Coriolis/Centrifugal compensation
        # From Euler-Lagrange: C(q, dq) dq = - g(q) * accel_geodesic
        accel_geo = self.manifold.compute_geodesic_acceleration(q, dq)
        coriolis_centrifugal = - g @ accel_geo

        # 5. Gravity compensation
        G = self.compute_gravity_compensation(q)

        # Total control torque
        tau = tau_task + tau_null + coriolis_centrifugal + G
        # Desired acceleration
        q_ddot = g_inv @ (tau - coriolis_centrifugal - G)
        return tau, q_ddot

    def execute_geodesic_trajectory(
        self,
        q_start: np.ndarray,
        target_pos: np.ndarray,
        max_steps: int = 150,
        goal_tolerance: float = 0.03
    ) -> TrajectoryExecutionReport:
        """
        Executes a continuous closed-loop robotic trajectory toward the target goal.
        Simulates physical joint dynamics, obstacle avoidance, and Carnot memory dissipation.
        """
        q = np.asarray(q_start, dtype=np.float64).copy()
        dq = np.zeros(self.robot.num_joints, dtype=np.float64)
        target_pos = np.asarray(target_pos, dtype=np.float64)

        initial_ee, _, _ = self.robot.forward_kinematics(q)
        initial_dist = float(np.linalg.norm(initial_ee - target_pos))

        records: List[ActuationStepRecord] = []
        cumulative_carnot_dE = 0.0
        min_clearance = float("inf")
        max_torque = 0.0

        for step in range(max_steps):
            ee_pos, _, joint_pos = self.robot.forward_kinematics(q)
            dist_goal = float(np.linalg.norm(ee_pos - target_pos))
            manip = self.robot.compute_manipulability(q)

            # Check obstacle distances
            for obs in self.manifold.obstacles:
                for jp in joint_pos:
                    d = float(np.linalg.norm(jp - obs.position)) - obs.radius
                    if d < min_clearance:
                        min_clearance = d

            # Compute torques
            tau, q_ddot = self.compute_control_torque(q, dq, target_pos)
            tau_norm = float(np.linalg.norm(tau))
            if tau_norm > max_torque:
                max_torque = tau_norm

            # Kinetic energy T = 1/2 dq^T g dq
            g = self.manifold.compute_metric(q)
            kin_energy = 0.5 * float(dq.T @ g @ dq)

            # Symplectic Euler time-stepping update with Carnot dissipation
            # v_{t+1} = (1 - γ dt) v_t + dt * q_ddot
            # q_{t+1} = q_t + dt * v_{t+1}
            dE_dissipated = 2.0 * self.damping_gamma * kin_energy * self.dt
            cumulative_carnot_dE += dE_dissipated

            dq = (1.0 - self.damping_gamma * self.dt) * dq + self.dt * q_ddot
            # Joint velocity clamping
            max_vel = 2.5
            dq = np.clip(dq, -max_vel, max_vel)

            q = q + self.dt * dq
            # Enforce physical joint limits
            for j in range(self.robot.num_joints):
                q[j] = np.clip(q[j], self.robot.joint_limits[j][0], self.robot.joint_limits[j][1])

            records.append(ActuationStepRecord(
                step_index=step,
                time_s=round(step * self.dt, 3),
                end_effector_pos=[round(float(p), 4) for p in ee_pos],
                distance_to_goal=round(dist_goal, 4),
                min_obstacle_dist=round(min_clearance, 4),
                manipulability=round(manip, 4),
                torque_norm=round(tau_norm, 2),
                kinetic_energy=round(kin_energy, 4),
                carnot_dissipated_dE=round(dE_dissipated, 6)
            ))

            if dist_goal <= goal_tolerance:
                break

        final_ee, _, _ = self.robot.forward_kinematics(q)
        final_dist = float(np.linalg.norm(final_ee - target_pos))
        is_success = final_dist <= goal_tolerance
        self.last_q = q.copy()

        return TrajectoryExecutionReport(
            success=is_success,
            total_steps=len(records),
            duration_s=len(records) * self.dt,
            initial_distance=initial_dist,
            final_distance=final_dist,
            min_obstacle_clearance=min_clearance,
            max_torque_nm=max_torque,
            total_carnot_dissipated_j=cumulative_carnot_dE,
            trajectory=records
        )

    # Alias for API uniformity
    execute_trajectory = execute_geodesic_trajectory
