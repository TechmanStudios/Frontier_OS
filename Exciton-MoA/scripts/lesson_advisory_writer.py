# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""Lesson Advisory Writer consumer (umbrella experiment #6, W3).

Reads the most recent lesson_compiler bundle (``lessons.json``) and, for
high-confidence lessons (``corroboration_count >= min_corroboration`` and
``contraindications == []``), writes an ``advisory_lesson_clamp`` block back
into the shared snowball ``state.json`` under the existing state lock.

The clamp is *advisory*: ``snowball_experiment.decide_next_config`` narrows
the explore neighbor lists to the union of applicable pockets when the clamp
intersects them. An empty intersection silently falls back to the full
allowlist — this consumer can never starve the runner of variants.

Emits:
 * ``consumers/lesson_advisory_writer/<utc>/advisory.json`` (payload).
 * A consumer ledger row.
 * Updates ``state.advisory_lesson_clamp`` (schema_version=1).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from snowball_consumer import (
    CONSUMERS_DIR,
    append_consumer_ledger,
    consumer_dir,
    utc_timestamp_token,
    utcnow_iso,
    write_consumer_artifact,
)
from snowball_experiment import SNOWBALL_DIR, load_state, save_state, state_lock

CONSUMER_NAME = "lesson_advisory_writer"
SOURCE_CONSUMER = "lesson_compiler"
STATE_LOCK_PATH = SNOWBALL_DIR / "state.lock"
ADVISORY_SCHEMA_VERSION = 1
DEFAULT_MIN_CORROBORATION = 3


def _find_latest_lessons_path(*, root: Path = CONSUMERS_DIR) -> Path | None:
    """Return the most recent ``lessons.json`` produced by lesson_compiler."""
    base = consumer_dir(SOURCE_CONSUMER, root=root)
    if not base.exists():
        return None
    candidates = sorted(
        (p for p in base.glob("*/lessons.json") if p.is_file()),
        key=lambda p: p.parent.name,
    )
    return candidates[-1] if candidates else None


def _read_lessons(path: Path) -> tuple[list[dict[str, Any]], str]:
    try:
        bundle = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], ""
    lessons = bundle.get("lessons") if isinstance(bundle, dict) else None
    if not isinstance(lessons, list):
        return [], ""
    source_token = path.parent.name
    return [lsn for lsn in lessons if isinstance(lsn, dict)], source_token


def select_high_confidence_lessons(
    lessons: list[dict[str, Any]],
    *,
    min_corroboration: int,
) -> list[dict[str, Any]]:
    """Return lessons with strong cross-pocket support and zero contraindications."""
    selected: list[dict[str, Any]] = []
    for lsn in lessons:
        try:
            corro = int(lsn.get("corroboration_count", 0) or 0)
        except (TypeError, ValueError):
            continue
        contras = lsn.get("contraindications") or []
        if corro >= min_corroboration and not contras:
            selected.append(lsn)
    return selected


def build_advisory_clamp(
    selected: list[dict[str, Any]],
    *,
    source_token: str,
) -> dict[str, Any]:
    applicable: set[str] = set()
    contraindicated: set[str] = set()
    lesson_types: set[str] = set()
    # C3: track recommended profile_used across selected v2 lessons. v1
    # lessons (no profile_used field) contribute "none".
    recommended_profile_counts: dict[str, int] = {}
    for lsn in selected:
        for pocket in lsn.get("applicable_constraints", []) or []:
            applicable.add(str(pocket))
        for pocket in lsn.get("contraindications", []) or []:
            contraindicated.add(str(pocket))
        if isinstance(lsn.get("lesson_type"), str):
            lesson_types.add(lsn["lesson_type"])
        profile_used = lsn.get("profile_used")
        if isinstance(profile_used, str) and profile_used and profile_used != "none":
            recommended_profile_counts[profile_used] = (
                recommended_profile_counts.get(profile_used, 0) + 1
            )
    return {
        "schema_version": ADVISORY_SCHEMA_VERSION,
        "applicable_pockets": sorted(applicable),
        "contraindicated_pockets": sorted(contraindicated),
        "source_lesson_token": source_token,
        "source_lesson_types": sorted(lesson_types),
        "lesson_count": len(selected),
        "recommended_profile_counts": recommended_profile_counts,
        "updated_utc": utcnow_iso(),
    }


def _update_state_with_clamp(clamp: dict[str, Any]) -> None:
    with state_lock(STATE_LOCK_PATH):
        state = load_state()
        state["advisory_lesson_clamp"] = clamp
        save_state(state)


