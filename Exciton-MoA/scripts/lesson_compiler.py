# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""Lesson Compiler consumer (umbrella experiment #6).

Scans ``sweep_summary.jsonl`` artifacts referenced by recent snowball ledger
rows and emits :data:`knowledge_lesson` payloads for cross-pocket regularities
worth promoting into the cross-manifold knowledge channel.

Design notes:
  * Scope is intentionally read-only. This consumer never mutates engine
    state, never updates ``state.json``, and never re-runs sweeps.
  * A "lesson" is a (coupling_posture, diagnosis_label) pair observed in
    ``min_corroboration`` distinct (locA, locB, drift) pockets. Single-pocket
    patterns are not lessons, by definition.
  * Lesson payloads are validated against
    :func:`agent_handoff_schemas.validate_knowledge_lesson` before write.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from agent_handoff_schemas import SCHEMA_VERSIONS, validate_knowledge_lesson
from snowball_consumer import (
    append_consumer_ledger,
    load_ledger_tail,
    utc_timestamp_token,
    utcnow_iso,
    write_consumer_artifact,
)

CONSUMER_NAME = "lesson_compiler"

# Each diagnosis_label maps to a lesson_type chosen from the schema enum.
DIAGNOSIS_TO_LESSON_TYPE = {
    "low_variance_candidate": "entrainment_stability",
    "threshold_conservative_candidate": "policy_generalization",
    "runtime_too_short_candidate": "entrainment_stability",
    "entered_stabilizer": "entrainment_stability",
}
DEFAULT_LESSON_TYPE = "gate_blocker_pattern"
# C3: per-profile natural-entry mean swing >= this triggers the
# ``posture_profile_lift`` lesson_type override. Tuned conservatively so a
# single noisy run cannot flip the lesson type.
POSTURE_PROFILE_LIFT_THRESHOLD = 0.10


def _read_sweep_summary(run_dir: Path) -> list[dict[str, Any]]:
    candidate = run_dir / "sweep_summary.jsonl"
    if not candidate.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        text = candidate.read_text(encoding="utf-8")
    except OSError:
        return []
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _pocket_key(row: dict[str, Any]) -> str:
    loc_a = row.get("embedding_a_loc")
    loc_b = row.get("embedding_b_loc")
    drift = row.get("embedding_drift")
    return f"locA={loc_a},locB={loc_b},drift={drift}"


def _row_profile_used(row: dict[str, Any]) -> str:
    value = row.get("coupling_posture_profile_used")
    if isinstance(value, str) and value:
        return value
    return "none"


def _row_msf_status_dominant(row: dict[str, Any]) -> str:
    counts = row.get("msf_status_counts")
    if isinstance(counts, dict) and counts:
        try:
            return max(
                counts.items(),
                key=lambda kv: (int(kv[1] or 0), str(kv[0])),
            )[0]
        except (TypeError, ValueError):
            pass
    return "disabled"


def _pattern_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    coupling = str(row.get("paper_synchrony_coupling_posture", "unknown"))
    diagnosis = str(row.get("diagnosis_label", "unknown"))
    profile_used = _row_profile_used(row)
    msf_status_dominant = _row_msf_status_dominant(row)
    return coupling, diagnosis, profile_used, msf_status_dominant


def _lesson_type_for(diagnosis: str) -> str:
    return DIAGNOSIS_TO_LESSON_TYPE.get(diagnosis, DEFAULT_LESSON_TYPE)


