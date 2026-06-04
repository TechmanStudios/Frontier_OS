# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""Tests for the decision report monitor consumer (Phase E E1)."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

EXCITON_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = EXCITON_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

decision_report_monitor = importlib.import_module("decision_report_monitor")


def _seed_decision_report_summary(
    consumers_root: Path,
    token: str,
    payload: dict,
) -> Path:
    base = consumers_root / "snowball_decision_report" / token
    base.mkdir(parents=True, exist_ok=True)
    path = base / "summary.json"
    path.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")
    return path


def test_run_monitor_no_summaries(tmp_path):
    outcome = decision_report_monitor.run_monitor(
        K=4,
        dry_run=False,
        consumers_root=tmp_path,
    )
    assert outcome["status"] == "noop"
    assert outcome["incident_fired"] is False


def test_run_monitor_no_regressions(tmp_path):
    # Two weeks of data, no regressions
    _seed_decision_report_summary(
        tmp_path,
        "20260601T000000Z",
        {
            "msf_promotion": {"status": "favors_treatment", "mean_delta": 0.8},
            "regime_counts": {"explore": 5, "exploit": 5, "hold": 1},
        },
    )
    _seed_decision_report_summary(
        tmp_path,
        "20260608T000000Z",
        {
            "msf_promotion": {"status": "favors_treatment", "mean_delta": 0.9},
            "regime_counts": {"explore": 4, "exploit": 6, "hold": 1},
        },
    )
    outcome = decision_report_monitor.run_monitor(
        K=4,
        dry_run=False,
        consumers_root=tmp_path,
    )
    assert outcome["status"] == "ok"
    assert outcome["incident_fired"] is False
    assert "no regressions found" in outcome["reason"]


def test_run_monitor_msf_promotion_flip(tmp_path):
    _seed_decision_report_summary(
        tmp_path,
        "20260601T000000Z",
        {
            "msf_promotion": {"status": "favors_treatment", "mean_delta": 0.8},
            "regime_counts": {"explore": 5, "exploit": 5},
        },
    )
    _seed_decision_report_summary(
        tmp_path,
        "20260608T000000Z",
        {
            "msf_promotion": {"status": "favors_control", "mean_delta": -0.8},
            "regime_counts": {"explore": 5, "exploit": 5},
        },
    )
    outcome = decision_report_monitor.run_monitor(
        K=4,
        dry_run=False,
        consumers_root=tmp_path,
    )
    assert outcome["status"] == "ok"
    assert outcome["incident_fired"] is True
    assert outcome["severity"] == "critical"
    
    # Check created files
    artifact_path = Path(outcome["artifact_path"])
    assert artifact_path.exists()
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert len(payload["breaches"]) == 2
    types = [b["type"] for b in payload["breaches"]]
    assert "msf_promotion_flip" in types
    assert "mean_delta_drop" in types
    assert payload["drift_metric"] == 1.0
    assert payload["threshold"] == 1.0

    summary_md_path = artifact_path.parent / "summary.md"
    assert summary_md_path.exists()
    assert "flipped from favors_treatment" in summary_md_path.read_text(encoding="utf-8")


def test_run_monitor_mean_delta_drop(tmp_path):
    _seed_decision_report_summary(
        tmp_path,
        "20260601T000000Z",
        {
            "msf_promotion": {"status": "favors_treatment", "mean_delta": 1.5},
            "regime_counts": {"explore": 5, "exploit": 5},
        },
    )
    _seed_decision_report_summary(
        tmp_path,
        "20260608T000000Z",
        {
            "msf_promotion": {"status": "favors_treatment", "mean_delta": 0.4},
            "regime_counts": {"explore": 5, "exploit": 5},
        },
    )
    outcome = decision_report_monitor.run_monitor(
        K=4,
        dry_run=False,
        consumers_root=tmp_path,
    )
    assert outcome["status"] == "ok"
    assert outcome["incident_fired"] is True
    
    payload = json.loads(Path(outcome["artifact_path"]).read_text(encoding="utf-8"))
    assert len(payload["breaches"]) == 1
    assert payload["breaches"][0]["type"] == "mean_delta_drop"
    # drop of 1.1 >= 1.0
    assert abs(payload["drift_metric"] - 1.1) < 1e-5


def test_run_monitor_hold_overuse(tmp_path):
    _seed_decision_report_summary(
        tmp_path,
        "20260601T000000Z",
        {
            "msf_promotion": {"status": "favors_treatment", "mean_delta": 0.8},
            # hold count ratio: 8 / 10 = 0.8 > 0.7
            "regime_counts": {"explore": 1, "exploit": 1, "hold": 8},
        },
    )
    outcome = decision_report_monitor.run_monitor(
        K=4,
        dry_run=False,
        consumers_root=tmp_path,
    )
    assert outcome["status"] == "ok"
    assert outcome["incident_fired"] is True
    
    payload = json.loads(Path(outcome["artifact_path"]).read_text(encoding="utf-8"))
    assert len(payload["breaches"]) == 1
    assert payload["breaches"][0]["type"] == "hold_overuse"
    assert abs(payload["drift_metric"] - 0.8) < 1e-5


def test_run_monitor_multiple_breaches_and_dry_run(tmp_path):
    _seed_decision_report_summary(
        tmp_path,
        "20260601T000000Z",
        {
            "msf_promotion": {"status": "favors_treatment", "mean_delta": 2.0},
            "regime_counts": {"explore": 5, "exploit": 5},
        },
    )
    _seed_decision_report_summary(
        tmp_path,
        "20260608T000000Z",
        {
            "msf_promotion": {"status": "favors_control", "mean_delta": 0.5},
            # flip + drop of 1.5 + hold overuse (8/10 = 0.8)
            "regime_counts": {"explore": 1, "exploit": 1, "hold": 8},
        },
    )
    outcome = decision_report_monitor.run_monitor(
        K=4,
        dry_run=True,
        consumers_root=tmp_path,
    )
    assert outcome["status"] == "dry_run"
    assert outcome["incident_fired"] is True
    assert len(outcome["payload"]["breaches"]) == 3
    # No files written under tmp_path / "decision_report_monitor"
    assert not (tmp_path / "decision_report_monitor").exists()


def test_main_cli_returns_zero(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(decision_report_monitor, "CONSUMERS_DIR", tmp_path)
    _seed_decision_report_summary(
        tmp_path,
        "20260601T000000Z",
        {
            "msf_promotion": {"status": "favors_treatment", "mean_delta": 0.8},
            "regime_counts": {"explore": 5, "exploit": 5},
        },
    )
    rc = decision_report_monitor.main(["--dry-run", "--K", "5"])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"status"' in out
