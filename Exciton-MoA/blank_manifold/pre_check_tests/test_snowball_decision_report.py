# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""Tests for the snowball decision-report consumer (Phase D D3)."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

EXCITON_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = EXCITON_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

snowball_decision_report = importlib.import_module("snowball_decision_report")
snowball_experiment = importlib.import_module("snowball_experiment")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        for row in rows:
            fp.write(json.dumps(row, sort_keys=True) + "\n")


def _seed_consumer_artifact(consumers_root: Path, name: str, token: str, filename: str, payload: dict) -> Path:
    base = consumers_root / name / token
    base.mkdir(parents=True, exist_ok=True)
    path = base / filename
    path.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")
    return path


def _seed_state(state_path: Path, **overrides) -> None:
    state = snowball_experiment.default_state()
    state.update(overrides)
    state_path.write_text(json.dumps(state, sort_keys=True, indent=2), encoding="utf-8")


def test_run_decision_report_with_full_inputs(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    _write_jsonl(
        ledger_path,
        [
            {
                "origin": "daily",
                "regime": "explore",
                "natural_entries": 4,
                "started_utc": "2026-06-01T00:00:00Z",
            },
            {
                "origin": "daily",
                "regime": "explore",
                "natural_entries": 7,
                "started_utc": "2026-06-02T00:00:00Z",
            },
            {
                "origin": "daily",
                "regime": "exploit",
                "natural_entries": 3,
                "started_utc": "2026-06-03T00:00:00Z",
            },
        ],
    )
    consumers_root = tmp_path / "consumers"
    _seed_consumer_artifact(
        consumers_root,
        "arm_promotion",
        "20260601T000000Z",
        "promotion.json",
        {
            "schema_version": 1,
            "msf": {
                "default_arm": "treatment",
                "mean_delta": 0.7,
                "paired_count": 10,
                "source_token": "tok",
                "updated_utc": "2026-06-01T00:00:00Z",
                "status": "favors_treatment",
            },
            "posture": {
                "default_arm": None,
                "mean_delta": 0.0,
                "paired_count": 0,
                "source_token": "tok",
                "updated_utc": "2026-06-01T00:00:00Z",
                "status": "insufficient_evidence",
            },
            "generated_utc": "2026-06-01T00:00:00Z",
        },
    )
    _seed_consumer_artifact(
        consumers_root,
        "lesson_advisory_writer",
        "20260601T000000Z",
        "advisory.json",
        {
            "clamp": {
                "applicable_pockets": ["locA=0.50,locB=0.57,drift=0.06"],
                "recommended_profile_counts": {"weak": 2},
                "source_lesson_token": "20260530T000000Z",
            },
        },
    )
    state_path = tmp_path / "state.json"
    _seed_state(state_path)
    outcome = snowball_decision_report.run_decision_report(
        ledger_tail=10,
        dry_run=False,
        consumers_root=consumers_root,
        ledger_path=ledger_path,
        state_path=state_path,
    )
    assert outcome["status"] == "ok"
    artifact = Path(outcome["artifact_path"])
    summary = json.loads(artifact.read_text(encoding="utf-8"))
    assert summary["ledger_rows_considered"] == 3
    assert summary["regime_counts"] == {"explore": 2, "exploit": 1}
    assert summary["msf_promotion"]["status"] == "favors_treatment"
    assert summary["msf_promotion"]["default_arm"] == "treatment"
    assert summary["posture_promotion"]["status"] == "insufficient_evidence"
    assert summary["advisory_clamp"]["recommended_profile_counts"] == {"weak": 2}
    assert summary["advisory_clamp"]["applicable_pocket_count"] == 1
    assert summary["safety_clamp"]["active"] is False
    # top_natural_entries sorted by descending natural_entries
    assert summary["top_natural_entries"][0]["natural_entries"] == 7
    report_path = Path(outcome["report_path"])
    assert report_path.exists()
    body = report_path.read_text(encoding="utf-8")
    assert "Snowball Decision Report" in body
    assert "favors_treatment" in body
    # Stable ledger row.
    ledger_consumer = consumers_root / "snowball_decision_report" / "ledger.jsonl"
    rows = [
        json.loads(line)
        for line in ledger_consumer.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    assert rows[0]["msf_status"] == "favors_treatment"


def test_run_decision_report_degrades_gracefully_with_no_inputs(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"  # missing
    consumers_root = tmp_path / "consumers"
    state_path = tmp_path / "state.json"  # missing
    outcome = snowball_decision_report.run_decision_report(
        ledger_tail=10,
        dry_run=False,
        consumers_root=consumers_root,
        ledger_path=ledger_path,
        state_path=state_path,
    )
    assert outcome["status"] == "ok"
    artifact = Path(outcome["artifact_path"])
    summary = json.loads(artifact.read_text(encoding="utf-8"))
    assert summary["ledger_rows_considered"] == 0
    assert summary["regime_counts"] == {}
    assert summary["msf_promotion"]["status"] is None
    assert summary["posture_promotion"]["status"] is None
    assert summary["advisory_clamp"]["applicable_pocket_count"] == 0
    assert summary["top_natural_entries"] == []


def test_run_decision_report_dry_run_emits_no_artifact(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    _write_jsonl(ledger_path, [{"origin": "daily", "regime": "hold"}])
    consumers_root = tmp_path / "consumers"
    state_path = tmp_path / "state.json"
    outcome = snowball_decision_report.run_decision_report(
        ledger_tail=10,
        dry_run=True,
        consumers_root=consumers_root,
        ledger_path=ledger_path,
        state_path=state_path,
    )
    assert outcome["status"] == "dry_run"
    assert "summary" in outcome
    assert not (consumers_root / "snowball_decision_report").exists()


def test_summary_json_keys_are_stable(tmp_path):
    consumers_root = tmp_path / "consumers"
    ledger_path = tmp_path / "ledger.jsonl"
    state_path = tmp_path / "state.json"
    _seed_state(state_path)
    outcome = snowball_decision_report.run_decision_report(
        ledger_tail=10,
        dry_run=True,
        consumers_root=consumers_root,
        ledger_path=ledger_path,
        state_path=state_path,
    )
    expected = {
        "schema_version",
        "origin",
        "generated_utc",
        "ledger_rows_considered",
        "regime_counts",
        "top_natural_entries",
        "msf_promotion",
        "posture_promotion",
        "advisory_clamp",
        "safety_clamp",
        "sources",
    }
    assert set(outcome["summary"].keys()) == expected


def test_safety_clamp_surfaces_when_state_has_incident(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    _write_jsonl(ledger_path, [])
    consumers_root = tmp_path / "consumers"
    state_path = tmp_path / "state.json"
    _seed_state(
        state_path,
        safety_clamp={"incident_id": "INC-42", "reason": "synchronicity"},
        safety_clamp_incident_id="INC-42",
    )
    outcome = snowball_decision_report.run_decision_report(
        ledger_tail=10,
        dry_run=True,
        consumers_root=consumers_root,
        ledger_path=ledger_path,
        state_path=state_path,
    )
    assert outcome["summary"]["safety_clamp"]["active"] is True
    assert outcome["summary"]["safety_clamp"]["incident_id"] == "INC-42"


def test_main_cli_dry_run_returns_zero(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(snowball_decision_report, "LEDGER_PATH", tmp_path / "missing.jsonl")
    monkeypatch.setattr(snowball_decision_report, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(snowball_decision_report, "CONSUMERS_DIR", tmp_path / "consumers")
    rc = snowball_decision_report.main(["--dry-run", "--ledger-tail", "5"])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"status"' in out
