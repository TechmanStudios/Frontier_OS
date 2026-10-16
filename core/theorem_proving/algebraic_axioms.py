"""
Frontier_OS: Formal Axiom System & Algebraic Grounding
File: Frontier_OS/core/theorem_proving/algebraic_axioms.py

Defines foundational mathematical axioms across boolean algebra, differential geometry,
information-theoretic causality, and arithmetic for autonomous theorem proving.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class MathematicalDomain(str, Enum):
    """Branches of mathematical inquiry explored by the discovery engine."""
    BOOLEAN_ALGEBRA = "BOOLEAN_ALGEBRA"         # Duality, idempotence, distributivity
    METRIC_GEOMETRY = "METRIC_GEOMETRY"         # Lie algebra generators, Ricci curvature, geodesics
    CAUSAL_INFORMATION = "CAUSAL_INFORMATION"   # Hoel Effective Information, degeneracy, coarse-graining
    ARITHMETIC_ALGEBRA = "ARITHMETIC_ALGEBRA"   # Ripple carry, modular groups, 2's complement


@dataclass
class AxiomDefinition:
    """Formal mathematical axiom providing bedrock deductive grounding."""
    axiom_id: str
    domain: MathematicalDomain
    name: str
    formula_latex: str
    statement: str
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serializes axiom specification."""
        return {
            "axiom_id": self.axiom_id,
            "domain": self.domain.value,
            "name": self.name,
            "formula_latex": self.formula_latex,
            "statement": self.statement,
            "description": self.description
        }


def build_axiom_library() -> Dict[str, AxiomDefinition]:
    """Compiles the core library of mathematical axioms."""
    axioms = {}

    # Boolean Duality Axioms
    axioms["AXIOM_DEMORGAN_AND"] = AxiomDefinition(
        axiom_id="AXIOM_DEMORGAN_AND",
        domain=MathematicalDomain.BOOLEAN_ALGEBRA,
        name="De Morgan's Duality (Conjunction)",
        formula_latex=r"\neg (A \wedge B) \iff (\neg A \vee \neg B)",
        statement="The negation of a conjunction is the disjunction of the negations.",
        description="Dual phase inversion on Riemannian interference wells."
    )

    axioms["AXIOM_DEMORGAN_OR"] = AxiomDefinition(
        axiom_id="AXIOM_DEMORGAN_OR",
        domain=MathematicalDomain.BOOLEAN_ALGEBRA,
        name="De Morgan's Duality (Disjunction)",
        formula_latex=r"\neg (A \vee B) \iff (\neg A \wedge \neg B)",
        statement="The negation of a disjunction is the conjunction of the negations.",
        description="Topological duality between constructive product lensing and union lensing."
    )

    axioms["AXIOM_XOR_INVOLUTION"] = AxiomDefinition(
        axiom_id="AXIOM_XOR_INVOLUTION",
        domain=MathematicalDomain.BOOLEAN_ALGEBRA,
        name="XOR Self-Inverse Involution",
        formula_latex=r"A \oplus B \oplus B = A",
        statement="Exclusive OR is its own inverse; double collision restores the original wave packet.",
        description="Symplectic wave conservation under destructive soliton reflection."
    )

    axioms["AXIOM_MAJORITY_SELF_DUAL"] = AxiomDefinition(
        axiom_id="AXIOM_MAJORITY_SELF_DUAL",
        domain=MathematicalDomain.BOOLEAN_ALGEBRA,
        name="Majority Self-Duality",
        formula_latex=r"\text{Maj}(\neg A, \neg B, \neg C) \iff \neg \text{Maj}(A, B, C)",
        statement="Inverting all inputs of an odd-arity majority voter inverts the final outcome.",
        description="Odd parity symmetry across Riemannian decision surfaces."
    )

    # Differential Geometric Axioms
    axioms["AXIOM_RICCI_POSITIVE_DEFINITE"] = AxiomDefinition(
        axiom_id="AXIOM_RICCI_POSITIVE_DEFINITE",
        domain=MathematicalDomain.METRIC_GEOMETRY,
        name="Metric Lie Exponential Retraction",
        formula_latex=r"g = \exp(S) \succ 0 \implies \det(g) > 0 \wedge \forall i, \lambda_i(g) > 0",
        statement="Any symmetric matrix exponentiated yields a strictly positive-definite Riemannian metric.",
        description="Guarantees non-singular Riemannian manifolds without coordinate caustics."
    )

    axioms["AXIOM_GEODESIC_LEVI_CIVITA"] = AxiomDefinition(
        axiom_id="AXIOM_GEODESIC_LEVI_CIVITA",
        domain=MathematicalDomain.METRIC_GEOMETRY,
        name="Symplectic Geodesic Energy Conservation",
        formula_latex=r"\frac{d^2 x^k}{dt^2} + \Gamma^k_{ij} \frac{dx^i}{dt} \frac{dx^j}{dt} = 0",
        statement="Autoparallel trajectories conserve kinetic energy under torsion-free Levi-Civita connections.",
        description="Non-branching soliton wave propagation along Riemannian geodesics."
    )

    # Causal Information Axioms
    axioms["AXIOM_OCCAM_CAUSAL_EMERGENCE"] = AxiomDefinition(
        axiom_id="AXIOM_OCCAM_CAUSAL_EMERGENCE",
        domain=MathematicalDomain.CAUSAL_INFORMATION,
        name="Degeneracy Quenching Causal Emergence",
        formula_latex=r"\Delta EI = EI(W_{\text{macro}}) - EI(W_{\text{micro}}) = \Delta \text{Det} + \Delta \text{Deg} > 0",
        statement="Macroscopic coarse graining quenches microscopic degeneracy, generating positive causal emergence.",
        description="Proven Erik Hoel formulation across multi-scale continuous circuits."
    )

    # Arithmetic Number Theory Axioms
    axioms["AXIOM_FULL_ADDER_DECOMPOSITION"] = AxiomDefinition(
        axiom_id="AXIOM_FULL_ADDER_DECOMPOSITION",
        domain=MathematicalDomain.ARITHMETIC_ALGEBRA,
        name="Full Adder Algebraic Decomposition",
        formula_latex=r"\text{Sum} = A \oplus B \oplus C_{\text{in}}, \quad C_{\text{out}} = \text{Maj}(A, B, C_{\text{in}})",
        statement="Binary addition decomposes canonically into parity sum and majority carry.",
        description="Geometric coupling between destructive collision and constructive majority lensing."
    )

    return axioms
