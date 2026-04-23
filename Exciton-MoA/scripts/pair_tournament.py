# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""Pair tournament consumer (umbrella experiment #2).

Collects per-variant records from recent snowball daily runs, scores each via
Slab C (:mod:`baseline_registry`), and proposes a ``best_pocket_tilt``
(embedding_a_loc / embedding_b_loc / embedding_drift / seed / cycles of the
winning variant).

Promotion rule — *two consecutive tournaments must agree on the same winner
params* before the tilt is actually written to ``state.best_pocket_tilt``.
The first time a winner appears it is stashed in
``state.pending_tournament_winner``; if the next tournament confirms, the
tilt is promoted and the pending slot is cleared.

No engine subprocess runs here. The tournament simply mines the evidence the
snowball has already produced.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from agent_handoff_schemas import SCHEMA_VERSIONS, validate_tournament_entry
from baseline_registry import ScoredRow, rank_variants
from snowball_consumer import (
    append_consumer_ledger,
    load_ledger_tail,
    utc_timestamp_token,
    utcnow_iso,
    write_consumer_artifact,
)
from snowball_experiment import SNOWBALL_DIR, load_state, save_state, state_lock

CONSUMER_NAME = "pair_tournament"
STATE_LOCK_PATH = SNOWBALL_DIR / "state.lock"

# Keys that define a pocket. A winner is only confirmed when the same tuple
# is proposed two tournaments in a row.
TILT_PARAM_KEYS = (
    "embedding_a_loc",
    "embedding_b_loc",
    "embedding_drift",
    "seed",
    "cycles",
)


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


def collect_candidates(
    ledger_rows: Sequence[dict[str, Any]],
    *,
    max_candidates: int = 16,
    origin_filter: tuple[str, ...] = ("daily",),
) -> list[dict[str, Any]]:
    """Collect per-variant records from the most recent daily ledger rows.

    The most-recent rows are scanned first; we stop once we have
    ``max_candidates`` variants.
    """
    candidates: list[dict[str, Any]] = []
    for row in reversed(ledger_rows):
        if str(row.get("origin") or "") not in origin_filter:
            continue
        run_dir_str = str(row.get("run_dir") or "")
        if not run_dir_str:
            continue
        run_dir = Path(run_dir_str)
        if not run_dir.exists():
            continue
        for idx, rec in enumerate(read_variant_records(run_dir)):
            enriched = dict(rec)
            enriched.setdefault("origin_run_dir", run_dir.as_posix())
            # Ensure each variant has a unique scorer id: use the parent run
            # dir plus the variant's param signature so duplicates across
            # runs still score independently.
            signature = "_".join(str(rec.get(k)) for k in TILT_PARAM_KEYS if rec.get(k) is not None)
            enriched["run_dir"] = f"{run_dir.as_posix()}#variant{idx}:{signature or 'unknown'}"
            # Map sweep record result fields onto the scorer's expected keys.
            enriched.setdefault("natural_entries", int(bool(rec.get("met_entry_policy", False))))
            enriched.setdefault(
                "paper_trigger",
                "synchrony"
                if bool(rec.get("paper_uncertainty_triggered", False))
                and str(rec.get("paper_synchrony_basis") or "") == "borderline"
                else ("basin_fragility" if bool(rec.get("paper_uncertainty_triggered", False)) else "none"),
            )
            enriched.setdefault("gate_pass_total", int(rec.get("gate_pass_count") or 0))
            enriched.setdefault("nudge_applied_total", int(rec.get("nudge_applied_count") or 0))
            enriched.setdefault(
                "positive_forward_window_total",
                int(rec.get("nudge_positive_forward_windows") or 0),
            )
            candidates.append(enriched)
            if len(candidates) >= max_candidates:
                return candidates
    return candidates


def tilt_from_variant(variant: dict[str, Any]) -> dict[str, Any]:
    """Extract the tilt params from a scored variant record."""
    return {k: variant.get(k) for k in TILT_PARAM_KEYS}


