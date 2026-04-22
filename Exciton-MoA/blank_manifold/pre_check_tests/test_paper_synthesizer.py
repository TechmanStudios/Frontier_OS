# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
from pathlib import Path

from paper_handoff import write_prefilled_paper_intake_handoff
from paper_synthesizer import ingest_paper_intake_handoff


def _sample_uncertainty_handoff(tmp_path: Path) -> Path:
    path = tmp_path / "sweep_uncertainty_paper_handoff.md"
    path.write_text(
        "\n".join(
            [
                "# UNCERTAINTY TO PAPER RECOMMENDATION",
                "",
                "## Uncertainty summary",
                "- current bottleneck: The pair stays calm but unresolved, and the current replay evidence cannot separate conservative gating from a structurally weak synchrony region.",
                "- why current repo knowledge is still insufficient: The repo still lacks one narrow outside source that maps synchrony feasibility onto the present telemetry and sweep signals.",
                "- why this is stable uncertainty rather than a one-off failure: The same borderline pattern persists across repeated sweeps without natural entry.",
                "",
                "## Observed signals",
                "- key telemetry fields: phase_coherence, entangler_coherence_delta, shared_flux_norm",
                "- key replay or sweep signals: ranked sweep posture, near-pass maturity, blocked observe reasons",
                "",
                "## Current local explanations",
                "- working hypothesis 1: The gate is still conservative relative to the best local synchrony pocket.",
                "- working hypothesis 2: The pair may remain globally fragile even when local behavior looks calm.",
                "- what remains unresolved or conflicting: Current runs do not separate policy conservatism from structural synchrony weakness.",
                "",
                "## Outside help needed",
                "- intervention class: control policy",
                "- desired paper role: one narrow paper on synchronization feasibility under ambiguous local evidence",
                "",
                "## Search guardrails",
                "- novelty relative to current `working_mind`: Add a tighter control-policy framing than the current seed papers.",
                "- stop condition for searching: stop if the synchrony pocket becomes well explained by local metrics alone.",
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_ingest_paper_intake_handoff_writes_index_and_summary(tmp_path: Path):
    working_mind_root = tmp_path / "working_mind"
    handoff_path = write_prefilled_paper_intake_handoff(
        uncertainty_handoff_path=_sample_uncertainty_handoff(tmp_path),
        output_path=tmp_path / "approved_paper_intake_handoff.md",
        source_url="https://example.org/control-paper",
        suggested_filename="control-paper.pdf",
        title="Control Paper",
        authors="A. Author",
        year="2026",
        domain_tags="synchrony, control-policy",
        recommendation_rationale="Recommended because it stays narrow and maps directly onto blocked-gate ambiguity.",
        working_mind_root=working_mind_root,
    )

    outputs = ingest_paper_intake_handoff(
        intake_handoff_path=handoff_path,
        working_mind_root=working_mind_root,
        ingested_on="2026-03-12",
    )

    index_text = (working_mind_root / "papers-index.md").read_text(encoding="utf-8")
    summary_text = (working_mind_root / "control-policy" / "control-paper.applied-summary.md").read_text(encoding="utf-8")

    assert outputs["source_status"] == "summary-first-pdf-pending"
    assert "### control-policy/control-paper.pdf" in index_text
    assert "- Source status: summary-first-pdf-pending" in index_text
    assert "- Ingested: 2026-03-12" in index_text
    assert "# Applied Summary: control-paper" in summary_text
    assert "- Intake mode: automatic bounded intake" in summary_text
    assert "Recommended because it stays narrow and maps directly onto blocked-gate ambiguity." in summary_text
    assert "This note was generated automatically from the intake handoff." in summary_text


def test_ingest_paper_intake_handoff_stages_local_pdf_when_present(tmp_path: Path):
    working_mind_root = tmp_path / "working_mind"
    local_pdf = tmp_path / "downloads" / "control-paper.pdf"
    local_pdf.parent.mkdir(parents=True, exist_ok=True)
    local_pdf.write_bytes(b"%PDF-1.4\n")

    handoff_path = write_prefilled_paper_intake_handoff(
        uncertainty_handoff_path=_sample_uncertainty_handoff(tmp_path),
        output_path=tmp_path / "approved_paper_intake_handoff.md",
        source_url="https://example.org/control-paper",
        suggested_filename="control-paper.pdf",
        local_file_path=str(local_pdf),
        title="Control Paper",
        authors="A. Author",
        year="2026",
        domain_tags="synchrony, control-policy",
        working_mind_root=working_mind_root,
    )

    outputs = ingest_paper_intake_handoff(
        intake_handoff_path=handoff_path,
        working_mind_root=working_mind_root,
        ingested_on="2026-03-12",
    )

    target_pdf = working_mind_root / "control-policy" / "control-paper.pdf"
    index_text = (working_mind_root / "papers-index.md").read_text(encoding="utf-8")

    assert outputs["source_status"] == "pdf-present"
    assert target_pdf.exists()
    assert "- Source status: pdf-present" in index_text


def test_ingest_paper_intake_handoff_is_idempotent(tmp_path: Path):
    working_mind_root = tmp_path / "working_mind"
    handoff_path = write_prefilled_paper_intake_handoff(
        uncertainty_handoff_path=_sample_uncertainty_handoff(tmp_path),
        output_path=tmp_path / "approved_paper_intake_handoff.md",
        source_url="https://example.org/control-paper",
        suggested_filename="control-paper.pdf",
        title="Control Paper",
        authors="A. Author",
        year="2026",
        domain_tags="synchrony, control-policy",
        working_mind_root=working_mind_root,
    )

    ingest_paper_intake_handoff(
        intake_handoff_path=handoff_path,
        working_mind_root=working_mind_root,
        ingested_on="2026-03-12",
    )
    ingest_paper_intake_handoff(
        intake_handoff_path=handoff_path,
        working_mind_root=working_mind_root,
        ingested_on="2026-03-12",
    )

    index_text = (working_mind_root / "papers-index.md").read_text(encoding="utf-8")
    assert index_text.count("### control-policy/control-paper.pdf") == 1


def test_ingest_updates_learning_ledger_after_repeated_subject_folder_intakes(tmp_path: Path):
    working_mind_root = tmp_path / "working_mind"
    first_handoff = write_prefilled_paper_intake_handoff(
        uncertainty_handoff_path=_sample_uncertainty_handoff(tmp_path),
        output_path=tmp_path / "approved_paper_intake_handoff_a.md",
        source_url="https://example.org/control-paper-a",
        suggested_filename="control-paper-a.pdf",
        title="Control Paper A",
        authors="A. Author",
        year="2026",
        domain_tags="synchrony, control-policy",
        working_mind_root=working_mind_root,
    )
    second_handoff = write_prefilled_paper_intake_handoff(
        uncertainty_handoff_path=_sample_uncertainty_handoff(tmp_path),
        output_path=tmp_path / "approved_paper_intake_handoff_b.md",
        source_url="https://example.org/control-paper-b",
        suggested_filename="control-paper-b.pdf",
        title="Control Paper B",
        authors="B. Author",
        year="2026",
        domain_tags="synchrony, control-policy",
        working_mind_root=working_mind_root,
    )

    ingest_paper_intake_handoff(
        intake_handoff_path=first_handoff,
        working_mind_root=working_mind_root,
        ingested_on="2026-03-12",
    )
    outputs = ingest_paper_intake_handoff(
        intake_handoff_path=second_handoff,
        working_mind_root=working_mind_root,
        ingested_on="2026-03-12",
    )

    ledger_text = Path(outputs["learning_ledger"]).read_text(encoding="utf-8")
    knowledge_note_path = working_mind_root / "knowledge_notes" / "control-policy.knowledge-note.md"
    repo_memory_promotion_path = working_mind_root / "repo-memory-promotions.md"
    assert "## control-policy" in ledger_text
    assert "- Evidence count: 2" in ledger_text
    assert "- Promotion status: candidate knowledge note" in ledger_text
    assert "- Knowledge note: knowledge_notes/control-policy.knowledge-note.md" in ledger_text
    assert "- Repo memory status: ready-to-mirror" in ledger_text
    assert "- Paper 1: control-policy/control-paper-a.pdf" in ledger_text
    assert "- Paper 2: control-policy/control-paper-b.pdf" in ledger_text
    assert outputs["knowledge_note_path"] == str(knowledge_note_path)
    assert outputs["repo_memory_promotion"] == str(repo_memory_promotion_path)
    assert knowledge_note_path.exists()
    assert repo_memory_promotion_path.exists()
    knowledge_note_text = knowledge_note_path.read_text(encoding="utf-8")
    repo_memory_text = repo_memory_promotion_path.read_text(encoding="utf-8")
    assert "# Frontier Knowledge Note: Control Policy" in knowledge_note_text
    assert "- Paper 1: control-policy/control-paper-a.pdf" in knowledge_note_text
    assert "- Paper 2: control-policy/control-paper-b.pdf" in knowledge_note_text
    assert "## control-policy" in repo_memory_text
    assert "- Status: ready for repo memory mirror" in repo_memory_text