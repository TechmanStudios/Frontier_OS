"""
Sheaf-Theoretic Knowledge Cohomology & Global Semantic Consistency Module
========================================================================
Vector 12 of SOL-Systems & Frontier_OS.
"""

from .cellular_sheaf import (
    CellularSheaf,
    EdgeRestriction
)
from .cohomology_engine import (
    CohomologyEngine,
    CohomologySpectrum,
    HarmonicDecomposition
)
from .sheaf_diffusion import (
    SheafDiffuser,
    DiffusionStepRecord,
    DiffusionTrajectory
)
from .topological_repair import (
    TopologicalRepairEngine,
    RepairAction,
    TopologicalRepairReport
)
from .cohomology_arbiter import (
    CohomologyArbiter,
    CohomologyAuditReport
)

__all__ = [
    "CellularSheaf",
    "EdgeRestriction",
    "CohomologyEngine",
    "CohomologySpectrum",
    "HarmonicDecomposition",
    "SheafDiffuser",
    "DiffusionStepRecord",
    "DiffusionTrajectory",
    "TopologicalRepairEngine",
    "RepairAction",
    "TopologicalRepairReport",
    "CohomologyArbiter",
    "CohomologyAuditReport",
]
