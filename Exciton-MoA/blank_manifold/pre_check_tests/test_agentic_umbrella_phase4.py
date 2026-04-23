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
    assert agent_handoff_schemas.SCHEMA_VERSIONS.get("knowledge_lesson") == 2


def test_validate_knowledge_lesson_accepts_v1_for_back_compat():
    payload = _ok_lesson()
    payload["schema_version"] = 1
    ok, errors = agent_handoff_schemas.validate_knowledge_lesson(payload)
    assert ok, errors


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
    weak_low = aggregates[("weak", "low_variance_candidate", "none", "disabled")]
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
    assert bundle["schema_versions"]["knowledge_lesson"] == 2
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


# ---------------------------------------------------------------------------
# W3: lesson_advisory_writer (high-confidence lesson -> advisory clamp)
# ---------------------------------------------------------------------------


lesson_advisory_writer = importlib.import_module("lesson_advisory_writer")
snowball_experiment = importlib.import_module("snowball_experiment")


def _seed_lessons_bundle(consumers_root: Path, token: str, lessons: list[dict]) -> Path:
    base = consumers_root / lesson_compiler.CONSUMER_NAME / token
    base.mkdir(parents=True, exist_ok=True)
    bundle = {
        "schema_versions": {"knowledge_lesson": 1},
        "generated_utc": "2026-04-23T00:00:00Z",
        "lessons": lessons,
    }
    path = base / "lessons.json"
    path.write_text(json.dumps(bundle, sort_keys=True, indent=2), encoding="utf-8")
    return path


def _patch_state_path(monkeypatch, tmp_path):
    state_path = tmp_path / "state.json"
    lock_path = tmp_path / "state.lock"
    monkeypatch.setattr(snowball_experiment, "STATE_PATH", state_path)
    monkeypatch.setattr(lesson_advisory_writer, "STATE_LOCK_PATH", lock_path)

    # load_state/save_state bind STATE_PATH as a *default argument* at def
    # time, so re-pointing the module-level constant doesn't reach them.
    # Patch the function references the writer imported, with our state_path
    # baked into a fresh closure.
    def _load(state_path_arg=state_path):
        return snowball_experiment.load_state(state_path=state_path_arg)

    def _save(state, state_path_arg=state_path):
        snowball_experiment.save_state(state, state_path=state_path_arg)

    monkeypatch.setattr(lesson_advisory_writer, "load_state", _load)
    monkeypatch.setattr(lesson_advisory_writer, "save_state", _save)
    return state_path


def _w3_lesson(corro: int, pockets: list[str], contras: list[str] | None = None) -> dict:
    return {
        "schema_version": 1,
        "lesson_type": "entrainment_stability",
        "corroboration_count": corro,
        "evidence_run_dirs": ["runs/daily/A", "runs/daily/B"],
        "key_findings": "Synthetic lesson",
        "applicable_constraints": pockets,
        "contraindications": contras or [],
        "generated_utc": "2026-04-23T00:00:00Z",
    }


def test_advisory_writer_noop_when_no_bundle(tmp_path, monkeypatch):
    consumers_root = tmp_path / "consumers"
    _patch_state_path(monkeypatch, tmp_path)
    outcome = lesson_advisory_writer.run_lesson_advisory_writer(
        min_corroboration=3,
        consumers_root=consumers_root,
    )
    assert outcome["status"] == "noop"
    assert "no lesson_compiler bundle" in outcome["reason"]


def test_advisory_writer_noop_when_no_qualifying_lessons(tmp_path, monkeypatch):
    consumers_root = tmp_path / "consumers"
    _patch_state_path(monkeypatch, tmp_path)
    _seed_lessons_bundle(
        consumers_root,
        "20260423T000000Z",
        [_w3_lesson(corro=2, pockets=["locA=0.50,locB=0.57,drift=0.06"])],
    )
    outcome = lesson_advisory_writer.run_lesson_advisory_writer(
        min_corroboration=3,
        consumers_root=consumers_root,
    )
    assert outcome["status"] == "noop"
    assert "corroboration_count >= 3" in outcome["reason"]


