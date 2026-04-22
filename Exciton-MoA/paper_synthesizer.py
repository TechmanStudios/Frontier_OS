# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, Optional


DEFAULT_WORKING_MIND_ROOT = Path(__file__).resolve().parent / "working_mind"
DEFAULT_LEARNING_LEDGER = DEFAULT_WORKING_MIND_ROOT / "frontier-learning-ledger.md"
DEFAULT_KNOWLEDGE_NOTES_DIR = "knowledge_notes"
DEFAULT_REPO_MEMORY_PROMOTIONS = DEFAULT_WORKING_MIND_ROOT / "repo-memory-promotions.md"
KNOWLEDGE_NOTE_THRESHOLD = 2


def load_markdown_bullets_by_section(path: Path) -> Dict[str, Dict[str, str]]:
    sections: Dict[str, Dict[str, str]] = {}
    current_section: Optional[str] = None
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


def clean_value(value: str) -> str:
    return str(value or "").strip().strip("`")


def to_posix_string(path: Path) -> str:
    return path.as_posix()


def resolve_repo_relative_source(path_text: str, *, working_mind_root: Path) -> Optional[Path]:
    normalized = clean_value(path_text)
    if not normalized or normalized == "[UNKNOWN]":
        return None

    source_path = Path(normalized)
    if source_path.is_absolute():
        return source_path
    return (Path(working_mind_root).parent / source_path).resolve()


@dataclass(frozen=True)
class IntakePayload:
    source_url: str
    local_file_path: str
    suggested_filename: str
    source_status: str
    current_engineering_problem: str
    repo_gap: str
    title: str
    authors: str
    year: str
    domain_tags: str
    subject_folder: str
    current_relevance_note: str
    why_this_matters_now: str
    actionable_concept: str
    next_influence_target: str
    telemetry_fields: str
    replay_signals: str
    sol_concepts: str
    intervention_class: str
    uncertainty_signal: str
    forward_use_signal: str
    rediscovery_policy: str
    working_mind_root: str
    target_local_paper_path: str
    target_summary_path: str
    trigger_artifact: str
    recommendation_rationale: str
    working_hypothesis_1: str
    working_hypothesis_2: str
    unresolved_note: str
    stop_condition: str


def parse_paper_intake_handoff(path: Path) -> IntakePayload:
    sections = load_markdown_bullets_by_section(path)
    source = sections.get("Source", {})
    bottleneck = sections.get("Bottleneck", {})
    metadata = sections.get("Required metadata", {})
    applied = sections.get("Applied summary target", {})
    translation = sections.get("Translation map", {})
    uncertainty = sections.get("Uncertainty and escalation", {})
    targets = sections.get("Output targets", {})
    provenance = sections.get("Prefill provenance", {})
    return IntakePayload(
        source_url=clean_value(source.get("stable URL", "")),
        local_file_path=clean_value(source.get("local file path", "[UNKNOWN]")),
        suggested_filename=clean_value(source.get("suggested filename", "[UNKNOWN]")),
        source_status=clean_value(source.get("source status", "metadata-only")),
        current_engineering_problem=clean_value(bottleneck.get("current engineering problem", "[TO_FILL]")),
        repo_gap=clean_value(bottleneck.get("why current repo knowledge is not enough yet", "[TO_FILL]")),
        title=clean_value(metadata.get("title", "[TO_FILL]")),
        authors=clean_value(metadata.get("authors", "[TO_FILL]")),
        year=clean_value(metadata.get("year", "[TO_FILL]")),
        domain_tags=clean_value(metadata.get("domain tags", "[TO_FILL]")),
        subject_folder=clean_value(metadata.get("subject folder", "synchronization")),
        current_relevance_note=clean_value(metadata.get("current relevance note", "[TO_FILL]")),
        why_this_matters_now=clean_value(applied.get("why this matters now", "[TO_FILL]")),
        actionable_concept=clean_value(applied.get("most actionable concept", "[TO_FILL]")),
        next_influence_target=clean_value(applied.get("what in the current codebase or workflow it should influence next", "[TO_FILL]")),
        telemetry_fields=clean_value(translation.get("nearest telemetry fields", "[TO_FILL]")),
        replay_signals=clean_value(translation.get("nearest replay or sweep signals", "[TO_FILL]")),
        sol_concepts=clean_value(translation.get("nearest SOL concepts or subsystem names", "[TO_FILL]")),
        intervention_class=clean_value(translation.get("intervention class", "diagnostics")),
        uncertainty_signal=clean_value(uncertainty.get("uncertainty signal that would justify using this paper later", "[TO_FILL]")),
        forward_use_signal=clean_value(uncertainty.get("what would count as a strong outside-the-box or forward-looking use", "[TO_FILL]")),
        rediscovery_policy=clean_value(uncertainty.get("should this stay manual-first or be queued for future agent rediscovery", "[TO_FILL]")),
        working_mind_root=clean_value(targets.get("working_mind root", str(DEFAULT_WORKING_MIND_ROOT))),
        target_local_paper_path=clean_value(targets.get("target local paper path", "[UNKNOWN]")),
        target_summary_path=clean_value(targets.get("target summary path", "[UNKNOWN]")),
        trigger_artifact=clean_value(provenance.get("source uncertainty handoff", "[UNKNOWN]")),
        recommendation_rationale=clean_value(provenance.get("retained recommendation rationale", "[NONE PROVIDED]")),
        working_hypothesis_1=clean_value(provenance.get("retained working hypothesis 1", "[TO_FILL]")),
        working_hypothesis_2=clean_value(provenance.get("retained working hypothesis 2", "[TO_FILL]")),
        unresolved_note=clean_value(provenance.get("retained unresolved note", "[TO_FILL]")),
        stop_condition=clean_value(provenance.get("retained stop condition", "[TO_FILL]")),
    )


