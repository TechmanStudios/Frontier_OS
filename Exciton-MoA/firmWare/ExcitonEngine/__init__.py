"""
Frontier_OS ExcitonEngine Module
"""

from .excitons import ExcitonEngine

__all__ = ["ExcitonEngine", "RiemannianGeodesicNavigator", "ChristoffelCalculator", "GeodesicStepResult"]


def __getattr__(name):
    """Load integrated navigation only when requested, keeping the base engine standalone."""
    if name in {"RiemannianGeodesicNavigator", "ChristoffelCalculator", "GeodesicStepResult"}:
        from . import geodesic_navigator

        value = getattr(geodesic_navigator, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
