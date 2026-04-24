# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""Snowball Decision Report consumer (umbrella experiment, Phase D D3).

Reads the snowball ledger tail, the latest ``arm_promotion`` artifact, the
latest ``lesson_advisory_writer`` artifact, and the current
``state.json``. Renders a human-readable ``report.md`` plus a stable
``summary.json`` so a weekly workflow can publish "what the snowball is
deciding right now" without blocking the runner.

Non-blocking by design: any missing input is treated as "nothing to report
yet" and the consumer still emits a (mostly empty) report so downstream
artifact pipelines remain happy.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from snowball_consumer import (
    CONSUMERS_DIR,
    append_consumer_ledger,
    consumer_dir,
    load_ledger_tail,
    utc_timestamp_token,
    utcnow_iso,
    write_consumer_artifact,
)
from snowball_experiment import LEDGER_PATH, STATE_PATH, load_state

CONSUMER_NAME = "snowball_decision_report"
DEFAULT_LEDGER_TAIL = 60


def _find_latest_artifact(consumer_name: str, filename: str, *, root: Path) -> Path | None:
    base = consumer_dir(consumer_name, root=root)
    if not base.exists():
        return None
    candidates = sorted(
        (p for p in base.glob(f"*/{filename}") if p.is_file()),
        key=lambda p: p.parent.name,
    )
    return candidates[-1] if candidates else None


def _safe_read_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def build_summary(
    *,
    ledger_rows: list[dict[str, Any]],
    promotion: dict[str, Any] | None,
    advisory: dict[str, Any] | None,
    state: dict[str, Any] | None,
) -> dict[str, Any]:
    regime_counts = Counter(str(row.get("regime") or "unknown") for row in ledger_rows)
    daily_rows = [row for row in ledger_rows if row.get("origin") == "daily"]
    top_natural = sorted(
        (
            (
                str(row.get("started_utc") or row.get("finished_utc") or "?"),
                int(row.get("natural_entries") or 0),
            )
            for row in daily_rows
        ),
        key=lambda kv: (-kv[1], kv[0]),
    )[:5]
    msf_block = (promotion or {}).get("msf") if isinstance(promotion, dict) else None
    posture_block = (promotion or {}).get("posture") if isinstance(promotion, dict) else None
    clamp = (advisory or {}).get("clamp") if isinstance(advisory, dict) else None
    safety = (state or {}).get("safety_clamp") if isinstance(state, dict) else None
    return {
        "schema_version": 1,
        "origin": CONSUMER_NAME,
        "generated_utc": utcnow_iso(),
        "ledger_rows_considered": len(ledger_rows),
        "regime_counts": dict(regime_counts),
        "top_natural_entries": [
            {"started_utc": s, "natural_entries": n} for s, n in top_natural
        ],
        "msf_promotion": {
            "status": (msf_block or {}).get("status") if isinstance(msf_block, dict) else None,
            "default_arm": (msf_block or {}).get("default_arm")
            if isinstance(msf_block, dict)
            else None,
            "mean_delta": (msf_block or {}).get("mean_delta")
            if isinstance(msf_block, dict)
            else None,
            "paired_count": (msf_block or {}).get("paired_count")
            if isinstance(msf_block, dict)
            else None,
        },
        "posture_promotion": {
            "status": (posture_block or {}).get("status")
            if isinstance(posture_block, dict)
            else None,
            "default_arm": (posture_block or {}).get("default_arm")
            if isinstance(posture_block, dict)
            else None,
            "mean_delta": (posture_block or {}).get("mean_delta")
            if isinstance(posture_block, dict)
            else None,
            "paired_count": (posture_block or {}).get("paired_count")
            if isinstance(posture_block, dict)
            else None,
        },
        "advisory_clamp": {
            "applicable_pocket_count": len((clamp or {}).get("applicable_pockets") or [])
            if isinstance(clamp, dict)
            else 0,
            "recommended_profile_counts": (clamp or {}).get("recommended_profile_counts") or {}
            if isinstance(clamp, dict)
            else {},
            "source_lesson_token": (clamp or {}).get("source_lesson_token")
            if isinstance(clamp, dict)
            else None,
        },
        "safety_clamp": {
            "active": bool(safety),
            "incident_id": (safety or {}).get("incident_id") if isinstance(safety, dict) else None,
        },
    }


