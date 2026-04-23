# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""Phase-1 regression coverage for the agentic umbrella.

Covers:
 * snowball_consumer (Slab A) — ledger tail, selectors, artifact writer.
 * agent_handoff_schemas (Slab B) — four validators.
 * replay_to_paper (#1) — payload construction, domain suggestion, dry-run.
 * counterfactual_probe (#4) — fragility_delta math, state writeback.

No engine subprocess is invoked.
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

snowball_consumer = importlib.import_module("snowball_consumer")
agent_handoff_schemas = importlib.import_module("agent_handoff_schemas")
replay_to_paper = importlib.import_module("replay_to_paper")
counterfactual_probe = importlib.import_module("counterfactual_probe")
snowball_experiment = importlib.import_module("snowball_experiment")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_ledger(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        for row in rows:
            fp.write(json.dumps(row, sort_keys=True) + "\n")


def _sample_rows(tmp_run_root: Path) -> list[dict]:
    # Oldest first.
    rd1 = tmp_run_root / "daily" / "20260101T000000Z"
    rd1.mkdir(parents=True)
    rd2 = tmp_run_root / "daily" / "20260102T000000Z"
    rd2.mkdir(parents=True)
    rd3 = tmp_run_root / "daily" / "20260103T000000Z"
    rd3.mkdir(parents=True)
    # Give rd3 an uncertainty handoff excerpt.
    (rd3 / "sweep_uncertainty_paper_handoff.md").write_text(
        "# handoff\n- trigger: synchrony\n- coupling: weak\n",
        encoding="utf-8",
    )
    return [
        {
            "origin": "daily",
            "regime": "hold",
            "paper_trigger": "none",
            "synchrony_consensus": "aligned",
            "coupling_consensus": "normal",
            "basin_consensus": "broad",
            "run_dir": rd1.as_posix(),
            "started_utc": "2026-01-01T00:00:00Z",
        },
        {
            "origin": "daily",
            "regime": "exploit",
            "paper_trigger": "basin_fragility",
            "synchrony_consensus": "aligned",
            "coupling_consensus": "normal",
            "basin_consensus": "fragile",
            "run_dir": rd2.as_posix(),
            "started_utc": "2026-01-02T00:00:00Z",
        },
        {
            "origin": "daily",
            "regime": "hold",
            "paper_trigger": "synchrony",
            "synchrony_consensus": "borderline",
            "coupling_consensus": "weak",
            "basin_consensus": "broad",
            "run_dir": rd3.as_posix(),
            "started_utc": "2026-01-03T00:00:00Z",
        },
    ]


@pytest.fixture()
def ledger(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    runs_root = tmp_path / "runs"
    rows = _sample_rows(runs_root)
    _write_ledger(ledger_path, rows)
    return {"path": ledger_path, "rows": rows, "runs_root": runs_root}


# ---------------------------------------------------------------------------
# Slab A: snowball_consumer
# ---------------------------------------------------------------------------


def test_load_ledger_tail_missing_file(tmp_path):
    rows = snowball_consumer.load_ledger_tail(5, ledger_path=tmp_path / "absent.jsonl")
    assert rows == []


def test_load_ledger_tail_returns_oldest_first(ledger):
    rows = snowball_consumer.load_ledger_tail(2, ledger_path=ledger["path"])
    assert [r["started_utc"] for r in rows] == [
        "2026-01-02T00:00:00Z",
        "2026-01-03T00:00:00Z",
    ]


def test_load_ledger_tail_ignores_malformed(tmp_path):
    path = tmp_path / "ledger.jsonl"
    path.write_text(
        '{"a": 1}\n\nnot-json\n{"b": 2}\n',
        encoding="utf-8",
    )
    rows = snowball_consumer.load_ledger_tail(5, ledger_path=path)
    assert rows == [{"a": 1}, {"b": 2}]


def test_select_ledger_row_rejects_unknown_selector(ledger):
    with pytest.raises(ValueError):
        snowball_consumer.select_ledger_row(ledger["rows"], selector="nope")


def test_select_ledger_row_most_recent(ledger):
    row = snowball_consumer.select_ledger_row(ledger["rows"], selector="most_recent")
    assert row["started_utc"] == "2026-01-03T00:00:00Z"


def test_select_ledger_row_most_recent_exploit(ledger):
    row = snowball_consumer.select_ledger_row(ledger["rows"], selector="most_recent_exploit")
    assert row and row["regime"] == "exploit"
    assert row["started_utc"] == "2026-01-02T00:00:00Z"


def test_select_ledger_row_highest_uncertainty_prefers_triggered(ledger):
    row = snowball_consumer.select_ledger_row(ledger["rows"], selector="highest_uncertainty")
    # Most recent triggered row is 2026-01-03 (synchrony).
    assert row and row["paper_trigger"] == "synchrony"


def test_select_ledger_row_handles_empty_and_all_none():
    assert snowball_consumer.select_ledger_row([], selector="most_recent") is None
    rows = [{"paper_trigger": "none", "regime": "hold"}]
    assert snowball_consumer.select_ledger_row(rows, selector="highest_uncertainty") is None
    assert snowball_consumer.select_ledger_row(rows, selector="most_recent_exploit") is None


def test_consumer_dir_rejects_bad_name(tmp_path):
    with pytest.raises(ValueError):
        snowball_consumer.consumer_dir("bad/name", root=tmp_path)


def test_write_consumer_artifact_round_trip(tmp_path):
    artifact = snowball_consumer.write_consumer_artifact(
        consumer_name="unit_test",
        run_token="20260423T120000Z",
        payload={"hello": "world", "n": 3},
        filename="payload.json",
        extra_files=(("summary.md", "hi\n"),),
        root=tmp_path,
    )
    assert artifact.artifact_path.exists()
    body = json.loads(artifact.artifact_path.read_text(encoding="utf-8"))
    assert body == {"hello": "world", "n": 3}
    assert (artifact.artifact_path.parent / "summary.md").read_text(encoding="utf-8") == "hi\n"
    assert artifact.ledger_row["consumer"] == "unit_test"
    assert artifact.ledger_row["run_token"] == "20260423T120000Z"


def test_append_consumer_ledger_creates_file(tmp_path):
    ledger_path = snowball_consumer.append_consumer_ledger("unit_test", {"a": 1}, root=tmp_path)
    snowball_consumer.append_consumer_ledger("unit_test", {"a": 2}, root=tmp_path)
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in lines] == [{"a": 1}, {"a": 2}]


# ---------------------------------------------------------------------------
# Slab B: agent_handoff_schemas
# ---------------------------------------------------------------------------


def _base_paper_handoff():
    return {
        "schema_version": agent_handoff_schemas.SCHEMA_VERSIONS["paper_handoff"],
        "origin": "replay_to_paper",
        "source_run_dir": "/tmp/runs/daily/xyz",
        "source_started_utc": "2026-01-03T00:00:00Z",
        "paper_trigger": "synchrony",
        "synchrony_consensus": "borderline",
        "coupling_consensus": "weak",
        "basin_consensus": "broad",
        "handoff_excerpt": "# excerpt",
        "suggested_domain": "synchronization",
        "generated_utc": "2026-01-04T00:00:00Z",
    }


def test_validate_paper_handoff_happy_path():
    ok, errors = agent_handoff_schemas.validate_paper_handoff(_base_paper_handoff())
    assert ok, errors


def test_validate_paper_handoff_rejects_bad_trigger_and_domain():
    payload = _base_paper_handoff()
    payload["paper_trigger"] = "nope"
    payload["suggested_domain"] = "nope"
    ok, errors = agent_handoff_schemas.validate_paper_handoff(payload)
    assert not ok
    joined = "\n".join(errors)
    assert "paper_trigger" in joined
    assert "suggested_domain" in joined


def test_validate_paper_handoff_rejects_bad_schema_version():
    payload = _base_paper_handoff()
    payload["schema_version"] = 99
    ok, errors = agent_handoff_schemas.validate_paper_handoff(payload)
    assert not ok
    assert any("schema_version" in e for e in errors)


def test_validate_paper_handoff_allows_empty_excerpt():
    payload = _base_paper_handoff()
    payload["handoff_excerpt"] = ""
    ok, errors = agent_handoff_schemas.validate_paper_handoff(payload)
    assert ok, errors


def test_validate_knowledge_promotion_candidate_happy():
    payload = {
        "schema_version": 1,
        "subject_folder": "synchronization",
        "corroboration_count": 3,
        "source_ledger_entries": ["consumers/replay_to_paper/20260423T120000Z"],
        "proposed_memory_line": "- subject:synchronization — ...",
        "generated_utc": "2026-04-23T12:00:00Z",
    }
    ok, errors = agent_handoff_schemas.validate_knowledge_promotion_candidate(payload)
    assert ok, errors


def test_validate_knowledge_promotion_candidate_rejects_zero_corroboration():
    payload = {
        "schema_version": 1,
        "subject_folder": "synchronization",
        "corroboration_count": 0,
        "source_ledger_entries": ["a"],
        "proposed_memory_line": "x",
        "generated_utc": "y",
    }
    ok, errors = agent_handoff_schemas.validate_knowledge_promotion_candidate(payload)
    assert not ok
    assert any("corroboration_count" in e for e in errors)


def test_validate_incident_report_happy():
    payload = {
        "schema_version": 1,
        "kind": "telemetry_drift",
        "severity": "warn",
        "drift_metric": 0.12,
        "threshold": 0.1,
        "baseline_id": "baseline-2026-01",
        "run_dirs_observed": ["/tmp/runs/daily/a"],
        "recommended_action": "clamp regime to hold",
        "generated_utc": "2026-04-23T12:00:00Z",
    }
    ok, errors = agent_handoff_schemas.validate_incident_report(payload)
    assert ok, errors


def test_validate_incident_report_rejects_bad_severity_and_metric():
    payload = {
        "schema_version": 1,
        "kind": "x",
        "severity": "panic",
        "drift_metric": "huge",
        "threshold": 0.1,
        "baseline_id": "b",
        "run_dirs_observed": [],
        "recommended_action": "hold",
        "generated_utc": "z",
    }
    ok, errors = agent_handoff_schemas.validate_incident_report(payload)
    assert not ok
    joined = "\n".join(errors)
    assert "severity" in joined
    assert "drift_metric" in joined


def test_validate_tournament_entry_happy():
    payload = {
        "schema_version": 1,
        "tournament_id": "T-20260423",
        "candidates": [
            {"variant_id": "v1", "score": 0.7},
            {"variant_id": "v2", "score": 0.5},
        ],
        "winner_variant_id": "v1",
        "proposed_tilt": {"embedding_a": 0.5},
        "generated_utc": "2026-04-23T12:00:00Z",
    }
    ok, errors = agent_handoff_schemas.validate_tournament_entry(payload)
    assert ok, errors


def test_validate_tournament_entry_rejects_empty_candidates():
    payload = {
        "schema_version": 1,
        "tournament_id": "T",
        "candidates": [],
        "winner_variant_id": "v1",
        "proposed_tilt": {},
        "generated_utc": "z",
    }
    ok, errors = agent_handoff_schemas.validate_tournament_entry(payload)
    assert not ok
    assert any("candidates" in e for e in errors)


def test_validators_reject_non_dict():
    for fn in (
        agent_handoff_schemas.validate_paper_handoff,
        agent_handoff_schemas.validate_knowledge_promotion_candidate,
        agent_handoff_schemas.validate_incident_report,
        agent_handoff_schemas.validate_tournament_entry,
    ):
        ok, errors = fn("not a dict")
        assert not ok
        assert errors


# ---------------------------------------------------------------------------
# replay_to_paper
# ---------------------------------------------------------------------------


def test_suggested_domain_for_synchrony_weak():
    row = {
        "paper_trigger": "synchrony",
        "synchrony_consensus": "borderline",
        "coupling_consensus": "weak",
    }
    assert replay_to_paper.suggested_domain_for(row) == "synchronization"


def test_suggested_domain_for_basin_fragility():
    row = {
        "paper_trigger": "basin_fragility",
        "synchrony_consensus": "aligned",
        "coupling_consensus": "normal",
    }
    assert replay_to_paper.suggested_domain_for(row) == "basin-stability"


def test_suggested_domain_for_basin_with_borderline_synchrony_is_control_policy():
    row = {
        "paper_trigger": "basin_fragility",
        "synchrony_consensus": "borderline",
        "coupling_consensus": "normal",
    }
    assert replay_to_paper.suggested_domain_for(row) == "control-policy"


def test_build_paper_handoff_payload_round_trip(ledger):
    # Most recent triggered row is the synchrony one (index 2).
    payload = replay_to_paper.build_paper_handoff_payload(ledger["rows"][2])
    ok, errors = agent_handoff_schemas.validate_paper_handoff(payload)
    assert ok, errors
    assert payload["paper_trigger"] == "synchrony"
    assert payload["suggested_domain"] == "synchronization"
    # Excerpt was seeded in the fixture.
    assert "trigger: synchrony" in payload["handoff_excerpt"]


def test_build_paper_handoff_payload_rejects_none_trigger(ledger):
    with pytest.raises(ValueError):
        replay_to_paper.build_paper_handoff_payload(ledger["rows"][0])


def test_run_replay_to_paper_noop_when_nothing_triggered(monkeypatch):
    monkeypatch.setattr(replay_to_paper, "load_ledger_tail", lambda n: [])
    out = replay_to_paper.run_replay_to_paper(ledger_tail=5, dry_run=True)
    assert out["status"] == "noop"


def test_run_replay_to_paper_dry_run_emits_valid_payload(monkeypatch, ledger):
    monkeypatch.setattr(
        replay_to_paper,
        "load_ledger_tail",
        lambda n: ledger["rows"],
    )
    out = replay_to_paper.run_replay_to_paper(ledger_tail=5, dry_run=True)
    assert out["status"] == "dry_run"
    ok, errors = agent_handoff_schemas.validate_paper_handoff(out["payload"])
    assert ok, errors


def test_run_replay_to_paper_writes_artifacts(monkeypatch, tmp_path, ledger):
    monkeypatch.setattr(
        replay_to_paper,
        "load_ledger_tail",
        lambda n: ledger["rows"],
    )
    monkeypatch.setattr(snowball_consumer, "CONSUMERS_DIR", tmp_path)
    # write_consumer_artifact and append_consumer_ledger were imported into
    # replay_to_paper at module load; monkeypatch them directly there.
    monkeypatch.setattr(
        replay_to_paper,
        "write_consumer_artifact",
        lambda **kw: snowball_consumer.write_consumer_artifact(root=tmp_path, **kw),
    )
    monkeypatch.setattr(
        replay_to_paper,
        "append_consumer_ledger",
        lambda name, row: snowball_consumer.append_consumer_ledger(name, row, root=tmp_path),
    )
    out = replay_to_paper.run_replay_to_paper(ledger_tail=5, dry_run=False)
    assert out["status"] == "ok"
    assert Path(out["artifact_path"]).exists()
    assert (tmp_path / "replay_to_paper" / "ledger.jsonl").exists()


# ---------------------------------------------------------------------------
# counterfactual_probe
# ---------------------------------------------------------------------------


def test_fragility_delta_all_fragile():
    records = [
        {"paper_basin_fragility": "fragile"},
        {"paper_basin_fragility": "narrow"},
    ]
    delta, counts = counterfactual_probe.compute_fragility_delta(records)
    assert delta == 1
    assert counts == {"fragile": 1, "narrow": 1}


def test_fragility_delta_all_robust():
    records = [
        {"paper_basin_fragility": "broad"},
        {"paper_basin_fragility": "broad"},
    ]
    delta, _ = counterfactual_probe.compute_fragility_delta(records)
    assert delta == -1


def test_fragility_delta_mixed_is_boundary():
    records = [
        {"paper_basin_fragility": "fragile"},
        {"paper_basin_fragility": "broad"},
    ]
    delta, _ = counterfactual_probe.compute_fragility_delta(records)
    assert delta == 0


def test_fragility_delta_empty_records_is_zero():
    delta, counts = counterfactual_probe.compute_fragility_delta([])
    assert delta == 0 and counts == {}


def test_fragility_delta_all_unknown_is_zero():
    records = [{"paper_basin_fragility": "unknown"}]
    delta, _ = counterfactual_probe.compute_fragility_delta(records)
    assert delta == 0


def _seed_sweep_variants(run_dir: Path, labels: list[str]) -> None:
    path = run_dir / "sweep_summary.jsonl"
    with path.open("w", encoding="utf-8") as fp:
        for lbl in labels:
            fp.write(json.dumps({"paper_basin_fragility": lbl}) + "\n")


def test_counterfactual_noop_when_no_exploit(monkeypatch, ledger):
    rows = [r for r in ledger["rows"] if r["regime"] != "exploit"]
    monkeypatch.setattr(counterfactual_probe, "load_ledger_tail", lambda n: rows)
    out = counterfactual_probe.run_counterfactual_probe(dry_run=True)
    assert out["status"] == "noop"


def test_counterfactual_noop_when_too_few_variants(monkeypatch, ledger):
    exploit_row = [r for r in ledger["rows"] if r["regime"] == "exploit"][0]
    _seed_sweep_variants(Path(exploit_row["run_dir"]), ["broad"])
    monkeypatch.setattr(counterfactual_probe, "load_ledger_tail", lambda n: ledger["rows"])
    out = counterfactual_probe.run_counterfactual_probe(dry_run=True)
    assert out["status"] == "noop"


def test_counterfactual_dry_run_builds_payload(monkeypatch, ledger):
    exploit_row = [r for r in ledger["rows"] if r["regime"] == "exploit"][0]
    _seed_sweep_variants(Path(exploit_row["run_dir"]), ["fragile", "narrow", "fragile"])
    monkeypatch.setattr(counterfactual_probe, "load_ledger_tail", lambda n: ledger["rows"])
    out = counterfactual_probe.run_counterfactual_probe(dry_run=True)
    assert out["status"] == "dry_run"
    assert out["payload"]["fragility_delta"] == 1
    assert out["payload"]["verdict"] == "confirmed_fragile"


def test_counterfactual_full_run_writes_artifact_and_state(monkeypatch, tmp_path, ledger):
    exploit_row = [r for r in ledger["rows"] if r["regime"] == "exploit"][0]
    _seed_sweep_variants(Path(exploit_row["run_dir"]), ["broad", "broad"])
    monkeypatch.setattr(counterfactual_probe, "load_ledger_tail", lambda n: ledger["rows"])
    monkeypatch.setattr(
        counterfactual_probe,
        "write_consumer_artifact",
        lambda **kw: snowball_consumer.write_consumer_artifact(root=tmp_path, **kw),
    )
    monkeypatch.setattr(
        counterfactual_probe,
        "append_consumer_ledger",
        lambda name, row: snowball_consumer.append_consumer_ledger(name, row, root=tmp_path),
    )
    captured: dict = {}

    def fake_update(delta, *, run_token):
        captured["delta"] = delta
        captured["run_token"] = run_token

    monkeypatch.setattr(counterfactual_probe, "_update_state_with_delta", fake_update)
    out = counterfactual_probe.run_counterfactual_probe(dry_run=False)
    assert out["status"] == "ok"
    assert out["verdict"] == "confirmed_robust"
    assert captured["delta"] == -1
    assert Path(out["artifact_path"]).exists()


def test_decide_next_config_surfaces_fragility_delta_in_rationale():
    state = snowball_experiment.default_state()
    state["paper_basin_fragility_delta"] = 1
    cfg = snowball_experiment.decide_next_config(state, "daily")
    assert "fragility_delta=1" in cfg.rationale
    # Behavior unchanged: default state -> hold regime.
    assert cfg.regime == "hold"


def test_decide_next_config_ignores_zero_fragility_delta():
    state = snowball_experiment.default_state()
    state["paper_basin_fragility_delta"] = 0
    cfg = snowball_experiment.decide_next_config(state, "daily")
    assert "fragility_delta" not in cfg.rationale
