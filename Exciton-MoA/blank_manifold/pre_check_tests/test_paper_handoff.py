# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
import sys
from pathlib import Path

from paper_handoff import (
    main,
    render_prefilled_paper_intake_handoff,
    resolve_working_mind_targets,
    write_prefilled_paper_intake_handoff,
)


def _sample_uncertainty_handoff(tmp_path: Path) -> Path:
    path = tmp_path / "sweep_uncertainty_paper_handoff.md"
    path.write_text(
        "\n".join(
            [
                "# UNCERTAINTY TO PAPER RECOMMENDATION",
                "",
                "Selected variant: variant_high",
                "Working dir: working_data/sweep/variant_high",
                "",
                "## Uncertainty summary",
                "- current bottleneck: The pair shows unresolved synchrony uncertainty under repeated blocked and contradictory local evidence.",
                "- why current repo knowledge is still insufficient: Current sweep evidence does not cleanly separate conservative gating from structural synchrony limits.",
                "- why this is stable uncertainty rather than a one-off failure: The trigger persists across gate blocks=4, near-passes=2, contradictions=2, and diagnosis=threshold_conservative_candidate.",
                "",
                "## Observed signals",
                "- key telemetry fields: phase_coherence, entangler_coherence_delta, entangler_hint_gate_reason, entangler_nudge_applied",
                "- key replay or sweep signals: coherence trend, hint gate summary, nudge outcome summary, sweep ranking",
                "- recent regimes or labels involved: borderline, narrow, threshold_conservative_candidate",
                "",
                "## Current local explanations",
                "- working hypothesis 1: The hint gate may still be conservative relative to the actual synchrony boundary in this neighborhood.",
                "- working hypothesis 2: The pair may sit in a structurally unfavorable synchronizable region even when local evidence intermittently improves.",
                "- what remains unresolved or conflicting: Current sweep evidence leaves borderline synchrony posture and narrow basin posture only partially explained by local diagnostics.",
                "",
                "## Outside help needed",
                "- intervention class: control policy",
                "- desired paper role: one paper on synchrony-margin diagnostics or conservative gating under ambiguous local evidence",
                "- preferred search envelope: one paper",
                "",
                "## Search guardrails",
                "- avoid broad literature survey: yes",
                "- novelty relative to current `working_mind`: Extend beyond the current synchrony-margin and basin-stability seeds with a tighter synchronization feasibility or controllability source.",
                "- stop condition for searching: Stop if nearby variants move the synchrony label to favorable or if local diagnostics clearly explain the blocked regime.",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _sample_recommendation_file(tmp_path: Path) -> Path:
    path = tmp_path / "paper_finder_recommendation.md"
    path.write_text(
        "\n".join(
            [
                "# PAPER FINDER RECOMMENDATION",
                "",
                "## Selected paper",
                "- stable URL: https://example.org/recommended-paper",
                "- suggested filename: recommended-paper.pdf",
                "- local file path: [UNKNOWN]",
                "- title: Recommended Paper",
                "- authors: A. Author; B. Author",
                "- year: 2025",
                "- domain tags: synchrony, control-policy",
                "- subject folder: control-policy",
                "- source status: summary-first-pdf-pending",
                "- current relevance note: Recommended because it best matches the calm-but-ambiguous blocked-gate regime.",
                "- recommendation rationale: Recommended because it stays narrow and maps directly onto the current bottleneck.",
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_render_prefilled_paper_intake_handoff_maps_uncertainty_fields(tmp_path: Path):
    handoff_path = _sample_uncertainty_handoff(tmp_path)
    working_mind_root = tmp_path / "working_mind"

    rendered = render_prefilled_paper_intake_handoff(
        uncertainty_handoff_path=handoff_path,
        source_url="https://example.org/paper.pdf",
        suggested_filename="example-paper.pdf",
        title="Example Paper",
        authors="A. Author; B. Author",
        year="2024",
        domain_tags="synchrony, control-policy",
        working_mind_root=working_mind_root,
    )

    assert "# PAPER INTAKE HANDOFF" in rendered
    assert "- stable URL: https://example.org/paper.pdf" in rendered
    assert (
        "- current engineering problem: The pair shows unresolved synchrony uncertainty under repeated blocked and contradictory local evidence."
        in rendered
    )
    assert (
        "- why current repo knowledge is not enough yet: Current sweep evidence does not cleanly separate conservative gating from structural synchrony limits."
        in rendered
    )
    assert (
        "- most actionable concept: one paper on synchrony-margin diagnostics or conservative gating under ambiguous local evidence"
        in rendered
    )
    assert (
        "- nearest telemetry fields: phase_coherence, entangler_coherence_delta, entangler_hint_gate_reason, entangler_nudge_applied"
        in rendered
    )
    assert (
        "- nearest replay or sweep signals: coherence trend, hint gate summary, nudge outcome summary, sweep ranking"
        in rendered
    )
    assert "- intervention class: control policy" in rendered
    assert "- source status: summary-first-pdf-pending" in rendered
    assert "- subject folder: control-policy" in rendered
    assert f"- working_mind root: {working_mind_root}" in rendered
    assert "- target local paper path: control-policy/example-paper.pdf" in rendered
    assert "- target summary path: control-policy/example-paper.applied-summary.md" in rendered
    assert (
        "- should this stay manual-first or be queued for future agent rediscovery: automatic bounded intake now; queue wider rediscovery only if the same uncertainty recurs and one paper is no longer enough"
        in rendered
    )
    assert "- retained recommendation rationale: [NONE PROVIDED]" in rendered


def test_render_prefilled_paper_intake_handoff_retains_recommendation_rationale(tmp_path: Path):
    handoff_path = _sample_uncertainty_handoff(tmp_path)

    rendered = render_prefilled_paper_intake_handoff(
        uncertainty_handoff_path=handoff_path,
        source_url="https://example.org/paper.pdf",
        suggested_filename="example-paper.pdf",
        recommendation_rationale="This paper best matches the blocked-gate ambiguity while staying narrower than topology-first alternatives.",
    )

    assert (
        "- retained recommendation rationale: This paper best matches the blocked-gate ambiguity while staying narrower than topology-first alternatives."
        in rendered
    )


def test_write_prefilled_paper_intake_handoff_uses_default_output_name(tmp_path: Path):
    handoff_path = _sample_uncertainty_handoff(tmp_path)

    output_path = write_prefilled_paper_intake_handoff(
        uncertainty_handoff_path=handoff_path,
        output_path=None,
        source_url="https://example.org/paper.pdf",
        suggested_filename="example-paper.pdf",
    )

    assert output_path.name == "approved_paper_intake_handoff.md"
    assert output_path.exists()
    assert "# PAPER INTAKE HANDOFF" in output_path.read_text(encoding="utf-8")


def test_resolve_working_mind_targets_prefers_tag_driven_subject_folder(tmp_path: Path):
    targets = resolve_working_mind_targets(
        working_mind_root=tmp_path / "working_mind",
        suggested_filename="nphys2516.pdf",
        intervention_class="diagnostics",
        domain_tags="basin stability, nonlinear stability",
        source_url="https://example.org/nphys2516",
    )

    assert targets["subject_folder"] == "basin-stability"
    assert targets["local_file"] == "basin-stability/nphys2516.pdf"
    assert targets["summary_file"] == "basin-stability/nphys2516.applied-summary.md"
    assert targets["source_status"] == "summary-first-pdf-pending"


def test_resolve_working_mind_targets_preserves_pdf_present_status(tmp_path: Path):
    targets = resolve_working_mind_targets(
        working_mind_root=tmp_path / "working_mind",
        suggested_filename="PhysRevLett.80.2109.pdf",
        intervention_class="diagnostics",
        domain_tags="synchronization, network dynamics",
        local_file_path="working_mind/synchronization/PhysRevLett.80.2109.pdf",
    )

    assert targets["subject_folder"] == "synchronization"
    assert targets["source_status"] == "pdf-present"


def test_paper_handoff_cli_writes_prefilled_intake(tmp_path: Path, monkeypatch, capsys):
    handoff_path = _sample_uncertainty_handoff(tmp_path)
    output_path = tmp_path / "custom_intake.md"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "paper_handoff.py",
            "--uncertainty-handoff",
            str(handoff_path),
            "--output-path",
            str(output_path),
            "--source-url",
            "https://example.org/paper.pdf",
            "--suggested-filename",
            "example-paper.pdf",
            "--title",
            "Example Paper",
            "--subject-folder",
            "synchronization",
            "--recommendation-rationale",
            "Recommended because it directly addresses synchrony-margin ambiguity under conservative gating.",
        ],
    )

    main()
    captured = capsys.readouterr().out

    assert "Wrote prefilled paper-intake handoff to" in captured
    assert output_path.exists()
    assert "- title: Example Paper" in output_path.read_text(encoding="utf-8")
    assert "- subject folder: synchronization" in output_path.read_text(encoding="utf-8")
    assert (
        "- retained recommendation rationale: Recommended because it directly addresses synchrony-margin ambiguity under conservative gating."
        in output_path.read_text(encoding="utf-8")
    )


def test_paper_handoff_cli_auto_ingests_working_mind_artifacts(tmp_path: Path, monkeypatch, capsys):
    handoff_path = _sample_uncertainty_handoff(tmp_path)
    output_path = tmp_path / "custom_intake.md"
    working_mind_root = tmp_path / "working_mind"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "paper_handoff.py",
            "--uncertainty-handoff",
            str(handoff_path),
            "--output-path",
            str(output_path),
            "--source-url",
            "https://example.org/paper.pdf",
            "--suggested-filename",
            "example-paper.pdf",
            "--title",
            "Example Paper",
            "--subject-folder",
            "synchronization",
            "--working-mind-root",
            str(working_mind_root),
            "--ingested-on",
            "2026-03-12",
            "--auto-ingest",
        ],
    )

    main()
    captured = capsys.readouterr().out

    assert "Updated papers index at" in captured
    assert (working_mind_root / "papers-index.md").exists()
    assert (working_mind_root / "synchronization" / "example-paper.applied-summary.md").exists()


def test_paper_handoff_cli_uses_recommendation_file_for_direct_ingest(tmp_path: Path, monkeypatch, capsys):
    handoff_path = _sample_uncertainty_handoff(tmp_path)
    recommendation_path = _sample_recommendation_file(tmp_path)
    output_path = tmp_path / "custom_intake.md"
    working_mind_root = tmp_path / "working_mind"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "paper_handoff.py",
            "--uncertainty-handoff",
            str(handoff_path),
            "--recommendation-file",
            str(recommendation_path),
            "--output-path",
            str(output_path),
            "--working-mind-root",
            str(working_mind_root),
            "--ingested-on",
            "2026-03-12",
            "--auto-ingest",
        ],
    )

    main()
    captured = capsys.readouterr().out

    index_text = (working_mind_root / "papers-index.md").read_text(encoding="utf-8")
    assert "Updated papers index at" in captured
    assert "### control-policy/recommended-paper.pdf" in index_text
    assert "- title: Recommended Paper" in output_path.read_text(encoding="utf-8")
    assert (working_mind_root / "control-policy" / "recommended-paper.applied-summary.md").exists()
