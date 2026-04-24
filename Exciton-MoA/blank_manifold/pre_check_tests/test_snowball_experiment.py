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


# ---------------------------------------------------------------------------
# W2: MSFGuard A/B alternation in daily explore/exploit
# ---------------------------------------------------------------------------


def test_decide_msf_ab_off_for_hold():
    state = snowball_experiment.default_state()
    cfg = snowball_experiment.decide_next_config(state, "daily")
    assert cfg.regime == "hold"
    assert "__msf_ab_treatment__" not in cfg.flags
    assert "msf_ab" not in cfg.rationale


def test_decide_msf_ab_off_for_pulse_even_when_explore():
    state = snowball_experiment.default_state()
    state["diagnosis_streak_label"] = "low_variance_candidate"
    state["diagnosis_streak_count"] = 3
    cfg = snowball_experiment.decide_next_config(state, "pulse")
    # Pulse never participates in the A/B series.
    assert "__msf_ab_treatment__" not in cfg.flags
    assert "msf_ab" not in cfg.rationale


def test_decide_msf_ab_alternates_on_daily_explore():
    state = snowball_experiment.default_state()
    state["diagnosis_streak_label"] = "low_variance_candidate"
    state["diagnosis_streak_count"] = 3
    state["msf_ab_alternation"] = 0
    cfg_a = snowball_experiment.decide_next_config(state, "daily")
    state["msf_ab_alternation"] = 1
    cfg_b = snowball_experiment.decide_next_config(state, "daily")
    assert cfg_a.regime == "explore"
    assert "__msf_ab_treatment__" not in cfg_a.flags
    assert "msf_ab: control" in cfg_a.rationale
    assert "__msf_ab_treatment__" in cfg_b.flags
    assert "msf_ab: treatment" in cfg_b.rationale


def test_build_engine_argv_msf_treatment_passes_enable_flag(tmp_path):
    state = snowball_experiment.default_state()
    state["diagnosis_streak_label"] = "low_variance_candidate"
    state["diagnosis_streak_count"] = 3
    state["msf_ab_alternation"] = 1  # treatment arm
    cfg = snowball_experiment.decide_next_config(state, "daily")
    argv = snowball_experiment.build_engine_argv(cfg, tmp_path / "runs/x")
    # Bookkeeping flag must NOT leak into the engine CLI.
    assert "__msf_ab_treatment__" not in argv
    assert "--enable-msf-guard" in argv
    assert "--no-enable-msf-guard" not in argv


def test_build_engine_argv_msf_control_passes_disable_flag(tmp_path):
    state = snowball_experiment.default_state()
    state["diagnosis_streak_label"] = "low_variance_candidate"
    state["diagnosis_streak_count"] = 3
    state["msf_ab_alternation"] = 0  # control arm
    cfg = snowball_experiment.decide_next_config(state, "daily")
    argv = snowball_experiment.build_engine_argv(cfg, tmp_path / "runs/x")
    assert "--no-enable-msf-guard" in argv
    assert "--enable-msf-guard" not in argv


def test_build_engine_argv_hold_does_not_request_msf_treatment(tmp_path):
    state = snowball_experiment.default_state()
    cfg = snowball_experiment.decide_next_config(state, "daily")
    argv = snowball_experiment.build_engine_argv(cfg, tmp_path / "runs/x")
    # Hold cycles default to control (no guard) so the engine still logs an
    # explicit arm choice without polluting the historical baseline.
    assert "--no-enable-msf-guard" in argv
    assert "--enable-msf-guard" not in argv


def test_apply_results_increments_msf_ab_alternation_on_daily_explore():
    state = snowball_experiment.default_state()
    state["diagnosis_streak_label"] = "low_variance_candidate"
    state["diagnosis_streak_count"] = 3
    cfg = snowball_experiment.decide_next_config(state, "daily")
    assert cfg.regime == "explore"
    results = {
        "consensus_diagnosis": "low_variance_candidate",
        "coupling_consensus": "weak",
        "paper_trigger": "synchrony",
        "natural_entries": 0,
        "gate_pass_total": 0,
        "positive_forward_window_total": 0,
    }
    s1 = snowball_experiment.apply_results_to_state(
        state, tier="daily", config=cfg, results=results, argv=["--sweep"]
    )
    assert s1["msf_ab_alternation"] == 1
    assert s1["last_msf_ab_arm"] == "control"
    s2 = snowball_experiment.apply_results_to_state(
        s1, tier="daily", config=cfg, results=results, argv=["--sweep"]
    )
    # Without re-deciding cfg, both bumps register; arm tag still reflects cfg.
    assert s2["msf_ab_alternation"] == 2


