"""
Frontier_OS: Non-Abelian Gauge Sheaves & Holonomy-Based Spatial Intelligence
Vector 16: SO(3)/SE(3) Lie Group Connections, Wilson Loops & Spatial Gauge Cohomology.
"""

from Frontier_OS.core.gauge.lie_group import (
    skew,
    unskew,
    so3_exp,
    so3_log,
    so3_geodesic_distance,
    se3_exp,
    se3_log,
    lie_bracket_so3,
    adjoint_so3,
    adjoint_matrix_so3,
    adjoint_se3,
    adjoint_matrix_se3,
    so3_left_jacobian,
    so3_left_jacobian_inv,
    so3_right_jacobian,
    so3_slerp,
    se3_interpolate
)
from Frontier_OS.core.gauge.gauge_sheaf import (
    WilsonLoopReport,
    FaceCurvatureReport,
    NonAbelianGaugeSheaf
)
from Frontier_OS.core.gauge.holonomic_navigator import (
    ToolDriftCompensationReport,
    GaugeNavigationAuditReport,
    HolonomicSpatialNavigator
)
from Frontier_OS.core.gauge.gauge_arbiter import (
    GaugeViolation,
    GaugeArbiterReport,
    NonAbelianGaugeArbiter
)

__all__ = [
    "skew",
    "unskew",
    "so3_exp",
    "so3_log",
    "so3_geodesic_distance",
    "se3_exp",
    "se3_log",
    "lie_bracket_so3",
    "adjoint_so3",
    "adjoint_matrix_so3",
    "adjoint_se3",
    "adjoint_matrix_se3",
    "so3_left_jacobian",
    "so3_left_jacobian_inv",
    "so3_right_jacobian",
    "so3_slerp",
    "se3_interpolate",
    "WilsonLoopReport",
    "FaceCurvatureReport",
    "NonAbelianGaugeSheaf",
    "ToolDriftCompensationReport",
    "GaugeNavigationAuditReport",
    "HolonomicSpatialNavigator",
    "GaugeViolation",
    "GaugeArbiterReport",
    "NonAbelianGaugeArbiter"
]