def aggregate_patterns(
    sweep_rows_by_run: Iterable[tuple[str, list[dict[str, Any]]]],
) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    """Group sweep rows by (coupling_posture, diagnosis_label, profile_used,
    msf_status_dominant) pattern (C3 v2 key).

    Returns a mapping pattern -> {pockets: set[str], runs: set[str],
    contraindication_pockets: set[str], per_profile_natural_entry_means:
    dict[str, float]}. ``contraindication_pockets`` is the set of pockets in
    which the same coupling_posture was observed but with a *different*
    diagnosis_label (independent of profile_used / msf_status_dominant).
    """
    # Materialize rows once so we can iterate multiple times without burning
    # the underlying generator on the contraindication second pass.
    materialized: list[tuple[str, list[dict[str, Any]]]] = [
        (run_dir, list(rows)) for run_dir, rows in sweep_rows_by_run
    ]
    pockets_by_pattern: dict[tuple[str, str, str, str], set[str]] = defaultdict(set)
    runs_by_pattern: dict[tuple[str, str, str, str], set[str]] = defaultdict(set)
    # C3: pre-group natural_entry signal by (coupling, profile_used) so each
    # final pattern can surface a per-profile lift comparison.
    natural_by_coupling_profile: dict[tuple[str, str], list[int]] = defaultdict(list)

    for run_dir, rows in materialized:
        for row in rows:
            pattern = _pattern_key(row)
            coupling, _diagnosis, profile_used, _msf = pattern
            pocket = _pocket_key(row)
            pockets_by_pattern[pattern].add(pocket)
            runs_by_pattern[pattern].add(run_dir)
            natural_by_coupling_profile[(coupling, profile_used)].append(
                int(bool(row.get("met_entry_policy", False)))
            )
    aggregates: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for pattern, pockets in pockets_by_pattern.items():
        coupling, _diagnosis, _profile, _msf = pattern
        contraindication_pockets: set[str] = set()
        for _run_dir, rows in materialized:
            for row in rows:
                if str(row.get("paper_synchrony_coupling_posture", "unknown")) != coupling:
                    continue
                # Contraindication is keyed on (coupling, diagnosis) only, so
                # compare on those two fields, not the full v2 key.
                if str(row.get("diagnosis_label", "unknown")) == pattern[1]:
                    continue
                contraindication_pockets.add(_pocket_key(row))
        per_profile_means: dict[str, float] = {}
        for (cpl, profile_used), values in natural_by_coupling_profile.items():
            if cpl != coupling or not values:
                continue
            per_profile_means[profile_used] = sum(values) / len(values)
        aggregates[pattern] = {
            "pockets": pockets,
            "runs": runs_by_pattern[pattern],
            "contraindication_pockets": contraindication_pockets,
            "per_profile_natural_entry_means": per_profile_means,
        }
    return aggregates


def build_lesson_payload(
    pattern: tuple[str, str, str, str],
    aggregate: dict[str, Any],
) -> dict[str, Any]:
    coupling, diagnosis, profile_used, msf_status_dominant = pattern
    pockets = sorted(aggregate["pockets"])
    runs = sorted(aggregate["runs"])
    contras = sorted(aggregate["contraindication_pockets"])
    per_profile = dict(aggregate.get("per_profile_natural_entry_means") or {})
    findings = (
        f"Across {len(pockets)} distinct pockets, coupling posture "
        f"{coupling!r} co-occurred with diagnosis_label {diagnosis!r} "
        f"(profile_used={profile_used!r}, msf_status_dominant={msf_status_dominant!r})."
    )
    # C3: promote lesson_type to posture_profile_lift when per-profile means
    # diverge by >= POSTURE_PROFILE_LIFT_THRESHOLD across the same coupling.
    if (
        len(per_profile) >= 2
        and (max(per_profile.values()) - min(per_profile.values()))
        >= POSTURE_PROFILE_LIFT_THRESHOLD
    ):
        lesson_type = "posture_profile_lift"
    else:
        lesson_type = _lesson_type_for(diagnosis)
    payload = {
        "schema_version": SCHEMA_VERSIONS["knowledge_lesson"],
        "lesson_type": lesson_type,
        "corroboration_count": len(pockets),
        "evidence_run_dirs": runs,
        "key_findings": findings,
        "applicable_constraints": pockets,
        "contraindications": contras,
        "generated_utc": utcnow_iso(),
        # C3 v2 additive fields.
        "profile_used": profile_used,
        "msf_status_dominant": msf_status_dominant,
        "per_profile_natural_entry_means": per_profile,
    }
    return payload