def test_apply_results_does_not_increment_msf_alt_on_hold_or_pulse():
    state = snowball_experiment.default_state()
    cfg_hold = snowball_experiment.decide_next_config(state, "daily")
    assert cfg_hold.regime == "hold"
    s1 = snowball_experiment.apply_results_to_state(
        state,
        tier="daily",
        config=cfg_hold,
        results={
            "consensus_diagnosis": "unknown",
            "coupling_consensus": "unknown",
            "paper_trigger": "none",
            "natural_entries": 0,
            "gate_pass_total": 0,
            "positive_forward_window_total": 0,
        },
        argv=["--sweep"],
    )
    assert s1["msf_ab_alternation"] == 0

    state["diagnosis_streak_label"] = "low_variance_candidate"
    state["diagnosis_streak_count"] = 3
    cfg_pulse = snowball_experiment.decide_next_config(state, "pulse")
    s2 = snowball_experiment.apply_results_to_state(
        state,
        tier="pulse",
        config=cfg_pulse,
        results={
            "consensus_diagnosis": "low_variance_candidate",
            "coupling_consensus": "weak",
            "paper_trigger": "none",
            "natural_entries": 0,
            "gate_pass_total": 0,
            "positive_forward_window_total": 0,
        },
        argv=["--sweep"],
    )
    assert s2["msf_ab_alternation"] == 0


# ---------------------------------------------------------------------------
# W3: Advisory lesson clamp on explore neighbor lists
# ---------------------------------------------------------------------------


def test_apply_lesson_clamp_filters_intersection():
    clamp = {
        "applicable_pockets": [
            "locA=0.50,locB=0.57,drift=0.06",
            "locA=0.51,locB=0.58,drift=0.06",
        ],
        "contraindicated_pockets": [],
    }
    a, b, d, status = snowball_experiment._apply_lesson_clamp(
        snowball_experiment.EXPLORE_LOC_A_NEIGHBORS,
        snowball_experiment.EXPLORE_LOC_B_NEIGHBORS,
        snowball_experiment.EXPLORE_DRIFT_NEIGHBORS,
        clamp,
    )
    assert status == "applied"
    assert a == (0.50, 0.51)
    assert b == (0.57, 0.58)
    assert d == (0.06,)


def test_apply_lesson_clamp_excludes_contraindicated_pockets():
    clamp = {
        "applicable_pockets": [
            "locA=0.50,locB=0.57,drift=0.06",
            "locA=0.49,locB=0.58,drift=0.08",
        ],
        "contraindicated_pockets": ["locA=0.49,locB=0.58,drift=0.08"],
    }
    a, b, d, status = snowball_experiment._apply_lesson_clamp(
        snowball_experiment.EXPLORE_LOC_A_NEIGHBORS,
        snowball_experiment.EXPLORE_LOC_B_NEIGHBORS,
        snowball_experiment.EXPLORE_DRIFT_NEIGHBORS,
        clamp,
    )
    assert status == "applied"
    assert a == (0.50,)
    assert b == (0.57,)
    assert d == (0.06,)


# ---------------------------------------------------------------------------
# C1: coupling-posture profile integration
# ---------------------------------------------------------------------------


def _c1_daily_explore_state() -> dict:
    state = snowball_experiment.default_state()
    # Force regime=explore via low_variance_candidate streak.
    state["diagnosis_streak_label"] = "low_variance_candidate"
    state["diagnosis_streak_count"] = 3
    return state


def test_default_state_includes_coupling_posture_profile_usage_counts():
    state = snowball_experiment.default_state()
    assert state["coupling_posture_profile_usage_counts"] == {}


def test_decide_emits_coupling_posture_profile_specs_on_daily_explore():
    state = _c1_daily_explore_state()
    state["posture_ab_alternation"] = 1
    config = snowball_experiment.decide_next_config(state, "daily")
    assert config.regime == "explore"
    assert config.coupling_posture_profile_specs == (
        "weak:0.45,0.55,none",
        "permissive:none,none,0.05",
    )
    assert "posture_ab: treatment" in config.rationale