def render_papers_index_entry(payload: IntakePayload, *, source_status: str, ingested_on: str) -> str:
    return "\n".join(
        [
            f"### {payload.target_local_paper_path}",
            f"- Title: {payload.title}",
            f"- Authors: {payload.authors}",
            f"- Year: {payload.year}",
            f"- Source URL: {payload.source_url}",
            f"- Subject folder: {payload.subject_folder}",
            f"- Local file: `{payload.target_local_paper_path}`",
            f"- Summary: `{payload.target_summary_path}`",
            f"- Ingested: {ingested_on}",
            f"- Domain tags: {payload.domain_tags}",
            f"- Current relevance: {payload.current_relevance_note}",
            f"- Source status: {source_status}",
            f"- Trigger artifact: {payload.trigger_artifact}",
            "- Status: active",
        ]
    )


def upsert_papers_index(index_path: Path, entry_heading: str, entry_body: str) -> None:
    if index_path.exists():
        text = index_path.read_text(encoding="utf-8")
    else:
        text = "# Working Mind Paper Index\n\n## Active papers\n"

    section_header = "## Active papers"
    if section_header not in text:
        text = text.rstrip() + f"\n\n{section_header}\n"

    marker = f"### {entry_heading}"
    if marker in text:
        start = text.index(marker)
        next_header = text.find("\n### ", start + len(marker))
        if next_header == -1:
            updated = text[:start].rstrip() + "\n\n" + entry_body.strip() + "\n"
        else:
            updated = text[:start].rstrip() + "\n\n" + entry_body.strip() + text[next_header:]
    else:
        insert_at = text.index(section_header) + len(section_header)
        updated = text[:insert_at].rstrip() + "\n\n" + entry_body.strip() + "\n" + text[insert_at:]

    index_path.write_text(updated.strip() + "\n", encoding="utf-8")


