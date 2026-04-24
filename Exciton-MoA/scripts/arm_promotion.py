# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""Arm-promotion engine consumer (umbrella experiment, Phase D D1).

Reads paired A/B outcome streams written by ``snowball_experiment``:

* ``working_data/snowball/msf_ab_outcomes.jsonl``
* ``working_data/snowball/posture_ab_outcomes.jsonl``

Computes a rolling-window mean of ``delta_natural_entries`` (treatment minus
control) per arm. When the mean's magnitude crosses ``threshold`` and the
window is full, the consumer "promotes" the winning arm (treatment or control)
so :func:`snowball_experiment.decide_next_config` can lock that arm next
cycle. Otherwise the arm stays in alternation.

Promotions are reversible: every fresh run rewrites
``state.arm_promotion`` from scratch, so a regression that drives the rolling
mean back below threshold flips the status to ``no_lift`` (default_arm=None)
on the next pass.

Emits:
 * ``consumers/arm_promotion/<utc>/promotion.json`` (validated by
   :func:`agent_handoff_schemas.validate_arm_promotion`).
 * A consumer ledger row.
 * Updates ``state.arm_promotion`` (schema_version=1).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from agent_handoff_schemas import SCHEMA_VERSIONS, validate_arm_promotion
from snowball_consumer import (
    CONSUMERS_DIR,
    append_consumer_ledger,
    utc_timestamp_token,
    utcnow_iso,
    write_consumer_artifact,
)
from snowball_experiment import (
    MSF_AB_OUTCOMES_PATH,
    POSTURE_AB_OUTCOMES_PATH,
    SNOWBALL_DIR,
    load_state,
    save_state,
    state_lock,
)

CONSUMER_NAME = "arm_promotion"
STATE_LOCK_PATH = SNOWBALL_DIR / "state.lock"
ARM_PROMOTION_SCHEMA_VERSION = SCHEMA_VERSIONS["arm_promotion"]
DEFAULT_WINDOW = 10
DEFAULT_THRESHOLD = 0.5


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    rows.append(obj)
    except OSError:
        return []
    return rows


def evaluate_arm(
    deltas: list[dict[str, Any]],
    *,
    window: int,
    threshold: float,
    source_token: str,
) -> dict[str, Any]:
    """Return an arm-promotion block from the tail of paired delta records.

    Promotion rule:

    * ``paired_count < window`` → ``insufficient_evidence`` (default_arm=None).
    * ``mean >= +threshold``    → ``favors_treatment`` (default_arm=treatment).
    * ``mean <= -threshold``    → ``favors_control`` (default_arm=control).
    * otherwise                  → ``no_lift`` (default_arm=None).
    """
    tail = deltas[-window:] if window > 0 else list(deltas)
    paired_count = len(tail)
    if paired_count == 0:
        mean_delta = 0.0
    else:
        try:
            total = sum(float(row.get("delta_natural_entries", 0) or 0) for row in tail)
        except (TypeError, ValueError):
            total = 0.0
        mean_delta = total / paired_count
    if paired_count < window:
        status = "insufficient_evidence"
        default_arm: str | None = None
    elif mean_delta >= threshold:
        status = "favors_treatment"
        default_arm = "treatment"
    elif mean_delta <= -threshold:
        status = "favors_control"
        default_arm = "control"
    else:
        status = "no_lift"
        default_arm = None
    return {
        "default_arm": default_arm,
        "mean_delta": mean_delta,
        "paired_count": paired_count,
        "source_token": source_token,
        "updated_utc": utcnow_iso(),
        "status": status,
    }


def build_promotion_payload(
    *,
    window: int,
    threshold: float,
    msf_path: Path,
    posture_path: Path,
    source_token: str,
) -> dict[str, Any]:
    msf_deltas = _read_jsonl(msf_path)
    posture_deltas = _read_jsonl(posture_path)
    msf_arm = evaluate_arm(
        msf_deltas, window=window, threshold=threshold, source_token=source_token
    )
    posture_arm = evaluate_arm(
        posture_deltas, window=window, threshold=threshold, source_token=source_token
    )
    return {
        "schema_version": ARM_PROMOTION_SCHEMA_VERSION,
        "origin": CONSUMER_NAME,
        "generated_utc": utcnow_iso(),
        "window": window,
        "threshold": threshold,
        "msf": msf_arm,
        "posture": posture_arm,
    }