def test_decide_emits_coupling_posture_profile_specs_on_daily_exploit():
    state = snowball_experiment.default_state()
    state["recent_yields_daily"] = [0, 1, 2]
    state["posture_ab_alternation"] = 1
    config = snowball_experiment.decide_next_config(state, "daily")
    assert config.regime == "exploit"
    assert config.coupling_posture_profile_specs is not None
    assert len(config.coupling_posture_profile_specs) == 2


def test_decide_omits_coupling_posture_profile_specs_on_hold():
    state = snowball_experiment.default_state()
    config = snowball_experiment.decide_next_config(state, "daily")
    assert config.regime == "hold"
    assert config.coupling_posture_profile_specs is None


def test_decide_omits_coupling_posture_profile_specs_on_pulse():
    state = _c1_daily_explore_state()
    state["posture_ab_alternation"] = 1
    config = snowball_experiment.decide_next_config(state, "pulse")
    assert config.coupling_posture_profile_specs is None


def test_build_engine_argv_passes_coupling_posture_profile_flags():
    state = _c1_daily_explore_state()
    state["posture_ab_alternation"] = 1
    config = snowball_experiment.decide_next_config(state, "daily")
    argv = snowball_experiment.build_engine_argv(config, Path("runs/x"))
    # Two repeated --coupling-posture-profile flags expected.
    indices = [i for i, tok in enumerate(argv) if tok == "--coupling-posture-profile"]
    assert len(indices) == 2
    payloads = [argv[i + 1] for i in indices]
    assert payloads == ["weak:0.45,0.55,none", "permissive:none,none,0.05"]


def test_build_engine_argv_omits_coupling_posture_profile_on_hold():
    state = snowball_experiment.default_state()
    config = snowball_experiment.decide_next_config(state, "daily")
    argv = snowball_experiment.build_engine_argv(config, Path("runs/x"))
    assert "--coupling-posture-profile" not in argv


def test_parse_results_aggregates_coupling_posture_profile_used_counts(tmp_path: Path):
    _write_records(
        tmp_path,
        [
            {
                "diagnosis_label": "low_variance_candidate",
                "met_entry_policy": False,
                "paper_synchrony_basis": "borderline",
                "paper_synchrony_coupling_posture": "weak",
                "paper_basin_fragility": "broad",
                "paper_uncertainty_triggered": False,
                "gate_pass_count": 0,
                "nudge_applied_count": 0,
                "nudge_positive_forward_windows": 0,
                "coupling_posture_profile_used": "weak",
            },
            {
                "diagnosis_label": "low_variance_candidate",
                "met_entry_policy": False,
                "paper_synchrony_basis": "borderline",
                "paper_synchrony_coupling_posture": "weak",
                "paper_basin_fragility": "broad",
                "paper_uncertainty_triggered": False,
                "gate_pass_count": 0,
                "nudge_applied_count": 0,
                "nudge_positive_forward_windows": 0,
                "coupling_posture_profile_used": "weak",
            },
            {
                "diagnosis_label": "low_variance_candidate",
                "met_entry_policy": False,
                "paper_synchrony_basis": "borderline",
                "paper_synchrony_coupling_posture": "permissive",
                "paper_basin_fragility": "broad",
                "paper_uncertainty_triggered": False,
                "gate_pass_count": 0,
                "nudge_applied_count": 0,
                "nudge_positive_forward_windows": 0,
                # missing -> "none"
            },
        ],
    )
    results = snowball_experiment.parse_results(tmp_path)
    counts = results["coupling_posture_profile_used_counts"]
    assert counts == {"weak": 2, "none": 1}


def test_apply_results_accumulates_coupling_posture_profile_usage_counts():
    state = _c1_daily_explore_state()
    config = snowball_experiment.decide_next_config(state, "daily")
    results = {
        "consensus_diagnosis": "low_variance_candidate",
        "coupling_consensus": "weak",
        "paper_trigger": "synchrony",
        "natural_entries": 0,
        "gate_pass_total": 0,
        "positive_forward_window_total": 0,
        "coupling_posture_profile_used_counts": {"weak": 2, "none": 1},
    }
    s1 = snowball_experiment.apply_results_to_state(
        state, tier="daily", config=config, results=results, argv=["--sweep"]
    )
    assert s1["coupling_posture_profile_usage_counts"] == {"weak": 2, "none": 1}
    s2 = snowball_experiment.apply_results_to_state(
        s1, tier="daily", config=config, results=results, argv=["--sweep"]
    )
    assert s2["coupling_posture_profile_usage_counts"] == {"weak": 4, "none": 2}


