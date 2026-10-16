"""
Frontier_OS: Multi-Agent Metacognitive Dialogue Arena
File: Frontier_OS/core/dialectics/dialectical_arena.py

Coordinates the multi-agent dialectical discourse between Thesis Proponent and
Antithesis Adversary clusters across continuous Riemannian manifolds:
1. Spawns and configures dual swarm clusters with coupled Kuramoto oscillators.
2. Directs affirmative synthesis, counter-example discovery, and adversarial metric testing.
3. Coordinates quantitative causal ablation to eliminate degenerate sub-manifolds.
4. Synthesizes higher-order Hegelian resolutions with positive causal emergence gains.
5. Emits real-time telemetric streams for the SOL Studio 3D visualizer and REST APIs.
"""

from dataclasses import dataclass, field
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from Frontier_OS.core.hippocampal_sink import DreamConsolidationReport
from Frontier_OS.core.metacognition.circuit_cache import HippocampalCircuitCache
from Frontier_OS.core.dialectics.proponent_cluster import (
    DialecticalProposition,
    PropositionType,
    EvidentiaryProofBundle,
    ProponentCluster
)
from Frontier_OS.core.dialectics.adversary_cluster import (
    AdversaryChallengeReport,
    AttackVerdict,
    AdversaryCluster
)
from Frontier_OS.core.dialectics.causal_ablation import (
    AblationTelemetry,
    QuantitativeCausalAblator
)
from Frontier_OS.core.dialectics.synthesis_arbiter import (
    DialecticalVerdict,
    DialecticalTheoremReport,
    SynthesisArbiter
)


@dataclass
class ArenaSessionReport:
    """Full comprehensive telemetry of a completed dialectical debate session."""
    session_id: str
    proposition: DialecticalProposition
    proof_bundle: EvidentiaryProofBundle
    adversary_report: AdversaryChallengeReport
    ablation_telemetry: AblationTelemetry
    theorem_report: DialecticalTheoremReport
    kuramoto_trajectory: List[float]
    final_consensus_order: float
    proponent_swarm_size: int
    adversary_swarm_size: int
    session_latency_ms: float

    def to_dict(self) -> Dict[str, Any]:
        """Serializes session report for API endpoints and JSON logs."""
        return {
            "session_id": self.session_id,
            "proposition": self.proposition.to_dict(),
            "proof_bundle": self.proof_bundle.to_dict(),
            "adversary_report": self.adversary_report.to_dict(),
            "ablation_telemetry": self.ablation_telemetry.to_dict(),
            "theorem_report": self.theorem_report.to_dict(),
            "kuramoto_trajectory": [round(float(v), 4) for v in self.kuramoto_trajectory],
            "final_consensus_order": round(float(self.final_consensus_order), 4),
            "proponent_swarm_size": self.proponent_swarm_size,
            "adversary_swarm_size": self.adversary_swarm_size,
            "session_latency_ms": round(float(self.session_latency_ms), 2)
        }


