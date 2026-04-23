# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""Knowledge-compiler promotion audit (umbrella experiment #3).

Scans the working_mind learning ledger and the repo-memory promotions index
for subject folders that have crossed their corroboration threshold but have
*not* yet been mirrored into ``/memories/repo/frontier-os-exciton-moa.md``.
For each unmirrored crossing, writes a ``knowledge_promotion_candidate``
artifact validated by Slab B and appends it to the consumer ledger.

The artifact is the input that :file:`sol-rsi.agent.md` (or a future
auto-PR workflow step) consumes. This script does not open PRs itself —
that's left to the workflow layer so the helper stays test-friendly and
side-effect-light.
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from agent_handoff_schemas import (
    SCHEMA_VERSIONS,
    VALID_SUBJECT_DOMAINS,
    validate_knowledge_promotion_candidate,
)
from snowball_consumer import (
    append_consumer_ledger,
    utc_timestamp_token,
    utcnow_iso,
    write_consumer_artifact,
)

CONSUMER_NAME = "promotion_audit"

EXCITON_ROOT = Path(__file__).resolve().parents[1]
WORKING_MIND_DIR = EXCITON_ROOT / "working_mind"
DEFAULT_LEARNING_LEDGER = WORKING_MIND_DIR / "frontier-learning-ledger.md"
DEFAULT_PROMOTIONS = WORKING_MIND_DIR / "repo-memory-promotions.md"

# Default repo-memory mirror lives outside the workspace folder; in CI the
# memory tree may not be mounted, so we fall back to a no-op when missing.
DEFAULT_REPO_MEMORY = Path("/memories/repo/frontier-os-exciton-moa.md")

_SECTION_RE = re.compile(r"^##\s+(?P<subject>[A-Za-z0-9_\-]+)\s*$", re.MULTILINE)
_LEADING_INT = re.compile(r"^\s*(\d+)")


def _parse_section_block(text: str, header_match: re.Match[str]) -> dict[str, str]:
    start = header_match.end()
    next_match = _SECTION_RE.search(text, pos=start)
    end = next_match.start() if next_match else len(text)
    block = text[start:end]
    fields: dict[str, str] = {}
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        if ":" not in line:
            continue
        key, _, value = line[2:].partition(":")
        fields[key.strip().lower()] = value.strip()
    return fields