def render_applied_summary(payload: IntakePayload, *, source_status: str) -> str:
    summary_stem = Path(payload.suggested_filename).stem.lower()
    scaffold_note = (
        "This note was generated automatically from the intake handoff. It preserves the engineering bottleneck, translation map, and bounded recommendation rationale, "
        "but it does not claim paper-specific findings beyond the supplied metadata. Expand it after direct reading."
    )
    if source_status != "pdf-present":
        scaffold_note += " The local PDF is not present yet, so this is a summary-first scaffold rather than a close-read extraction."

    return "\n".join(
        [
            f"# Applied Summary: {summary_stem}",
            "",
            "## Intake status",
            "- Intake mode: automatic bounded intake",
            f"- Source status: {source_status}",
            f"- Trigger artifact: {payload.trigger_artifact}",
            f"- Recommendation rationale: {payload.recommendation_rationale}",
            "",
            "## Paper",
            f"- Title: {payload.title}",
            f"- Authors: {payload.authors}",
            f"- Year: {payload.year}",
            f"- Source: {payload.source_url}",
            f"- Local file: `{Path(payload.target_local_paper_path).name}`",
            "",
            "## Why this paper is in working_mind",
            payload.current_relevance_note,
            "",
            "## Current bottleneck",
            f"- Current engineering problem: {payload.current_engineering_problem}",
            f"- Why repo knowledge is still insufficient: {payload.repo_gap}",
            f"- Actionable concept to translate next: {payload.actionable_concept}",
            f"- Immediate influence target: {payload.next_influence_target}",
            "",
            "## Translation map",
            f"- Nearest telemetry fields: {payload.telemetry_fields}",
            f"- Nearest replay or sweep signals: {payload.replay_signals}",
            f"- Nearest SOL concepts or subsystem names: {payload.sol_concepts}",
            f"- Intervention class: {payload.intervention_class}",
            "",
            "## Uncertainty carry-forward",
            f"- Stable uncertainty signal: {payload.uncertainty_signal}",
            f"- Forward-looking use signal: {payload.forward_use_signal}",
            f"- Rediscovery policy: {payload.rediscovery_policy}",
            f"- Retained working hypothesis 1: {payload.working_hypothesis_1}",
            f"- Retained working hypothesis 2: {payload.working_hypothesis_2}",
            f"- Retained unresolved note: {payload.unresolved_note}",
            f"- Retained stop condition: {payload.stop_condition}",
            "",
            "## Writer status",
            scaffold_note,
        ]
    )


def render_learning_ledger_section(payload: IntakePayload, *, papers: list[str]) -> str:
    evidence_count = len(papers)
    promotion_status = "candidate knowledge note" if evidence_count >= KNOWLEDGE_NOTE_THRESHOLD else "hold in working_mind"
    knowledge_note_path = (
        f"{DEFAULT_KNOWLEDGE_NOTES_DIR}/{payload.subject_folder}.knowledge-note.md"
        if evidence_count >= KNOWLEDGE_NOTE_THRESHOLD
        else "[PENDING]"
    )
    repo_memory_status = "ready-to-mirror" if evidence_count >= KNOWLEDGE_NOTE_THRESHOLD else "not-ready"
    candidate_lesson = (
        f"Repeated `{payload.subject_folder}` ingests are converging on `{payload.actionable_concept}` for `{payload.next_influence_target}`."
    )
    lines = [
        f"## {payload.subject_folder}",
        f"- Evidence count: {evidence_count}",
        "- Promotion threshold: 2 corroborating ingests in one subject folder",
        f"- Promotion status: {promotion_status}",
        f"- Latest actionable concept: {payload.actionable_concept}",
        f"- Latest influence target: {payload.next_influence_target}",
        f"- Latest telemetry anchors: {payload.telemetry_fields}",
        f"- Current candidate lesson: {candidate_lesson}",
        f"- Knowledge note: {knowledge_note_path}",
        f"- Repo memory status: {repo_memory_status}",
    ]
    for index, paper_path in enumerate(papers, start=1):
        lines.append(f"- Paper {index}: {paper_path}")
    return "\n".join(lines)


def upsert_learning_ledger(ledger_path: Path, payload: IntakePayload) -> Dict[str, object]:
    if ledger_path.exists():
        sections = load_markdown_bullets_by_section(ledger_path)
        text = ledger_path.read_text(encoding="utf-8")
    else:
        sections = {}
        text = "# Frontier-OS Learning Ledger\n\nThis note is updated automatically from bounded `working_mind` ingests.\n\n"

    current_section = sections.get(payload.subject_folder, {})
    papers = [
        clean_value(value)
        for key, value in current_section.items()
        if key.startswith("Paper ") and clean_value(value)
    ]
    if payload.target_local_paper_path not in papers:
        papers.append(payload.target_local_paper_path)

    new_section = render_learning_ledger_section(payload, papers=papers)
    marker = f"## {payload.subject_folder}"
    if marker in text:
        start = text.index(marker)
        next_header = text.find("\n## ", start + len(marker))
        if next_header == -1:
            updated = text[:start].rstrip() + "\n\n" + new_section.strip() + "\n"
        else:
            updated = text[:start].rstrip() + "\n\n" + new_section.strip() + text[next_header:]
    else:
        updated = text.rstrip() + "\n\n" + new_section.strip() + "\n"

    ledger_path.write_text(updated.strip() + "\n", encoding="utf-8")
    evidence_count = len(papers)
    return {
        "papers": papers,
        "evidence_count": evidence_count,
        "knowledge_note_relative": (
            f"{DEFAULT_KNOWLEDGE_NOTES_DIR}/{payload.subject_folder}.knowledge-note.md"
            if evidence_count >= KNOWLEDGE_NOTE_THRESHOLD
            else ""
        ),
        "repo_memory_status": "ready-to-mirror" if evidence_count >= KNOWLEDGE_NOTE_THRESHOLD else "not-ready",
    }


