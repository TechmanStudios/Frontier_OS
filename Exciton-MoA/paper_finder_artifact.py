# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
from __future__ import annotations

import argparse
from pathlib import Path

from paper_handoff import derive_source_status, load_markdown_bullets_by_section, resolve_subject_folder

DEFAULT_RECOMMENDATION_FILENAME = "paper_finder_recommendation.md"


def parse_uncertainty_handoff_context(path: Path) -> dict[str, str]:
    text = Path(path).read_text(encoding="utf-8")
    sections = load_markdown_bullets_by_section(Path(path))
    uncertainty = sections.get("Uncertainty summary", {})
    outside = sections.get("Outside help needed", {})
    context: dict[str, str] = {
        "selected_variant": "[UNKNOWN]",
        "working_dir": "[UNKNOWN]",
        "current_bottleneck": str(uncertainty.get("current bottleneck", "[TO_FILL]")),
        "intervention_class": str(outside.get("intervention class", "diagnostics")),
        "desired_paper_role": str(outside.get("desired paper role", "one paper")),
    }
    for raw_line in text.splitlines():
        if raw_line.startswith("Selected variant:"):
            context["selected_variant"] = raw_line.split(":", 1)[1].strip() or "[UNKNOWN]"
        elif raw_line.startswith("Working dir:"):
            context["working_dir"] = raw_line.split(":", 1)[1].strip() or "[UNKNOWN]"
    return context


def resolve_recommendation_output_path(
    *,
    uncertainty_handoff_path: Path,
    output_path: Path | None = None,
) -> Path:
    if output_path is not None:
        return Path(output_path)
    return Path(uncertainty_handoff_path).with_name(DEFAULT_RECOMMENDATION_FILENAME)


def render_paper_finder_recommendation(
    *,
    uncertainty_handoff_path: Path,
    source_url: str = "",
    suggested_filename: str = "",
    local_file_path: str = "[UNKNOWN]",
    title: str = "[TO_FILL]",
    authors: str = "[TO_FILL]",
    year: str = "[TO_FILL]",
    domain_tags: str = "[TO_FILL]",
    subject_folder: str | None = None,
    source_status: str | None = None,
    current_relevance_note: str | None = None,
    recommendation_rationale: str = "[TO_FILL]",
) -> str:
    context = parse_uncertainty_handoff_context(Path(uncertainty_handoff_path))
    resolved_subject_folder = resolve_subject_folder(
        intervention_class=context["intervention_class"],
        domain_tags=domain_tags,
        subject_folder=subject_folder,
    )
    resolved_source_status = derive_source_status(
        source_url=source_url,
        local_file_path=local_file_path,
        source_status=source_status,
    )
    relevance_note = current_relevance_note or context["current_bottleneck"]
    return "\n".join(
        [
            "# PAPER FINDER RECOMMENDATION",
            "",
            "## Recommendation context",
            f"- source uncertainty handoff: {Path(uncertainty_handoff_path)}",
            f"- selected variant: {context['selected_variant']}",
            f"- working dir: {context['working_dir']}",
            f"- intervention class: {context['intervention_class']}",
            f"- desired paper role: {context['desired_paper_role']}",
            "- preferred search envelope: one paper",
            "",
            "## Selected paper",
            f"- stable URL: {source_url}",
            f"- suggested filename: {suggested_filename}",
            f"- local file path: {local_file_path}",
            f"- title: {title}",
            f"- authors: {authors}",
            f"- year: {year}",
            f"- domain tags: {domain_tags}",
            f"- subject folder: {resolved_subject_folder}",
            f"- source status: {resolved_source_status}",
            f"- current relevance note: {relevance_note}",
            f"- recommendation rationale: {recommendation_rationale}",
        ]
    )


def write_paper_finder_recommendation(
    *,
    uncertainty_handoff_path: Path,
    output_path: Path | None = None,
    source_url: str = "",
    suggested_filename: str = "",
    local_file_path: str = "[UNKNOWN]",
    title: str = "[TO_FILL]",
    authors: str = "[TO_FILL]",
    year: str = "[TO_FILL]",
    domain_tags: str = "[TO_FILL]",
    subject_folder: str | None = None,
    source_status: str | None = None,
    current_relevance_note: str | None = None,
    recommendation_rationale: str = "[TO_FILL]",
) -> Path:
    resolved_output = resolve_recommendation_output_path(
        uncertainty_handoff_path=uncertainty_handoff_path,
        output_path=output_path,
    )
    rendered = render_paper_finder_recommendation(
        uncertainty_handoff_path=uncertainty_handoff_path,
        source_url=source_url,
        suggested_filename=suggested_filename,
        local_file_path=local_file_path,
        title=title,
        authors=authors,
        year=year,
        domain_tags=domain_tags,
        subject_folder=subject_folder,
        source_status=source_status,
        current_relevance_note=current_relevance_note,
        recommendation_rationale=recommendation_rationale,
    )
    resolved_output.write_text(rendered + "\n", encoding="utf-8")
    return resolved_output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write a bounded paper finder recommendation artifact next to a sweep uncertainty handoff."
    )
    parser.add_argument(
        "--uncertainty-handoff", type=Path, required=True, help="Path to sweep_uncertainty_paper_handoff.md."
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=None,
        help="Optional output path for paper_finder_recommendation.md.",
    )
    parser.add_argument("--source-url", default="", help="Recommended paper source URL.")
    parser.add_argument(
        "--suggested-filename", default="", help="Suggested local filename for the recommended paper."
    )
    parser.add_argument(
        "--local-file-path", default="[UNKNOWN]", help="Local file path if the paper is already downloaded."
    )
    parser.add_argument("--title", default="[TO_FILL]", help="Recommended paper title.")
    parser.add_argument("--authors", default="[TO_FILL]", help="Recommended paper authors.")
    parser.add_argument("--year", default="[TO_FILL]", help="Recommended paper year.")
    parser.add_argument("--domain-tags", default="[TO_FILL]", help="Domain tags for the recommended paper.")
    parser.add_argument("--subject-folder", default=None, help="Optional canonical subject folder override.")
    parser.add_argument("--source-status", default=None, help="Optional source status override.")
    parser.add_argument("--current-relevance-note", default=None, help="Optional relevance note override.")
    parser.add_argument(
        "--recommendation-rationale", default="[TO_FILL]", help="Recommendation rationale text."
    )
    args = parser.parse_args()

    output_path = write_paper_finder_recommendation(
        uncertainty_handoff_path=args.uncertainty_handoff,
        output_path=args.output_path,
        source_url=str(args.source_url),
        suggested_filename=str(args.suggested_filename),
        local_file_path=str(args.local_file_path),
        title=str(args.title),
        authors=str(args.authors),
        year=str(args.year),
        domain_tags=str(args.domain_tags),
        subject_folder=args.subject_folder,
        source_status=args.source_status,
        current_relevance_note=args.current_relevance_note,
        recommendation_rationale=str(args.recommendation_rationale),
    )
    print(f"Wrote paper finder recommendation to {output_path}")


if __name__ == "__main__":
    main()
