"""
Frontier_OS: Embodied Robotics & Geodesic Actuation
Vector 15: Closed-Loop Physical Robotics on Configuration Space Riemannian Manifolds.
"""

from Frontier_OS.core.robotics.kinematic_manifold import (
    Obstacle3D,
    KinematicState,
    ArticulatedManipulator6DOF,
    RoboticConfigurationManifold
)
from Frontier_OS.core.robotics.actuation_controller import (
    ActuationStepRecord,
    TrajectoryExecutionReport,
    GeodesicActuationController
)
from Frontier_OS.core.robotics.safety_arbiter import (
    SafetyViolation,
    RoboticSafetyAuditReport,
    RoboticSafetyArbiter
)

__all__ = [
    "Obstacle3D",
    "KinematicState",
    "ArticulatedManipulator6DOF",
    "RoboticConfigurationManifold",
    "ActuationStepRecord",
    "TrajectoryExecutionReport",
    "GeodesicActuationController",
    "SafetyViolation",
    "RoboticSafetyAuditReport",
    "RoboticSafetyArbiter"
]