def titleize_subject_folder(subject_folder: str) -> str:
    return str(subject_folder or "working-mind").replace("-", " ").title()


def render_knowledge_note(payload: IntakePayload, *, papers: list[str]) -> str:
    candidate_lesson = (
        f"Repeated `{payload.subject_folder}` ingests converge on `{payload.actionable_concept}` for `{payload.next_influence_target}`."
    )
    lines = [
        f"# Frontier Knowledge Note: {titleize_subject_folder(payload.subject_folder)}",
        "",
        "## Promotion status",
        f"- Subject folder: {payload.subject_folder}",
        f"- Evidence count: {len(papers)}",
        "- Promotion basis: repeated corroborating working_mind ingests",
        f"- Latest actionable concept: {payload.actionable_concept}",
        f"- Latest influence target: {payload.next_influence_target}",
        f"- Latest intervention class: {payload.intervention_class}",
        "",
        "## Candidate lesson",
        candidate_lesson,
        "",
        "## Translation anchors",
        f"- Nearest telemetry fields: {payload.telemetry_fields}",
        f"- Nearest replay or sweep signals: {payload.replay_signals}",
        f"- Nearest SOL concepts or subsystem names: {payload.sol_concepts}",
        "",
        "## Source papers",
    ]
    for index, paper_path in enumerate(papers, start=1):
        lines.append(f"- Paper {index}: {paper_path}")
    lines.extend(
        [
            "",
            "## Promotion handoff",
            "- Repo memory mirror: required",
            f"- Latest trigger artifact: {payload.trigger_artifact}",
            f"- Latest recommendation rationale: {payload.recommendation_rationale}",
        ]
    )
    return "\n".join(lines)


def upsert_knowledge_note(knowledge_note_path: Path, payload: IntakePayload, *, papers: list[str]) -> None:
    knowledge_note_path.parent.mkdir(parents=True, exist_ok=True)
    knowledge_note_path.write_text(render_knowledge_note(payload, papers=papers) + "\n", encoding="utf-8")


def render_repo_memory_promotion(payload: IntakePayload, *, papers: list[str], knowledge_note_relative: str) -> str:
    memory_line = (
        f"- {payload.subject_folder} knowledge candidate: {len(papers)} corroborating working_mind ingests converge on "
        f"{payload.actionable_concept} for {payload.next_influence_target}; see {knowledge_note_relative}."
    )
    lines = [
        f"## {payload.subject_folder}",
        "- Status: ready for repo memory mirror",
        f"- Knowledge note: {knowledge_note_relative}",
        f"- Evidence count: {len(papers)}",
        f"- Memory line: {memory_line}",
    ]
    for index, paper_path in enumerate(papers, start=1):
        lines.append(f"- Paper {index}: {paper_path}")
    return "\n".join(lines)


def upsert_repo_memory_promotion(
    promotions_path: Path,
    payload: IntakePayload,
    *,
    papers: list[str],
    knowledge_note_relative: str,
) -> None:
    if promotions_path.exists():
        text = promotions_path.read_text(encoding="utf-8")
    else:
        text = (
            "# Repo Memory Promotions\n\n"
            "This file is updated automatically from promoted working_mind candidates.\n\n"
            "Mirror the `Memory line` into `/memories/repo/frontier-os-exciton-moa.md` when the corresponding knowledge note is accepted.\n"
        )

    section = render_repo_memory_promotion(
        payload,
        papers=papers,
        knowledge_note_relative=knowledge_note_relative,
    )
    marker = f"## {payload.subject_folder}"
    if marker in text:
        start = text.index(marker)
        next_header = text.find("\n## ", start + len(marker))
        if next_header == -1:
            updated = text[:start].rstrip() + "\n\n" + section.strip() + "\n"
        else:
            updated = text[:start].rstrip() + "\n\n" + section.strip() + text[next_header:]
    else:
        updated = text.rstrip() + "\n\n" + section.strip() + "\n"

    promotions_path.write_text(updated.strip() + "\n", encoding="utf-8")


