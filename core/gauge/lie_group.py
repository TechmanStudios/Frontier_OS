"""
Frontier_OS: Non-Abelian Lie Groups & Lie Algebras (SO(3) and SE(3))
File: Frontier_OS/core/gauge/lie_group.py

Implements non-abelian Lie group theory for spatial gauge connections:
1. SO(3) 3D Rotations and so(3) Lie algebra (Rodrigues exponential and logarithm).
2. SE(3) Rigid Body Transformations and se(3) Lie algebra (Screw theory & twists).
3. Lie brackets, Adjoint representations, and Riemannian geodesic distances.
"""

from dataclasses import dataclass
import math
from typing import Tuple, Union
import numpy as np


def skew(omega: np.ndarray) -> np.ndarray:
    """
    Hat operator ^: R^3 -> so(3).
    Maps 3D angular velocity vector to skew-symmetric matrix.
    """
    omega = np.asarray(omega, dtype=np.float64)
    return np.array([
        [0.0, -omega[2], omega[1]],
        [omega[2], 0.0, -omega[0]],
        [-omega[1], omega[0], 0.0]
    ], dtype=np.float64)


def unskew(W: np.ndarray) -> np.ndarray:
    """
    Vee operator ∨: so(3) -> R^3.
    Extracts 3D vector from skew-symmetric matrix.
    """
    return np.array([W[2, 1], W[0, 2], W[1, 0]], dtype=np.float64)


def so3_exp(omega: np.ndarray) -> np.ndarray:
    """
    Exponential map exp: so(3) -> SO(3) via Rodrigues formula.
    exp(omega^) = I + (sin θ / θ) omega^ + ((1 - cos θ) / θ^2) (omega^)^2
    """
    omega = np.asarray(omega, dtype=np.float64)
    theta = float(np.linalg.norm(omega))
    if theta < 1e-9:
        return np.eye(3, dtype=np.float64) + skew(omega)

    W = skew(omega)
    A = math.sin(theta) / theta
    B = (1.0 - math.cos(theta)) / (theta * theta)
    return np.eye(3, dtype=np.float64) + A * W + B * (W @ W)


def so3_log(R: np.ndarray) -> np.ndarray:
    """
    Logarithmic map log: SO(3) -> so(3) -> R^3.
    Extracts axis-angle vector omega such that exp(omega^) = R.
    """
    R = np.asarray(R, dtype=np.float64)
    # Numerical protection for trace
    tr = float(np.trace(R))
    cos_theta = np.clip((tr - 1.0) * 0.5, -1.0, 1.0)
    theta = math.acos(cos_theta)

    if theta < 1e-7:
        # First order expansion for small angles
        return unskew(R - R.T) * 0.5

    if math.isclose(theta, math.pi, rel_tol=1e-5):
        # 180 degree rotation singularity
        diag = np.diag(R)
        axis_idx = int(np.argmax(diag))
        col = R[:, axis_idx].copy()
        col[axis_idx] += 1.0
        norm = np.linalg.norm(col)
        if norm > 1e-6:
            axis = col / norm
            return axis * math.pi

    sin_theta = math.sin(theta)
    W = (R - R.T) / (2.0 * sin_theta)
    return unskew(W) * theta


def so3_geodesic_distance(R1: np.ndarray, R2: np.ndarray) -> float:
    """
    Intrinsic Riemannian distance on SO(3) bi-invariant metric.
    d(R1, R2) = ||log(R1^T R2)|| = theta in [0, pi] radians.
    """
    R_rel = R1.T @ R2
    omega = so3_log(R_rel)
    return float(np.linalg.norm(omega))


def se3_exp(twist: np.ndarray) -> np.ndarray:
    """
    Exponential map exp: se(3) -> SE(3).
    twist = [v; omega] ∈ R^6 (translational velocity, angular velocity).
    Returns 4x4 homogeneous transformation matrix T.
    """
    twist = np.asarray(twist, dtype=np.float64)
    v = twist[:3]
    omega = twist[3:]

    theta = float(np.linalg.norm(omega))
    T = np.eye(4, dtype=np.float64)

    if theta < 1e-9:
        T[:3, :3] = np.eye(3)
        T[:3, 3] = v
        return T

    R = so3_exp(omega)
    W = skew(omega)
    # Left Jacobian V = I + (1-cos θ)/θ^2 W + (θ - sin θ)/θ^3 W^2
    V = np.eye(3) + ((1.0 - math.cos(theta)) / (theta**2)) * W + ((theta - math.sin(theta)) / (theta**3)) * (W @ W)

    T[:3, :3] = R
    T[:3, 3] = V @ v
    return T


def se3_log(T: np.ndarray) -> np.ndarray:
    """
    Logarithmic map log: SE(3) -> se(3) -> R^6.
    Extracts twist vector [v; omega] from 4x4 matrix T.
    """
    T = np.asarray(T, dtype=np.float64)
    R = T[:3, :3]
    p = T[:3, 3]

    omega = so3_log(R)
    theta = float(np.linalg.norm(omega))

    if theta < 1e-9:
        v = p.copy()
    else:
        W = skew(omega)
        # Inverse Left Jacobian
        A = (1.0 - (theta * math.sin(theta)) / (2.0 * (1.0 - math.cos(theta)))) / (theta**2)
        V_inv = np.eye(3) - 0.5 * W + A * (W @ W)
        v = V_inv @ p

    twist = np.zeros(6, dtype=np.float64)
    twist[:3] = v
    twist[3:] = omega
    return twist