def test_advisory_writer_excludes_lessons_with_contraindications(tmp_path, monkeypatch):
    consumers_root = tmp_path / "consumers"
    _patch_state_path(monkeypatch, tmp_path)
    _seed_lessons_bundle(
        consumers_root,
        "20260423T000000Z",
        [
            _w3_lesson(
                corro=4,
                pockets=["locA=0.50,locB=0.57,drift=0.06"],
                contras=["locA=0.49,locB=0.57,drift=0.06"],
            ),
        ],
    )
    outcome = lesson_advisory_writer.run_lesson_advisory_writer(
        min_corroboration=3,
        consumers_root=consumers_root,
    )
    assert outcome["status"] == "noop"


def test_advisory_writer_dry_run_emits_clamp_payload(tmp_path, monkeypatch):
    consumers_root = tmp_path / "consumers"
    _patch_state_path(monkeypatch, tmp_path)
    _seed_lessons_bundle(
        consumers_root,
        "20260423T000000Z",
        [
            _w3_lesson(
                corro=3,
                pockets=[
                    "locA=0.50,locB=0.57,drift=0.06",
                    "locA=0.51,locB=0.58,drift=0.06",
                ],
            ),
        ],
    )
    outcome = lesson_advisory_writer.run_lesson_advisory_writer(
        min_corroboration=3,
        dry_run=True,
        consumers_root=consumers_root,
    )
    assert outcome["status"] == "dry_run"
    clamp = outcome["payload"]["clamp"]
    assert clamp["applicable_pockets"] == [
        "locA=0.50,locB=0.57,drift=0.06",
        "locA=0.51,locB=0.58,drift=0.06",
    ]
    assert clamp["lesson_count"] == 1
    assert clamp["source_lesson_token"] == "20260423T000000Z"


def test_advisory_writer_writes_state_clamp(tmp_path, monkeypatch):
    consumers_root = tmp_path / "consumers"
    state_path = _patch_state_path(monkeypatch, tmp_path)
    _seed_lessons_bundle(
        consumers_root,
        "20260423T000000Z",
        [
            _w3_lesson(
                corro=3,
                pockets=["locA=0.50,locB=0.57,drift=0.06"],
            ),
        ],
    )
    outcome = lesson_advisory_writer.run_lesson_advisory_writer(
        min_corroboration=3,
        consumers_root=consumers_root,
    )
    assert outcome["status"] == "ok"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    clamp = state["advisory_lesson_clamp"]
    assert clamp["schema_version"] == 1
    assert clamp["applicable_pockets"] == ["locA=0.50,locB=0.57,drift=0.06"]
    assert clamp["lesson_count"] == 1


def test_advisory_writer_clears_clamp_when_no_qualifying_lessons(tmp_path, monkeypatch):
    consumers_root = tmp_path / "consumers"
    state_path = _patch_state_path(monkeypatch, tmp_path)
    # Seed a stale clamp.
    state = snowball_experiment.default_state()
    state["advisory_lesson_clamp"] = {
        "schema_version": 1,
        "applicable_pockets": ["locA=0.50,locB=0.57,drift=0.06"],
        "contraindicated_pockets": [],
        "source_lesson_token": "old",
        "source_lesson_types": [],
        "lesson_count": 1,
        "updated_utc": "2026-04-22T00:00:00Z",
    }
    snowball_experiment.save_state(state, state_path=state_path)
    _seed_lessons_bundle(
        consumers_root,
        "20260423T000000Z",
        [_w3_lesson(corro=1, pockets=["locA=0.50,locB=0.57,drift=0.06"])],
    )
    outcome = lesson_advisory_writer.run_lesson_advisory_writer(
        min_corroboration=3,
        consumers_root=consumers_root,
    )
    assert outcome["status"] == "noop"
    state_after = json.loads(state_path.read_text(encoding="utf-8"))
    cleared = state_after["advisory_lesson_clamp"]
    assert cleared["applicable_pockets"] == []
    assert cleared["lesson_count"] == 0
    assert cleared.get("cleared_reason") == "no_qualifying_lessons"


