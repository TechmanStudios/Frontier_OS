# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""Focused regression coverage for the snowball experiment runner.

The runtime call into ``entangled_manifolds.py`` is intentionally not
exercised here — that surface is covered by ``test_entangled_manifolds.py``.
These tests pin the closed-loop policy shape: state schema, decision policy,
argv translation, result parsing, ledger row, and retention.
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

snowball_experiment = importlib.import_module("snowball_experiment")


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------


def test_default_state_has_expected_keys():
    state = snowball_experiment.default_state()
    expected = {
        "schema_version",
        "regime",
        "regime_streak",
        "diagnosis_streak_label",
        "diagnosis_streak_count",
        "last_paper_trigger",
        "last_coupling_posture",
        "weak_synchrony_streak",
        "observe_only_streak",
        "recent_yields_pulse",
        "recent_yields_daily",
        "last_config_pulse",
        "last_config_daily",
        "policy_probe_alternation",
        "history_window",
        "updated_utc",
    }
    assert expected.issubset(state.keys())
    assert state["regime"] == "hold"
    assert state["recent_yields_pulse"] == []
    assert state["recent_yields_daily"] == []


def test_load_state_round_trip(tmp_path: Path):
    state_path = tmp_path / "state.json"
    initial = snowball_experiment.default_state()
    initial["regime"] = "explore"
    initial["recent_yields_daily"] = [0, 1, 2]
    snowball_experiment.save_state(initial, state_path=state_path)

    loaded = snowball_experiment.load_state(state_path=state_path)
    assert loaded["regime"] == "explore"
    assert loaded["recent_yields_daily"] == [0, 1, 2]
    assert loaded["updated_utc"] is not None


def test_load_state_recovers_from_corrupt_file(tmp_path: Path):
    state_path = tmp_path / "state.json"
    state_path.write_text("not json", encoding="utf-8")
    loaded = snowball_experiment.load_state(state_path=state_path)
    assert loaded["regime"] == "hold"


# ---------------------------------------------------------------------------
# Decision policy
# ---------------------------------------------------------------------------


def test_decide_hold_on_fresh_state():
    state = snowball_experiment.default_state()
    config = snowball_experiment.decide_next_config(state, "daily")
    assert config.regime == "hold"
    assert config.size == "medium"
    assert config.tier == "daily"
    assert "no transition" in config.rationale


def test_decide_explore_after_three_low_variance():
    state = snowball_experiment.default_state()
    state["diagnosis_streak_label"] = "low_variance_candidate"
    state["diagnosis_streak_count"] = 3
    config = snowball_experiment.decide_next_config(state, "daily")
    assert config.regime == "explore"
    assert config.size == "medium"


def test_decide_exploit_with_rising_yield_promotes_to_large_on_daily():
    state = snowball_experiment.default_state()
    state["recent_yields_daily"] = [0, 1, 2]
    config = snowball_experiment.decide_next_config(state, "daily")
    assert config.regime == "exploit"
    assert config.size == "large"


def test_decide_pulse_always_tight_even_if_exploit():
    state = snowball_experiment.default_state()
    state["recent_yields_daily"] = [0, 1, 2]
    config = snowball_experiment.decide_next_config(state, "pulse")
    assert config.size == "tight"
    # Regime may be exploit at decision time; the cross-tier rule kicks in
    # only when the result is folded back into state via apply_results_to_state.
    assert config.regime == "exploit"


def test_decide_policy_probe_synchrony_alternation():
    state = snowball_experiment.default_state()
    state["last_paper_trigger"] = "synchrony"
    state["last_coupling_posture"] = "weak"
    state["weak_synchrony_streak"] = 2
    state["policy_probe_alternation"] = 0
    config_a = snowball_experiment.decide_next_config(state, "daily")
    state["policy_probe_alternation"] = 1
    config_b = snowball_experiment.decide_next_config(state, "daily")
    assert config_a.regime == "policy_probe"
    assert "--enable-negative-collapse-stabilize" in config_a.flags
    assert "--enable-near-pass-maturity-nudges" in config_b.flags


def test_decide_policy_probe_observe_streak_threshold_relax():
    state = snowball_experiment.default_state()
    state["observe_only_streak"] = 3
    config = snowball_experiment.decide_next_config(state, "daily")
    assert config.regime == "policy_probe"
    assert "__conf_rel_probe__" in config.flags


