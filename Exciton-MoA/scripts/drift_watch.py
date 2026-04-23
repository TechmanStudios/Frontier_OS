# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""Drift-watch consumer (umbrella experiment #5).

Compares the recent distribution of two ledger fields (``consensus_diagnosis``
and ``coupling_consensus``) to pinned baselines from :mod:`baseline_registry`.
When total-variation drift exceeds a threshold, the drift-watch writes an
``incident_report`` artifact and sets ``state.safety_clamp = "hold"`` so the
next snowball decision falls back to ``hold`` regardless of what the
optimization layer wants.

When drift returns under threshold on a subsequent run, the clamp is cleared.
Explicit operator override can also clear the clamp by deleting the state
key manually (the ``clear-incident`` CLI flag is a future extension).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from agent_handoff_schemas import SCHEMA_VERSIONS, validate_incident_report
from baseline_registry import (
    counts_from_rows,
    distribution_drift,
    is_over_threshold,
    load_baseline,
)
from snowball_consumer import (
    append_consumer_ledger,
    load_ledger_tail,
    utc_timestamp_token,
    utcnow_iso,
    write_consumer_artifact,
)
from snowball_experiment import SNOWBALL_DIR, load_state, save_state, state_lock

CONSUMER_NAME = "drift_watch"
STATE_LOCK_PATH = SNOWBALL_DIR / "state.lock"

# Baseline IDs + ledger fields they watch.
WATCH_FIELDS: tuple[tuple[str, str], ...] = (
    ("diagnosis_distribution_v1", "consensus_diagnosis"),
    ("coupling_distribution_v1", "coupling_consensus"),
)

DEFAULT_THRESHOLD = 0.35
DEFAULT_WINDOW = 12


def _severity_for(drift: float, threshold: float) -> str:
    if drift <= threshold:
        return "info"
    if drift <= threshold * 1.5:
        return "warn"
    return "critical"


def build_incident_report(
    *,
    breaches: list[dict[str, Any]],
    baseline_ids: list[str],
    run_dirs_observed: list[str],
    threshold: float,
) -> dict[str, Any]:
    worst = max(breaches, key=lambda b: b["drift"])
    severity = _severity_for(worst["drift"], threshold)
    return {
        "schema_version": SCHEMA_VERSIONS["incident_report"],
        "kind": "telemetry_drift",
        "severity": severity,
        "drift_metric": worst["drift"],
        "threshold": threshold,
        "baseline_id": worst["baseline_id"],
        "run_dirs_observed": run_dirs_observed,
        "recommended_action": "clamp regime to hold until distributions return under threshold",
        "generated_utc": utcnow_iso(),
        "breaches": breaches,
        "baseline_ids_watched": baseline_ids,
    }


def render_summary_markdown(payload: dict[str, Any], *, clamp_applied: bool) -> str:
    lines = [
        "# Drift watch",
        "",
        f"- kind: {payload['kind']}",
        f"- severity: {payload['severity']}",
        f"- threshold: {payload['threshold']}",
        f"- worst drift metric: {payload['drift_metric']}",
        f"- safety clamp applied: {'yes' if clamp_applied else 'no'}",
        f"- generated (UTC): {payload['generated_utc']}",
        "",
        "## Breaches",
        "",
    ]
    for b in payload["breaches"]:
        lines.append(f"- {b['baseline_id']} (field={b['field']}): drift={b['drift']}")
    return "\n".join(lines) + "\n"


def _apply_safety_clamp(*, incident_id: str, clear: bool) -> dict[str, Any] | None:
    """Set or clear ``state.safety_clamp``. Returns the previous value."""
    with state_lock(STATE_LOCK_PATH):
        state = load_state()
        previous = state.get("safety_clamp")
        if clear:
            if "safety_clamp" in state:
                state["safety_clamp"] = None
                state["safety_clamp_updated_utc"] = utcnow_iso()
                state["safety_clamp_incident_id"] = None
        else:
            state["safety_clamp"] = "hold"
            state["safety_clamp_incident_id"] = incident_id
            state["safety_clamp_updated_utc"] = utcnow_iso()
        save_state(state)
    return previous


