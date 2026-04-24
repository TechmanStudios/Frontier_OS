# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""Tests for the arm-promotion engine consumer (Phase D D1)."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

EXCITON_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = EXCITON_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

agent_handoff_schemas = importlib.import_module("agent_handoff_schemas")
arm_promotion = importlib.import_module("arm_promotion")
snowball_experiment = importlib.import_module("snowball_experiment")


def _patch_state_path(monkeypatch, tmp_path):
    state_path = tmp_path / "state.json"
    lock_path = tmp_path / "state.lock"
    monkeypatch.setattr(snowball_experiment, "STATE_PATH", state_path)
    monkeypatch.setattr(arm_promotion, "STATE_LOCK_PATH", lock_path)

    def _load(state_path_arg=state_path):
        return snowball_experiment.load_state(state_path=state_path_arg)

    def _save(state, state_path_arg=state_path):
        snowball_experiment.save_state(state, state_path=state_path_arg)

    monkeypatch.setattr(arm_promotion, "load_state", _load)
    monkeypatch.setattr(arm_promotion, "save_state", _save)
    return state_path


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        for row in rows:
            fp.write(json.dumps(row, sort_keys=True) + "\n")


def _delta(value: float) -> dict:
    return {"delta_natural_entries": value, "delta_observe_only_streak": 0}


# ---------------------------------------------------------------------------
# evaluate_arm: rolling window + threshold semantics
# ---------------------------------------------------------------------------


def test_evaluate_arm_insufficient_evidence_when_below_window():
    block = arm_promotion.evaluate_arm(
        [_delta(2.0)] * 5,
        window=10,
        threshold=0.5,
        source_token="tok",
    )
    assert block["status"] == "insufficient_evidence"
    assert block["default_arm"] is None
    assert block["paired_count"] == 5


def test_evaluate_arm_favors_treatment_at_positive_threshold():
    block = arm_promotion.evaluate_arm(
        [_delta(0.5)] * 10,
        window=10,
        threshold=0.5,
        source_token="tok",
    )
    assert block["status"] == "favors_treatment"
    assert block["default_arm"] == "treatment"
    assert block["mean_delta"] == pytest.approx(0.5)
    assert block["paired_count"] == 10


def test_evaluate_arm_favors_control_at_negative_threshold():
    block = arm_promotion.evaluate_arm(
        [_delta(-0.5)] * 10,
        window=10,
        threshold=0.5,
        source_token="tok",
    )
    assert block["status"] == "favors_control"
    assert block["default_arm"] == "control"


def test_evaluate_arm_no_lift_just_below_threshold():
    block = arm_promotion.evaluate_arm(
        [_delta(0.49)] * 10,
        window=10,
        threshold=0.5,
        source_token="tok",
    )
    assert block["status"] == "no_lift"
    assert block["default_arm"] is None


def test_evaluate_arm_uses_only_window_tail():
    rows = [_delta(-5.0)] * 5 + [_delta(1.0)] * 10
    block = arm_promotion.evaluate_arm(
        rows, window=10, threshold=0.5, source_token="tok"
    )
    # Window tail averages +1.0, ignoring the leading regression rows.
    assert block["mean_delta"] == pytest.approx(1.0)
    assert block["status"] == "favors_treatment"


# ---------------------------------------------------------------------------
# build_promotion_payload + schema validation
# ---------------------------------------------------------------------------


def test_build_promotion_payload_validates_against_schema(tmp_path):
    msf_path = tmp_path / "msf.jsonl"
    posture_path = tmp_path / "posture.jsonl"
    _write_jsonl(msf_path, [_delta(1.0)] * 10)
    _write_jsonl(posture_path, [_delta(-1.0)] * 10)
    payload = arm_promotion.build_promotion_payload(
        window=10,
        threshold=0.5,
        msf_path=msf_path,
        posture_path=posture_path,
        source_token="tok",
    )
    ok, errors = agent_handoff_schemas.validate_arm_promotion(
        {
            "schema_version": payload["schema_version"],
            "msf": payload["msf"],
            "posture": payload["posture"],
            "generated_utc": payload["generated_utc"],
        }
    )
    assert ok, errors
    assert payload["msf"]["status"] == "favors_treatment"
    assert payload["posture"]["status"] == "favors_control"


def test_build_promotion_payload_handles_missing_files(tmp_path):
    payload = arm_promotion.build_promotion_payload(
        window=10,
        threshold=0.5,
        msf_path=tmp_path / "missing_msf.jsonl",
        posture_path=tmp_path / "missing_posture.jsonl",
        source_token="tok",
    )
    assert payload["msf"]["status"] == "insufficient_evidence"
    assert payload["posture"]["status"] == "insufficient_evidence"
    assert payload["msf"]["paired_count"] == 0


# ---------------------------------------------------------------------------
# run_arm_promotion: dry_run, state writeback, ledger
# ---------------------------------------------------------------------------