def test_decide_force_regime_overrides():
    state = snowball_experiment.default_state()
    config = snowball_experiment.decide_next_config(state, "daily", force_regime="explore")
    assert config.regime == "explore"
    assert "forced regime" in config.rationale


def test_decide_force_size_overrides():
    state = snowball_experiment.default_state()
    config = snowball_experiment.decide_next_config(state, "pulse", force_size="medium")
    assert config.size == "medium"


def test_decide_rejects_unknown_tier_size_regime():
    state = snowball_experiment.default_state()
    with pytest.raises(ValueError):
        snowball_experiment.decide_next_config(state, "weekly")
    with pytest.raises(ValueError):
        snowball_experiment.decide_next_config(state, "daily", force_size="huge")
    with pytest.raises(ValueError):
        snowball_experiment.decide_next_config(state, "daily", force_regime="party")


# ---------------------------------------------------------------------------
# CLI translation
# ---------------------------------------------------------------------------


def _build_argv(tier: str, **state_overrides) -> list[str]:
    state = snowball_experiment.default_state()
    state.update(state_overrides)
    config = snowball_experiment.decide_next_config(state, tier)
    return list(snowball_experiment.build_engine_argv(config, Path("runs/x")))


def test_argv_tight_pulse_uses_best_pocket_single_variant():
    argv = _build_argv("pulse")
    assert "--sweep" in argv
    assert "--runtime-preset" in argv
    assert argv[argv.index("--runtime-preset") + 1] == "best-pocket"
    assert "--clean-run-reset" in argv
    assert "--enable-hint-gate" in argv
    assert "--enable-bounded-nudges" in argv
    a_idx = argv.index("--sweep-embedding-a-locs")
    assert argv[a_idx + 1] == str(snowball_experiment.BEST_LOC_A)
    cycle_idx = argv.index("--sweep-cycle-counts")
    assert argv[cycle_idx + 1] == "6"


def test_argv_medium_daily_explore_has_neighbor_set():
    argv = _build_argv(
        "daily",
        diagnosis_streak_label="low_variance_candidate",
        diagnosis_streak_count=3,
    )
    a_idx = argv.index("--sweep-embedding-a-locs")
    locs = []
    for token in argv[a_idx + 1 :]:
        if token.startswith("--"):
            break
        locs.append(token)
    assert len(locs) >= 2
    drift_idx = argv.index("--sweep-embedding-drifts")
    drifts = []
    for token in argv[drift_idx + 1 :]:
        if token.startswith("--"):
            break
        drifts.append(token)
    assert len(drifts) >= 2


def test_argv_large_daily_when_exploit():
    argv = _build_argv("daily", recent_yields_daily=[0, 1, 2])
    cycle_idx = argv.index("--sweep-cycle-counts")
    cycles = []
    for token in argv[cycle_idx + 1 :]:
        if token.startswith("--"):
            break
        cycles.append(token)
    assert "12" in cycles and "18" in cycles


def test_argv_includes_probe_flags_when_synchrony_weak():
    state = snowball_experiment.default_state()
    state["last_paper_trigger"] = "synchrony"
    state["last_coupling_posture"] = "weak"
    state["weak_synchrony_streak"] = 2
    config = snowball_experiment.decide_next_config(state, "daily")
    argv = snowball_experiment.build_engine_argv(config, Path("runs/x"))
    assert "--enable-negative-collapse-stabilize" in argv


def test_argv_observe_streak_uses_relaxed_thresholds():
    state = snowball_experiment.default_state()
    state["observe_only_streak"] = 3
    config = snowball_experiment.decide_next_config(state, "daily")
    argv = snowball_experiment.build_engine_argv(config, Path("runs/x"))
    conf = argv[argv.index("--hint-confidence-threshold") + 1]
    rel = argv[argv.index("--hint-reliability-threshold") + 1]
    assert float(conf) == snowball_experiment.CONF_REL_PROBE[0]
    assert float(rel) == snowball_experiment.CONF_REL_PROBE[1]


# ---------------------------------------------------------------------------
# Result parsing
# ---------------------------------------------------------------------------


def _write_records(run_dir: Path, records: list[dict]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "sweep_summary.jsonl").write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in records) + "\n",
        encoding="utf-8",
    )