def evaluate_drift(
    rows: list[dict[str, Any]],
    *,
    threshold: float,
    baselines_root: Path | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Return ``(all_measurements, baseline_ids_found)``.

    Each measurement: ``{baseline_id, field, drift, counts, baseline}``.
    Baselines that are missing on disk are skipped.
    """
    measurements: list[dict[str, Any]] = []
    found_ids: list[str] = []
    for baseline_id, field in WATCH_FIELDS:
        baseline = (
            load_baseline(baseline_id, root=baselines_root)
            if baselines_root is not None
            else load_baseline(baseline_id)
        )
        if not baseline or "counts" not in baseline:
            continue
        found_ids.append(baseline_id)
        counts = counts_from_rows(rows, field=field)
        drift = distribution_drift(counts, baseline["counts"])
        measurements.append(
            {
                "baseline_id": baseline_id,
                "field": field,
                "drift": drift,
                "counts": counts,
                "baseline": dict(baseline["counts"]),
                "over_threshold": is_over_threshold(drift, threshold),
            }
        )
    return measurements, found_ids


def run_drift_watch(
    *,
    window: int = DEFAULT_WINDOW,
    threshold: float = DEFAULT_THRESHOLD,
    dry_run: bool = False,
    baselines_root: Path | None = None,
) -> dict[str, Any]:
    rows = load_ledger_tail(window)
    if not rows:
        return {"status": "noop", "reason": "ledger empty"}
    measurements, baseline_ids = evaluate_drift(rows, threshold=threshold, baselines_root=baselines_root)
    if not measurements:
        return {
            "status": "noop",
            "reason": "no baselines present under working_data/snowball/baselines/",
            "window": window,
        }
    breaches = [m for m in measurements if m["over_threshold"]]
    run_dirs = [str(r.get("run_dir") or "") for r in rows if r.get("run_dir")]
    if not breaches:
        if dry_run:
            return {
                "status": "dry_run",
                "clean": True,
                "measurements": measurements,
            }
        # Clear any stale clamp.
        previous = _apply_safety_clamp(incident_id="", clear=True)
        return {
            "status": "ok",
            "clean": True,
            "measurements": measurements,
            "previous_safety_clamp": previous,
        }
    payload = build_incident_report(
        breaches=breaches,
        baseline_ids=baseline_ids,
        run_dirs_observed=run_dirs,
        threshold=threshold,
    )
    ok, errors = validate_incident_report(payload)
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
    incident_id = f"INC-{run_token}"
    previous = _apply_safety_clamp(incident_id=incident_id, clear=False)
    summary_md = render_summary_markdown(payload, clamp_applied=True)
    artifact = write_consumer_artifact(
        consumer_name=CONSUMER_NAME,
        run_token=run_token,
        payload=payload,
        filename="incident.json",
        extra_files=(("summary.md", summary_md),),
    )
    ledger_row = {
        **artifact.ledger_row,
        "incident_id": incident_id,
        "severity": payload["severity"],
        "drift_metric": payload["drift_metric"],
    }
    append_consumer_ledger(CONSUMER_NAME, ledger_row)
    return {
        "status": "ok",
        "artifact_path": artifact.artifact_path.as_posix(),
        "run_token": run_token,
        "incident_id": incident_id,
        "severity": payload["severity"],
        "previous_safety_clamp": previous,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Drift-watch consumer")
    p.add_argument("--window", type=int, default=DEFAULT_WINDOW, help="Ledger rows to inspect")
    p.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help="TV drift threshold")
    p.add_argument("--dry-run", action="store_true", help="Validate and print but do not write")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    outcome = run_drift_watch(window=args.window, threshold=args.threshold, dry_run=args.dry_run)
    print(json.dumps(outcome, sort_keys=True, indent=2, default=str))
    return 0 if outcome.get("status") in {"ok", "dry_run", "noop"} else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
