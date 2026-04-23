# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
from __future__ import annotations

import argparse
from pathlib import Path

from paper_synthesizer import ingest_paper_intake_handoff

DEFAULT_WORKING_MIND_ROOT = Path(__file__).resolve().parent / "working_mind"
DEFAULT_SUBJECT_FOLDER = "synchronization"


def slugify_folder_name(value: str) -> str:
    normalized = "-".join(str(value or "").strip().lower().replace("/", " ").split())
    return normalized or DEFAULT_SUBJECT_FOLDER


def parse_domain_tags(domain_tags: str) -> list[str]:
    return [tag.strip().lower() for tag in str(domain_tags or "").split(",") if tag.strip()]


def resolve_subject_folder(
    *, intervention_class: str, domain_tags: str, subject_folder: str | None = None
) -> str:
    if subject_folder:
        return slugify_folder_name(subject_folder)

    normalized_intervention = str(intervention_class or "diagnostics").strip().lower()
    if normalized_intervention == "topology design":
        return "topology-design"
    if normalized_intervention == "control policy":
        return "control-policy"
    if normalized_intervention == "experiment design":
        return "experiment-design"

    tags = parse_domain_tags(domain_tags)
    if any("basin" in tag or "fragility" in tag for tag in tags):
        return "basin-stability"
    if any("topology" in tag for tag in tags):
        return "topology-design"
    if any("control" in tag for tag in tags):
        return "control-policy"
    return DEFAULT_SUBJECT_FOLDER


def derive_source_status(*, source_url: str, local_file_path: str, source_status: str | None = None) -> str:
    if source_status:
        return str(source_status).strip()
    local_value = str(local_file_path or "").strip()
    if local_value and local_value != "[UNKNOWN]":
        return "pdf-present"
    if str(source_url or "").strip():
        return "summary-first-pdf-pending"
    return "metadata-only"


def build_summary_filename(suggested_filename: str) -> str:
    return f"{Path(suggested_filename).stem.lower()}.applied-summary.md"


def to_posix_path(path: Path) -> str:
    return path.as_posix()


def resolve_working_mind_targets(
    *,
    working_mind_root: Path,
    suggested_filename: str,
    intervention_class: str,
    domain_tags: str,
    source_url: str = "",
    local_file_path: str = "[UNKNOWN]",
    subject_folder: str | None = None,
    source_status: str | None = None,
) -> dict[str, str]:
    folder_name = resolve_subject_folder(
        intervention_class=intervention_class,
        domain_tags=domain_tags,
        subject_folder=subject_folder,
    )
    resolved_source_status = derive_source_status(
        source_url=source_url,
        local_file_path=local_file_path,
        source_status=source_status,
    )
    local_filename = Path(suggested_filename).name
    summary_filename = build_summary_filename(local_filename)
    subject_root = Path(working_mind_root) / folder_name
    return {
        "working_mind_root": str(Path(working_mind_root)),
        "subject_folder": folder_name,
        "local_file": to_posix_path(Path(folder_name) / local_filename),
        "summary_file": to_posix_path(Path(folder_name) / summary_filename),
        "source_status": resolved_source_status,
        "subject_root": to_posix_path(subject_root),
    }


def load_markdown_bullets_by_section(path: Path) -> dict[str, dict[str, str]]:
    sections: dict[str, dict[str, str]] = {}
    current_section: str | None = None
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("## "):
            current_section = line[3:].strip()
            sections.setdefault(current_section, {})
            continue
        if current_section is None or not line.startswith("- ") or ":" not in line:
            continue
        key, value = line[2:].split(":", 1)
        sections[current_section][key.strip()] = value.strip()
    return sections


def parse_paper_recommendation(path: Path) -> dict[str, str]:
    sections = load_markdown_bullets_by_section(Path(path))
    recommendation = sections.get("Selected paper", {})
    return {
        "source_url": str(recommendation.get("stable URL", "")).strip(),
        "suggested_filename": str(recommendation.get("suggested filename", "")).strip(),
        "local_file_path": str(recommendation.get("local file path", "[UNKNOWN]")).strip(),
        "title": str(recommendation.get("title", "[TO_FILL]")).strip(),
        "authors": str(recommendation.get("authors", "[TO_FILL]")).strip(),
        "year": str(recommendation.get("year", "[TO_FILL]")).strip(),
        "domain_tags": str(recommendation.get("domain tags", "[TO_FILL]")).strip(),
        "subject_folder": str(recommendation.get("subject folder", "")).strip() or None,
        "source_status": str(recommendation.get("source status", "")).strip() or None,
        "current_relevance_note": str(recommendation.get("current relevance note", "")).strip() or None,
        "recommendation_rationale": str(
            recommendation.get("recommendation rationale", "[NONE PROVIDED]")
        ).strip(),
    }


