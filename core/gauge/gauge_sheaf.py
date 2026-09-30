"""
Frontier_OS: Non-Abelian Gauge Sheaves & Wilson-Loop Holonomy
File: Frontier_OS/core/gauge/gauge_sheaf.py

Implements non-abelian cellular sheaves with SO(3) Lie group connections:
1. Vertices V carry reference frames R_v ∈ SO(3).
2. Directed edges E carry parallel transport gauge connections R_{uv} ∈ SO(3).
3. Wilson Loop Holonomies W(γ) = ∏ R_e detecting orientational dislocations.
4. Non-Abelian Dirichlet Energy E_G and Riemannian manifold Lie gradient flow.
"""

from dataclasses import dataclass, field
import math
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np

from Frontier_OS.core.gauge.lie_group import (
    skew,
    unskew,
    so3_exp,
    so3_log,
    so3_geodesic_distance
)


@dataclass
class WilsonLoopReport:
    """Holonomy telemetry for a single closed cycle on the gauge complex."""
    loop_id: str
    cycle_nodes: List[str]
    holonomy_matrix: np.ndarray       # (3, 3) SO(3)
    trace: float                       # Tr(W) ∈ [-1, 3]
    defect_angle_rad: float            # ||log(W)|| ∈ [0, pi]
    defect_angle_deg: float
    is_flat: bool                      # defect < tolerance
    curvature_vector: np.ndarray       # axis-angle vector in so(3)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes Wilson loop report."""
        return {
            "loop_id": self.loop_id,
            "cycle_nodes": self.cycle_nodes,
            "trace": round(float(self.trace), 4),
            "defect_angle_rad": round(float(self.defect_angle_rad), 5),
            "defect_angle_deg": round(float(self.defect_angle_deg), 2),
            "is_flat": self.is_flat,
            "curvature_norm": round(float(np.linalg.norm(self.curvature_vector)), 5)
        }


@dataclass
class FaceCurvatureReport:
    """Curvature 2-form telemetry for an oriented 2-simplex face."""
    face_id: str
    vertices: List[str]
    holonomy_matrix: np.ndarray       # (3, 3) SO(3)
    curvature_vector: np.ndarray      # so(3) vector F_f = log(W_f)
    curvature_magnitude: float        # ||F_f|| in radians
    defect_angle_deg: float
    trace: float
    is_flat: bool

    def to_dict(self) -> Dict[str, Any]:
        """Serializes face curvature report."""
        return {
            "face_id": self.face_id,
            "vertices": self.vertices,
            "curvature_magnitude": round(float(self.curvature_magnitude), 5),
            "defect_angle_deg": round(float(self.defect_angle_deg), 2),
            "trace": round(float(self.trace), 4),
            "is_flat": self.is_flat
        }