def lie_bracket_so3(omega1: np.ndarray, omega2: np.ndarray) -> np.ndarray:
    """
    Lie algebra bracket on so(3): [w1^, w2^] = (w1 x w2)^.
    Returns cross product w1 x w2.
    """
    return np.cross(omega1, omega2)


def adjoint_so3(omega: np.ndarray) -> np.ndarray:
    """
    Adjoint action ad_omega on so(3): ad_omega(v) = [omega^, v^] = omega x v.
    Returns 3x3 skew-symmetric matrix hat(omega).
    """
    return skew(omega)


def adjoint_matrix_so3(R: np.ndarray) -> np.ndarray:
    """
    Adjoint representation Ad_R on SO(3): Ad_R(omega^) = R omega^ R^T = (R omega)^.
    Returns 3x3 rotation matrix R.
    """
    return np.asarray(R, dtype=np.float64)


def adjoint_se3(twist: np.ndarray) -> np.ndarray:
    """
    Lie algebra adjoint ad_xi on se(3):
    ad_xi = [[omega^,  v^   ],
             [0,       omega^]] ∈ R^{6x6}.
    """
    twist = np.asarray(twist, dtype=np.float64)
    v = twist[:3]
    omega = twist[3:]
    ad = np.zeros((6, 6), dtype=np.float64)
    ad[:3, :3] = skew(omega)
    ad[:3, 3:] = skew(v)
    ad[3:, 3:] = skew(omega)
    return ad


def adjoint_matrix_se3(T: np.ndarray) -> np.ndarray:
    """
    Lie group Adjoint representation Ad_T on SE(3):
    Ad_T = [[R,  p^ R],
            [0,  R   ]] ∈ R^{6x6}.
    """
    T = np.asarray(T, dtype=np.float64)
    R = T[:3, :3]
    p = T[:3, 3]
    Ad = np.zeros((6, 6), dtype=np.float64)
    Ad[:3, :3] = R
    Ad[:3, 3:] = skew(p) @ R
    Ad[3:, 3:] = R
    return Ad


def so3_left_jacobian(omega: np.ndarray) -> np.ndarray:
    """
    Left Jacobian matrix J_l(omega) on SO(3):
    Maps tangent perturbations: exp(omega + d_omega) ≈ exp(J_l d_omega) exp(omega).
    J_l = I + ((1 - cos theta) / theta^2) omega^ + ((theta - sin theta) / theta^3) (omega^)^2.
    """
    omega = np.asarray(omega, dtype=np.float64)
    theta = float(np.linalg.norm(omega))
    if theta < 1e-9:
        return np.eye(3, dtype=np.float64) + 0.5 * skew(omega)

    W = skew(omega)
    A = (1.0 - math.cos(theta)) / (theta * theta)
    B = (theta - math.sin(theta)) / (theta * theta * theta)
    return np.eye(3, dtype=np.float64) + A * W + B * (W @ W)


def so3_left_jacobian_inv(omega: np.ndarray) -> np.ndarray:
    """
    Inverse Left Jacobian J_l^{-1}(omega) on SO(3):
    J_l^{-1} = I - 1/2 omega^ + ((1/theta^2) - (1 + cos theta)/(2 theta sin theta)) (omega^)^2.
    """
    omega = np.asarray(omega, dtype=np.float64)
    theta = float(np.linalg.norm(omega))
    if theta < 1e-9:
        return np.eye(3, dtype=np.float64) - 0.5 * skew(omega)

    W = skew(omega)
    A = (1.0 - (theta * math.sin(theta)) / (2.0 * (1.0 - math.cos(theta)))) / (theta * theta)
    return np.eye(3, dtype=np.float64) - 0.5 * W + A * (W @ W)


def so3_right_jacobian(omega: np.ndarray) -> np.ndarray:
    """Right Jacobian matrix J_r(omega) = J_l(-omega)."""
    return so3_left_jacobian(-np.asarray(omega, dtype=np.float64))


def so3_slerp(R1: np.ndarray, R2: np.ndarray, t: float) -> np.ndarray:
    """
    Spherical Linear Interpolation (SLERP) along intrinsic SO(3) geodesic:
    R(t) = R1 exp(t * log(R1^T R2)).
    Guarantees constant angular velocity and minimal geodesic path.
    """
    R1 = np.asarray(R1, dtype=np.float64)
    R2 = np.asarray(R2, dtype=np.float64)
    R_rel = R1.T @ R2
    omega = so3_log(R_rel)
    return R1 @ so3_exp(t * omega)


def se3_interpolate(T1: np.ndarray, T2: np.ndarray, t: float) -> np.ndarray:
    """
    Geodesic screw motion interpolation on SE(3):
    T(t) = T1 exp(t * log(T1^{-1} T2)).
    """
    T1 = np.asarray(T1, dtype=np.float64)
    T2 = np.asarray(T2, dtype=np.float64)
    R1 = T1[:3, :3]
    p1 = T1[:3, 3]
    T1_inv = np.eye(4, dtype=np.float64)
    T1_inv[:3, :3] = R1.T
    T1_inv[:3, 3] = -R1.T @ p1
    T_rel = T1_inv @ T2
    twist = se3_log(T_rel)
    return T1 @ se3_exp(t * twist)