def _tilts_match(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return all(a.get(k) == b.get(k) for k in TILT_PARAM_KEYS)


def build_tournament_entry(
    *,
    scored: Sequence[ScoredRow],
    winner_variant: dict[str, Any],
    tournament_id: str,
) -> dict[str, Any]:
    candidates_payload = [
        {
            "variant_id": s.variant_id,
            "score": s.score,
            "components": s.components,
        }
        for s in scored
    ]
    return {
        "schema_version": SCHEMA_VERSIONS["tournament_entry"],
        "tournament_id": tournament_id,
        "candidates": candidates_payload,
        "winner_variant_id": scored[0].variant_id,
        "proposed_tilt": tilt_from_variant(winner_variant),
        "generated_utc": utcnow_iso(),
    }


def render_summary_markdown(payload: dict[str, Any], *, promoted: bool) -> str:
    lines = [
        "# Pair tournament",
        "",
        f"- tournament id: {payload['tournament_id']}",
        f"- generated (UTC): {payload['generated_utc']}",
        f"- winner variant: {payload['winner_variant_id']}",
        f"- promoted to best_pocket_tilt: {'yes' if promoted else 'no (needs confirmation)'}",
        "",
        "## Proposed tilt",
        "",
    ]
    for k, v in payload["proposed_tilt"].items():
        lines.append(f"- {k}: {v}")
    lines.extend(["", "## Candidates (top-down)", ""])
    for c in payload["candidates"]:
        lines.append(f"- {c['variant_id']}: score={c['score']}")
    return "\n".join(lines) + "\n"


def _apply_tilt_to_state(
    *,
    proposed_tilt: dict[str, Any],
    tournament_id: str,
) -> tuple[bool, dict[str, Any] | None]:
    """Promote the tilt only if the pending slot matches. Returns (promoted, previous_tilt)."""
    with state_lock(STATE_LOCK_PATH):
        state = load_state()
        pending = state.get("pending_tournament_winner") or {}
        previous_tilt = state.get("best_pocket_tilt")
        promoted = False
        if pending and _tilts_match(pending, proposed_tilt):
            state["best_pocket_tilt"] = dict(proposed_tilt)
            state["best_pocket_tilt_tournament_id"] = tournament_id
            state["best_pocket_tilt_updated_utc"] = utcnow_iso()
            state["pending_tournament_winner"] = None
            promoted = True
        else:
            state["pending_tournament_winner"] = dict(proposed_tilt)
            state["pending_tournament_winner_tournament_id"] = tournament_id
            state["pending_tournament_winner_updated_utc"] = utcnow_iso()
        save_state(state)
    return promoted, previous_tilt


def run_pair_tournament(
    *,
    ledger_tail: int = 20,
    max_candidates: int = 16,
    dry_run: bool = False,
) -> dict[str, Any]:
    ledger_rows = load_ledger_tail(ledger_tail)
    candidates = collect_candidates(ledger_rows, max_candidates=max_candidates)
    if not candidates:
        return {
            "status": "noop",
            "reason": "no recent daily sweep variants to score",
            "inspected_rows": len(ledger_rows),
        }
    scored = rank_variants(candidates)
    # Recover the specific candidate dict that produced the top score so we
    # can lift its tilt params onto the payload.
    winner_variant = _variant_by_score(candidates, scored[0])
    tournament_id = f"T-{utc_timestamp_token()}"
    payload = build_tournament_entry(
        scored=scored,
        winner_variant=winner_variant,
        tournament_id=tournament_id,
    )
    ok, errors = validate_tournament_entry(payload)
    if not ok:
        return {
            "status": "invalid",
            "reason": "schema validation failed",
            "errors": errors,
            "payload": payload,
        }
    if dry_run:
        return {"status": "dry_run", "payload": payload}
    run_token = utc_timestamp_token()
    promoted, previous_tilt = _apply_tilt_to_state(
        proposed_tilt=payload["proposed_tilt"],
        tournament_id=tournament_id,
    )
    summary_md = render_summary_markdown(payload, promoted=promoted)
    artifact = write_consumer_artifact(
        consumer_name=CONSUMER_NAME,
        run_token=run_token,
        payload=payload,
        filename="tournament.json",
        extra_files=(("summary.md", summary_md),),
    )
    ledger_row = {
        **artifact.ledger_row,
        "tournament_id": tournament_id,
        "winner_variant_id": payload["winner_variant_id"],
        "promoted": promoted,
    }
    append_consumer_ledger(CONSUMER_NAME, ledger_row)
    return {
        "status": "ok",
        "artifact_path": artifact.artifact_path.as_posix(),
        "run_token": run_token,
        "tournament_id": tournament_id,
        "promoted": promoted,
        "previous_tilt": previous_tilt,
        "payload": payload,
    }


def _variant_by_score(candidates: Sequence[dict[str, Any]], scored_row: ScoredRow) -> dict[str, Any]:
    """Find the candidate that produced ``scored_row``. Falls back to the first."""
    from baseline_registry import score_variant

    for cand in candidates:
        if score_variant(cand).variant_id == scored_row.variant_id:
            return dict(cand)
    return dict(candidates[0])


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Pair tournament consumer")
    p.add_argument("--ledger-tail", type=int, default=20, help="Ledger rows to scan for variants")
    p.add_argument(
        "--max-candidates",
        type=int,
        default=16,
        help="Max per-variant records to score",
    )
    p.add_argument("--dry-run", action="store_true", help="Validate and print but do not write")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    outcome = run_pair_tournament(
        ledger_tail=args.ledger_tail,
        max_candidates=args.max_candidates,
        dry_run=args.dry_run,
    )
    print(json.dumps(outcome, sort_keys=True, indent=2, default=str))
    return 0 if outcome.get("status") in {"ok", "dry_run", "noop"} else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
