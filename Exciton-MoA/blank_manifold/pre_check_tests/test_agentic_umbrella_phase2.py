# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""Phase-2 regression coverage for the agentic umbrella.

Covers:
 * baseline_registry (Slab C) — load/save baselines, scoring, drift, counts.
 * pair_tournament (#2) — variant collection, ranking, two-cycle promotion.
 * drift_watch (#5) — drift evaluation, incident payload, safety-clamp path.
 * snowball_experiment.decide_next_config — safety_clamp override + tilt
   informational rationale.

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

baseline_registry = importlib.import_module("baseline_registry")
pair_tournament = importlib.import_module("pair_tournament")
drift_watch = importlib.import_module("drift_watch")
snowball_consumer = importlib.import_module("snowball_consumer")
agent_handoff_schemas = importlib.import_module("agent_handoff_schemas")
snowball_experiment = importlib.import_module("snowball_experiment")


# ---------------------------------------------------------------------------
# Slab C: baseline_registry
# ---------------------------------------------------------------------------


def test_baseline_path_rejects_bad_id(tmp_path):
    with pytest.raises(ValueError):
        baseline_registry.baseline_path("bad/name", root=tmp_path)


def test_load_baseline_missing_returns_none(tmp_path):
    assert baseline_registry.load_baseline("absent", root=tmp_path) is None


def test_save_then_load_baseline_round_trip(tmp_path):
    payload = {"counts": {"aligned": 7, "borderline": 3}, "version": 1}
    baseline_registry.save_baseline("diag_v1", payload, root=tmp_path)
    loaded = baseline_registry.load_baseline("diag_v1", root=tmp_path)
    assert loaded == payload


def test_load_baseline_tolerates_corrupt_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("not json", encoding="utf-8")
    assert baseline_registry.load_baseline("bad", root=tmp_path) is None


def test_score_variant_clean_run_beats_triggered_run():
    clean = {
        "natural_entries": 1,
        "gate_pass_total": 4,
        "positive_forward_window_total": 2,
        "paper_trigger": "none",
        "nudge_applied_total": 0,
        "run_dir": "clean",
    }
    triggered = {
        "natural_entries": 1,
        "gate_pass_total": 4,
        "positive_forward_window_total": 2,
        "paper_trigger": "synchrony",
        "nudge_applied_total": 0,
        "run_dir": "noisy",
    }
    s_clean = baseline_registry.score_variant(clean)
    s_triggered = baseline_registry.score_variant(triggered)
    assert s_clean.score > s_triggered.score


def test_score_variant_nudge_penalty_is_capped():
    big = {"natural_entries": 0, "nudge_applied_total": 1000, "run_dir": "x"}
    s = baseline_registry.score_variant(big)
    assert s.components["nudge_applied_penalty"] >= -0.5


def test_rank_variants_sorts_descending_then_by_id():
    rows = [
        {"natural_entries": 1, "run_dir": "b"},
        {"natural_entries": 1, "run_dir": "a"},
        {"natural_entries": 2, "run_dir": "c"},
    ]
    ranked = baseline_registry.rank_variants(rows)
    assert [r.variant_id for r in ranked] == ["c", "a", "b"]


def test_distribution_drift_identical_is_zero():
    assert baseline_registry.distribution_drift({"a": 1, "b": 1}, {"a": 5, "b": 5}) == 0.0


def test_distribution_drift_disjoint_is_one():
    assert baseline_registry.distribution_drift({"a": 4}, {"b": 4}) == 1.0


def test_distribution_drift_missing_keys_count_as_zero():
    drift = baseline_registry.distribution_drift({"a": 3, "b": 1}, {"a": 4})
    assert 0.0 < drift < 1.0


def test_is_over_threshold_strict():
    assert not baseline_registry.is_over_threshold(0.3, 0.3)
    assert baseline_registry.is_over_threshold(0.31, 0.3)


def test_counts_from_rows_buckets_unknown():
    counts = baseline_registry.counts_from_rows(
        [
            {"x": "a"},
            {"x": "a"},
            {"x": None},
            {},
        ],
        field="x",
    )
    assert counts == {"a": 2, "unknown": 2}


# ---------------------------------------------------------------------------
# pair_tournament
# ---------------------------------------------------------------------------


def _seed_run_with_variants(run_dir: Path, variants: list[dict]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "sweep_summary.jsonl"
    with path.open("w", encoding="utf-8") as fp:
        for v in variants:
            fp.write(json.dumps(v) + "\n")


def _ledger_row_for(run_dir: Path, *, origin: str = "daily") -> dict:
    return {
        "origin": origin,
        "regime": "exploit",
        "run_dir": run_dir.as_posix(),
        "started_utc": "2026-01-02T00:00:00Z",
    }


def test_collect_candidates_filters_origin(tmp_path):
    daily_dir = tmp_path / "daily" / "20260102T000000Z"
    pulse_dir = tmp_path / "pulse" / "20260102T010000Z"
    _seed_run_with_variants(
        daily_dir,
        [
            {
                "embedding_a_loc": 0.5,
                "embedding_b_loc": 0.57,
                "embedding_drift": 0.06,
                "seed": 149,
                "cycles": 12,
                "met_entry_policy": True,
                "paper_uncertainty_triggered": False,
                "gate_pass_count": 3,
                "nudge_applied_count": 0,
            }
        ],
    )
    _seed_run_with_variants(
        pulse_dir,
        [
            {
                "embedding_a_loc": 0.5,
                "embedding_b_loc": 0.57,
                "embedding_drift": 0.06,
                "seed": 149,
                "cycles": 6,
                "met_entry_policy": False,
            }
        ],
    )
    rows = [_ledger_row_for(daily_dir, origin="daily"), _ledger_row_for(pulse_dir, origin="pulse")]
    cands = pair_tournament.collect_candidates(rows)
    assert len(cands) == 1
    assert cands[0]["seed"] == 149
    assert cands[0]["origin_run_dir"] == daily_dir.as_posix()


def test_collect_candidates_assigns_unique_run_dir_per_variant(tmp_path):
    run_dir = tmp_path / "daily" / "20260102T000000Z"
    _seed_run_with_variants(
        run_dir,
        [
            {
                "embedding_a_loc": 0.5,
                "embedding_b_loc": 0.57,
                "embedding_drift": 0.06,
                "seed": 149,
                "cycles": 12,
                "met_entry_policy": True,
            },
            {
                "embedding_a_loc": 0.5,
                "embedding_b_loc": 0.58,
                "embedding_drift": 0.06,
                "seed": 83,
                "cycles": 12,
                "met_entry_policy": True,
            },
        ],
    )
    cands = pair_tournament.collect_candidates([_ledger_row_for(run_dir)])
    assert len({c["run_dir"] for c in cands}) == 2


def test_tilt_from_variant_extracts_pinned_keys():
    variant = {
        "embedding_a_loc": 0.5,
        "embedding_b_loc": 0.57,
        "embedding_drift": 0.06,
        "seed": 149,
        "cycles": 12,
        "extra": "ignored",
    }
    tilt = pair_tournament.tilt_from_variant(variant)
    assert tilt == {
        "embedding_a_loc": 0.5,
        "embedding_b_loc": 0.57,
        "embedding_drift": 0.06,
        "seed": 149,
        "cycles": 12,
    }


def test_run_pair_tournament_noop_when_no_candidates(monkeypatch):
    monkeypatch.setattr(pair_tournament, "load_ledger_tail", lambda n: [])
    out = pair_tournament.run_pair_tournament(dry_run=True)
    assert out["status"] == "noop"


def test_run_pair_tournament_dry_run_validates(monkeypatch, tmp_path):
    run_dir = tmp_path / "daily" / "20260102T000000Z"
    _seed_run_with_variants(
        run_dir,
        [
            {
                "embedding_a_loc": 0.5,
                "embedding_b_loc": 0.57,
                "embedding_drift": 0.06,
                "seed": 149,
                "cycles": 12,
                "met_entry_policy": True,
                "paper_uncertainty_triggered": False,
                "gate_pass_count": 4,
                "nudge_applied_count": 0,
                "nudge_positive_forward_windows": 1,
            },
            {
                "embedding_a_loc": 0.5,
                "embedding_b_loc": 0.58,
                "embedding_drift": 0.06,
                "seed": 83,
                "cycles": 12,
                "met_entry_policy": False,
                "paper_uncertainty_triggered": True,
                "gate_pass_count": 1,
                "nudge_applied_count": 5,
            },
        ],
    )
    monkeypatch.setattr(pair_tournament, "load_ledger_tail", lambda n: [_ledger_row_for(run_dir)])
    out = pair_tournament.run_pair_tournament(dry_run=True)
    assert out["status"] == "dry_run"
    ok, errors = agent_handoff_schemas.validate_tournament_entry(out["payload"])
    assert ok, errors
    # The clean variant should win.
    assert out["payload"]["proposed_tilt"]["seed"] == 149


def test_apply_tilt_to_state_promotes_only_when_pending_matches(monkeypatch, tmp_path):
    state_dump = {}

    def fake_load_state():
        return dict(state_dump.get("current") or {})

    def fake_save_state(s):
        state_dump["current"] = dict(s)

    class _FakeLock:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(pair_tournament, "load_state", fake_load_state)
    monkeypatch.setattr(pair_tournament, "save_state", fake_save_state)
    monkeypatch.setattr(pair_tournament, "state_lock", lambda *_a, **_kw: _FakeLock())

    tilt_a = {"embedding_a_loc": 0.5, "embedding_b_loc": 0.57, "seed": 149}
    tilt_b = {"embedding_a_loc": 0.51, "embedding_b_loc": 0.57, "seed": 149}

    promoted, _ = pair_tournament._apply_tilt_to_state(proposed_tilt=tilt_a, tournament_id="T-1")
    assert promoted is False
    assert state_dump["current"]["pending_tournament_winner"] == tilt_a
    assert "best_pocket_tilt" not in state_dump["current"]

    # Different tilt — still no promotion, just refreshes pending.
    promoted, _ = pair_tournament._apply_tilt_to_state(proposed_tilt=tilt_b, tournament_id="T-2")
    assert promoted is False
    assert state_dump["current"]["pending_tournament_winner"] == tilt_b

    # Same tilt as last time — promote.
    promoted, _ = pair_tournament._apply_tilt_to_state(proposed_tilt=tilt_b, tournament_id="T-3")
    assert promoted is True
    assert state_dump["current"]["best_pocket_tilt"] == tilt_b
    assert state_dump["current"]["pending_tournament_winner"] is None


# ---------------------------------------------------------------------------
# drift_watch
# ---------------------------------------------------------------------------


def test_severity_for_thresholds():
    assert drift_watch._severity_for(0.1, 0.2) == "info"
    assert drift_watch._severity_for(0.21, 0.2) == "warn"
    assert drift_watch._severity_for(0.5, 0.2) == "critical"


def test_evaluate_drift_skips_missing_baselines(tmp_path):
    measurements, ids = drift_watch.evaluate_drift(
        [{"consensus_diagnosis": "stable"}],
        threshold=0.2,
        baselines_root=tmp_path,
    )
    assert measurements == [] and ids == []


def test_evaluate_drift_detects_breach(tmp_path):
    baseline_registry.save_baseline(
        "diagnosis_distribution_v1",
        {"counts": {"stable": 8, "low_variance_candidate": 2}},
        root=tmp_path,
    )
    rows = [
        {"consensus_diagnosis": "low_variance_candidate"},
        {"consensus_diagnosis": "low_variance_candidate"},
        {"consensus_diagnosis": "low_variance_candidate"},
    ]
    measurements, ids = drift_watch.evaluate_drift(rows, threshold=0.2, baselines_root=tmp_path)
    assert "diagnosis_distribution_v1" in ids
    diag = next(m for m in measurements if m["baseline_id"] == "diagnosis_distribution_v1")
    assert diag["over_threshold"] is True
    assert diag["drift"] > 0.2


def test_run_drift_watch_clean_clears_clamp(monkeypatch, tmp_path):
    baseline_registry.save_baseline(
        "diagnosis_distribution_v1",
        {"counts": {"stable": 1}},
        root=tmp_path,
    )
    monkeypatch.setattr(drift_watch, "load_ledger_tail", lambda n: [{"consensus_diagnosis": "stable"}])
    captured = {}

    def fake_clamp(*, incident_id, clear):
        captured["incident_id"] = incident_id
        captured["clear"] = clear
        return None

    monkeypatch.setattr(drift_watch, "_apply_safety_clamp", fake_clamp)
    out = drift_watch.run_drift_watch(window=5, threshold=0.5, dry_run=False, baselines_root=tmp_path)
    assert out["status"] == "ok"
    assert out["clean"] is True
    assert captured["clear"] is True


def test_run_drift_watch_breach_writes_incident(monkeypatch, tmp_path):
    baseline_registry.save_baseline(
        "diagnosis_distribution_v1",
        {"counts": {"stable": 9, "low_variance_candidate": 1}},
        root=tmp_path,
    )
    rows = [{"consensus_diagnosis": "low_variance_candidate", "run_dir": "/r/a"}] * 5
    monkeypatch.setattr(drift_watch, "load_ledger_tail", lambda n: rows)
    captured = {}

    def fake_clamp(*, incident_id, clear):
        captured["incident_id"] = incident_id
        captured["clear"] = clear
        return None

    monkeypatch.setattr(drift_watch, "_apply_safety_clamp", fake_clamp)
    monkeypatch.setattr(
        drift_watch,
        "write_consumer_artifact",
        lambda **kw: snowball_consumer.write_consumer_artifact(root=tmp_path, **kw),
    )
    monkeypatch.setattr(
        drift_watch,
        "append_consumer_ledger",
        lambda name, row: snowball_consumer.append_consumer_ledger(name, row, root=tmp_path),
    )
    out = drift_watch.run_drift_watch(window=5, threshold=0.2, dry_run=False, baselines_root=tmp_path)
    assert out["status"] == "ok"
    assert captured["clear"] is False
    assert out["incident_id"].startswith("INC-")
    assert Path(out["artifact_path"]).exists()


def test_run_drift_watch_dry_run_clean(monkeypatch, tmp_path):
    baseline_registry.save_baseline(
        "diagnosis_distribution_v1",
        {"counts": {"stable": 1}},
        root=tmp_path,
    )
    monkeypatch.setattr(drift_watch, "load_ledger_tail", lambda n: [{"consensus_diagnosis": "stable"}])
    out = drift_watch.run_drift_watch(window=5, threshold=0.5, dry_run=True, baselines_root=tmp_path)
    assert out["status"] == "dry_run" and out["clean"] is True


# ---------------------------------------------------------------------------
# snowball_experiment.decide_next_config — Phase 2 hooks
# ---------------------------------------------------------------------------


def test_decide_next_config_safety_clamp_overrides_explore():
    state = snowball_experiment.default_state()
    state["diagnosis_streak_label"] = "low_variance_candidate"
    state["diagnosis_streak_count"] = 5  # would normally trigger explore
    state["safety_clamp"] = "hold"
    state["safety_clamp_incident_id"] = "INC-XYZ"
    cfg = snowball_experiment.decide_next_config(state, "daily")
    assert cfg.regime == "hold"
    assert "safety_clamp=hold" in cfg.rationale
    assert "INC-XYZ" in cfg.rationale


def test_decide_next_config_safety_clamp_yields_to_force_regime():
    state = snowball_experiment.default_state()
    state["safety_clamp"] = "hold"
    cfg = snowball_experiment.decide_next_config(state, "daily", force_regime="explore")
    assert cfg.regime == "explore"
    # Rationale still shows the clamp informationally? Force takes the branch
    # so we shouldn't see the clamp branch text.
    assert "safety_clamp=hold" not in cfg.rationale


def test_decide_next_config_best_pocket_tilt_appears_in_rationale():
    state = snowball_experiment.default_state()
    state["best_pocket_tilt"] = {"seed": 149, "embedding_a_loc": 0.5}
    cfg = snowball_experiment.decide_next_config(state, "daily")
    assert "best_pocket_tilt confirmed" in cfg.rationale


def test_decide_next_config_no_extras_when_state_clean():
    cfg = snowball_experiment.decide_next_config(snowball_experiment.default_state(), "daily")
    assert "safety_clamp" not in cfg.rationale
    assert "best_pocket_tilt" not in cfg.rationale
    assert "fragility_delta" not in cfg.rationale
