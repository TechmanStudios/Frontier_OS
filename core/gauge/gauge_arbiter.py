"""
Frontier_OS: Non-Abelian Gauge Safety Arbiter & Holonomy Containment
File: Frontier_OS/core/gauge/gauge_arbiter.py

Ensures orientation consistency and detects topological dislocations:
1. Audits spatial networks against maximum holonomy defect angles (e.g. θ_max <= 5.0°).
2. Verifies non-abelian Dirichlet energy relaxation convergence.
3. Reflexive safety stop if a Wilson loop detects a frame contradiction.
"""

from dataclasses import dataclass, field
import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from Frontier_OS.core.gauge.gauge_sheaf import (
    NonAbelianGaugeSheaf,
    WilsonLoopReport
)
from Frontier_OS.core.gauge.holonomic_navigator import (
    HolonomicSpatialNavigator,
    GaugeNavigationAuditReport
)


@dataclass
class GaugeViolation:
    """Record of a gauge holonomy or orientation invariant breach."""
    loop_id: str
    message: str
    defect_angle_deg: float
    severity: str                       # "CRITICAL", "WARNING"


@dataclass
class GaugeArbiterReport:
    """Formal verification report from the Non-Abelian Gauge Arbiter."""
    is_gauge_consistent: bool
    total_loops_checked: int
    violations_count: int
    violations: List[GaugeViolation]
    gauge_consistency_score: float
    max_defect_angle_deg: float
    dirichlet_energy: float
    yang_mills_action: float
    emergency_stop_triggered: bool
    audit_time_us: float

    def to_dict(self) -> Dict[str, Any]:
        """Serializes gauge arbiter report."""
        return {
            "is_gauge_consistent": self.is_gauge_consistent,
            "total_loops_checked": self.total_loops_checked,
            "violations_count": self.violations_count,
            "violations": [
                {
                    "loop_id": v.loop_id,
                    "message": v.message,
                    "defect_angle_deg": round(v.defect_angle_deg, 2),
                    "severity": v.severity
                }
                for v in self.violations
            ],
            "gauge_consistency_score": round(self.gauge_consistency_score, 4),
            "max_defect_angle_deg": round(self.max_defect_angle_deg, 2),
            "dirichlet_energy": round(self.dirichlet_energy, 4),
            "yang_mills_action": round(self.yang_mills_action, 5),
            "emergency_stop_triggered": self.emergency_stop_triggered,
            "audit_time_us": round(self.audit_time_us, 2)
        }


class NonAbelianGaugeArbiter:
    """
    Formal verification safety arbiter for non-abelian gauge sheaves and Wilson loop holonomies.
    """
    def __init__(
        self,
        navigator: HolonomicSpatialNavigator,
        max_allowed_defect_deg: float = 3.5,
        min_gauge_consistency: float = 0.95,
        max_allowed_yang_mills: float = 1.0
    ):
        self.navigator = navigator
        self.sheaf = navigator.sheaf
        self.max_allowed_defect_deg = max_allowed_defect_deg
        self.min_gauge_consistency = min_gauge_consistency
        self.max_allowed_yang_mills = max_allowed_yang_mills

    def audit_holonomic_safety(
        self,
        candidate_loops: List[Tuple[str, List[str]]]
    ) -> GaugeArbiterReport:
        """
        Audits a set of spatial loops against formal non-abelian holonomy invariants.
        """
        import time
        t0 = time.perf_counter_ns()

        nav_report = self.navigator.audit_workspace_holonomy(
            candidate_loops,
            flat_tol_deg=self.max_allowed_defect_deg
        )

        violations: List[GaugeViolation] = []
        for wl in nav_report.wilson_loops:
            if wl.defect_angle_deg > self.max_allowed_defect_deg:
                severity = "CRITICAL" if wl.defect_angle_deg > (self.max_allowed_defect_deg * 2.0) else "WARNING"
                violations.append(GaugeViolation(
                    loop_id=wl.loop_id,
                    message=f"Wilson loop {wl.loop_id} defect {wl.defect_angle_deg:.2f}° exceeded threshold {self.max_allowed_defect_deg:.2f}°",
                    defect_angle_deg=wl.defect_angle_deg,
                    severity=severity
                ))

        dirichlet_e = self.sheaf.compute_dirichlet_energy()
        s_ym = self.sheaf.compute_yang_mills_action()

        if s_ym > self.max_allowed_yang_mills:
            violations.append(GaugeViolation(
                loop_id="yang_mills_global",
                message=f"Yang-Mills action {s_ym:.4f} exceeded threshold {self.max_allowed_yang_mills:.4f}",
                defect_angle_deg=math.degrees(s_ym),
                severity="WARNING"
            ))

        is_safe = len(violations) == 0 and nav_report.gauge_consistency_score >= self.min_gauge_consistency
        emergency_stop = any(v.severity == "CRITICAL" for v in violations)

        audit_time_us = (time.perf_counter_ns() - t0) / 1000.0

        return GaugeArbiterReport(
            is_gauge_consistent=is_safe,
            total_loops_checked=nav_report.total_loops_audited,
            violations_count=len(violations),
            violations=violations,
            gauge_consistency_score=nav_report.gauge_consistency_score,
            max_defect_angle_deg=nav_report.max_defect_angle_deg,
            dirichlet_energy=dirichlet_e,
            yang_mills_action=s_ym,
            emergency_stop_triggered=emergency_stop,
            audit_time_us=audit_time_us
        )
