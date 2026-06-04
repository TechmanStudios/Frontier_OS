# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""Decision Report monitor consumer (umbrella experiment, Phase E E1).

Reads the last K (default 4) decision report summaries, checks for MSF promotion
flips, week-over-week drop in natural entries mean_delta, and hold regime overuse.
Fires a schema-validated incident_report if any regressions are found.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from agent_handoff_schemas import SCHEMA_VERSIONS, validate_incident_report
from snowball_consumer import (
    CONSUMERS_DIR,
    append_consumer_ledger,
    consumer_dir,
    utc_timestamp_token,
    utcnow_iso,
    write_consumer_artifact,
)

CONSUMER_NAME = "decision_report_monitor"
DEFAULT_K = 4


def find_summaries(consumers_root: Path) -> list[tuple[str, Path]]:
    """Locate all weekly decision report summary files, sorted by run token ascending."""
    base = consumer_dir("snowball_decision_report", root=consumers_root)
    if not base.exists():
        return []
    candidates = []
    for p in base.glob("*/summary.json"):
        if p.is_file():
            candidates.append((p.parent.name, p))
    candidates.sort(key=lambda x: x[0])
    return candidates


def load_summaries(candidates: list[tuple[str, Path]]) -> list[tuple[str, dict[str, Any]]]:
    """Parse JSON payloads from the found summary paths."""
    summaries = []
    for token, path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                summaries.append((token, data))
        except (OSError, json.JSONDecodeError):
            continue
    return summaries


def evaluate_regressions(
    summaries: list[tuple[str, dict[str, Any]]]
) -> list[dict[str, Any]]:
    """Scan the summaries tail for triggered breaches."""
    breaches: list[dict[str, Any]] = []
    if not summaries:
        return breaches

    # 1. Check for MSF promotion flip and mean_delta drop week-over-week
    for i in range(1, len(summaries)):
        prev_token, prev_data = summaries[i - 1]
        curr_token, curr_data = summaries[i]

        prev_msf = prev_data.get("msf_promotion") or {}
        curr_msf = curr_data.get("msf_promotion") or {}

        # MSF Promotion status flip: favors_treatment -> favors_control
        prev_status = prev_msf.get("status")
        curr_status = curr_msf.get("status")
        if prev_status == "favors_treatment" and curr_status == "favors_control":
            breaches.append({
                "type": "msf_promotion_flip",
                "description": (
                    f"MSF promotion flipped from favors_treatment ({prev_token}) "
                    f"to favors_control ({curr_token})"
                ),
                "metric": 1.0,
                "threshold": 1.0,
                "baseline_token": prev_token,
                "target_token": curr_token,
            })

        # Mean delta of natural entries drops by >= 1.0
        prev_delta = prev_msf.get("mean_delta")
        curr_delta = curr_msf.get("mean_delta")
        if prev_delta is not None and curr_delta is not None:
            if isinstance(prev_delta, (int, float)) and isinstance(curr_delta, (int, float)):
                drop = prev_delta - curr_delta
                if drop >= 1.0:
                    breaches.append({
                        "type": "mean_delta_drop",
                        "description": (
                            f"MSF mean_delta dropped from {prev_delta:.3f} to "
                            f"{curr_delta:.3f} (drop of {drop:.3f} >= 1.0)"
                        ),
                        "metric": drop,
                        "threshold": 1.0,
                        "baseline_token": prev_token,
                        "target_token": curr_token,
                    })

    # 2. Check hold overuse in the latest summary
    latest_token, latest_data = summaries[-1]
    regime_counts = latest_data.get("regime_counts") or {}
    if isinstance(regime_counts, dict) and regime_counts:
        hold_count = regime_counts.get("hold", 0)
        total_count = sum(regime_counts.values())
        if total_count > 0:
            hold_ratio = hold_count / total_count
            if hold_ratio > 0.7:
                breaches.append({
                    "type": "hold_overuse",
                    "description": (
                        f"Hold regime count ({hold_count}/{total_count}) "
                        f"ratio {hold_ratio:.3f} exceeds 0.7 threshold"
                    ),
                    "metric": hold_ratio,
                    "threshold": 0.7,
                    "baseline_token": latest_token,
                    "target_token": latest_token,
                })

    return breaches