# ---------------------------------------------------------------------------
# C2: coupling-posture A/B variant
# ---------------------------------------------------------------------------


def test_default_state_includes_posture_ab_fields():
    state = snowball_experiment.default_state()
    assert state["posture_ab_alternation"] == 0
    assert state["last_posture_ab_arm"] is None


def test_decide_posture_ab_control_arm_when_parity_even():
    state = _c1_daily_explore_state()
    state["posture_ab_alternation"] = 0
    config = snowball_experiment.decide_next_config(state, "daily")
    assert config.coupling_posture_profile_specs == ()
    assert "__posture_ab_treatment__" not in config.flags
    assert "posture_ab: control" in config.rationale


def test_decide_posture_ab_treatment_arm_when_parity_odd():
    state = _c1_daily_explore_state()
    state["posture_ab_alternation"] = 1
    config = snowball_experiment.decide_next_config(state, "daily")
    assert config.coupling_posture_profile_specs == (
        "weak:0.45,0.55,none",
        "permissive:none,none,0.05",
    )
    assert "__posture_ab_treatment__" in config.flags
    assert "posture_ab: treatment" in config.rationale


def test_build_engine_argv_omits_profile_flags_on_control_arm():
    state = _c1_daily_explore_state()
    state["posture_ab_alternation"] = 0
    config = snowball_experiment.decide_next_config(state, "daily")
    argv = snowball_experiment.build_engine_argv(config, Path("runs/x"))
    assert "--coupling-posture-profile" not in argv
    # bookkeeping marker must never leak into argv
    assert "__posture_ab_treatment__" not in argv


def test_build_engine_argv_emits_profile_flags_on_treatment_arm():
    state = _c1_daily_explore_state()
    state["posture_ab_alternation"] = 1
    config = snowball_experiment.decide_next_config(state, "daily")
    argv = snowball_experiment.build_engine_argv(config, Path("runs/x"))
    assert argv.count("--coupling-posture-profile") == 2
    assert "__posture_ab_treatment__" not in argv


def test_apply_results_increments_posture_ab_alternation_only_on_daily_explore_exploit():
    state = _c1_daily_explore_state()
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
    assert s1["posture_ab_alternation"] == 1
    assert s1["last_posture_ab_arm"] == "control"

    # After the bump, parity flips to treatment.
    config2 = snowball_experiment.decide_next_config(s1, "daily")
    assert "__posture_ab_treatment__" in config2.flags
    s2 = snowball_experiment.apply_results_to_state(
        s1, tier="daily", config=config2, results=results, argv=["--sweep"]
    )
    assert s2["posture_ab_alternation"] == 2
    assert s2["last_posture_ab_arm"] == "treatment"


def test_apply_results_does_not_bump_posture_ab_on_pulse_or_hold():
    state = snowball_experiment.default_state()  # hold
    config = snowball_experiment.decide_next_config(state, "daily")
    assert config.regime == "hold"
    results = {
        "consensus_diagnosis": "unknown",
        "coupling_consensus": "unknown",
        "paper_trigger": "none",
        "natural_entries": 0,
        "gate_pass_total": 0,
        "positive_forward_window_total": 0,
    }
    s1 = snowball_experiment.apply_results_to_state(
        state, tier="daily", config=config, results=results, argv=["--sweep"]
    )
    assert s1["posture_ab_alternation"] == 0


def test_summarize_posture_ab_outcomes_pairs_control_then_treatment(tmp_path: Path):
    rows = [
        {
            "origin": "daily",
            "regime": "explore",
            "posture_ab_arm": "control",
            "natural_entries": 1,
            "observe_only_streak": 2,
            "finished_utc": "2026-01-01T00:00:00Z",
            "coupling_posture_profile_used_counts": {"none": 4},
        },
        {
            "origin": "daily",
            "regime": "explore",
            "posture_ab_arm": "treatment",
            "natural_entries": 3,
            "observe_only_streak": 0,
            "finished_utc": "2026-01-02T00:00:00Z",
            "coupling_posture_profile_used_counts": {"weak": 3, "none": 1},
        },
    ]
    out_path = tmp_path / "posture_ab_outcomes.jsonl"
    deltas = snowball_experiment.summarize_posture_ab_outcomes(rows, output_path=out_path)
    assert len(deltas) == 1
    assert deltas[0]["delta_natural_entries"] == 2
    assert deltas[0]["delta_observe_only_streak"] == -2
    assert deltas[0]["profile_used_b"] == "weak"
    assert out_path.exists()
    written = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines() if line]
    assert written == deltas