def suggest_sol_concepts(intervention_class: str) -> list[str]:
    normalized = str(intervention_class or "diagnostics").strip().lower()
    if normalized in {"control policy", "topology design", "diagnostics"}:
        return [
            "HippocampalReplay",
            "Entangler Giant",
            "hint gate",
            "bounded nudges",
            "pair sweep diagnostics",
        ]
    return [
        "HippocampalReplay",
        "EntangledSOLPair",
        "pair sweep diagnostics",
        "working_mind translation layer",
        "stabilization paper bridge",
    ]


def render_prefilled_paper_intake_handoff(
    *,
    uncertainty_handoff_path: Path,
    source_url: str,
    suggested_filename: str,
    local_file_path: str = "[UNKNOWN]",
    title: str = "[TO_FILL]",
    authors: str = "[TO_FILL]",
    year: str = "[TO_FILL]",
    domain_tags: str = "[TO_FILL]",
    subject_folder: str | None = None,
    source_status: str | None = None,
    current_relevance_note: str | None = None,
    nearest_sol_concepts: str | None = None,
    recommendation_rationale: str | None = None,
    working_mind_root: Path = DEFAULT_WORKING_MIND_ROOT,
) -> str:
    sections = load_markdown_bullets_by_section(Path(uncertainty_handoff_path))
    uncertainty = sections.get("Uncertainty summary", {})
    observed = sections.get("Observed signals", {})
    local = sections.get("Current local explanations", {})
    outside = sections.get("Outside help needed", {})
    guardrails = sections.get("Search guardrails", {})

    current_problem = uncertainty.get("current bottleneck", "[TO_FILL]")
    repo_gap = uncertainty.get("why current repo knowledge is still insufficient", "[TO_FILL]")
    stable_uncertainty = uncertainty.get(
        "why this is stable uncertainty rather than a one-off failure", "[TO_FILL]"
    )
    telemetry_fields = observed.get("key telemetry fields", "[TO_FILL]")
    replay_signals = observed.get("key replay or sweep signals", "[TO_FILL]")
    desired_paper_role = outside.get("desired paper role", "[TO_FILL]")
    intervention_class = outside.get("intervention class", "diagnostics")
    novelty_summary = guardrails.get("novelty relative to current `working_mind`", "[TO_FILL]")
    stop_condition = guardrails.get("stop condition for searching", "[TO_FILL]")
    hypothesis_1 = local.get("working hypothesis 1", "[TO_FILL]")
    hypothesis_2 = local.get("working hypothesis 2", "[TO_FILL]")
    unresolved = local.get("what remains unresolved or conflicting", "[TO_FILL]")
    relevance_note = current_relevance_note or current_problem
    sol_concepts = nearest_sol_concepts or ", ".join(suggest_sol_concepts(intervention_class))
    rationale_text = recommendation_rationale or "[NONE PROVIDED]"
    targets = resolve_working_mind_targets(
        working_mind_root=working_mind_root,
        suggested_filename=suggested_filename,
        intervention_class=intervention_class,
        domain_tags=domain_tags,
        source_url=source_url,
        local_file_path=local_file_path,
        subject_folder=subject_folder,
        source_status=derive_source_status(
            source_url=source_url,
            local_file_path=local_file_path,
            source_status=source_status,
        ),
    )

    return "\n".join(
        [
            "# PAPER INTAKE HANDOFF",
            "",
            "## Source",
            f"- stable URL: {source_url}",
            f"- local file path: {local_file_path}",
            f"- suggested filename: {suggested_filename}",
            f"- source status: {targets['source_status']}",
            "",
            "## Bottleneck",
            f"- current engineering problem: {current_problem}",
            f"- why current repo knowledge is not enough yet: {repo_gap}",
            "",
            "## Required metadata",
            f"- title: {title}",
            f"- authors: {authors}",
            f"- year: {year}",
            f"- domain tags: {domain_tags}",
            f"- subject folder: {targets['subject_folder']}",
            f"- current relevance note: {relevance_note}",
            "",
            "## Applied summary target",
            f"- why this matters now: {current_problem}",
            f"- most actionable concept: {desired_paper_role}",
            f"- what in the current codebase or workflow it should influence next: {intervention_class} decisions around {replay_signals}",
            "",
            "## Translation map",
            f"- nearest telemetry fields: {telemetry_fields}",
            f"- nearest replay or sweep signals: {replay_signals}",
            f"- nearest SOL concepts or subsystem names: {sol_concepts}",
            f"- intervention class: {intervention_class}",
            "",
            "## Output targets",
            f"- working_mind root: {targets['working_mind_root']}",
            f"- target local paper path: {targets['local_file']}",
            f"- target summary path: {targets['summary_file']}",
            "",
            "## Uncertainty and escalation",
            f"- uncertainty signal that would justify using this paper later: {stable_uncertainty}",
            f"- what would count as a strong outside-the-box or forward-looking use: {novelty_summary}",
            "- should this stay manual-first or be queued for future agent rediscovery: automatic bounded intake now; queue wider rediscovery only if the same uncertainty recurs and one paper is no longer enough",
            "",
            "## Expected outputs",
            "- `working_mind/papers-index.md` entry",
            "- `<paper-file-base>.applied-summary.md`",
            "- optional follow-on design note if the translation is already concrete",
            "",
            "## Prefill provenance",
            f"- source uncertainty handoff: {Path(uncertainty_handoff_path)}",
            f"- retained recommendation rationale: {rationale_text}",
            f"- retained working hypothesis 1: {hypothesis_1}",
            f"- retained working hypothesis 2: {hypothesis_2}",
            f"- retained unresolved note: {unresolved}",
            f"- retained stop condition: {stop_condition}",
        ]
    )