def build_incident_payload(
    breaches: list[dict[str, Any]],
    run_dirs_observed: list[str]
) -> dict[str, Any]:
    """Construct schema-compliant incident payload."""
    primary = breaches[0]
    actions = []
    has_flip = any(b["type"] == "msf_promotion_flip" for b in breaches)
    has_drop = any(b["type"] == "mean_delta_drop" for b in breaches)
    has_hold = any(b["type"] == "hold_overuse" for b in breaches)

    if has_flip:
        actions.append("review MSF control-treatment alternation results and promotion logs")
    if has_drop:
        actions.append("investigate why natural entries mean delta dropped significantly")
    if has_hold:
        actions.append("verify if the system is stuck in an active safety clamp or hold regime")

    recommended_action = "Operator review required: " + "; ".join(actions)

    return {
        "schema_version": SCHEMA_VERSIONS["incident_report"],
        "kind": "decision_report_regression",
        "severity": "critical",
        "drift_metric": float(primary["metric"]),
        "threshold": float(primary["threshold"]),
        "baseline_id": primary["baseline_token"],
        "run_dirs_observed": run_dirs_observed,
        "recommended_action": recommended_action,
        "generated_utc": utcnow_iso(),
        "breaches": breaches,
    }


def render_summary_markdown(payload: dict[str, Any]) -> str:
    """Render incident details to operator-readable markdown."""
    lines = [
        "# Decision Report Monitor Alert",
        "",
        f"- **Kind**: {payload['kind']}",
        f"- **Severity**: {payload['severity']}",
        f"- **Generated (UTC)**: {payload['generated_utc']}",
        f"- **Primary Metric**: {payload['drift_metric']:.3f} (Threshold: {payload['threshold']:.3f})",
        f"- **Baseline ID**: {payload['baseline_id']}",
        f"- **Recommended Action**: {payload['recommended_action']}",
        "",
        "## Active Breaches",
        "",
    ]
    for b in payload["breaches"]:
        lines.append(f"- **{b['type']}**: {b['description']}")
    return "\n".join(lines) + "\n"


def run_monitor(
    *,
    K: int = DEFAULT_K,
    dry_run: bool = False,
    consumers_root: Path | None = None,
) -> dict[str, Any]:
    """Execute the monitor sweep."""
    root = consumers_root if consumers_root is not None else CONSUMERS_DIR
    candidates = find_summaries(root)
    if not candidates:
        return {
            "status": "noop",
            "reason": "no decision report summaries found",
            "incident_fired": False,
        }

    window_candidates = candidates[-K:] if K > 0 else candidates
    summaries = load_summaries(window_candidates)
    if not summaries:
        return {
            "status": "noop",
            "reason": "failed to load decision report summaries",
            "incident_fired": False,
        }

    breaches = evaluate_regressions(summaries)
    if not breaches:
        return {
            "status": "ok",
            "reason": f"no regressions found across {len(summaries)} summaries",
            "incident_fired": False,
        }

    observed_runs = [p.parent.as_posix() for _, p in window_candidates]
    payload = build_incident_payload(breaches, observed_runs)

    ok, errors = validate_incident_report(payload)
    if not ok:
        return {
            "status": "invalid",
            "reason": "incident payload schema validation failed",
            "errors": errors,
            "incident_fired": False,
        }

    if dry_run:
        return {
            "status": "dry_run",
            "payload": payload,
            "incident_fired": True,
        }

    run_token = utc_timestamp_token()
    incident_id = f"INC-MON-{run_token}"
    summary_md = render_summary_markdown(payload)

    artifact = write_consumer_artifact(
        consumer_name=CONSUMER_NAME,
        run_token=run_token,
        payload=payload,
        filename="incident.json",
        extra_files=(("summary.md", summary_md),),
        root=root,
    )

    ledger_row = {
        **artifact.ledger_row,
        "incident_id": incident_id,
        "severity": payload["severity"],
        "drift_metric": payload["drift_metric"],
        "breach_types": [b["type"] for b in breaches],
    }
    append_consumer_ledger(CONSUMER_NAME, ledger_row, root=root)

    return {
        "status": "ok",
        "artifact_path": artifact.artifact_path.as_posix(),
        "run_token": run_token,
        "incident_id": incident_id,
        "severity": payload["severity"],
        "incident_fired": True,
        "breaches": breaches,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Decision report regression monitor")
    p.add_argument(
        "--K",
        type=int,
        default=DEFAULT_K,
        help="Number of trailing summaries to analyze (default 4)",
    )
    p.add_argument("--dry-run", action="store_true", help="Render but do not write")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    outcome = run_monitor(K=args.K, dry_run=args.dry_run)
    print(json.dumps({k: v for k, v in outcome.items() if k != "payload"}, sort_keys=True, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
