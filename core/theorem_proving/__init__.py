"""
Frontier_OS: Open-Ended Mathematical Discovery & Automated Theorem Proving (Vector 11)
File: Frontier_OS/core/theorem_proving/__init__.py

Core package for autonomous conjecture generation, dialectical theorem proving,
algebraic and geometric invariance verification, and formal theorem corpus crystallization.
"""

from Frontier_OS.core.theorem_proving.algebraic_axioms import (
    MathematicalDomain,
    AxiomDefinition,
    AlgebraicRewriter,
    build_axiom_library,
    build_canonical_axiom_system,
    build_default_axiom_registry,
)
from Frontier_OS.core.theorem_proving.conjecture_engine import (
    ConjectureType,
    MathematicalConjecture,
    AutonomousConjectureEngine,
    generate_canonical_conjectures,
)
from Frontier_OS.core.theorem_proving.proof_engine import (
    ProofVerdict,
    ProofStep,
    TheoremProofCertificate,
    FormalProofCertificate,
    AutomatedProofEngine
)
from Frontier_OS.core.theorem_proving.theorem_corpus import (
    TheoremRecord,
    TheoremCorpus
)

__all__ = [
    "MathematicalDomain",
    "AxiomDefinition",
    "AlgebraicRewriter",
    "build_axiom_library",
    "build_canonical_axiom_system",
    "build_default_axiom_registry",
    "ConjectureType",
    "MathematicalConjecture",
    "AutonomousConjectureEngine",
    "generate_canonical_conjectures",
    "ProofVerdict",
    "ProofStep",
    "TheoremProofCertificate",
    "FormalProofCertificate",
    "AutomatedProofEngine",
    "TheoremRecord",
    "TheoremCorpus",
]