def test_run_arm_promotion_dry_run_does_not_write(tmp_path, monkeypatch):
    state_path = _patch_state_path(monkeypatch, tmp_path)
    msf_path = tmp_path / "msf.jsonl"
    posture_path = tmp_path / "posture.jsonl"
    _write_jsonl(msf_path, [_delta(1.0)] * 10)
    _write_jsonl(posture_path, [_delta(0.0)] * 10)
    consumers_root = tmp_path / "consumers"
    outcome = arm_promotion.run_arm_promotion(
        window=10,
        threshold=0.5,
        dry_run=True,
        consumers_root=consumers_root,
        msf_path=msf_path,
        posture_path=posture_path,
    )
    assert outcome["status"] == "dry_run"
    assert not state_path.exists()
    assert not (consumers_root / arm_promotion.CONSUMER_NAME).exists()


def test_run_arm_promotion_writes_state_and_artifact(tmp_path, monkeypatch):
    state_path = _patch_state_path(monkeypatch, tmp_path)
    msf_path = tmp_path / "msf.jsonl"
    posture_path = tmp_path / "posture.jsonl"
    _write_jsonl(msf_path, [_delta(1.0)] * 10)
    _write_jsonl(posture_path, [_delta(-1.0)] * 10)
    consumers_root = tmp_path / "consumers"
    outcome = arm_promotion.run_arm_promotion(
        window=10,
        threshold=0.5,
        dry_run=False,
        consumers_root=consumers_root,
        msf_path=msf_path,
        posture_path=posture_path,
    )
    assert outcome["status"] == "ok"
    assert outcome["msf_status"] == "favors_treatment"
    assert outcome["posture_status"] == "favors_control"
    artifact = Path(outcome["artifact_path"])
    assert artifact.exists()
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["msf"]["default_arm"] == "treatment"
    assert payload["posture"]["default_arm"] == "control"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    promotion = state["arm_promotion"]
    assert promotion["msf"]["default_arm"] == "treatment"
    assert promotion["posture"]["default_arm"] == "control"
    ledger_path = (
        consumers_root / arm_promotion.CONSUMER_NAME / "ledger.jsonl"
    )
    assert ledger_path.exists()
    rows = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    assert rows[0]["msf_status"] == "favors_treatment"
    assert rows[0]["posture_status"] == "favors_control"


def test_run_arm_promotion_is_reversible(tmp_path, monkeypatch):
    state_path = _patch_state_path(monkeypatch, tmp_path)
    msf_path = tmp_path / "msf.jsonl"
    posture_path = tmp_path / "posture.jsonl"
    consumers_root = tmp_path / "consumers"
    # First pass: clear treatment win.
    _write_jsonl(msf_path, [_delta(1.0)] * 10)
    _write_jsonl(posture_path, [_delta(1.0)] * 10)
    arm_promotion.run_arm_promotion(
        window=10,
        threshold=0.5,
        dry_run=False,
        consumers_root=consumers_root,
        msf_path=msf_path,
        posture_path=posture_path,
    )
    state_after_first = json.loads(state_path.read_text(encoding="utf-8"))
    assert state_after_first["arm_promotion"]["msf"]["default_arm"] == "treatment"
    # Second pass with regression -> falls back to no_lift, default_arm=None.
    _write_jsonl(msf_path, [_delta(0.0)] * 10)
    _write_jsonl(posture_path, [_delta(0.0)] * 10)
    arm_promotion.run_arm_promotion(
        window=10,
        threshold=0.5,
        dry_run=False,
        consumers_root=consumers_root,
        msf_path=msf_path,
        posture_path=posture_path,
    )
    state_after_second = json.loads(state_path.read_text(encoding="utf-8"))
    assert state_after_second["arm_promotion"]["msf"]["status"] == "no_lift"
    assert state_after_second["arm_promotion"]["msf"]["default_arm"] is None


def test_run_arm_promotion_arms_are_independent(tmp_path, monkeypatch):
    _patch_state_path(monkeypatch, tmp_path)
    msf_path = tmp_path / "msf.jsonl"
    posture_path = tmp_path / "posture.jsonl"
    _write_jsonl(msf_path, [_delta(1.0)] * 10)
    _write_jsonl(posture_path, [_delta(0.0)] * 5)  # below window
    consumers_root = tmp_path / "consumers"
    outcome = arm_promotion.run_arm_promotion(
        window=10,
        threshold=0.5,
        dry_run=False,
        consumers_root=consumers_root,
        msf_path=msf_path,
        posture_path=posture_path,
    )
    assert outcome["msf_status"] == "favors_treatment"
    assert outcome["posture_status"] == "insufficient_evidence"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_main_cli_dry_run_returns_zero(tmp_path, monkeypatch, capsys):
    _patch_state_path(monkeypatch, tmp_path)
    monkeypatch.setattr(arm_promotion, "MSF_AB_OUTCOMES_PATH", tmp_path / "msf.jsonl")
    monkeypatch.setattr(
        arm_promotion, "POSTURE_AB_OUTCOMES_PATH", tmp_path / "posture.jsonl"
    )
    monkeypatch.setattr(
        arm_promotion, "CONSUMERS_DIR", tmp_path / "consumers"
    )
    rc = arm_promotion.main(["--dry-run", "--window", "10", "--threshold", "0.5"])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"status"' in out