def test_advisory_writer_picks_latest_bundle_token(tmp_path, monkeypatch):
    consumers_root = tmp_path / "consumers"
    _patch_state_path(monkeypatch, tmp_path)
    _seed_lessons_bundle(
        consumers_root,
        "20260101T000000Z",
        [_w3_lesson(corro=5, pockets=["locA=0.49,locB=0.57,drift=0.06"])],
    )
    _seed_lessons_bundle(
        consumers_root,
        "20260423T000000Z",
        [_w3_lesson(corro=5, pockets=["locA=0.51,locB=0.58,drift=0.08"])],
    )
    outcome = lesson_advisory_writer.run_lesson_advisory_writer(
        min_corroboration=3,
        dry_run=True,
        consumers_root=consumers_root,
    )
    assert outcome["status"] == "dry_run"
    assert outcome["payload"]["clamp"]["source_lesson_token"] == "20260423T000000Z"
    assert outcome["payload"]["clamp"]["applicable_pockets"] == [
        "locA=0.51,locB=0.58,drift=0.08",
    ]


def test_advisory_writer_main_cli_returns_zero(tmp_path, monkeypatch, capsys):
    import snowball_consumer

    consumers_root = tmp_path / "consumers"
    _patch_state_path(monkeypatch, tmp_path)
    monkeypatch.setattr(snowball_consumer, "CONSUMERS_DIR", consumers_root)
    monkeypatch.setattr(lesson_advisory_writer, "CONSUMERS_DIR", consumers_root)
    _seed_lessons_bundle(
        consumers_root,
        "20260423T000000Z",
        [_w3_lesson(corro=3, pockets=["locA=0.50,locB=0.57,drift=0.06"])],
    )
    rc = lesson_advisory_writer.main(["--dry-run", "--min-corroboration", "3"])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"dry_run"' in out


# ---------------------------------------------------------------------------
# C3: Lesson Compiler v2 (profile-aware grouping + posture_profile_lift)
# ---------------------------------------------------------------------------


def _v2_row(
    loc_a: float,
    loc_b: float,
    drift: float,
    coupling: str,
    diagnosis: str,
    *,
    profile_used: str = "none",
    msf_status_counts: dict | None = None,
    met_entry_policy: bool = False,
) -> dict:
    return {
        "embedding_a_loc": loc_a,
        "embedding_b_loc": loc_b,
        "embedding_drift": drift,
        "paper_synchrony_coupling_posture": coupling,
        "diagnosis_label": diagnosis,
        "coupling_posture_profile_used": profile_used,
        "msf_status_counts": msf_status_counts or {},
        "met_entry_policy": met_entry_policy,
    }


def test_pattern_key_returns_four_tuple_with_defaults():
    row = {
        "paper_synchrony_coupling_posture": "weak",
        "diagnosis_label": "low_variance_candidate",
    }
    assert lesson_compiler._pattern_key(row) == (
        "weak",
        "low_variance_candidate",
        "none",
        "disabled",
    )


def test_pattern_key_uses_profile_and_msf_status_dominant():
    row = {
        "paper_synchrony_coupling_posture": "weak",
        "diagnosis_label": "low_variance_candidate",
        "coupling_posture_profile_used": "weak",
        "msf_status_counts": {"enabled": 5, "disabled": 1},
    }
    assert lesson_compiler._pattern_key(row) == (
        "weak",
        "low_variance_candidate",
        "weak",
        "enabled",
    )


def test_aggregate_patterns_includes_per_profile_natural_entry_means(tmp_path):
    rd = tmp_path / "runs" / "daily" / "20260301T000000Z"
    sweep_by_run = [
        (
            rd.as_posix(),
            [
                _v2_row(0.50, 0.57, 0.06, "weak", "low_variance_candidate",
                        profile_used="none", met_entry_policy=False),
                _v2_row(0.50, 0.58, 0.06, "weak", "low_variance_candidate",
                        profile_used="none", met_entry_policy=False),
                _v2_row(0.51, 0.57, 0.06, "weak", "low_variance_candidate",
                        profile_used="weak", met_entry_policy=True),
                _v2_row(0.51, 0.58, 0.06, "weak", "low_variance_candidate",
                        profile_used="weak", met_entry_policy=True),
            ],
        ),
    ]
    aggregates = lesson_compiler.aggregate_patterns(sweep_by_run)
    weak_none = aggregates[("weak", "low_variance_candidate", "none", "disabled")]
    weak_weak = aggregates[("weak", "low_variance_candidate", "weak", "disabled")]
    means_none = weak_none["per_profile_natural_entry_means"]
    means_weak = weak_weak["per_profile_natural_entry_means"]
    # Same coupling -> identical per-profile means dict.
    assert means_none == means_weak
    assert means_none["none"] == 0.0
    assert means_none["weak"] == 1.0


