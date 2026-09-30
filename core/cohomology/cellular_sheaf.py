"""
Cellular Sheaf Data Structures & Coboundary Operations
======================================================
Implements Cellular Sheaves over 1D cell complexes (graphs) for multi-agent
semantic consistency, formalizing local stalks and linear restriction maps.

Mathematical Formulation:
--------------------------
Let X = (V, E) be a 1-cell complex (directed graph).
A Cellular Sheaf F over X assigns:
- To each vertex v in V, a stalk vector space F(v) = R^{d_v}.
- To each edge e in E, a stalk vector space F(e) = R^{d_e}.
- To each incident pair v <= e, a linear restriction map:
    F_{u <= e}: F(u) -> F(e)  (source restriction map, d_e x d_u)
    F_{v <= e}: F(v) -> F(e)  (target restriction map, d_e x d_v)

The 0-cochain space is C^0(X; F) = bigoplus_{v in V} F(v), dim D_V = sum d_v.
The 1-cochain space is C^1(X; F) = bigoplus_{e in E} F(e), dim D_E = sum d_e.

Coboundary Operator:
    delta^0: C^0(X; F) -> C^1(X; F)
    (delta^0 x)_e = F_{v <= e}(x_v) - F_{u <= e}(x_u)

Sheaf Laplacian:
    Delta^0 = (delta^0)^T delta^0  in R^{D_V x D_V}
    Delta^0 is symmetric positive semi-definite.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any
import numpy as np


@dataclass
class EdgeRestriction:
    """Stores restriction maps for a directed edge e = (source -> target)."""
    edge_id: str
    source_id: str
    target_id: str
    dim_edge: int
    source_map: np.ndarray  # Shape: (dim_edge, dim_source)
    target_map: np.ndarray  # Shape: (dim_edge, dim_target)
    weight: float = 1.0


class CellularSheaf:
    """
    Cellular Sheaf F over a directed 1-cell complex (graph) X = (V, E).
    
    Provides exact assembly of:
    - Coboundary matrix delta^0 (D_E x D_V)
    - Sheaf Laplacian matrix Delta^0 = (delta^0)^T delta^0 (D_V x D_V)
    - Sheaf cochain inner products and Dirichlet energy
    """

    def __init__(self):
        self.vertices: List[str] = []
        self.vertex_dims: Dict[str, int] = {}
        self.vertex_offsets: Dict[str, int] = {}
        self.edges: Dict[str, EdgeRestriction] = {}
        self.edge_order: List[str] = []
        self.edge_offsets: Dict[str, int] = {}
        
        self._total_v_dim: int = 0
        self._total_e_dim: int = 0
        self._coboundary_cache: Optional[np.ndarray] = None
        self._laplacian_cache: Optional[np.ndarray] = None

    def add_vertex(self, vertex_id: str, dim: int = 1) -> None:
        """Add a vertex with a specified stalk dimension d_v."""
        if vertex_id in self.vertex_dims:
            if self.vertex_dims[vertex_id] != dim:
                raise ValueError(f"Vertex {vertex_id} already exists with dimension {self.vertex_dims[vertex_id]} != {dim}")
            return
        if dim <= 0:
            raise ValueError(f"Stalk dimension must be positive, got {dim}")
        
        self.vertices.append(vertex_id)
        self.vertex_dims[vertex_id] = dim
        self._invalidate_cache()

    def add_edge(
        self,
        edge_id: str,
        source_id: str,
        target_id: str,
        dim_edge: Optional[int] = None,
        source_map: Optional[np.ndarray] = None,
        target_map: Optional[np.ndarray] = None,
        weight: float = 1.0
    ) -> None:
        """
        Add a directed edge e = (source_id -> target_id) with linear restriction maps.
        If restriction maps are omitted, defaults to identity maps (trivial sheaf connection).
        """
        if source_id not in self.vertex_dims:
            raise ValueError(f"Source vertex {source_id} not registered in sheaf")
        if target_id not in self.vertex_dims:
            raise ValueError(f"Target vertex {target_id} not registered in sheaf")

        dim_src = self.vertex_dims[source_id]
        dim_tgt = self.vertex_dims[target_id]

        if dim_edge is None:
            if dim_src == dim_tgt:
                dim_edge = dim_src
            else:
                dim_edge = max(dim_src, dim_tgt)

        if source_map is None:
            if dim_edge == dim_src:
                source_map = np.eye(dim_edge, dtype=np.float64)
            else:
                source_map = np.zeros((dim_edge, dim_src), dtype=np.float64)
                min_d = min(dim_edge, dim_src)
                source_map[:min_d, :min_d] = np.eye(min_d)
        else:
            source_map = np.asarray(source_map, dtype=np.float64)
            if source_map.shape != (dim_edge, dim_src):
                raise ValueError(f"Source map shape {source_map.shape} != ({dim_edge}, {dim_src})")

        if target_map is None:
            if dim_edge == dim_tgt:
                target_map = np.eye(dim_edge, dtype=np.float64)
            else:
                target_map = np.zeros((dim_edge, dim_tgt), dtype=np.float64)
                min_d = min(dim_edge, dim_tgt)
                target_map[:min_d, :min_d] = np.eye(min_d)
        else:
            target_map = np.asarray(target_map, dtype=np.float64)
            if target_map.shape != (dim_edge, dim_tgt):
                raise ValueError(f"Target map shape {target_map.shape} != ({dim_edge}, {dim_tgt})")

        if edge_id in self.edges:
            self.edge_order.remove(edge_id)

        self.edges[edge_id] = EdgeRestriction(
            edge_id=edge_id,
            source_id=source_id,
            target_id=target_id,
            dim_edge=dim_edge,
            source_map=source_map,
            target_map=target_map,
            weight=float(weight)
        )
        self.edge_order.append(edge_id)
        self._invalidate_cache()

    def remove_edge(self, edge_id: str) -> bool:
        """Remove an edge from the sheaf (used in surgical resection)."""
        if edge_id in self.edges:
            del self.edges[edge_id]
            self.edge_order.remove(edge_id)
            self._invalidate_cache()
            return True
        return False

    def update_restriction_maps(
        self,
        edge_id: str,
        source_map: Optional[np.ndarray] = None,
        target_map: Optional[np.ndarray] = None,
        weight: Optional[float] = None
    ) -> None:
        """Update restriction maps for an existing edge (used in sheaf learning / repair)."""
        if edge_id not in self.edges:
            raise KeyError(f"Edge {edge_id} does not exist in sheaf")
        
        edge = self.edges[edge_id]
        if source_map is not None:
            sm = np.asarray(source_map, dtype=np.float64)
            if sm.shape != (edge.dim_edge, self.vertex_dims[edge.source_id]):
                raise ValueError(f"New source map shape {sm.shape} invalid")
            edge.source_map = sm

        if target_map is not None:
            tm = np.asarray(target_map, dtype=np.float64)
            if tm.shape != (edge.dim_edge, self.vertex_dims[edge.target_id]):
                raise ValueError(f"New target map shape {tm.shape} invalid")
            edge.target_map = tm

        if weight is not None:
            edge.weight = float(weight)

        self._invalidate_cache()

    def _rebuild_indices(self) -> None:
        """Compute flat indices and offsets for cochain vectors."""
        self.vertex_offsets.clear()
        cur_v = 0
        for v in self.vertices:
            self.vertex_offsets[v] = cur_v
            cur_v += self.vertex_dims[v]
        self._total_v_dim = cur_v

        self.edge_offsets.clear()
        cur_e = 0
        for e_id in self.edge_order:
            self.edge_offsets[e_id] = cur_e
            cur_e += self.edges[e_id].dim_edge
        self._total_e_dim = cur_e

    def _invalidate_cache(self) -> None:
        self._coboundary_cache = None
        self._laplacian_cache = None

    @property
    def total_vertex_dim(self) -> int:
        if not self.vertex_offsets:
            self._rebuild_indices()
        return self._total_v_dim

    @property
    def total_edge_dim(self) -> int:
        if not self.edge_offsets:
            self._rebuild_indices()
        return self._total_e_dim

    def build_coboundary(self) -> np.ndarray:
        """
        Assemble the coboundary matrix delta^0: C^0(X; F) -> C^1(X; F).
        Shape: (D_E, D_V)
        
        For each directed edge e = (u -> v):
        (delta^0 x)_e = sqrt(weight) * [ F_{v <= e} x_v - F_{u <= e} x_u ]
        """
        if self._coboundary_cache is not None:
            return self._coboundary_cache

        self._rebuild_indices()
        D_E = self._total_e_dim
        D_V = self._total_v_dim

        delta = np.zeros((D_E, D_V), dtype=np.float64)

        for e_id in self.edge_order:
            edge = self.edges[e_id]
            e_off = self.edge_offsets[e_id]
            e_dim = edge.dim_edge
            sqrt_w = np.sqrt(max(0.0, edge.weight))

            u_off = self.vertex_offsets[edge.source_id]
            u_dim = self.vertex_dims[edge.source_id]
            v_off = self.vertex_offsets[edge.target_id]
            v_dim = self.vertex_dims[edge.target_id]

            # Source restriction map: -sqrt(w) * F_{u <= e}
            delta[e_off : e_off + e_dim, u_off : u_off + u_dim] = -sqrt_w * edge.source_map
            # Target restriction map: +sqrt(w) * F_{v <= e}
            delta[e_off : e_off + e_dim, v_off : v_off + v_dim] += sqrt_w * edge.target_map

        self._coboundary_cache = delta
        return delta

    def build_laplacian(self) -> np.ndarray:
        """
        Assemble the Sheaf Laplacian Delta^0 = (delta^0)^T delta^0.
        Shape: (D_V, D_V). Symmetric, positive semi-definite.
        """
        if self._laplacian_cache is not None:
            return self._laplacian_cache

        delta = self.build_coboundary()
        laplacian = delta.T @ delta
        # Enforce exact floating point symmetry
        laplacian = 0.5 * (laplacian + laplacian.T)
        self._laplacian_cache = laplacian
        return laplacian

    def pack_0cochain(self, stalk_vectors: Dict[str, np.ndarray]) -> np.ndarray:
        """Pack a mapping of {vertex_id: vector} into a flattened 0-cochain x in C^0(X; F)."""
        if not self.vertex_offsets:
            self._rebuild_indices()
        x = np.zeros(self._total_v_dim, dtype=np.float64)
        for v, off in self.vertex_offsets.items():
            dim = self.vertex_dims[v]
            if v in stalk_vectors:
                vec = np.asarray(stalk_vectors[v], dtype=np.float64).ravel()
                if len(vec) != dim:
                    raise ValueError(f"Vector for {v} has length {len(vec)} != required {dim}")
                x[off : off + dim] = vec
            else:
                x[off : off + dim] = 0.0
        return x

    def unpack_0cochain(self, x: np.ndarray) -> Dict[str, np.ndarray]:
        """Unpack a flattened 0-cochain x into {vertex_id: vector}."""
        if not self.vertex_offsets:
            self._rebuild_indices()
        x = np.asarray(x, dtype=np.float64).ravel()
        if len(x) != self._total_v_dim:
            raise ValueError(f"0-cochain length {len(x)} != total vertex dimension {self._total_v_dim}")
        
        result = {}
        for v, off in self.vertex_offsets.items():
            dim = self.vertex_dims[v]
            result[v] = x[off : off + dim].copy()
        return result

    def pack_1cochain(self, edge_vectors: Dict[str, np.ndarray]) -> np.ndarray:
        """Pack a mapping of {edge_id: vector} into a flattened 1-cochain y in C^1(X; F)."""
        if not self.edge_offsets:
            self._rebuild_indices()
        y = np.zeros(self._total_e_dim, dtype=np.float64)
        for e_id, off in self.edge_offsets.items():
            dim = self.edges[e_id].dim_edge
            if e_id in edge_vectors:
                vec = np.asarray(edge_vectors[e_id], dtype=np.float64).ravel()
                if len(vec) != dim:
                    raise ValueError(f"Vector for edge {e_id} has length {len(vec)} != required {dim}")
                y[off : off + dim] = vec
        return y

    def unpack_1cochain(self, y: np.ndarray) -> Dict[str, np.ndarray]:
        """Unpack a flattened 1-cochain y into {edge_id: vector}."""
        if not self.edge_offsets:
            self._rebuild_indices()
        y = np.asarray(y, dtype=np.float64).ravel()
        if len(y) != self._total_e_dim:
            raise ValueError(f"1-cochain length {len(y)} != total edge dimension {self._total_e_dim}")
        
        result = {}
        for e_id, off in self.edge_offsets.items():
            dim = self.edges[e_id].dim_edge
            result[e_id] = y[off : off + dim].copy()
        return result

    def compute_coboundary_of(self, x: np.ndarray) -> np.ndarray:
        """Compute y = delta^0 x (the edge discrepancies)."""
        delta = self.build_coboundary()
        return delta @ x

    def dirichlet_energy(self, x: np.ndarray) -> float:
        """
        Compute Sheaf Dirichlet Energy:
            E_F(x) = (1/2) x^T Delta^0 x = (1/2) ||delta^0 x||^2
        """
        y = self.compute_coboundary_of(x)
        return 0.5 * float(np.dot(y, y))

    def edge_energies(self, x: np.ndarray) -> Dict[str, float]:
        """Compute the breakdown of Dirichlet energy on each edge: E_e = (1/2) ||(delta^0 x)_e||^2."""
        y = self.compute_coboundary_of(x)
        unpacked_y = self.unpack_1cochain(y)
        energies = {}
        for e_id, val in unpacked_y.items():
            energies[e_id] = 0.5 * float(np.dot(val, val))
        return energies