def test_summarize_posture_ab_outcomes_skips_non_daily_and_hold(tmp_path: Path):
    rows = [
        {"origin": "pulse", "regime": "explore", "posture_ab_arm": "control", "natural_entries": 5},
        {"origin": "daily", "regime": "hold", "posture_ab_arm": "control", "natural_entries": 5},
        {
            "origin": "daily",
            "regime": "explore",
            "posture_ab_arm": "control",
            "natural_entries": 0,
            "observe_only_streak": 0,
        },
        {
            "origin": "daily",
            "regime": "explore",
            "posture_ab_arm": "treatment",
            "natural_entries": 1,
            "observe_only_streak": 1,
            "coupling_posture_profile_used_counts": {},
        },
    ]
    deltas = snowball_experiment.summarize_posture_ab_outcomes(rows, output_path=None)
    assert len(deltas) == 1
    assert deltas[0]["profile_used_b"] == "none"


def test_summarize_msf_ab_outcomes_pairs_control_then_treatment(tmp_path: Path):
    rows = [
        {
            "origin": "daily",
            "regime": "explore",
            "msf_ab_arm": "control",
            "natural_entries": 0,
            "observe_only_streak": 1,
            "finished_utc": "2026-01-01T00:00:00Z",
            "msf_status_counts": {"disabled": 4},
        },
        {
            "origin": "daily",
            "regime": "explore",
            "msf_ab_arm": "treatment",
            "natural_entries": 4,
            "observe_only_streak": 0,
            "finished_utc": "2026-01-02T00:00:00Z",
            "msf_status_counts": {"enabled": 3, "disabled": 1},
        },
    ]
    out_path = tmp_path / "msf_ab_outcomes.jsonl"
    deltas = snowball_experiment.summarize_msf_ab_outcomes(rows, output_path=out_path)
    assert len(deltas) == 1
    assert deltas[0]["delta_natural_entries"] == 4
    assert deltas[0]["delta_observe_only_streak"] == -1
    assert deltas[0]["msf_status_dominant_b"] == "enabled"
    assert deltas[0]["msf_status_counts_b"] == {"enabled": 3, "disabled": 1}
    assert out_path.exists()


def test_summarize_msf_ab_outcomes_skips_non_daily_and_hold():
    rows = [
        {"origin": "pulse", "regime": "explore", "msf_ab_arm": "control", "natural_entries": 5},
        {"origin": "daily", "regime": "hold", "msf_ab_arm": "treatment", "natural_entries": 5},
        {
            "origin": "daily",
            "regime": "explore",
            "msf_ab_arm": "control",
            "natural_entries": 0,
            "observe_only_streak": 0,
            "msf_status_counts": {},
        },
        {
            "origin": "daily",
            "regime": "explore",
            "msf_ab_arm": "treatment",
            "natural_entries": 1,
            "observe_only_streak": 0,
            "msf_status_counts": {},
        },
    ]
    deltas = snowball_experiment.summarize_msf_ab_outcomes(rows, output_path=None)
    assert len(deltas) == 1
    assert deltas[0]["msf_status_dominant_b"] == "disabled"
    assert deltas[0]["msf_status_counts_b"] == {}


def test_apply_lesson_clamp_empty_intersection_falls_back():
    clamp = {
        "applicable_pockets": ["locA=0.99,locB=0.99,drift=0.99"],
        "contraindicated_pockets": [],
    }
    a, b, d, status = snowball_experiment._apply_lesson_clamp(
        snowball_experiment.EXPLORE_LOC_A_NEIGHBORS,
        snowball_experiment.EXPLORE_LOC_B_NEIGHBORS,
        snowball_experiment.EXPLORE_DRIFT_NEIGHBORS,
        clamp,
    )
    assert status == "skipped:empty_intersection"
    assert a == snowball_experiment.EXPLORE_LOC_A_NEIGHBORS
    assert b == snowball_experiment.EXPLORE_LOC_B_NEIGHBORS
    assert d == snowball_experiment.EXPLORE_DRIFT_NEIGHBORS