def test_parse_results_handles_missing_artifacts(tmp_path: Path):
    results = snowball_experiment.parse_results(tmp_path)
    assert results["variant_count"] == 0
    assert results["natural_entries"] == 0
    assert results["paper_trigger"] == "none"
    assert results["consensus_diagnosis"] == "unknown"


def test_parse_results_aggregates_consensus(tmp_path: Path):
    _write_records(
        tmp_path,
        [
            {
                "diagnosis_label": "low_variance_candidate",
                "met_entry_policy": False,
                "paper_synchrony_basis": "borderline",
                "paper_synchrony_coupling_posture": "weak",
                "paper_basin_fragility": "broad",
                "paper_uncertainty_triggered": True,
                "gate_pass_count": 1,
                "nudge_applied_count": 1,
                "nudge_positive_forward_windows": 0,
            },
            {
                "diagnosis_label": "low_variance_candidate",
                "met_entry_policy": True,
                "paper_synchrony_basis": "borderline",
                "paper_synchrony_coupling_posture": "weak",
                "paper_basin_fragility": "broad",
                "paper_uncertainty_triggered": True,
                "gate_pass_count": 0,
                "nudge_applied_count": 0,
                "nudge_positive_forward_windows": 0,
            },
        ],
    )
    results = snowball_experiment.parse_results(tmp_path)
    assert results["variant_count"] == 2
    assert results["natural_entries"] == 1
    assert results["consensus_diagnosis"] == "low_variance_candidate"
    assert results["coupling_consensus"] == "weak"
    assert results["synchrony_consensus"] == "borderline"
    assert results["paper_trigger"] == "synchrony"
    assert results["gate_pass_total"] == 1


# ---------------------------------------------------------------------------
# State updates
# ---------------------------------------------------------------------------


def test_apply_results_grows_diagnosis_streak():
    state = snowball_experiment.default_state()
    config = snowball_experiment.decide_next_config(state, "daily")
    results = {
        "consensus_diagnosis": "low_variance_candidate",
        "coupling_consensus": "weak",
        "paper_trigger": "synchrony",
        "natural_entries": 0,
        "gate_pass_total": 0,
        "positive_forward_window_total": 0,
    }
    s1 = snowball_experiment.apply_results_to_state(
        state, tier="daily", config=config, results=results, argv=["--sweep"]
    )
    s2 = snowball_experiment.apply_results_to_state(
        s1, tier="daily", config=config, results=results, argv=["--sweep"]
    )
    assert s2["diagnosis_streak_label"] == "low_variance_candidate"
    assert s2["diagnosis_streak_count"] == 2
    assert s2["weak_synchrony_streak"] == 2


def test_apply_results_resets_streaks_on_change():
    state = snowball_experiment.default_state()
    state["diagnosis_streak_label"] = "low_variance_candidate"
    state["diagnosis_streak_count"] = 5
    state["weak_synchrony_streak"] = 4
    state["observe_only_streak"] = 3
    config = snowball_experiment.decide_next_config(state, "daily")
    results = {
        "consensus_diagnosis": "threshold_conservative_candidate",
        "coupling_consensus": "permissive",
        "paper_trigger": "none",
        "natural_entries": 1,
        "gate_pass_total": 2,
        "positive_forward_window_total": 1,
    }
    s = snowball_experiment.apply_results_to_state(
        state, tier="daily", config=config, results=results, argv=["--sweep"]
    )
    assert s["diagnosis_streak_label"] == "threshold_conservative_candidate"
    assert s["diagnosis_streak_count"] == 1
    assert s["weak_synchrony_streak"] == 0
    assert s["observe_only_streak"] == 0


def test_apply_results_pulse_cannot_persist_exploit_regime():
    """Cross-tier safety: pulse alone can never leave the loop in exploit."""
    state = snowball_experiment.default_state()
    state["recent_yields_daily"] = [0, 1, 2]
    config = snowball_experiment.decide_next_config(state, "pulse")
    assert config.regime == "exploit"
    s = snowball_experiment.apply_results_to_state(
        state,
        tier="pulse",
        config=config,
        results={
            "consensus_diagnosis": "low_variance_candidate",
            "coupling_consensus": "weak",
            "paper_trigger": "none",
            "natural_entries": 1,
            "gate_pass_total": 0,
            "positive_forward_window_total": 0,
        },
        argv=["--sweep"],
    )
    assert s["regime"] == "hold"


