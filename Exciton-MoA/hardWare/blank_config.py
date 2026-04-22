# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
from dataclasses import dataclass, field
from typing import Tuple, Optional, List

@dataclass
class BlankManifoldConfig:
    """
    Initialization Parameters for the 'Blank Slate' Manifold.
    Unlike a Crystalline Storage manifold (which is pre-weighted by data),
    this manifold relies purely on topological and physical parameters to
    provide a neutral substrate for autonomous agents and external data streams.
    """
    
    # --- Topological Parameters ---
    # A base node count. While hyperbolic space allows near-infinite packing,
    # we need a discrete lattice to compute physical interactions (O(n^2) scaling).
    base_node_count: int = 1024 
    
    # The geometric space the manifold is embedded in.
    # Options: 'hyperbolic_uniform', 'flat_lattice', 'spherical', 'poincare_disk'
    topology_type: str = "hyperbolic_uniform" 
    
    # Dimensionality of the manifold. Higher dimensions allow more complex
    # orthogonal resonance frequencies.
    dimensionality: int = 3 

    # --- Physics / Dynamics Parameters ---
    # Baseline threshold for information to collapse into a stable basin
    base_jeans_mass: float = 1.0 
    
    # How quickly resonance dissipates without constructive interference
    base_damping_factor: float = 0.05 
    
    # Base connection strength between unweighted nodes
    baseline_coupling: float = 0.1 

    def __post_init__(self):
        # We can add validation logic here if needed for dimensionality
        # or layout constraints
        pass