def render_summary_markdown(payloads: list[dict[str, Any]]) -> str:
    if not payloads:
        return "# Lesson Compiler\n\n_No cross-pocket lessons reached the corroboration threshold._\n"
    lines = ["# Lesson Compiler", "", f"- generated (UTC): {payloads[0]['generated_utc']}", ""]
    for payload in payloads:
        lines.extend(
            [
                f"## {payload['lesson_type']} (corroboration {payload['corroboration_count']})",
                "",
                payload["key_findings"],
                "",
                "Evidence runs:",
                *[f"- {p}" for p in payload["evidence_run_dirs"]],
                "",
                "Applicable pockets:",
                *[f"- {p}" for p in payload["applicable_constraints"]],
                "",
                "Contraindications:",
                *(
                    [f"- {p}" for p in payload["contraindications"]]
                    if payload["contraindications"]
                    else ["- _(none)_"]
                ),
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def run_lesson_compiler(
    *,
    ledger_tail: int = 30,
    min_corroboration: int = 2,
    dry_run: bool = False,
    ledger_path: Path | None = None,
    consumers_root: Path | None = None,
) -> dict[str, Any]:
    """Main entry point. Returns an outcome dict suitable for CLI output."""
    kwargs = {"ledger_path": ledger_path} if ledger_path is not None else {}
    rows = load_ledger_tail(ledger_tail, **kwargs)
    sweep_rows_by_run: list[tuple[str, list[dict[str, Any]]]] = []
    for row in rows:
        run_dir = str(row.get("run_dir") or "")
        if not run_dir:
            continue
        path = Path(run_dir)
        sweep_rows = _read_sweep_summary(path)
        if sweep_rows:
            sweep_rows_by_run.append((run_dir, sweep_rows))
    if not sweep_rows_by_run:
        return {
            "status": "noop",
            "reason": "no ledger row referenced a readable sweep_summary.jsonl",
            "inspected_rows": len(rows),
        }
    aggregates = aggregate_patterns(sweep_rows_by_run)
    qualifying = {p: a for p, a in aggregates.items() if len(a["pockets"]) >= min_corroboration}
    if not qualifying:
        return {
            "status": "noop",
            "reason": f"no pattern reached corroboration_count >= {min_corroboration}",
            "inspected_rows": len(rows),
            "patterns_observed": len(aggregates),
        }
    payloads: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for pattern in sorted(qualifying):
        payload = build_lesson_payload(pattern, qualifying[pattern])
        ok, errors = validate_knowledge_lesson(payload)
        if not ok:
            invalid.append({"pattern": list(pattern), "errors": errors, "payload": payload})
            continue
        payloads.append(payload)
    if invalid:
        return {
            "status": "invalid",
            "reason": "schema validation failed",
            "errors": invalid,
        }
    if dry_run:
        return {"status": "dry_run", "lessons": payloads}
    run_token = utc_timestamp_token()
    summary_md = render_summary_markdown(payloads)
    bundle = {
        "schema_versions": {"knowledge_lesson": SCHEMA_VERSIONS["knowledge_lesson"]},
        "generated_utc": payloads[0]["generated_utc"] if payloads else utcnow_iso(),
        "lessons": payloads,
    }
    write_kwargs = {"root": consumers_root} if consumers_root is not None else {}
    artifact = write_consumer_artifact(
        consumer_name=CONSUMER_NAME,
        run_token=run_token,
        payload=bundle,
        filename="lessons.json",
        extra_files=(("summary.md", summary_md),),
        **write_kwargs,
    )
    ledger_row = {
        **artifact.ledger_row,
        "lesson_count": len(payloads),
        "lesson_types": sorted({p["lesson_type"] for p in payloads}),
        "max_corroboration": max(p["corroboration_count"] for p in payloads),
    }
    append_consumer_ledger(CONSUMER_NAME, ledger_row, **write_kwargs)
    return {
        "status": "ok",
        "artifact_path": artifact.artifact_path.as_posix(),
        "run_token": run_token,
        "lesson_count": len(payloads),
        "lesson_types": ledger_row["lesson_types"],
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Lesson Compiler consumer")
    p.add_argument("--ledger-tail", type=int, default=30, help="Number of ledger rows to inspect")
    p.add_argument(
        "--min-corroboration",
        type=int,
        default=2,
        help="Minimum number of distinct pockets a pattern must appear in to qualify as a lesson",
    )
    p.add_argument("--dry-run", action="store_true", help="Validate and print but do not write")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    outcome = run_lesson_compiler(
        ledger_tail=args.ledger_tail,
        min_corroboration=args.min_corroboration,
        dry_run=args.dry_run,
    )
    print(json.dumps(outcome, sort_keys=True, indent=2, default=str))
    return 0 if outcome.get("status") in {"ok", "dry_run", "noop"} else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