class NonAbelianGaugeSheaf:
    """
    Cellular Sheaf with non-abelian SO(3) gauge group connection.
    Models spatial reference frames, relative orientations, and Wilson loop holonomies.
    """
    def __init__(self):
        self.vertices: List[str] = []
        self.vertex_frames: Dict[str, np.ndarray] = {}  # v -> R_v in SO(3)
        self.edges: Dict[str, Tuple[str, str]] = {}     # edge_id -> (u, v)
        self.gauge_connections: Dict[str, np.ndarray] = {} # edge_id -> R_{uv} in SO(3)
        self.adjacency: Dict[str, List[Tuple[str, str, bool]]] = {} # u -> [(v, edge_id, is_forward)]
        self.faces: Dict[str, List[str]] = {}           # face_id -> [v0, v1, v2]

    def add_vertex(self, vertex_id: str, frame: Optional[np.ndarray] = None):
        """Adds a vertex with an SO(3) orientation frame."""
        if vertex_id not in self.vertices:
            self.vertices.append(vertex_id)
            self.adjacency[vertex_id] = []
        self.vertex_frames[vertex_id] = np.eye(3, dtype=np.float64) if frame is None else np.asarray(frame, dtype=np.float64)

    def add_edge(self, edge_id: str, u: str, v: str, connection: Optional[np.ndarray] = None):
        """
        Adds a directed edge e = (u -> v) with gauge parallel transport connection R_{uv}.
        R_{uv} maps a vector in frame u to frame v: v_in_v = R_{uv} * v_in_u.
        """
        if u not in self.vertices:
            self.add_vertex(u)
        if v not in self.vertices:
            self.add_vertex(v)

        self.edges[edge_id] = (u, v)
        conn = np.eye(3, dtype=np.float64) if connection is None else np.asarray(connection, dtype=np.float64)
        self.gauge_connections[edge_id] = conn
        self.adjacency[u].append((v, edge_id, True))
        self.adjacency[v].append((u, edge_id, False))

    def compute_wilson_loop(self, loop_id: str, cycle_nodes: List[str], tol_rad: float = 1e-3) -> WilsonLoopReport:
        """
        Computes the Wilson loop holonomy matrix W(γ) along a closed cycle:
        W(γ) = R_{n,1} * ... * R_{2,3} * R_{1,2} ∈ SO(3).
        Measures total orientational dislocation when circumnavigating the cycle.
        """
        if len(cycle_nodes) < 3:
            raise ValueError("A closed cycle must contain at least 3 vertices.")
        if cycle_nodes[0] != cycle_nodes[-1]:
            # Close the loop
            cycle_nodes = list(cycle_nodes) + [cycle_nodes[0]]

        W = np.eye(3, dtype=np.float64)
        for i in range(len(cycle_nodes) - 1):
            u = cycle_nodes[i]
            v = cycle_nodes[i + 1]

            # Find connecting edge
            edge_conn = None
            for nbr, e_id, is_forward in self.adjacency[u]:
                if nbr == v:
                    R_edge = self.gauge_connections[e_id]
                    edge_conn = R_edge if is_forward else R_edge.T
                    break

            if edge_conn is None:
                raise ValueError(f"No direct edge found between {u} and {v} in cycle.")

            W = edge_conn @ W

        # Ensure exact SO(3) projection
        U, _, Vt = np.linalg.svd(W)
        W = U @ Vt
        if np.linalg.det(W) < 0:
            U[:, -1] *= -1
            W = U @ Vt

        omega = so3_log(W)
        defect_rad = float(np.linalg.norm(omega))
        tr = float(np.trace(W))
        is_flat = defect_rad < tol_rad

        return WilsonLoopReport(
            loop_id=loop_id,
            cycle_nodes=cycle_nodes[:-1],
            holonomy_matrix=W,
            trace=tr,
            defect_angle_rad=defect_rad,
            defect_angle_deg=math.degrees(defect_rad),
            is_flat=is_flat,
            curvature_vector=omega
        )

    def compute_dirichlet_energy(self) -> float:
        """
        Computes non-abelian Dirichlet energy across all edges:
        E_G = 1/2 sum_{(u,v)} ||log(R_v^T R_{uv} R_u)||^2.
        Measures orientational mismatch between vertex frames and edge connections.
        """
        energy = 0.0
        for edge_id, (u, v) in self.edges.items():
            R_u = self.vertex_frames[u]
            R_v = self.vertex_frames[v]
            R_uv = self.gauge_connections[edge_id]

            # Relative frame alignment error R_err = R_v^T R_{uv} R_u
            R_err = R_v.T @ (R_uv @ R_u)
            omega = so3_log(R_err)
            energy += 0.5 * float(np.sum(omega**2))

        return energy

    def diffuse_gauge_frames(self, steps: int = 25, lr: float = 0.2) -> Tuple[float, float, List[float]]:
        """
        Performs Riemannian manifold gradient descent on SO(3) to relax vertex frames:
        R_v <- exp(-lr * grad_v) * R_v.
        Returns: (initial_energy, final_energy, energy_history).
        """
        e_init = self.compute_dirichlet_energy()
        history = [e_init]

        for _ in range(steps):
            grads: Dict[str, np.ndarray] = {v: np.zeros(3, dtype=np.float64) for v in self.vertices}

            for edge_id, (u, v) in self.edges.items():
                R_u = self.vertex_frames[u]
                R_v = self.vertex_frames[v]
                R_uv = self.gauge_connections[edge_id]

                # Discrepancy vector from u to v
                R_err_v = R_v.T @ (R_uv @ R_u)
                w_v = so3_log(R_err_v)
                grads[v] -= w_v

                # Discrepancy vector from v to u
                R_err_u = R_u.T @ (R_uv.T @ R_v)
                w_u = so3_log(R_err_u)
                grads[u] -= w_u

            # Riemannian update on Lie group manifold
            for v in self.vertices:
                delta_R = so3_exp(-lr * grads[v])
                self.vertex_frames[v] = delta_R @ self.vertex_frames[v]

            history.append(self.compute_dirichlet_energy())

        e_final = history[-1]
        return e_init, e_final, history

    def add_face(self, face_id: str, vertices: List[str]):
        """
        Adds an oriented 2-simplex face f = (v0, v1, v2) to the simplicial gauge complex.
        Vertices define the oriented boundary cycle.
        """
        if len(vertices) < 3:
            raise ValueError(f"Face {face_id} must have at least 3 vertices.")
        for v in vertices:
            if v not in self.vertices:
                self.add_vertex(v)
        self.faces[face_id] = list(vertices)

    def compute_face_curvature(self, face_id: str, tol_rad: float = 1e-3) -> FaceCurvatureReport:
        """
        Computes the Yang-Mills curvature 2-form F_f on a discrete 2-cell:
        F_f = log(W_f) ∈ so(3), where W_f = ∏_{e ∈ ∂f} R_e.
        """
        if face_id not in self.faces:
            raise KeyError(f"Face '{face_id}' is not registered in the gauge sheaf.")
        verts = self.faces[face_id]
        wl = self.compute_wilson_loop(f"loop_{face_id}", verts, tol_rad=tol_rad)
        return FaceCurvatureReport(
            face_id=face_id,
            vertices=verts,
            holonomy_matrix=wl.holonomy_matrix,
            curvature_vector=wl.curvature_vector,
            curvature_magnitude=wl.defect_angle_rad,
            defect_angle_deg=wl.defect_angle_deg,
            trace=wl.trace,
            is_flat=wl.is_flat
        )

    def compute_yang_mills_action(self) -> float:
        """
        Computes the discrete Yang-Mills lattice gauge action across all 2-simplex faces:
        S_YM = sum_{f ∈ F} (1 - 1/3 * Tr(W_f)).
        Zero for flat connections; strictly non-negative S_YM >= 0.
        """
        if not self.faces:
            return 0.0
        s_ym = 0.0
        for face_id in self.faces:
            rep = self.compute_face_curvature(face_id)
            s_ym += max(0.0, 1.0 - (rep.trace / 3.0))
        return float(s_ym)

    def apply_gauge_transformation(self, gauge_elements: Dict[str, np.ndarray]):
        """
        Performs an arbitrary local gauge transformation g ∈ Map(V, SO(3)):
        1. Reference frames transform covariantly: R'_v = g_v * R_v.
        2. Edge connections transform by gauge conjugation: R'_{uv} = g_v * R_{uv} * g_u^T.
        Gauge-invariant observables (Tr(W(γ)) and S_YM) remain strictly invariant.
        """
        for v, g_v in gauge_elements.items():
            if v in self.vertex_frames:
                g_mat = np.asarray(g_v, dtype=np.float64)
                self.vertex_frames[v] = g_mat @ self.vertex_frames[v]

        for edge_id, (u, v) in self.edges.items():
            g_u = np.asarray(gauge_elements.get(u, np.eye(3)), dtype=np.float64)
            g_v = np.asarray(gauge_elements.get(v, np.eye(3)), dtype=np.float64)
            R_old = self.gauge_connections[edge_id]
            self.gauge_connections[edge_id] = g_v @ R_old @ g_u.T

    def verify_gauge_invariance(
        self,
        gauge_elements: Dict[str, np.ndarray],
        cycles: Optional[List[Tuple[str, List[str]]]] = None
    ) -> Dict[str, Any]:
        """
        Verifies non-abelian gauge invariance of Wilson loop observables and Yang-Mills action.
        Evaluates observables before and after local transformation, then reverts.
        """
        test_cycles = cycles or [(f_id, verts) for f_id, verts in self.faces.items()]
        
        # 1. Measure prior observables
        s_ym_pre = self.compute_yang_mills_action()
        traces_pre = [self.compute_wilson_loop(c_id, c_nodes).trace for c_id, c_nodes in test_cycles]

        # 2. Apply gauge transformation
        self.apply_gauge_transformation(gauge_elements)

        # 3. Measure post observables
        s_ym_post = self.compute_yang_mills_action()
        traces_post = [self.compute_wilson_loop(c_id, c_nodes).trace for c_id, c_nodes in test_cycles]

        # 4. Revert transformation with inverse elements g_v^T
        inverse_elements = {v: np.asarray(g, dtype=np.float64).T for v, g in gauge_elements.items()}
        self.apply_gauge_transformation(inverse_elements)

        # 5. Quantify invariance residual
        trace_errors = [abs(t_pre - t_post) for t_pre, t_post in zip(traces_pre, traces_post)]
        max_trace_error = max(trace_errors) if trace_errors else 0.0
        sym_error = abs(s_ym_pre - s_ym_post)

        return {
            "s_ym_pre": round(s_ym_pre, 6),
            "s_ym_post": round(s_ym_post, 6),
            "sym_invariance_error": float(sym_error),
            "max_wilson_trace_error": float(max_trace_error),
            "is_strictly_gauge_invariant": (sym_error < 1e-10) and (max_trace_error < 1e-10)
        }

    def verify_non_abelian_bianchi(self, tet_nodes: List[str]) -> Dict[str, Any]:
        """
        Verifies the discrete non-abelian Bianchi identity D F = 0 on a 3-simplex (tetrahedron):
        The boundary product of properly transported face holonomies around the closed 2-sphere equals identity:
        W_{∂Δ³} = ∏_{f ∈ ∂Δ³} W_f = I.
        """
        if len(tet_nodes) != 4:
            raise ValueError("Tetrahedron must consist of exactly 4 nodes [v0, v1, v2, v3].")
        v0, v1, v2, v3 = tet_nodes

        # Faces based at v0:
        # w012: (v0 -> v1 -> v2 -> v0)
        w012 = self.compute_wilson_loop("f012", [v0, v1, v2]).holonomy_matrix
        # w023: (v0 -> v2 -> v3 -> v0)
        w023 = self.compute_wilson_loop("f023", [v0, v2, v3]).holonomy_matrix
        # w031: (v0 -> v3 -> v1 -> v0)
        w031 = self.compute_wilson_loop("f031", [v0, v3, v1]).holonomy_matrix
        # w123: face (v1 -> v2 -> v3 -> v1)
        w123 = self.compute_wilson_loop("f123", [v1, v2, v3]).holonomy_matrix

        # Find R_{v0, v1}
        r_01 = None
        for nbr, e_id, is_fwd in self.adjacency[v0]:
            if nbr == v1:
                r_01 = self.gauge_connections[e_id] if is_fwd else self.gauge_connections[e_id].T
                break
        if r_01 is None:
            raise ValueError(f"No direct edge found between {v0} and {v1}")

        r_10 = r_01.T

        # Discrete non-abelian boundary product around closed 2-sphere boundary of tetrahedron:
        # w031 @ w023 @ w012 @ r_10 @ w123^T @ r_01 = I (down to machine epsilon)
        composite = w031 @ w023 @ w012 @ r_10 @ w123.T @ r_01
        defect_norm = float(np.linalg.norm(composite - np.eye(3)))

        return {
            "bianchi_defect_norm": defect_norm,
            "is_bianchi_satisfied": defect_norm < 1e-10,
            "composite_trace": round(float(np.trace(composite)), 6)
        }

