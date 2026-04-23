# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""Replay-to-paper consumer (umbrella experiment #1).

Reads the snowball ledger tail, picks the highest-uncertainty row, reads the
matching sweep ``sweep_uncertainty_paper_handoff.md`` excerpt, and emits a
validated ``paper_handoff`` payload under
``working_data/snowball/consumers/replay_to_paper/<utc>/``.

Nothing in this script runs the engine or re-executes the replay — all
uncertainty consolidation has already happened inside the snowball runner.
This script is the bridge from that ledger into the ``sol-paper-finder``
chain.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from agent_handoff_schemas import SCHEMA_VERSIONS, validate_paper_handoff
from snowball_consumer import (
    append_consumer_ledger,
    load_ledger_tail,
    select_ledger_row,
    utc_timestamp_token,
    utcnow_iso,
    write_consumer_artifact,
)

CONSUMER_NAME = "replay_to_paper"

DOMAIN_FOR_TRIGGER = {
    "synchrony": "synchronization",
    "basin_fragility": "basin-stability",
}


def _first_lines(text: str, n: int) -> str:
    if not text:
        return ""
    return "\n".join(text.splitlines()[:n])


def _read_handoff_excerpt(run_dir: Path, *, max_lines: int = 12) -> str:
    candidate = run_dir / "sweep_uncertainty_paper_handoff.md"
    if not candidate.exists():
        return ""
    try:
        return _first_lines(candidate.read_text(encoding="utf-8"), max_lines)
    except OSError:
        return ""


def suggested_domain_for(row: dict[str, Any]) -> str:
    trigger = str(row.get("paper_trigger") or "none")
    synchrony = str(row.get("synchrony_consensus") or "")
    coupling = str(row.get("coupling_consensus") or "")
    if trigger == "synchrony" and coupling == "weak":
        return "synchronization"
    if trigger == "synchrony":
        return "synchronization"
    if trigger == "basin_fragility":
        if synchrony == "borderline":
            return "control-policy"
        return "basin-stability"
    return "experiment-design"


def build_paper_handoff_payload(row: dict[str, Any]) -> dict[str, Any]:
    """Build a validated-shape paper_handoff payload from a ledger row."""
    trigger = str(row.get("paper_trigger") or "none")
    if trigger not in ("synchrony", "basin_fragility"):
        raise ValueError(f"row has non-paper paper_trigger={trigger!r}; cannot build handoff")
    run_dir = Path(str(row.get("run_dir") or ""))
    excerpt = _read_handoff_excerpt(run_dir) if str(row.get("run_dir") or "") else ""
    payload = {
        "schema_version": SCHEMA_VERSIONS["paper_handoff"],
        "origin": CONSUMER_NAME,
        "source_run_dir": str(row.get("run_dir") or ""),
        "source_started_utc": str(row.get("started_utc") or ""),
        "paper_trigger": trigger,
        "synchrony_consensus": str(row.get("synchrony_consensus") or "unknown"),
        "coupling_consensus": str(row.get("coupling_consensus") or "unknown"),
        "basin_consensus": str(row.get("basin_consensus") or "unknown"),
        "handoff_excerpt": excerpt,
        "suggested_domain": suggested_domain_for(row),
        "generated_utc": utcnow_iso(),
    }
    return payload


def render_summary_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Replay-to-Paper handoff",
        "",
        f"- origin: {payload['origin']}",
        f"- generated (UTC): {payload['generated_utc']}",
        f"- source run_dir: {payload['source_run_dir']}",
        f"- source started (UTC): {payload['source_started_utc']}",
        f"- paper_trigger: {payload['paper_trigger']}",
        f"- synchrony consensus: {payload['synchrony_consensus']}",
        f"- coupling consensus: {payload['coupling_consensus']}",
        f"- basin consensus: {payload['basin_consensus']}",
        f"- suggested domain: {payload['suggested_domain']}",
        "",
        "## Handoff excerpt",
        "",
        payload["handoff_excerpt"] or "_(no uncertainty handoff artifact present)_",
    ]
    return "\n".join(lines) + "\n"


def run_replay_to_paper(
    *,
    ledger_tail: int = 5,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Main entry point. Returns an outcome dict suitable for CLI output."""
    rows = load_ledger_tail(ledger_tail)
    row = select_ledger_row(rows, selector="highest_uncertainty")
    if row is None:
        return {
            "status": "noop",
            "reason": "no ledger row with non-none paper_trigger",
            "inspected": len(rows),
        }
    payload = build_paper_handoff_payload(row)
    ok, errors = validate_paper_handoff(payload)
    if not ok:
        return {
            "status": "invalid",
            "reason": "schema validation failed",
            "errors": errors,
            "payload": payload,
        }
    if dry_run:
        return {"status": "dry_run", "payload": payload, "source_row": row}
    run_token = utc_timestamp_token()
    summary_md = render_summary_markdown(payload)
    artifact = write_consumer_artifact(
        consumer_name=CONSUMER_NAME,
        run_token=run_token,
        payload=payload,
        filename="handoff.json",
        extra_files=(("summary.md", summary_md),),
    )
    ledger_row = {
        **artifact.ledger_row,
        "source_run_dir": payload["source_run_dir"],
        "paper_trigger": payload["paper_trigger"],
        "suggested_domain": payload["suggested_domain"],
    }
    append_consumer_ledger(CONSUMER_NAME, ledger_row)
    return {
        "status": "ok",
        "artifact_path": artifact.artifact_path.as_posix(),
        "run_token": run_token,
        "payload": payload,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Replay-to-Paper consumer")
    p.add_argument("--ledger-tail", type=int, default=5, help="Number of ledger rows to inspect")
    p.add_argument("--dry-run", action="store_true", help="Validate and print but do not write")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    outcome = run_replay_to_paper(ledger_tail=args.ledger_tail, dry_run=args.dry_run)
    print(json.dumps(outcome, sort_keys=True, indent=2, default=str))
    return 0 if outcome.get("status") in {"ok", "dry_run", "noop"} else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
