# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""Phase-4 regression coverage for the agentic umbrella.

Covers the lesson_compiler consumer (umbrella experiment #6) and its
``knowledge_lesson`` schema contract.

No engine subprocess is invoked; all sweep_summary inputs are synthetic.
"""

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
lesson_compiler = importlib.import_module("lesson_compiler")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_sweep(run_dir: Path, rows: list[dict]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "sweep_summary.jsonl"
    with path.open("w", encoding="utf-8") as fp:
        for row in rows:
            fp.write(json.dumps(row, sort_keys=True) + "\n")


def _write_ledger(path: Path, run_dirs: list[Path]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        for i, rd in enumerate(run_dirs):
            row = {
                "origin": "daily",
                "regime": "hold",
                "run_dir": rd.as_posix(),
                "started_utc": f"2026-01-{i + 1:02d}T00:00:00Z",
            }
            fp.write(json.dumps(row, sort_keys=True) + "\n")


def _row(loc_a: float, loc_b: float, drift: float, coupling: str, diagnosis: str) -> dict:
    return {
        "embedding_a_loc": loc_a,
        "embedding_b_loc": loc_b,
        "embedding_drift": drift,
        "paper_synchrony_coupling_posture": coupling,
        "diagnosis_label": diagnosis,
    }


@pytest.fixture()
def umbrella_world(tmp_path):
    runs_root = tmp_path / "runs"
    rd1 = runs_root / "daily" / "20260101T000000Z"
    rd2 = runs_root / "daily" / "20260102T000000Z"
    rd3 = runs_root / "daily" / "20260103T000000Z"
    # Pattern (weak, low_variance_candidate) appears in 3 distinct pockets
    # spread across 3 runs -> qualifies as a lesson.
    _write_sweep(
        rd1,
        [
            _row(0.50, 0.57, 0.06, "weak", "low_variance_candidate"),
            _row(0.50, 0.58, 0.06, "weak", "low_variance_candidate"),
            # Contraindication: same coupling, different diagnosis.
            _row(0.49, 0.57, 0.06, "weak", "threshold_conservative_candidate"),
        ],
    )
    _write_sweep(
        rd2,
        [
            _row(0.50, 0.57, 0.08, "weak", "low_variance_candidate"),
            # A balanced pattern with only 1 pocket -> should NOT qualify.
            _row(0.40, 0.40, 0.00, "balanced", "entered_stabilizer"),
        ],
    )
    _write_sweep(
        rd3,
        [
            # Repeats an existing pocket; should not inflate corroboration.
            _row(0.50, 0.57, 0.06, "weak", "low_variance_candidate"),
        ],
    )
    ledger_path = tmp_path / "ledger.jsonl"
    _write_ledger(ledger_path, [rd1, rd2, rd3])
    consumers_root = tmp_path / "consumers"
    return {
        "ledger_path": ledger_path,
        "consumers_root": consumers_root,
        "run_dirs": [rd1, rd2, rd3],
    }


# ---------------------------------------------------------------------------
# Schema validator
# ---------------------------------------------------------------------------


def _ok_lesson() -> dict:
    return {
        "schema_version": agent_handoff_schemas.SCHEMA_VERSIONS["knowledge_lesson"],
        "lesson_type": "entrainment_stability",
        "corroboration_count": 2,
        "evidence_run_dirs": ["runs/daily/A", "runs/daily/B"],
        "key_findings": "Two pockets converged on a stable diagnosis.",
        "applicable_constraints": ["locA=0.5,locB=0.57,drift=0.06"],
        "contraindications": [],
        "generated_utc": "2026-01-03T00:00:00Z",
    }


def test_validate_knowledge_lesson_accepts_minimal_ok_payload():
    ok, errors = agent_handoff_schemas.validate_knowledge_lesson(_ok_lesson())
    assert ok, errors
    assert errors == []


def test_validate_knowledge_lesson_rejects_corroboration_below_two():
    bad = _ok_lesson()
    bad["corroboration_count"] = 1
    ok, errors = agent_handoff_schemas.validate_knowledge_lesson(bad)
    assert not ok
    assert any("corroboration_count" in e for e in errors)


def test_validate_knowledge_lesson_rejects_unknown_lesson_type():
    bad = _ok_lesson()
    bad["lesson_type"] = "not_a_real_type"
    ok, errors = agent_handoff_schemas.validate_knowledge_lesson(bad)
    assert not ok
    assert any("lesson_type" in e for e in errors)


def test_validate_knowledge_lesson_rejects_missing_evidence():
    bad = _ok_lesson()
    del bad["evidence_run_dirs"]
    ok, errors = agent_handoff_schemas.validate_knowledge_lesson(bad)
    assert not ok
    assert any("evidence_run_dirs" in e for e in errors)


def test_schema_versions_contains_knowledge_lesson():
    assert agent_handoff_schemas.SCHEMA_VERSIONS.get("knowledge_lesson") == 1


# ---------------------------------------------------------------------------
# Aggregation logic
# ---------------------------------------------------------------------------


def test_aggregate_patterns_groups_by_coupling_and_diagnosis(umbrella_world):
    sweep_by_run: list[tuple[str, list[dict]]] = []
    for rd in umbrella_world["run_dirs"]:
        rows = json.loads(
            "[" + ",".join((rd / "sweep_summary.jsonl").read_text().splitlines()) + "]"
        )
        sweep_by_run.append((rd.as_posix(), rows))
    aggregates = lesson_compiler.aggregate_patterns(sweep_by_run)
    weak_low = aggregates[("weak", "low_variance_candidate")]
    # 3 distinct pockets across runs (the rd3 repeat doesn't inflate the set).
    assert len(weak_low["pockets"]) == 3
    # Contraindication pocket from rd1 (same weak coupling, different diagnosis).
    assert "locA=0.49,locB=0.57,drift=0.06" in weak_low["contraindication_pockets"]


# ---------------------------------------------------------------------------
# Consumer end-to-end
# ---------------------------------------------------------------------------


def test_run_lesson_compiler_dry_run_returns_lessons(umbrella_world):
    outcome = lesson_compiler.run_lesson_compiler(
        ledger_tail=10,
        min_corroboration=2,
        dry_run=True,
        ledger_path=umbrella_world["ledger_path"],
        consumers_root=umbrella_world["consumers_root"],
    )
    assert outcome["status"] == "dry_run"
    lesson_types = {p["lesson_type"] for p in outcome["lessons"]}
    assert "entrainment_stability" in lesson_types
    # The single-pocket balanced pattern should be filtered out.
    assert all(p["corroboration_count"] >= 2 for p in outcome["lessons"])
    # Schema validation already ran inside run_lesson_compiler.
    for p in outcome["lessons"]:
        ok, errors = agent_handoff_schemas.validate_knowledge_lesson(p)
        assert ok, errors


def test_run_lesson_compiler_writes_artifact_and_ledger(umbrella_world):
    outcome = lesson_compiler.run_lesson_compiler(
        ledger_tail=10,
        min_corroboration=2,
        dry_run=False,
        ledger_path=umbrella_world["ledger_path"],
        consumers_root=umbrella_world["consumers_root"],
    )
    assert outcome["status"] == "ok"
    artifact_path = Path(outcome["artifact_path"])
    assert artifact_path.exists()
    bundle = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert bundle["schema_versions"]["knowledge_lesson"] == 1
    assert bundle["lessons"]
    summary_path = artifact_path.parent / "summary.md"
    assert summary_path.exists()
    assert "Lesson Compiler" in summary_path.read_text(encoding="utf-8")
    ledger_path = umbrella_world["consumers_root"] / lesson_compiler.CONSUMER_NAME / "ledger.jsonl"
    assert ledger_path.exists()
    rows = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    assert rows[0]["lesson_count"] == outcome["lesson_count"]
    assert rows[0]["max_corroboration"] >= 2


def test_run_lesson_compiler_noop_when_no_sweep_summaries(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    rd = tmp_path / "runs" / "daily" / "20260101T000000Z"
    rd.mkdir(parents=True)
    _write_ledger(ledger_path, [rd])  # no sweep_summary.jsonl written
    outcome = lesson_compiler.run_lesson_compiler(
        ledger_tail=10,
        min_corroboration=2,
        dry_run=True,
        ledger_path=ledger_path,
        consumers_root=tmp_path / "consumers",
    )
    assert outcome["status"] == "noop"


def test_run_lesson_compiler_noop_when_min_corroboration_too_high(umbrella_world):
    outcome = lesson_compiler.run_lesson_compiler(
        ledger_tail=10,
        min_corroboration=99,
        dry_run=True,
        ledger_path=umbrella_world["ledger_path"],
        consumers_root=umbrella_world["consumers_root"],
    )
    assert outcome["status"] == "noop"
    assert "corroboration_count >= 99" in outcome["reason"]


def test_run_lesson_compiler_re_run_appends_second_ledger_row(umbrella_world):
    common = dict(
        ledger_tail=10,
        min_corroboration=2,
        dry_run=False,
        ledger_path=umbrella_world["ledger_path"],
        consumers_root=umbrella_world["consumers_root"],
    )
    o1 = lesson_compiler.run_lesson_compiler(**common)
    o2 = lesson_compiler.run_lesson_compiler(**common)
    assert o1["status"] == o2["status"] == "ok"
    ledger_path = umbrella_world["consumers_root"] / lesson_compiler.CONSUMER_NAME / "ledger.jsonl"
    rows = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 2


def test_main_cli_returns_zero_on_dry_run(umbrella_world, capsys, monkeypatch):
    # Patch the default ledger so main() picks up our synthetic world.
    import snowball_consumer

    monkeypatch.setattr(snowball_consumer, "LEDGER_PATH", umbrella_world["ledger_path"])
    monkeypatch.setattr(
        snowball_consumer,
        "CONSUMERS_DIR",
        umbrella_world["consumers_root"],
    )
    rc = lesson_compiler.main(["--dry-run", "--ledger-tail", "10"])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"status"' in out