def _clear_state_clamp(reason: str, *, source_token: str | None) -> None:
    with state_lock(STATE_LOCK_PATH):
        state = load_state()
        if state.get("advisory_lesson_clamp"):
            state["advisory_lesson_clamp"] = {
                "schema_version": ADVISORY_SCHEMA_VERSION,
                "applicable_pockets": [],
                "contraindicated_pockets": [],
                "source_lesson_token": source_token or "",
                "source_lesson_types": [],
                "lesson_count": 0,
                "cleared_reason": reason,
                "updated_utc": utcnow_iso(),
            }
            save_state(state)


def render_summary_markdown(payload: dict[str, Any]) -> str:
    clamp = payload["clamp"]
    lines = [
        "# Lesson Advisory Writer",
        "",
        f"- generated (UTC): {payload['generated_utc']}",
        f"- source lessons token: {clamp['source_lesson_token']}",
        f"- min corroboration threshold: {payload['min_corroboration']}",
        f"- selected lessons: {clamp['lesson_count']}",
        f"- applicable pockets: {len(clamp['applicable_pockets'])}",
        f"- contraindicated pockets: {len(clamp['contraindicated_pockets'])}",
        f"- lesson types: {', '.join(clamp['source_lesson_types']) or '(none)'}",
        "",
        "## Applicable pockets",
        "",
    ]
    for pocket in clamp["applicable_pockets"]:
        lines.append(f"- {pocket}")
    if not clamp["applicable_pockets"]:
        lines.append("- _(none — clamp will be a no-op)_")
    return "\n".join(lines) + "\n"


def run_lesson_advisory_writer(
    *,
    min_corroboration: int = DEFAULT_MIN_CORROBORATION,
    dry_run: bool = False,
    consumers_root: Path | None = None,
) -> dict[str, Any]:
    root = consumers_root if consumers_root is not None else CONSUMERS_DIR
    lessons_path = _find_latest_lessons_path(root=root)
    if lessons_path is None:
        return {
            "status": "noop",
            "reason": "no lesson_compiler bundle found on disk",
        }
    lessons, source_token = _read_lessons(lessons_path)
    if not lessons:
        return {
            "status": "noop",
            "reason": "lesson_compiler bundle had no parseable lessons",
            "source_path": lessons_path.as_posix(),
        }
    selected = select_high_confidence_lessons(lessons, min_corroboration=min_corroboration)
    if not selected:
        # No qualifying lessons. Clear any previously written clamp so we
        # don't keep applying advice that no longer holds.
        if not dry_run:
            _clear_state_clamp("no_qualifying_lessons", source_token=source_token)
        return {
            "status": "noop",
            "reason": (
                f"no lesson met corroboration_count >= {min_corroboration} "
                "with empty contraindications"
            ),
            "source_path": lessons_path.as_posix(),
            "candidates": len(lessons),
        }
    clamp = build_advisory_clamp(selected, source_token=source_token)
    payload = {
        "schema_version": ADVISORY_SCHEMA_VERSION,
        "origin": CONSUMER_NAME,
        "generated_utc": clamp["updated_utc"],
        "min_corroboration": min_corroboration,
        "source_lessons_path": lessons_path.as_posix(),
        "selected_lesson_count": len(selected),
        "candidate_lesson_count": len(lessons),
        "clamp": clamp,
    }
    if dry_run:
        return {"status": "dry_run", "payload": payload}
    run_token = utc_timestamp_token()
    summary_md = render_summary_markdown(payload)
    write_kwargs = {"root": root}
    artifact = write_consumer_artifact(
        consumer_name=CONSUMER_NAME,
        run_token=run_token,
        payload=payload,
        filename="advisory.json",
        extra_files=(("summary.md", summary_md),),
        **write_kwargs,
    )
    ledger_row = {
        **artifact.ledger_row,
        "source_lesson_token": source_token,
        "selected_lesson_count": len(selected),
        "applicable_pocket_count": len(clamp["applicable_pockets"]),
    }
    append_consumer_ledger(CONSUMER_NAME, ledger_row, **write_kwargs)
    _update_state_with_clamp(clamp)
    return {
        "status": "ok",
        "artifact_path": artifact.artifact_path.as_posix(),
        "run_token": run_token,
        "selected_lesson_count": len(selected),
        "applicable_pocket_count": len(clamp["applicable_pockets"]),
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Lesson Advisory Writer consumer")
    p.add_argument(
        "--min-corroboration",
        type=int,
        default=DEFAULT_MIN_CORROBORATION,
        help="Minimum corroboration_count for a lesson to feed the clamp",
    )
    p.add_argument("--dry-run", action="store_true", help="Validate and print but do not write")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    outcome = run_lesson_advisory_writer(
        min_corroboration=args.min_corroboration,
        dry_run=args.dry_run,
    )
    print(json.dumps(outcome, sort_keys=True, indent=2, default=str))
    return 0 if outcome.get("status") in {"ok", "dry_run", "noop"} else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
