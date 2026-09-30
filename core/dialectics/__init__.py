"""
Frontier_OS: Multi-Agent Metacognitive Dialogue Arena & Dialectical Reasoning (Vector 10)
File: Frontier_OS/core/dialectics/__init__.py

Core package for multi-agent dialectical discourse, adversarial Riemannian manifold
synthesis, counter-example discovery, quantitative causal ablation, and higher-order
Hegelian synthesis.
"""

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
    NodeCausalClassification,
    AblationTelemetry,
    MinimalCausalKernel,
    QuantitativeCausalAblator
)
from Frontier_OS.core.dialectics.synthesis_arbiter import (
    DialecticalVerdict,
    DialecticalTheoremReport,
    SynthesisArbiter
)
from Frontier_OS.core.dialectics.dialectical_arena import (
    DialecticalArena,
    ArenaSessionReport
)

__all__ = [
    "DialecticalProposition",
    "PropositionType",
    "EvidentiaryProofBundle",
    "ProponentCluster",
    "AdversaryChallengeReport",
    "AttackVerdict",
    "AdversaryCluster",
    "NodeCausalClassification",
    "AblationTelemetry",
    "MinimalCausalKernel",
    "QuantitativeCausalAblator",
    "DialecticalVerdict",
    "DialecticalTheoremReport",
    "SynthesisArbiter",
    "DialecticalArena",
    "ArenaSessionReport",
]
