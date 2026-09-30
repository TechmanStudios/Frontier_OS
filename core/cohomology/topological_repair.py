"""
Sheaf Topological Self-Repair & Connection Learning
===================================================
Repairs topological obstructions and semantic contradictions across Cellular Sheaves
by optimizing edge restriction maps (sheaf learning) and surgically resecting
irreconcilable communication bottlenecks.

Mathematical Formulation:
--------------------------
1. Restriction Map Gradient Descent:
    Given stubborn or persistent agent beliefs x in C^0(X; F):
    L(F) = (1/2) ||delta^0 x||^2 = (1/2) sum_{e=(u->v)} ||F_{v <= e} x_v - F_{u <= e} x_u||^2
    grad_{F_{v <= e}} = (delta^0 x)_e x_v^T
    grad_{F_{u <= e}} = - (delta^0 x)_e x_u^T

2. Orthogonal Procrustes Projection (Preserves O(d) or SO(d) Frame Rotations):
    M_{new} = F - eta * grad
    U, Sigma, V^T = SVD(M_{new})
    F_{proj} = U V^T  in O(d)

3. Surgical Resection:
    For any edge where E_e = (1/2) ||(delta^0 x)_e||^2 exceeds resection threshold tau,
    either down-weight edge w_e -> 0 or excise e in E to restore beta_1 -> 0 and E_F(x) -> 0.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
import numpy as np
import scipy.linalg as la

from .cellular_sheaf import CellularSheaf, EdgeRestriction
from .cohomology_engine import CohomologyEngine, CohomologySpectrum


@dataclass
class RepairAction:
    action_type: str  # "RESTRICTION_MAP_UPDATE" | "SURGICAL_EDGE_EXCISION" | "EDGE_DOWNWEIGHT"
    target_id: str
    initial_energy: float
    final_energy: float
    description: str


@dataclass
class TopologicalRepairReport:
    initial_energy: float
    final_energy: float
    energy_dissipated: float
    initial_beta_0: int
    final_beta_0: int
    initial_beta_1: int
    final_beta_1: int
    initial_consistency: float
    final_consistency: float
    actions: List[RepairAction]
    repaired_sheaf: CellularSheaf


class TopologicalRepairEngine:
    """
    Diagnoses and autonomously repairs topological obstructions in Cellular Sheaves.
    """

    def __init__(self, sheaf: CellularSheaf, zero_tolerance: float = 1e-7):
        self.sheaf = sheaf
        self.zero_tolerance = zero_tolerance

    def optimize_restriction_maps(
        self,
        x: np.ndarray,
        learning_rate: float = 0.1,
        iterations: int = 50,
        enforce_orthogonal: bool = True
    ) -> List[RepairAction]:
        """
        Gradient-based adaptation of edge restriction maps to accommodate agent states x.
        If enforce_orthogonal=True, projects each updated map to O(d) via SVD.
        """
        actions: List[RepairAction] = []
        unpacked_x = self.sheaf.unpack_0cochain(x)

        for it in range(iterations):
            y = self.sheaf.compute_coboundary_of(x)
            unpacked_y = self.sheaf.unpack_1cochain(y)

            max_delta_map = 0.0

            for e_id in list(self.sheaf.edge_order):
                edge = self.sheaf.edges[e_id]
                diff_e = unpacked_y[e_id]  # Shape: (dim_edge,)
                x_u = unpacked_x[edge.source_id]  # Shape: (dim_src,)
                x_v = unpacked_x[edge.target_id]  # Shape: (dim_tgt,)

                # Gradients
                # L_e = (1/2) ||F_v x_v - F_u x_u||^2
                # dL/dF_v = diff_e * x_v^T
                # dL/dF_u = - diff_e * x_u^T
                grad_Fv = np.outer(diff_e, x_v)
                grad_Fu = - np.outer(diff_e, x_u)

                new_Fv = edge.target_map - learning_rate * grad_Fv
                new_Fu = edge.source_map - learning_rate * grad_Fu

                if enforce_orthogonal and edge.dim_edge == self.sheaf.vertex_dims[edge.target_id]:
                    # Project target map
                    U_v, _, Vt_v = la.svd(new_Fv)
                    new_Fv = U_v @ Vt_v

                if enforce_orthogonal and edge.dim_edge == self.sheaf.vertex_dims[edge.source_id]:
                    # Project source map
                    U_u, _, Vt_u = la.svd(new_Fu)
                    new_Fu = U_u @ Vt_u

                delta_v = float(np.max(np.abs(new_Fv - edge.target_map)))
                delta_u = float(np.max(np.abs(new_Fu - edge.source_map)))
                max_delta_map = max(max_delta_map, delta_v, delta_u)

                self.sheaf.update_restriction_maps(
                    e_id,
                    source_map=new_Fu,
                    target_map=new_Fv
                )

            if max_delta_map < 1e-6:
                break

        actions.append(RepairAction(
            action_type="RESTRICTION_MAP_UPDATE",
            target_id="ALL_EDGES",
            initial_energy=0.0,
            final_energy=self.sheaf.dirichlet_energy(x),
            description=f"Adapted restriction maps over {iterations} gradient iterations (orthogonal={enforce_orthogonal})"
        ))

        return actions

    def surgical_resection(
        self,
        x: np.ndarray,
        energy_threshold: float = 0.5
    ) -> List[RepairAction]:
        """
        Identify and excise edges carrying severe irreconcilable contradiction energy.
        """
        actions: List[RepairAction] = []
        edge_e = self.sheaf.edge_energies(x)

        edges_to_remove = [e_id for e_id, en in edge_e.items() if en > energy_threshold]

        for e_id in edges_to_remove:
            init_en = edge_e[e_id]
            self.sheaf.remove_edge(e_id)
            actions.append(RepairAction(
                action_type="SURGICAL_EDGE_EXCISION",
                target_id=e_id,
                initial_energy=init_en,
                final_energy=0.0,
                description=f"Excised high-contradiction edge {e_id} with energy {init_en:.4f} > {energy_threshold}"
            ))

        return actions

    def repair_sheaf(
        self,
        x: np.ndarray,
        allow_resection: bool = True,
        resection_threshold: float = 0.5,
        learning_rate: float = 0.15,
        iterations: int = 50
    ) -> TopologicalRepairReport:
        """
        Execute full autonomous topological repair pipeline on the sheaf:
        1. Evaluate initial cohomology invariants (beta_0, beta_1, energy).
        2. Gradient adaptation of restriction maps.
        3. If residual contradiction remains and allow_resection=True, excise bottleneck edges.
        4. Recompute cohomology invariants and output full diagnostic report.
        """
        engine_init = CohomologyEngine(self.sheaf, self.zero_tolerance)
        spec_init = engine_init.compute_spectrum()
        init_energy = self.sheaf.dirichlet_energy(x)
        norm_sq_x = float(np.dot(x, x))
        y_init = self.sheaf.compute_coboundary_of(x)
        init_consist = float(np.exp(- (np.linalg.norm(y_init)**2) / (norm_sq_x + 1e-6)))

        all_actions: List[RepairAction] = []

        # Phase 1: Map adaptation
        opt_actions = self.optimize_restriction_maps(
            x,
            learning_rate=learning_rate,
            iterations=iterations
        )
        all_actions.extend(opt_actions)

        # Phase 2: Surgical Resection if energy still high
        cur_energy = self.sheaf.dirichlet_energy(x)
        if allow_resection and cur_energy > resection_threshold:
            resect_actions = self.surgical_resection(x, energy_threshold=resection_threshold)
            all_actions.extend(resect_actions)

        engine_final = CohomologyEngine(self.sheaf, self.zero_tolerance)
        spec_final = engine_final.compute_spectrum()
        final_energy = self.sheaf.dirichlet_energy(x)
        y_final = self.sheaf.compute_coboundary_of(x)
        final_consist = float(np.exp(- (np.linalg.norm(y_final)**2) / (norm_sq_x + 1e-6)))

        return TopologicalRepairReport(
            initial_energy=init_energy,
            final_energy=final_energy,
            energy_dissipated=init_energy - final_energy,
            initial_beta_0=spec_init.beta_0,
            final_beta_0=spec_final.beta_0,
            initial_beta_1=spec_init.beta_1,
            final_beta_1=spec_final.beta_1,
            initial_consistency=init_consist,
            final_consistency=final_consist,
            actions=all_actions,
            repaired_sheaf=self.sheaf
        )