def stage_local_pdf(payload: IntakePayload, *, working_mind_root: Path, stage_local_file: bool) -> str:
    target_path = Path(working_mind_root) / Path(payload.target_local_paper_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if target_path.exists():
        return "pdf-present"

    if not stage_local_file:
        return payload.source_status

    source_path = resolve_repo_relative_source(payload.local_file_path, working_mind_root=working_mind_root)
    if source_path is None or not source_path.exists():
        return payload.source_status

    if source_path.resolve() != target_path.resolve():
        shutil.copy2(source_path, target_path)
    return "pdf-present"


def ingest_paper_intake_handoff(
    *,
    intake_handoff_path: Path,
    working_mind_root: Optional[Path] = None,
    ingested_on: Optional[str] = None,
    stage_local_file: bool = True,
) -> Dict[str, str]:
    payload = parse_paper_intake_handoff(Path(intake_handoff_path))
    resolved_root = Path(working_mind_root) if working_mind_root is not None else Path(payload.working_mind_root)
    resolved_root.mkdir(parents=True, exist_ok=True)

    resolved_source_status = stage_local_pdf(
        payload,
        working_mind_root=resolved_root,
        stage_local_file=stage_local_file,
    )

    summary_path = resolved_root / Path(payload.target_summary_path)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(render_applied_summary(payload, source_status=resolved_source_status) + "\n", encoding="utf-8")

    index_path = resolved_root / "papers-index.md"
    entry_body = render_papers_index_entry(
        payload,
        source_status=resolved_source_status,
        ingested_on=ingested_on or date.today().isoformat(),
    )
    upsert_papers_index(index_path, payload.target_local_paper_path, entry_body)

    learning_ledger_path = resolved_root / DEFAULT_LEARNING_LEDGER.name
    learning_state = upsert_learning_ledger(learning_ledger_path, payload)

    knowledge_note_path = ""
    repo_memory_promotion_path = ""
    if int(learning_state.get("evidence_count", 0)) >= KNOWLEDGE_NOTE_THRESHOLD:
        knowledge_note_relative = str(learning_state.get("knowledge_note_relative", "")).strip()
        if knowledge_note_relative:
            knowledge_note = resolved_root / Path(knowledge_note_relative)
            upsert_knowledge_note(
                knowledge_note,
                payload,
                papers=list(learning_state.get("papers", [])),
            )
            knowledge_note_path = str(knowledge_note)

            repo_memory_promotion = resolved_root / DEFAULT_REPO_MEMORY_PROMOTIONS.name
            upsert_repo_memory_promotion(
                repo_memory_promotion,
                payload,
                papers=list(learning_state.get("papers", [])),
                knowledge_note_relative=knowledge_note_relative,
            )
            repo_memory_promotion_path = str(repo_memory_promotion)

    return {
        "working_mind_root": str(resolved_root),
        "papers_index": str(index_path),
        "summary_path": str(summary_path),
        "local_paper_path": str(resolved_root / Path(payload.target_local_paper_path)),
        "source_status": resolved_source_status,
        "learning_ledger": str(learning_ledger_path),
        "knowledge_note_path": knowledge_note_path,
        "repo_memory_promotion": repo_memory_promotion_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Write working_mind artifacts from a paper intake handoff.")
    parser.add_argument("--intake-handoff", type=Path, required=True, help="Path to approved_paper_intake_handoff.md or a compatible intake payload.")
    parser.add_argument("--working-mind-root", type=Path, default=None, help="Optional override for the working_mind root.")
    parser.add_argument("--ingested-on", default=None, help="Optional ingestion date override in YYYY-MM-DD form.")
    parser.add_argument("--no-stage-local-file", action="store_true", help="Do not copy a local PDF into working_mind even if one is available.")
    args = parser.parse_args()

    outputs = ingest_paper_intake_handoff(
        intake_handoff_path=args.intake_handoff,
        working_mind_root=args.working_mind_root,
        ingested_on=args.ingested_on,
        stage_local_file=not args.no_stage_local_file,
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