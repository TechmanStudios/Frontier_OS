# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""Counterfactual probe consumer (umbrella experiment #4).

Picks the most recent ``regime=="exploit"`` snowball run, reads its
``sweep_summary.jsonl``, and measures basin-fragility *spread* across the
neighbor variants that already ran. No new engine subprocess — the spread
itself *is* the counterfactual.

Emits:
 * ``consumers/counterfactual/<utc>/report.json`` (payload).
 * A consumer ledger row.
 * An additive ``paper_basin_fragility_delta`` field written back into the
   shared snowball ``state.json`` under the existing state lock.

``fragility_delta`` is ``{-1, 0, +1}``:
 * ``+1`` — all variants agree on a fragile/narrow basin (stable fragility).
 * ``-1`` — all variants agree the basin is not fragile (stable robustness).
 * ``0`` — variants disagree (boundary).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from snowball_consumer import (
    append_consumer_ledger,
    load_ledger_tail,
    select_ledger_row,
    utc_timestamp_token,
    utcnow_iso,
    write_consumer_artifact,
)
from snowball_experiment import SNOWBALL_DIR, load_state, save_state, state_lock

STATE_LOCK_PATH = SNOWBALL_DIR / "state.lock"

CONSUMER_NAME = "counterfactual"

FRAGILE_LABELS = frozenset({"fragile", "narrow"})


def read_variant_records(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "sweep_summary.jsonl"
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            records.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return records


def compute_fragility_delta(records: list[dict[str, Any]]) -> tuple[int, dict[str, int]]:
    """Return ``(delta, label_counts)`` from the sweep variants."""
    counts: Counter[str] = Counter()
    for r in records:
        label = str(r.get("paper_basin_fragility") or "unknown")
        counts[label] += 1
    label_counts = dict(counts)
    if not counts:
        return 0, label_counts
    labels_seen = {lbl for lbl, n in counts.items() if n > 0 and lbl != "unknown"}
    if not labels_seen:
        return 0, label_counts
    if labels_seen.issubset(FRAGILE_LABELS):
        return 1, label_counts
    if not labels_seen & FRAGILE_LABELS:
        return -1, label_counts
    return 0, label_counts


def build_payload(
    *,
    source_row: dict[str, Any],
    records: list[dict[str, Any]],
    fragility_delta: int,
    label_counts: dict[str, int],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "origin": CONSUMER_NAME,
        "generated_utc": utcnow_iso(),
        "source_run_dir": str(source_row.get("run_dir") or ""),
        "source_started_utc": str(source_row.get("started_utc") or ""),
        "source_regime": str(source_row.get("regime") or ""),
        "source_paper_trigger": str(source_row.get("paper_trigger") or "none"),
        "variant_count": len(records),
        "fragility_label_counts": label_counts,
        "fragility_delta": fragility_delta,
        "verdict": (
            "confirmed_fragile"
            if fragility_delta == 1
            else "confirmed_robust"
            if fragility_delta == -1
            else "boundary"
        ),
    }


def render_summary_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Counterfactual probe",
        "",
        f"- origin: {payload['origin']}",
        f"- generated (UTC): {payload['generated_utc']}",
        f"- source run_dir: {payload['source_run_dir']}",
        f"- source regime: {payload['source_regime']}",
        f"- source paper_trigger: {payload['source_paper_trigger']}",
        f"- variant count: {payload['variant_count']}",
        f"- fragility_delta: {payload['fragility_delta']}",
        f"- verdict: {payload['verdict']}",
        "",
        "## Fragility label counts",
        "",
    ]
    for label, count in sorted(payload["fragility_label_counts"].items()):
        lines.append(f"- {label}: {count}")
    return "\n".join(lines) + "\n"


def _update_state_with_delta(fragility_delta: int, *, run_token: str) -> None:
    with state_lock(STATE_LOCK_PATH):
        state = load_state()
        state["paper_basin_fragility_delta"] = fragility_delta
        state["paper_basin_fragility_delta_run_token"] = run_token
        state["paper_basin_fragility_delta_updated_utc"] = utcnow_iso()
        save_state(state)


def run_counterfactual_probe(*, ledger_tail: int = 20, dry_run: bool = False) -> dict[str, Any]:
    rows = load_ledger_tail(ledger_tail)
    row = select_ledger_row(rows, selector="most_recent_exploit")
    if row is None:
        return {
            "status": "noop",
            "reason": "no recent exploit row in ledger tail",
            "inspected": len(rows),
        }
    run_dir = Path(str(row.get("run_dir") or ""))
    if not run_dir.exists():
        return {
            "status": "noop",
            "reason": "source run_dir missing on disk",
            "run_dir": run_dir.as_posix(),
        }
    records = read_variant_records(run_dir)
    if not records:
        return {
            "status": "noop",
            "reason": "source run has no sweep_summary.jsonl records",
            "run_dir": run_dir.as_posix(),
        }
    if len(records) < 2:
        return {
            "status": "noop",
            "reason": "need >=2 variants for counterfactual spread",
            "run_dir": run_dir.as_posix(),
            "variant_count": len(records),
        }
    delta, label_counts = compute_fragility_delta(records)
    payload = build_payload(
        source_row=row,
        records=records,
        fragility_delta=delta,
        label_counts=label_counts,
    )
    if dry_run:
        return {"status": "dry_run", "payload": payload}
    run_token = utc_timestamp_token()
    summary_md = render_summary_markdown(payload)
    artifact = write_consumer_artifact(
        consumer_name=CONSUMER_NAME,
        run_token=run_token,
        payload=payload,
        filename="report.json",
        extra_files=(("summary.md", summary_md),),
    )
    ledger_row = {
        **artifact.ledger_row,
        "source_run_dir": payload["source_run_dir"],
        "fragility_delta": delta,
        "verdict": payload["verdict"],
    }
    append_consumer_ledger(CONSUMER_NAME, ledger_row)
    _update_state_with_delta(delta, run_token=run_token)
    return {
        "status": "ok",
        "artifact_path": artifact.artifact_path.as_posix(),
        "run_token": run_token,
        "fragility_delta": delta,
        "verdict": payload["verdict"],
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Counterfactual probe consumer")
    p.add_argument("--ledger-tail", type=int, default=20, help="Ledger rows to scan for exploit row")
    p.add_argument("--dry-run", action="store_true", help="Validate and print but do not write")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    outcome = run_counterfactual_probe(ledger_tail=args.ledger_tail, dry_run=args.dry_run)
    print(json.dumps(outcome, sort_keys=True, indent=2, default=str))
    return 0 if outcome.get("status") in {"ok", "dry_run", "noop"} else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