def _state_block_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": payload["schema_version"],
        "msf": payload["msf"],
        "posture": payload["posture"],
        "generated_utc": payload["generated_utc"],
        "window": payload["window"],
        "threshold": payload["threshold"],
    }


def _update_state(promotion_block: dict[str, Any]) -> None:
    with state_lock(STATE_LOCK_PATH):
        state = load_state()
        state["arm_promotion"] = promotion_block
        save_state(state)


def render_summary_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Arm Promotion",
        "",
        f"- generated (UTC): {payload['generated_utc']}",
        f"- window: {payload['window']}",
        f"- threshold: {payload['threshold']}",
        "",
        "## MSF arm",
        "",
        f"- status: {payload['msf']['status']}",
        f"- default_arm: {payload['msf']['default_arm']}",
        f"- mean_delta: {payload['msf']['mean_delta']:.3f}",
        f"- paired_count: {payload['msf']['paired_count']}",
        "",
        "## Posture arm",
        "",
        f"- status: {payload['posture']['status']}",
        f"- default_arm: {payload['posture']['default_arm']}",
        f"- mean_delta: {payload['posture']['mean_delta']:.3f}",
        f"- paired_count: {payload['posture']['paired_count']}",
        "",
    ]
    return "\n".join(lines)


def run_arm_promotion(
    *,
    window: int = DEFAULT_WINDOW,
    threshold: float = DEFAULT_THRESHOLD,
    dry_run: bool = False,
    consumers_root: Path | None = None,
    msf_path: Path | None = None,
    posture_path: Path | None = None,
) -> dict[str, Any]:
    root = consumers_root if consumers_root is not None else CONSUMERS_DIR
    msf_in = msf_path if msf_path is not None else MSF_AB_OUTCOMES_PATH
    posture_in = posture_path if posture_path is not None else POSTURE_AB_OUTCOMES_PATH
    run_token = utc_timestamp_token()
    payload = build_promotion_payload(
        window=window,
        threshold=threshold,
        msf_path=msf_in,
        posture_path=posture_in,
        source_token=run_token,
    )
    state_block = _state_block_from_payload(payload)
    ok, errors = validate_arm_promotion(
        {
            "schema_version": payload["schema_version"],
            "msf": payload["msf"],
            "posture": payload["posture"],
            "generated_utc": payload["generated_utc"],
        }
    )
    if not ok:
        return {"status": "error", "errors": errors, "payload": payload}
    if dry_run:
        return {"status": "dry_run", "payload": payload}
    summary_md = render_summary_markdown(payload)
    artifact = write_consumer_artifact(
        consumer_name=CONSUMER_NAME,
        run_token=run_token,
        payload=payload,
        filename="promotion.json",
        extra_files=(("summary.md", summary_md),),
        root=root,
    )
    ledger_row = {
        **artifact.ledger_row,
        "msf_status": payload["msf"]["status"],
        "msf_default_arm": payload["msf"]["default_arm"],
        "msf_paired_count": payload["msf"]["paired_count"],
        "posture_status": payload["posture"]["status"],
        "posture_default_arm": payload["posture"]["default_arm"],
        "posture_paired_count": payload["posture"]["paired_count"],
    }
    append_consumer_ledger(CONSUMER_NAME, ledger_row, root=root)
    _update_state(state_block)
    return {
        "status": "ok",
        "artifact_path": artifact.artifact_path.as_posix(),
        "run_token": run_token,
        "msf_status": payload["msf"]["status"],
        "posture_status": payload["posture"]["status"],
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Arm-promotion engine consumer")
    p.add_argument(
        "--window",
        type=int,
        default=DEFAULT_WINDOW,
        help="Rolling window of paired A/B records to average (default 10)",
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help="|mean_delta| at or above this promotes the winning arm (default 0.5)",
    )
    p.add_argument("--dry-run", action="store_true", help="Compute and print but do not write")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    outcome = run_arm_promotion(
        window=args.window,
        threshold=args.threshold,
        dry_run=args.dry_run,
    )
    print(json.dumps(outcome, sort_keys=True, indent=2, default=str))
    return 0 if outcome.get("status") in {"ok", "dry_run", "noop"} else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