def test_apply_lesson_clamp_no_pockets_skips():
    a, b, d, status = snowball_experiment._apply_lesson_clamp(
        snowball_experiment.EXPLORE_LOC_A_NEIGHBORS,
        snowball_experiment.EXPLORE_LOC_B_NEIGHBORS,
        snowball_experiment.EXPLORE_DRIFT_NEIGHBORS,
        {"applicable_pockets": []},
    )
    assert status == "skipped:no_pockets"
    assert a == snowball_experiment.EXPLORE_LOC_A_NEIGHBORS


def test_apply_lesson_clamp_malformed_pocket_skips():
    a, b, d, status = snowball_experiment._apply_lesson_clamp(
        snowball_experiment.EXPLORE_LOC_A_NEIGHBORS,
        snowball_experiment.EXPLORE_LOC_B_NEIGHBORS,
        snowball_experiment.EXPLORE_DRIFT_NEIGHBORS,
        {"applicable_pockets": ["this is not a pocket key"]},
    )
    assert status == "skipped:malformed_clamp"


def test_decide_explore_applies_lesson_clamp_to_overrides():
    state = snowball_experiment.default_state()
    state["diagnosis_streak_label"] = "low_variance_candidate"
    state["diagnosis_streak_count"] = 3
    state["advisory_lesson_clamp"] = {
        "schema_version": 1,
        "applicable_pockets": [
            "locA=0.50,locB=0.57,drift=0.06",
            "locA=0.51,locB=0.58,drift=0.06",
        ],
        "contraindicated_pockets": [],
    }
    cfg = snowball_experiment.decide_next_config(state, "daily")
    assert cfg.regime == "explore"
    assert cfg.explore_loc_a_override == (0.50, 0.51)
    assert cfg.explore_drift_override == (0.06,)
    assert "lesson_clamp: applied" in cfg.rationale


def test_decide_explore_lesson_clamp_empty_intersection_logs_skip(tmp_path):
    state = snowball_experiment.default_state()
    state["diagnosis_streak_label"] = "low_variance_candidate"
    state["diagnosis_streak_count"] = 3
    state["advisory_lesson_clamp"] = {
        "schema_version": 1,
        "applicable_pockets": ["locA=0.99,locB=0.99,drift=0.99"],
        "contraindicated_pockets": [],
    }
    cfg = snowball_experiment.decide_next_config(state, "daily")
    assert cfg.explore_loc_a_override is None
    assert "lesson_clamp: skipped:empty_intersection" in cfg.rationale
    # Engine still gets the full allowlist.
    argv = snowball_experiment.build_engine_argv(cfg, tmp_path / "runs/x")
    assert "0.49" in argv  # untouched EXPLORE_LOC_A_NEIGHBORS sentinel


def test_decide_hold_ignores_lesson_clamp():
    state = snowball_experiment.default_state()
    state["advisory_lesson_clamp"] = {
        "schema_version": 1,
        "applicable_pockets": ["locA=0.50,locB=0.57,drift=0.06"],
        "contraindicated_pockets": [],
    }
    cfg = snowball_experiment.decide_next_config(state, "daily")
    assert cfg.regime == "hold"
    assert cfg.explore_loc_a_override is None
    assert "lesson_clamp" not in cfg.rationale


def test_build_engine_argv_explore_uses_clamp_overrides(tmp_path):
    state = snowball_experiment.default_state()
    state["diagnosis_streak_label"] = "low_variance_candidate"
    state["diagnosis_streak_count"] = 3
    state["advisory_lesson_clamp"] = {
        "schema_version": 1,
        "applicable_pockets": ["locA=0.50,locB=0.57,drift=0.06"],
        "contraindicated_pockets": [],
    }
    cfg = snowball_experiment.decide_next_config(state, "daily")
    argv = snowball_experiment.build_engine_argv(cfg, tmp_path / "runs/x")
    # The engine must NOT see the pruned-out neighbor values in the explore axes.
    a_idx = argv.index("--sweep-embedding-a-locs")
    b_idx = argv.index("--sweep-embedding-b-locs")
    d_idx = argv.index("--sweep-embedding-drifts")
    s_idx = argv.index("--sweep-seeds")
    a_vals = argv[a_idx + 1 : b_idx]
    b_vals = argv[b_idx + 1 : d_idx]
    d_vals = argv[d_idx + 1 : s_idx]
    assert a_vals == ["0.5"]
    assert b_vals == ["0.57"]
    assert d_vals == ["0.06"]