def parse_learning_ledger(path: Path) -> dict[str, dict[str, str]]:
    """Parse a frontier-learning-ledger.md file into ``{subject: fields}``."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    out: dict[str, dict[str, str]] = {}
    for header in _SECTION_RE.finditer(text):
        subject = header.group("subject")
        out[subject] = _parse_section_block(text, header)
    return out


def parse_promotions(path: Path) -> dict[str, dict[str, str]]:
    """Same shape as :func:`parse_learning_ledger`, for repo-memory-promotions.md."""
    return parse_learning_ledger(path)


def _leading_int(value: str) -> int | None:
    m = _LEADING_INT.match(value or "")
    return int(m.group(1)) if m else None


def _normalize_subject_domain(subject: str) -> str:
    """Map a working_mind subject folder to a Slab-B ``suggested_domain`` value."""
    candidate = subject.strip().lower()
    if candidate in VALID_SUBJECT_DOMAINS:
        return candidate
    # Common aliases — keep narrow, don't invent new categories.
    aliases = {
        "synchronization": "synchronization",
        "synchrony": "synchronization",
        "basin": "basin-stability",
        "basin_stability": "basin-stability",
        "basin-fragility": "basin-stability",
        "control": "control-policy",
        "control_policy": "control-policy",
        "topology": "topology-design",
    }
    return aliases.get(candidate, "experiment-design")


def is_already_mirrored(memory_text: str, *, subject: str, memory_line: str) -> bool:
    """Return True when the memory line (or its anchor phrase) is already mirrored.

    We accept either an exact substring of the proposed line or an anchor of
    the form ``"<subject> knowledge candidate"`` so a slightly-edited mirror
    still counts.
    """
    if not memory_text:
        return False
    anchor = f"{subject} knowledge candidate"
    return anchor.lower() in memory_text.lower() or (
        memory_line and memory_line.strip() and memory_line.strip() in memory_text
    )


def collect_candidates(
    *,
    learning: dict[str, dict[str, str]],
    promotions: dict[str, dict[str, str]],
    repo_memory_text: str,
) -> list[dict[str, Any]]:
    """Return a list of promotion-candidate dicts ready for validation."""
    candidates: list[dict[str, Any]] = []
    for subject, fields in learning.items():
        evidence = _leading_int(fields.get("evidence count", ""))
        threshold = _leading_int(fields.get("promotion threshold", ""))
        if evidence is None or threshold is None:
            continue
        if evidence < threshold:
            continue
        promo_fields = promotions.get(subject, {})
        memory_line = promo_fields.get("memory line", "").strip()
        if not memory_line:
            # Nothing concrete to mirror — skip silently.
            continue
        if is_already_mirrored(repo_memory_text, subject=subject, memory_line=memory_line):
            continue
        sources: list[str] = []
        for k in ("paper 1", "paper 2", "paper 3", "knowledge note"):
            value = fields.get(k) or promo_fields.get(k)
            if value:
                sources.append(value.strip())
        sources.append(f"working_mind/frontier-learning-ledger.md#{subject}")
        sources.append(f"working_mind/repo-memory-promotions.md#{subject}")
        payload = {
            "schema_version": SCHEMA_VERSIONS["knowledge_promotion_candidate"],
            "subject_folder": subject,
            "corroboration_count": evidence,
            "source_ledger_entries": sources,
            "proposed_memory_line": memory_line,
            "generated_utc": utcnow_iso(),
            "suggested_domain": _normalize_subject_domain(subject),
            "promotion_threshold": threshold,
        }
        candidates.append(payload)
    return candidates


def render_pr_body(candidate: dict[str, Any]) -> str:
    lines = [
        f"# Promote `{candidate['subject_folder']}` knowledge candidate",
        "",
        f"- corroboration_count: {candidate['corroboration_count']}",
        f"- promotion_threshold: {candidate['promotion_threshold']}",
        f"- suggested_domain: {candidate['suggested_domain']}",
        f"- generated_utc: {candidate['generated_utc']}",
        "",
        "## Proposed `/memories/repo/frontier-os-exciton-moa.md` line",
        "",
        candidate["proposed_memory_line"],
        "",
        "## Source ledger entries",
        "",
    ]
    for src in candidate["source_ledger_entries"]:
        lines.append(f"- {src}")
    lines += [
        "",
        "Assignee: `sol-rsi`",
        "",
        "_Generated by `Exciton-MoA/scripts/promotion_audit.py`._",
    ]
    return "\n".join(lines) + "\n"


def render_summary_markdown(candidates: Sequence[dict[str, Any]]) -> str:
    if not candidates:
        return "# Promotion audit\n\n- candidates: 0\n"
    lines = ["# Promotion audit", "", f"- candidates: {len(candidates)}", ""]
    for c in candidates:
        lines.append(
            f"- {c['subject_folder']}: evidence={c['corroboration_count']} "
            f">= threshold={c['promotion_threshold']} (domain={c['suggested_domain']})"
        )
    return "\n".join(lines) + "\n"


def run_promotion_audit(
    *,
    learning_ledger_path: Path = DEFAULT_LEARNING_LEDGER,
    promotions_path: Path = DEFAULT_PROMOTIONS,
    repo_memory_path: Path = DEFAULT_REPO_MEMORY,
    dry_run: bool = False,
) -> dict[str, Any]:
    learning = parse_learning_ledger(learning_ledger_path)
    promotions = parse_promotions(promotions_path)
    if not learning:
        return {
            "status": "noop",
            "reason": f"learning ledger missing or empty: {learning_ledger_path.as_posix()}",
        }
    repo_text = repo_memory_path.read_text(encoding="utf-8") if repo_memory_path.exists() else ""
    candidates = collect_candidates(learning=learning, promotions=promotions, repo_memory_text=repo_text)
    validation_errors: list[dict[str, Any]] = []
    valid: list[dict[str, Any]] = []
    for c in candidates:
        ok, errors = validate_knowledge_promotion_candidate(c)
        if ok:
            valid.append(c)
        else:
            validation_errors.append({"subject_folder": c["subject_folder"], "errors": errors})
    if not valid:
        return {
            "status": "noop",
            "reason": "no unmirrored candidates above threshold",
            "scanned_subjects": sorted(learning),
            "validation_errors": validation_errors,
        }
    if dry_run:
        return {
            "status": "dry_run",
            "candidates": valid,
            "validation_errors": validation_errors,
        }
    run_token = utc_timestamp_token()
    written: list[dict[str, Any]] = []
    for candidate in valid:
        subject = candidate["subject_folder"]
        artifact = write_consumer_artifact(
            consumer_name=CONSUMER_NAME,
            run_token=f"{run_token}_{subject}",
            payload=candidate,
            filename="candidate.json",
            extra_files=(
                ("pr_body.md", render_pr_body(candidate)),
                ("summary.md", render_summary_markdown([candidate])),
            ),
        )
        ledger_row = {
            **artifact.ledger_row,
            "subject_folder": subject,
            "corroboration_count": candidate["corroboration_count"],
            "suggested_domain": candidate["suggested_domain"],
        }
        append_consumer_ledger(CONSUMER_NAME, ledger_row)
        written.append(
            {
                "subject_folder": subject,
                "artifact_path": artifact.artifact_path.as_posix(),
            }
        )
    return {
        "status": "ok",
        "run_token": run_token,
        "written": written,
        "validation_errors": validation_errors,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Knowledge-compiler promotion audit")
    p.add_argument(
        "--learning-ledger",
        type=Path,
        default=DEFAULT_LEARNING_LEDGER,
        help="Path to working_mind/frontier-learning-ledger.md",
    )
    p.add_argument(
        "--promotions",
        type=Path,
        default=DEFAULT_PROMOTIONS,
        help="Path to working_mind/repo-memory-promotions.md",
    )
    p.add_argument(
        "--repo-memory",
        type=Path,
        default=DEFAULT_REPO_MEMORY,
        help="Path to /memories/repo/frontier-os-exciton-moa.md (mirror target)",
    )
    p.add_argument("--dry-run", action="store_true", help="Validate and print but do not write")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    outcome = run_promotion_audit(
        learning_ledger_path=args.learning_ledger,
        promotions_path=args.promotions,
        repo_memory_path=args.repo_memory,
        dry_run=args.dry_run,
    )
    print(json.dumps(outcome, sort_keys=True, indent=2, default=str))
    return 0 if outcome.get("status") in {"ok", "dry_run", "noop"} else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