def render_report_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Snowball Decision Report",
        "",
        f"- generated (UTC): {summary['generated_utc']}",
        f"- ledger rows considered: {summary['ledger_rows_considered']}",
        "",
        "## Regime distribution (window)",
        "",
    ]
    if summary["regime_counts"]:
        for regime, count in sorted(summary["regime_counts"].items()):
            lines.append(f"- {regime}: {count}")
    else:
        lines.append("- _(no rows)_")
    lines += [
        "",
        "## MSF arm promotion",
        "",
        f"- status: {summary['msf_promotion']['status']}",
        f"- default_arm: {summary['msf_promotion']['default_arm']}",
        f"- mean_delta: {summary['msf_promotion']['mean_delta']}",
        f"- paired_count: {summary['msf_promotion']['paired_count']}",
        "",
        "## Posture arm promotion",
        "",
        f"- status: {summary['posture_promotion']['status']}",
        f"- default_arm: {summary['posture_promotion']['default_arm']}",
        f"- mean_delta: {summary['posture_promotion']['mean_delta']}",
        f"- paired_count: {summary['posture_promotion']['paired_count']}",
        "",
        "## Advisory clamp",
        "",
        f"- applicable pockets: {summary['advisory_clamp']['applicable_pocket_count']}",
        f"- recommended profile counts: {summary['advisory_clamp']['recommended_profile_counts']}",
        f"- source lesson token: {summary['advisory_clamp']['source_lesson_token']}",
        "",
        "## Safety clamp",
        "",
        f"- active: {summary['safety_clamp']['active']}",
        f"- incident id: {summary['safety_clamp']['incident_id']}",
        "",
        "## Top natural-entry runs (daily, window)",
        "",
    ]
    if summary["top_natural_entries"]:
        for row in summary["top_natural_entries"]:
            lines.append(f"- {row['started_utc']}: {row['natural_entries']}")
    else:
        lines.append("- _(no daily rows in window)_")
    return "\n".join(lines) + "\n"


def run_decision_report(
    *,
    ledger_tail: int = DEFAULT_LEDGER_TAIL,
    dry_run: bool = False,
    consumers_root: Path | None = None,
    ledger_path: Path | None = None,
    state_path: Path | None = None,
) -> dict[str, Any]:
    root = consumers_root if consumers_root is not None else CONSUMERS_DIR
    ledger_in = ledger_path if ledger_path is not None else LEDGER_PATH
    rows = load_ledger_tail(ledger_tail, ledger_path=ledger_in)
    promotion_path = _find_latest_artifact("arm_promotion", "promotion.json", root=root)
    advisory_path = _find_latest_artifact("lesson_advisory_writer", "advisory.json", root=root)
    promotion = _safe_read_json(promotion_path)
    advisory = _safe_read_json(advisory_path)
    state_in = state_path if state_path is not None else STATE_PATH
    try:
        state = load_state(state_path=state_in)
    except Exception:  # pragma: no cover - defensive: load_state already tolerates missing file
        state = None
    summary = build_summary(
        ledger_rows=rows,
        promotion=promotion,
        advisory=advisory,
        state=state if isinstance(state, dict) else None,
    )
    summary["sources"] = {
        "ledger_path": ledger_in.as_posix(),
        "promotion_path": promotion_path.as_posix() if promotion_path else None,
        "advisory_path": advisory_path.as_posix() if advisory_path else None,
        "state_path": state_in.as_posix(),
    }
    report_md = render_report_markdown(summary)
    if dry_run:
        return {"status": "dry_run", "summary": summary, "report_md": report_md}
    run_token = utc_timestamp_token()
    artifact = write_consumer_artifact(
        consumer_name=CONSUMER_NAME,
        run_token=run_token,
        payload=summary,
        filename="summary.json",
        extra_files=(("report.md", report_md),),
        root=root,
    )
    ledger_row = {
        **artifact.ledger_row,
        "ledger_rows_considered": summary["ledger_rows_considered"],
        "msf_status": summary["msf_promotion"]["status"],
        "posture_status": summary["posture_promotion"]["status"],
    }
    append_consumer_ledger(CONSUMER_NAME, ledger_row, root=root)
    return {
        "status": "ok",
        "artifact_path": artifact.artifact_path.as_posix(),
        "report_path": (artifact.artifact_path.parent / "report.md").as_posix(),
        "run_token": run_token,
        "ledger_rows_considered": summary["ledger_rows_considered"],
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Snowball decision report consumer")
    p.add_argument(
        "--ledger-tail",
        type=int,
        default=DEFAULT_LEDGER_TAIL,
        help="Number of trailing ledger rows to consider (default 60)",
    )
    p.add_argument("--dry-run", action="store_true", help="Render but do not write")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    outcome = run_decision_report(ledger_tail=args.ledger_tail, dry_run=args.dry_run)
    print(json.dumps({k: v for k, v in outcome.items() if k != "report_md"}, sort_keys=True, indent=2, default=str))
    return 0 if outcome.get("status") in {"ok", "dry_run", "noop"} else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