class DialecticalArena:
    """
    Autonomous Multi-Agent Dialectical Reasoning Arena.
    Orchestrates discourse, counter-example interrogation, causal ablation,
    and higher-order Hegelian synthesis across Riemannian manifolds.
    """
    def __init__(
        self,
        proponent: Optional[ProponentCluster] = None,
        adversary: Optional[AdversaryCluster] = None,
        ablator: Optional[QuantitativeCausalAblator] = None,
        arbiter: Optional[SynthesisArbiter] = None,
        circuit_cache: Optional[HippocampalCircuitCache] = None,
        proponent_swarm_size: int = 16,
        adversary_swarm_size: int = 16
    ):
        self.circuit_cache = circuit_cache or HippocampalCircuitCache()
        self.proponent = proponent or ProponentCluster()
        self.adversary = adversary or AdversaryCluster()
        self.ablator = ablator or QuantitativeCausalAblator()
        self.arbiter = arbiter or SynthesisArbiter(circuit_cache=self.circuit_cache)
        self.proponent_swarm_size = proponent_swarm_size
        self.adversary_swarm_size = adversary_swarm_size

    def conduct_debate(
        self,
        proposition: DialecticalProposition,
        max_debate_rounds: int = 12
    ) -> ArenaSessionReport:
        """
        Executes an end-to-end multi-agent dialectical discourse session.
        """
        t0 = time.time()
        session_id = f"arena_{proposition.prop_id}_{int(time.time()*1000)}"

        # Step 1: Thesis Proponent synthesizes affirmative manifold & proof bundle
        proof_bundle = self.proponent.synthesize_thesis_manifold(proposition)

        # Step 2: Antithesis Adversary challenges the Thesis
        adversary_report = self.adversary.challenge_thesis(proposition, proof_bundle)

        # Step 3: Kuramoto Hegelian Phase Coupling Dynamics
        # Simulate phase synchronization across the dual swarm clusters
        N_T = self.proponent_swarm_size
        N_A = self.adversary_swarm_size
        total_agents = N_T + N_A

        # Initialize phases: Proponents around 0, Adversaries around pi/2
        theta_T = np.random.normal(0.0, 0.15, size=N_T)
        theta_A = np.random.normal(np.pi / 2.0, 0.25, size=N_A)

        kuramoto_trajectory: List[float] = []

        is_refuted = (adversary_report.verdict == AttackVerdict.REFUTED)

        for r in range(max_debate_rounds):
            all_phases = np.concatenate([theta_T, theta_A])
            # Order parameter r = |(1/N) * sum e^{i theta_j}|
            complex_order = np.mean(np.exp(1j * all_phases))
            order_mag = float(np.abs(complex_order))
            kuramoto_trajectory.append(order_mag)

            if is_refuted:
                # Under contradiction, phases repel: adversarial cluster bifurcates to pi
                theta_T += 0.05 * np.sin(0.0 - theta_T)
                theta_A += 0.15 * np.sin(np.pi - theta_A)
            else:
                # Under agreement/synthesis, mutual coupling pulls phases toward consensus
                mean_T = float(np.mean(theta_T))
                theta_T += 0.25 * np.sin(mean_T - theta_T)
                theta_A += 0.35 * np.sin(mean_T - theta_A)

        all_phases_final = np.concatenate([theta_T, theta_A])
        final_order = float(np.abs(np.mean(np.exp(1j * all_phases_final))))

        # Step 4: Quantitative Causal Ablation
        # If thesis survived or is evaluated, extract Minimal Causal Kernel
        spec = proposition.target_spec or self.proponent.canonical_specs.get(proposition.title)
        if spec is None:
            from sol.kernel.synthesis.circuit_synthesizer import TruthTableSpec
            spec = TruthTableSpec(
                name=proposition.prop_id,
                inputs=["A", "B"],
                outputs=["OUT"],
                table={(0, 0): (0,), (0, 1): (1,), (1, 0): (1,), (1, 1): (1,)}
            )

        ablation_telemetry = self.ablator.ablate_circuit(
            proof_bundle.circuit,
            spec,
            prop_id=proposition.prop_id
        )

        # Step 5: Synthesis Arbiter issues formal verdict
        theorem_report = self.arbiter.resolve_debate(
            proposition=proposition,
            proof_bundle=proof_bundle,
            adversary_report=adversary_report,
            ablation_telemetry=ablation_telemetry,
            consensus_order=final_order
        )

        t_elapsed_ms = (time.time() - t0) * 1000.0

        return ArenaSessionReport(
            session_id=session_id,
            proposition=proposition,
            proof_bundle=proof_bundle,
            adversary_report=adversary_report,
            ablation_telemetry=ablation_telemetry,
            theorem_report=theorem_report,
            kuramoto_trajectory=kuramoto_trajectory,
            final_consensus_order=final_order,
            proponent_swarm_size=self.proponent_swarm_size,
            adversary_swarm_size=self.adversary_swarm_size,
            session_latency_ms=t_elapsed_ms
        )