def test_apply_results_records_yields_per_tier():
    state = snowball_experiment.default_state()
    config = snowball_experiment.decide_next_config(state, "pulse")
    s1 = snowball_experiment.apply_results_to_state(
        state,
        tier="pulse",
        config=config,
        results={
            "consensus_diagnosis": "low_variance_candidate",
            "coupling_consensus": "unknown",
            "paper_trigger": "none",
            "natural_entries": 2,
            "gate_pass_total": 0,
            "positive_forward_window_total": 0,
        },
        argv=["--sweep"],
    )
    assert s1["recent_yields_pulse"] == [2]
    assert s1["recent_yields_daily"] == []
    assert s1["last_config_pulse"] == ["--sweep"]


# ---------------------------------------------------------------------------
# Ledger + retention
# ---------------------------------------------------------------------------


def test_append_ledger_row(tmp_path: Path):
    ledger = tmp_path / "ledger.jsonl"
    config = snowball_experiment.NextConfig(
        tier="pulse", size="tight", regime="hold", rationale="test", flags=()
    )
    snowball_experiment.append_ledger_row(
        tier="pulse",
        config=config,
        results={
            "natural_entries": 1,
            "variant_count": 1,
            "gate_pass_total": 0,
            "nudge_applied_total": 0,
            "positive_forward_window_total": 0,
            "consensus_diagnosis": "low_variance_candidate",
            "synchrony_consensus": "broad",
            "coupling_consensus": "permissive",
            "basin_consensus": "broad",
            "paper_trigger": "none",
        },
        run_dir=tmp_path / "runs" / "pulse" / "abc",
        state_after=snowball_experiment.default_state(),
        started_utc="2026-04-23T00:00:00Z",
        finished_utc="2026-04-23T00:01:00Z",
        engine_returncode=0,
        ledger_path=ledger,
    )
    rows = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0]["origin"] == "pulse"
    assert rows[0]["natural_entries"] == 1


def test_prune_old_runs_keeps_retention(tmp_path: Path):
    runs_root = tmp_path / "runs"
    tier_dir = runs_root / "pulse"
    tier_dir.mkdir(parents=True)
    for i in range(5):
        (tier_dir / f"run_{i:03d}").mkdir()
    pruned = snowball_experiment.prune_old_runs("pulse", retention=2, runs_dir=runs_root)
    remaining = sorted(p.name for p in tier_dir.iterdir())
    assert len(pruned) == 3
    assert remaining == ["run_003", "run_004"]


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def test_render_report_contains_key_sections(tmp_path: Path):
    state_before = snowball_experiment.default_state()
    state_after = dict(state_before)
    state_after["regime"] = "explore"
    config = snowball_experiment.NextConfig(
        tier="daily", size="medium", regime="explore", rationale="test", flags=()
    )
    report = snowball_experiment.render_report(
        tier="daily",
        config=config,
        results={
            "variant_count": 4,
            "natural_entries": 0,
            "gate_pass_total": 0,
            "nudge_applied_total": 0,
            "positive_forward_window_total": 0,
            "consensus_diagnosis": "low_variance_candidate",
            "synchrony_consensus": "borderline",
            "coupling_consensus": "weak",
            "basin_consensus": "broad",
            "paper_trigger": "synchrony",
            "diagnosis_counts": {"low_variance_candidate": 4},
            "coupling_counts": {"weak": 4},
            "synchrony_counts": {"borderline": 4},
            "basin_counts": {"broad": 4},
            "handoff_excerpt": "# UNCERTAINTY TO PAPER RECOMMENDATION",
        },
        state_before=state_before,
        state_after=state_after,
        argv=["--sweep", "--runtime-preset", "best-pocket"],
        run_dir=tmp_path / "runs" / "daily" / "abc",
        started_utc="2026-04-23T00:00:00Z",
        finished_utc="2026-04-23T00:25:00Z",
        engine_returncode=0,
    )
    assert "Snowball daily report" in report
    assert "regime: hold -> explore" in report
    assert "natural Stabilizer entries: 0" in report
    assert "paper trigger: synchrony" in report
    assert "UNCERTAINTY TO PAPER RECOMMENDATION" in report
