"""
Frontier_OS: Theorem Corpus & Lemma Dependency Graph
File: Frontier_OS/core/theorem_proving/theorem_corpus.py

Manages the formal mathematical library of proved theorems, refutation counter-examples,
lemma dependency DAGs, and LaTeX/Markdown monograph generation.
"""

from dataclasses import dataclass, field
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import numpy as np

from Frontier_OS.core.theorem_proving.algebraic_axioms import (
    MathematicalDomain
)
from Frontier_OS.core.theorem_proving.conjecture_engine import (
    MathematicalConjecture
)
from Frontier_OS.core.theorem_proving.proof_engine import (
    ProofVerdict,
    TheoremProofCertificate
)


@dataclass
class TheoremRecord:
    """A formally proved mathematical theorem with its proof certificate."""
    theorem_id: str
    conjecture_id: str
    title: str
    statement: str
    latex_formula: str
    domain: MathematicalDomain
    proof_certificate: TheoremProofCertificate
    dependencies: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        """Serializes theorem record."""
        return {
            "theorem_id": self.theorem_id,
            "conjecture_id": self.conjecture_id,
            "title": self.title,
            "statement": self.statement,
            "latex_formula": self.latex_formula,
            "domain": self.domain.value,
            "proof_certificate": self.proof_certificate.to_dict(),
            "dependencies": self.dependencies,
            "timestamp": self.timestamp
        }

    def to_markdown(self) -> str:
        """Formats theorem for academic monograph / formal documentation."""
        cert = self.proof_certificate
        lines = [
            f"### Theorem: {self.title} (`{self.theorem_id}`)",
            f"**Domain:** `{self.domain.value}` | **Timestamp:** {self.timestamp}",
            f"",
            f"**Statement:** {self.statement}",
            f"",
            f"$$\n{self.latex_formula}\n$$",
            f"",
            f"**Proof Summary:**",
            f"- **Verdict:** `{cert.verdict.value}`",
            f"- **Hegelian Consensus:** $r = {cert.hegelian_consensus_order:.4f}$",
            f"- **Dialectical Causal Gain:** $+{cert.causal_emergence_gain:.4f}$ bits",
            f"- **Minimal Causal Kernel:** {cert.minimal_causal_kernel_nodes} nodes",
            f"- **Proof Latency:** {cert.proof_duration_ms:.2f} ms",
            f"- **Hippocampal Crystallization:** `{cert.is_crystallized}`",
            f"",
            f"**Verification Steps:**"
        ]
        for step in cert.proof_steps:
            mark = "PASS" if step.passed else "FAIL"
            lines.append(f"- **Step {step.step_index} [{step.phase_name}] [{mark}]:** {step.claim}")
        lines.append("")
        return "\n".join(lines)


class TheoremCorpus:
    """
    Central repository of mathematically proved theorems, lemma dependency DAGs,
    and refutation counter-example logs.
    """
    def __init__(self):
        self.theorems: Dict[str, TheoremRecord] = {}
        self.refutations: Dict[str, TheoremProofCertificate] = {}

    def add_proved_theorem(
        self,
        conjecture: MathematicalConjecture,
        cert: TheoremProofCertificate,
        dependencies: Optional[List[str]] = None
    ) -> TheoremRecord:
        """Registers a proved theorem into the corpus."""
        th_id = f"THM_{conjecture.conjecture_id.upper()}"
        deps = dependencies or list(conjecture.axioms_referenced)
        rec = TheoremRecord(
            theorem_id=th_id,
            conjecture_id=conjecture.conjecture_id,
            title=conjecture.title,
            statement=conjecture.statement,
            latex_formula=conjecture.latex_formula,
            domain=conjecture.domain,
            proof_certificate=cert,
            dependencies=deps
        )
        self.theorems[th_id] = rec
        return rec

    def add_refutation(
        self,
        conjecture: MathematicalConjecture,
        cert: TheoremProofCertificate
    ) -> None:
        """Records a refuted conjecture with its counter-example witness."""
        self.refutations[conjecture.conjecture_id] = cert

    def generate_mermaid_dag(self) -> str:
        """Generates a Mermaid dependency graph of axioms, lemmas, and proved theorems."""
        lines = ["flowchart TD"]
        # Axiom nodes
        axioms_used = set()
        for th in self.theorems.values():
            for dep in th.dependencies:
                axioms_used.add(dep)

        for ax in sorted(axioms_used):
            lines.append(f'    {ax}["Axiom: {ax}"]:::axiomNode')

        for th_id, th in self.theorems.items():
            lines.append(f'    {th_id}["{th.title}<br>r={th.proof_certificate.hegelian_consensus_order:.2f}, +{th.proof_certificate.causal_emergence_gain:.2f}b"]:::thmNode')
            for dep in th.dependencies:
                lines.append(f"    {dep} --> {th_id}")

        lines.append("    classDef axiomNode fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#f8fafc;")
        lines.append("    classDef thmNode fill:#0f172a,stroke:#fbbf24,stroke-width:2px,color:#fbbf24;")
        return "\n".join(lines)

    def export_corpus_markdown(self, filepath: Optional[str] = None) -> str:
        """Exports the complete formal mathematical corpus as Markdown."""
        lines = [
            "# Formal Corpus of Proven Mathematical Theorems",
            "",
            f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}  ",
            f"**Total Theorems Proved:** {len(self.theorems)}  ",
            f"**Total Conjectures Refuted:** {len(self.refutations)}  ",
            "",
            "## 1. Theorem Dependency Graph",
            "",
            "```mermaid",
            self.generate_mermaid_dag(),
            "```",
            "",
            "---",
            "",
            "## 2. Proved Theorems Catalogue",
            ""
        ]

        for th in self.theorems.values():
            lines.append(th.to_markdown())

        if self.refutations:
            lines.append("---")
            lines.append("")
            lines.append("## 3. Disproved Conjectures & Witness Certificates")
            lines.append("")
            for cid, cert in self.refutations.items():
                wit = cert.counter_example_witness
                lines.append(f"### Refuted: {cert.title} (`{cid}`)")
                lines.append(f"- **Verdict:** `{cert.verdict.value}`")
                lines.append(f"- **Hegelian Antiphase Bifurcation:** $r = {cert.hegelian_consensus_order:.4f}$")
                if wit:
                    lines.append(f"- **Counter-Example Witness:**")
                    lines.append(f"  - Input Vector: `{wit.get('input_vector')}`")
                    lines.append(f"  - Observed Output: `{wit.get('observed_output')}`")
                    lines.append(f"  - Expected Output: `{wit.get('expected_output')}`")
                lines.append("")

        doc = "\n".join(lines)
        if filepath:
            p = Path(filepath)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(doc)

        return doc
