# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
import sys
from pathlib import Path

from paper_finder_artifact import main, write_paper_finder_recommendation


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
                "",
                "## Outside help needed",
                "- intervention class: control policy",
                "- desired paper role: one paper on synchrony-margin diagnostics or conservative gating under ambiguous local evidence",
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_write_paper_finder_recommendation_defaults_to_sweep_dir(tmp_path: Path):
    handoff_path = _sample_uncertainty_handoff(tmp_path)

    output_path = write_paper_finder_recommendation(
        uncertainty_handoff_path=handoff_path,
        source_url="https://example.org/recommended-paper",
        suggested_filename="recommended-paper.pdf",
        title="Recommended Paper",
        authors="A. Author",
        year="2026",
        domain_tags="synchrony, control-policy",
        recommendation_rationale="Recommended because it directly matches the blocked-gate ambiguity.",
    )

    text = output_path.read_text(encoding="utf-8")
    assert output_path.name == "paper_finder_recommendation.md"
    assert "- source uncertainty handoff:" in text
    assert "- selected variant: variant_high" in text
    assert "- subject folder: control-policy" in text
    assert "- stable URL: https://example.org/recommended-paper" in text


def test_paper_finder_artifact_cli_writes_stub_into_sweep_dir(tmp_path: Path, monkeypatch, capsys):
    handoff_path = _sample_uncertainty_handoff(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "paper_finder_artifact.py",
            "--uncertainty-handoff",
            str(handoff_path),
        ],
    )

    main()
    captured = capsys.readouterr().out
    output_path = tmp_path / "paper_finder_recommendation.md"
    text = output_path.read_text(encoding="utf-8")

    assert "Wrote paper finder recommendation to" in captured
    assert output_path.exists()
    assert "# PAPER FINDER RECOMMENDATION" in text
    assert "- subject folder: control-policy" in text
    assert "- source status: metadata-only" in text