def write_prefilled_paper_intake_handoff(
    *,
    uncertainty_handoff_path: Path,
    output_path: Path | None,
    source_url: str,
    suggested_filename: str,
    local_file_path: str = "[UNKNOWN]",
    title: str = "[TO_FILL]",
    authors: str = "[TO_FILL]",
    year: str = "[TO_FILL]",
    domain_tags: str = "[TO_FILL]",
    subject_folder: str | None = None,
    source_status: str | None = None,
    current_relevance_note: str | None = None,
    nearest_sol_concepts: str | None = None,
    recommendation_rationale: str | None = None,
    working_mind_root: Path = DEFAULT_WORKING_MIND_ROOT,
) -> Path:
    resolved_output = (
        Path(output_path)
        if output_path is not None
        else Path(uncertainty_handoff_path).with_name("approved_paper_intake_handoff.md")
    )
    rendered = render_prefilled_paper_intake_handoff(
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
        nearest_sol_concepts=nearest_sol_concepts,
        recommendation_rationale=recommendation_rationale,
        working_mind_root=working_mind_root,
    )
    resolved_output.write_text(rendered, encoding="utf-8")
    return resolved_output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prefill a paper-intake handoff from a bounded sweep uncertainty handoff."
    )
    parser.add_argument(
        "--uncertainty-handoff",
        type=Path,
        required=True,
        help="Path to sweep_uncertainty_paper_handoff.md or a compatible bounded uncertainty handoff.",
    )
    parser.add_argument(
        "--recommendation-file",
        type=Path,
        default=None,
        help="Optional finder recommendation artifact that supplies paper metadata directly.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=None,
        help="Optional output path for the prefilled intake handoff markdown.",
    )
    parser.add_argument("--source-url", default=None, help="Approved paper source URL.")
    parser.add_argument(
        "--suggested-filename", default=None, help="Suggested local filename for the approved paper."
    )
    parser.add_argument(
        "--local-file-path", default="[UNKNOWN]", help="Local file path if the paper is already downloaded."
    )
    parser.add_argument("--title", default="[TO_FILL]", help="Approved paper title.")
    parser.add_argument("--authors", default="[TO_FILL]", help="Approved paper authors.")
    parser.add_argument("--year", default="[TO_FILL]", help="Approved paper year.")
    parser.add_argument("--domain-tags", default="[TO_FILL]", help="Domain tags for papers-index.md.")
    parser.add_argument(
        "--subject-folder", default=None, help="Optional canonical subject folder under working_mind."
    )
    parser.add_argument(
        "--source-status",
        default=None,
        help="Optional source status override: pdf-present, summary-first-pdf-pending, or metadata-only.",
    )
    parser.add_argument(
        "--current-relevance-note", default=None, help="Optional override for the current relevance note."
    )
    parser.add_argument(
        "--nearest-sol-concepts",
        default=None,
        help="Optional override for derived SOL concepts or subsystem names.",
    )
    parser.add_argument(
        "--recommendation-rationale",
        default=None,
        help="Optional rationale text from the accepted paper recommendation.",
    )
    parser.add_argument(
        "--working-mind-root",
        type=Path,
        default=DEFAULT_WORKING_MIND_ROOT,
        help="Root directory for working_mind path resolution.",
    )
    parser.add_argument(
        "--auto-ingest",
        action="store_true",
        help="Immediately write working_mind artifacts after generating the prefilled intake handoff.",
    )
    parser.add_argument(
        "--ingested-on",
        default=None,
        help="Optional ingestion date override for auto-ingest in YYYY-MM-DD form.",
    )
    args = parser.parse_args()

    recommendation = (
        parse_paper_recommendation(args.recommendation_file) if args.recommendation_file is not None else {}
    )
    source_url = str(args.source_url or recommendation.get("source_url") or "").strip()
    suggested_filename = str(
        args.suggested_filename or recommendation.get("suggested_filename") or ""
    ).strip()
    if not source_url or not suggested_filename:
        raise SystemExit(
            "source-url and suggested-filename are required unless recommendation-file supplies them"
        )

    output_path = write_prefilled_paper_intake_handoff(
        uncertainty_handoff_path=args.uncertainty_handoff,
        output_path=args.output_path,
        source_url=source_url,
        suggested_filename=suggested_filename,
        local_file_path=str(
            args.local_file_path
            if args.local_file_path != "[UNKNOWN]"
            else recommendation.get("local_file_path", "[UNKNOWN]")
        ),
        title=str(args.title if args.title != "[TO_FILL]" else recommendation.get("title", "[TO_FILL]")),
        authors=str(
            args.authors if args.authors != "[TO_FILL]" else recommendation.get("authors", "[TO_FILL]")
        ),
        year=str(args.year if args.year != "[TO_FILL]" else recommendation.get("year", "[TO_FILL]")),
        domain_tags=str(
            args.domain_tags
            if args.domain_tags != "[TO_FILL]"
            else recommendation.get("domain_tags", "[TO_FILL]")
        ),
        subject_folder=args.subject_folder or recommendation.get("subject_folder"),
        source_status=args.source_status or recommendation.get("source_status"),
        current_relevance_note=args.current_relevance_note or recommendation.get("current_relevance_note"),
        nearest_sol_concepts=args.nearest_sol_concepts,
        recommendation_rationale=args.recommendation_rationale
        or recommendation.get("recommendation_rationale"),
        working_mind_root=args.working_mind_root,
    )
    print(f"Wrote prefilled paper-intake handoff to {output_path}")
    if args.auto_ingest:
        outputs = ingest_paper_intake_handoff(
            intake_handoff_path=output_path,
            working_mind_root=args.working_mind_root,
            ingested_on=args.ingested_on,
        )
        print(f"Updated papers index at {outputs['papers_index']}")
        print(f"Wrote applied summary to {outputs['summary_path']}")
        print(f"Resolved local paper path to {outputs['local_paper_path']}")
        print(f"Source status: {outputs['source_status']}")
        print(f"Updated learning ledger at {outputs['learning_ledger']}")
        if outputs["knowledge_note_path"]:
            print(f"Updated knowledge note at {outputs['knowledge_note_path']}")
        if outputs["repo_memory_promotion"]:
            print(f"Updated repo memory promotion at {outputs['repo_memory_promotion']}")


if __name__ == "__main__":
    main()