def test_build_lesson_payload_promotes_to_posture_profile_lift_on_swing(tmp_path):
    pattern = ("weak", "low_variance_candidate", "weak", "disabled")
    aggregate = {
        "pockets": {"locA=0.51,locB=0.57,drift=0.06"},
        "runs": {"runs/daily/A"},
        "contraindication_pockets": set(),
        "per_profile_natural_entry_means": {"none": 0.0, "weak": 1.0},
    }
    payload = lesson_compiler.build_lesson_payload(pattern, aggregate)
    assert payload["lesson_type"] == "posture_profile_lift"
    assert payload["schema_version"] == 2
    assert payload["profile_used"] == "weak"
    assert payload["msf_status_dominant"] == "disabled"
    assert payload["per_profile_natural_entry_means"] == {"none": 0.0, "weak": 1.0}


def test_build_lesson_payload_keeps_default_lesson_type_when_swing_below_threshold():
    pattern = ("weak", "low_variance_candidate", "weak", "disabled")
    aggregate = {
        "pockets": {"locA=0.51,locB=0.57,drift=0.06"},
        "runs": {"runs/daily/A"},
        "contraindication_pockets": set(),
        # Swing of 0.05 is below the 0.10 threshold.
        "per_profile_natural_entry_means": {"none": 0.45, "weak": 0.50},
    }
    payload = lesson_compiler.build_lesson_payload(pattern, aggregate)
    assert payload["lesson_type"] == "entrainment_stability"


def test_validate_knowledge_lesson_v2_accepts_optional_fields():
    payload = _ok_lesson()
    payload["schema_version"] = 2
    payload["profile_used"] = "weak"
    payload["msf_status_dominant"] = "enabled"
    payload["per_profile_natural_entry_means"] = {"weak": 0.6, "none": 0.4}
    ok, errors = agent_handoff_schemas.validate_knowledge_lesson(payload)
    assert ok, errors


def test_advisory_writer_records_recommended_profile_from_v2_lessons(tmp_path, monkeypatch):
    consumers_root = tmp_path / "consumers"
    _patch_state_path(monkeypatch, tmp_path)
    v2_lesson = _w3_lesson(
        corro=3,
        pockets=["locA=0.51,locB=0.57,drift=0.06"],
    )
    v2_lesson["schema_version"] = 2
    v2_lesson["profile_used"] = "weak"
    v2_lesson["msf_status_dominant"] = "enabled"
    v2_lesson["per_profile_natural_entry_means"] = {"none": 0.0, "weak": 1.0}
    _seed_lessons_bundle(consumers_root, "20260601T000000Z", [v2_lesson])
    outcome = lesson_advisory_writer.run_lesson_advisory_writer(
        min_corroboration=3,
        dry_run=True,
        consumers_root=consumers_root,
    )
    assert outcome["status"] == "dry_run"
    clamp = outcome["payload"]["clamp"]
    assert clamp["recommended_profile_counts"] == {"weak": 1}


def test_advisory_writer_v1_lessons_yield_empty_recommended_profile_counts(tmp_path, monkeypatch):
    consumers_root = tmp_path / "consumers"
    _patch_state_path(monkeypatch, tmp_path)
    _seed_lessons_bundle(
        consumers_root,
        "20260601T000000Z",
        [_w3_lesson(corro=3, pockets=["locA=0.50,locB=0.57,drift=0.06"])],
    )
    outcome = lesson_advisory_writer.run_lesson_advisory_writer(
        min_corroboration=3,
        dry_run=True,
        consumers_root=consumers_root,
    )
    assert outcome["status"] == "dry_run"
    clamp = outcome["payload"]["clamp"]
    assert clamp["recommended_profile_counts"] == {}

