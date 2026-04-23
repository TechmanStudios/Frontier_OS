# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""Adaptive Exciton-MoA experiment snowball runner.

Runs a small entangled-pair experiment via ``entangled_manifolds.py`` and
updates a shared closed-loop ``state.json`` that biases the next run.

Two cadences share one state:
  * ``--tier pulse`` — fast, tight variant (~3-5 min); cron every 4h.
  * ``--tier daily`` — medium mini-sweep (~15-25 min) or large (~45-90 min)
    when the policy promotes it; cron once per day.

Public surface (kept small for tests):
  * :func:`load_state` / :func:`save_state` / :func:`default_state`
  * :func:`decide_next_config`
  * :func:`build_engine_argv`
  * :func:`parse_results`
  * :func:`render_report`
  * :func:`apply_results_to_state`
  * :func:`run_snowball`

The runner only ever varies parameters and policy flags that already exist on
``entangled_manifolds.build_pair_runtime_parser``.  Sizes and parameter
neighbors are pinned to a hard allowlist so the loop cannot wander off-policy.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

EXCITON_ROOT = Path(__file__).resolve().parent.parent
ENGINE_SCRIPT = EXCITON_ROOT / "entangled_manifolds.py"
SNOWBALL_DIR = EXCITON_ROOT / "working_data" / "snowball"
STATE_PATH = SNOWBALL_DIR / "state.json"
LEDGER_PATH = SNOWBALL_DIR / "ledger.jsonl"
LATEST_REPORT_PATH = SNOWBALL_DIR / "latest_report.md"
RUNS_DIR = SNOWBALL_DIR / "runs"

PULSE_RETENTION = 60
DAILY_RETENTION = 30

STATE_SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------
# Allowlist: sizes and policy-controlled neighbor sets
# ---------------------------------------------------------------------------

VALID_SIZES = ("tight", "medium", "large")
VALID_TIERS = ("pulse", "daily")
VALID_REGIMES = ("hold", "explore", "exploit", "policy_probe")
VALID_PAPER_TRIGGERS = ("synchrony", "basin_fragility", "none")
VALID_COUPLING_POSTURES = ("weak", "permissive", "mixed", "unknown")

# Best-pocket center (from prior validated sweeps).
BEST_LOC_A = 0.50
BEST_LOC_B = 0.57
BEST_DRIFT = 0.06
BEST_SCALE = 0.08
BEST_CYCLES = 12
BEST_SEED = 149

# Allowed neighbor values (no free-form drift).
EXPLORE_LOC_A_NEIGHBORS = (0.49, 0.50, 0.51)
EXPLORE_LOC_B_NEIGHBORS = (0.57, 0.58)
EXPLORE_DRIFT_NEIGHBORS = (0.06, 0.08)
EXPLORE_SEEDS = (149, 83, 29, 167)

LARGE_LOC_A = (0.49, 0.50)
LARGE_LOC_B = (0.57, 0.58)
LARGE_DRIFT = (0.06, 0.08)
LARGE_CYCLES = (12, 18)
LARGE_SEEDS = (149, 83, 29, 167)

CONF_REL_BASE = (0.55, 0.60)
CONF_REL_PROBE = (0.50, 0.42)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


def default_state() -> dict[str, Any]:
    """Return a fresh state dict.  Used on first run or if state is corrupt."""
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "regime": "hold",
        "regime_streak": 0,
        "diagnosis_streak_label": None,
        "diagnosis_streak_count": 0,
        "last_paper_trigger": "none",
        "last_coupling_posture": "unknown",
        "weak_synchrony_streak": 0,
        "observe_only_streak": 0,
        "recent_yields_pulse": [],
        "recent_yields_daily": [],
        "last_config_pulse": None,
        "last_config_daily": None,
        "policy_probe_alternation": 0,
        "msf_ab_alternation": 0,
        "last_msf_ab_arm": None,
        "coupling_posture_profile_usage_counts": {},
        "posture_ab_alternation": 0,
        "last_posture_ab_arm": None,
        # Cross-consumer additive fields. Listed here so that load_state's
        # default-state allowlist preserves them across reads. Defaults are
        # "absent" sentinels so decide_next_config's `state.get(...)` checks
        # remain semantically equivalent to "not yet written".
        "paper_basin_fragility_delta": None,
        "best_pocket_tilt": None,
        "safety_clamp": None,
        "safety_clamp_incident_id": None,
        "advisory_lesson_clamp": None,
        "history_window": 8,
        "updated_utc": None,
    }


def load_state(state_path: Path = STATE_PATH) -> dict[str, Any]:
    if not state_path.exists():
        return default_state()
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_state()
    state = default_state()
    if isinstance(raw, dict):
        state.update({k: v for k, v in raw.items() if k in state})
    return state


def save_state(state: dict[str, Any], state_path: Path = STATE_PATH) -> None:
    state = dict(state)
    state["updated_utc"] = _utcnow_iso()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_path.with_suffix(state_path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, state_path)


@contextlib.contextmanager
def state_lock(lock_path: Path):
    """Naive cross-process lock backed by an O_EXCL lock file.

    Workflow concurrency groups already serialize daily vs pulse, so this
    only guards rare overlap and local manual invocations.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + 30.0
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            if time.monotonic() > deadline:
                # Stale lock fallback: take it over.
                with contextlib.suppress(FileNotFoundError):
                    lock_path.unlink()
                continue
            time.sleep(0.2)
    try:
        yield
    finally:
        with contextlib.suppress(FileNotFoundError):
            lock_path.unlink()


# ---------------------------------------------------------------------------
# Decision policy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NextConfig:
    tier: str
    size: str
    regime: str
    rationale: str
    flags: tuple[str, ...]  # extra named flags applied (for the report)
    explore_loc_a_override: tuple[float, ...] | None = None
    explore_loc_b_override: tuple[float, ...] | None = None
    explore_drift_override: tuple[float, ...] | None = None
    coupling_posture_profile_specs: tuple[str, ...] | None = None


def _parse_pocket_key(key: str) -> dict[str, float] | None:
    """Parse a pocket key like ``"locA=0.5,locB=0.57,drift=0.06"``.

    Returns ``None`` on any parse failure so callers can skip silently.
    """
    parts: dict[str, float] = {}
    for chunk in str(key).split(","):
        if "=" not in chunk:
            return None
        name, _, raw = chunk.partition("=")
        try:
            parts[name.strip()] = float(raw)
        except ValueError:
            return None
    if not {"locA", "locB", "drift"}.issubset(parts):
        return None
    return parts


def _apply_lesson_clamp(
    loc_a: Sequence[float],
    loc_b: Sequence[float],
    drifts: Sequence[float],
    clamp: dict[str, Any],
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...], str]:
    """Filter explore axes by an advisory lesson clamp.

    Returns ``(loc_a_filtered, loc_b_filtered, drifts_filtered, status)``
    where ``status`` is one of ``"applied"``, ``"skipped:empty_intersection"``,
    ``"skipped:no_pockets"``, or ``"skipped:malformed_clamp"``. When the
    intersection on any axis is empty the originals are returned untouched —
    advisory lessons must never starve the runner of variants.
    """
    pockets = clamp.get("applicable_pockets") or []
    contras = set(clamp.get("contraindicated_pockets") or [])
    if not isinstance(pockets, (list, tuple)) or not pockets:
        return tuple(loc_a), tuple(loc_b), tuple(drifts), "skipped:no_pockets"
    keep_a: set[float] = set()
    keep_b: set[float] = set()
    keep_d: set[float] = set()
    saw_any = False
    for raw in pockets:
        if raw in contras:
            continue
        parsed = _parse_pocket_key(raw)
        if parsed is None:
            continue
        keep_a.add(parsed["locA"])
        keep_b.add(parsed["locB"])
        keep_d.add(parsed["drift"])
        saw_any = True
    if not saw_any:
        return tuple(loc_a), tuple(loc_b), tuple(drifts), "skipped:malformed_clamp"
    filt_a = tuple(v for v in loc_a if v in keep_a)
    filt_b = tuple(v for v in loc_b if v in keep_b)
    filt_d = tuple(v for v in drifts if v in keep_d)
    if not filt_a or not filt_b or not filt_d:
        return tuple(loc_a), tuple(loc_b), tuple(drifts), "skipped:empty_intersection"
    return filt_a, filt_b, filt_d, "applied"


def decide_next_config(
    state: dict[str, Any],
    tier: str,
    *,
    force_regime: str | None = None,
    force_size: str | None = None,
) -> NextConfig:
    """Pure function: state -> next config."""
    if tier not in VALID_TIERS:
        raise ValueError(f"unknown tier {tier!r}")
    if force_size and force_size not in (*VALID_SIZES, "auto"):
        raise ValueError(f"unknown size {force_size!r}")
    if force_regime and force_regime not in (*VALID_REGIMES, "auto"):
        raise ValueError(f"unknown regime {force_regime!r}")

    diagnosis_label = state.get("diagnosis_streak_label")
    diagnosis_streak = int(state.get("diagnosis_streak_count", 0) or 0)
    paper_trigger = str(state.get("last_paper_trigger") or "none")
    coupling = str(state.get("last_coupling_posture") or "unknown")
    weak_synch_streak = int(state.get("weak_synchrony_streak", 0) or 0)
    observe_streak = int(state.get("observe_only_streak", 0) or 0)
    yields_daily = list(state.get("recent_yields_daily", []) or [])
    rising = _is_rising(yields_daily)

    rationale_parts: list[str] = []
    flags: list[str] = []

    # Additive: surface consumer signals in the rationale when present. These
    # reads are informational only — behavior stays deterministic.
    fragility_delta = state.get("paper_basin_fragility_delta")
    if fragility_delta in (-1, 1):
        rationale_parts.append(f"counterfactual fragility_delta={fragility_delta} (informational)")

    best_pocket_tilt = state.get("best_pocket_tilt")
    if isinstance(best_pocket_tilt, dict) and best_pocket_tilt:
        rationale_parts.append(
            f"pair_tournament best_pocket_tilt confirmed ({len(best_pocket_tilt)} params, informational)"
        )

    # Safety clamp — drift_watch incident can force the regime to hold. Takes
    # precedence over automatic promotion but is still beaten by an explicit
    # force_regime override from the operator.
    safety_clamp = state.get("safety_clamp")
    if force_regime and force_regime != "auto":
        regime = force_regime
        rationale_parts.append(f"forced regime={force_regime}")
    elif safety_clamp == "hold":
        regime = "hold"
        rationale_parts.append(
            f"drift_watch safety_clamp=hold (incident={state.get('safety_clamp_incident_id')})"
        )
    elif diagnosis_label == "low_variance_candidate" and diagnosis_streak >= 3:
        regime = "explore"
        rationale_parts.append(f"low_variance_candidate streak={diagnosis_streak} >=3 -> explore")
    elif yields_daily and yields_daily[-1] >= 1 and rising:
        regime = "exploit"
        rationale_parts.append(f"recent daily entry={yields_daily[-1]} with rising yield -> exploit")
    elif paper_trigger == "synchrony" and coupling == "weak" and weak_synch_streak >= 2:
        regime = "policy_probe"
        rationale_parts.append(f"synchrony+weak coupling streak={weak_synch_streak} -> policy_probe")
    elif observe_streak >= 3:
        regime = "policy_probe"
        rationale_parts.append(f"observe-only streak={observe_streak} -> policy_probe (conf/rel relax)")
    else:
        regime = "hold"
        rationale_parts.append("no transition condition met -> hold")

    # Size selection.
    if force_size and force_size != "auto":
        size = force_size
        rationale_parts.append(f"forced size={force_size}")
    elif tier == "pulse":
        size = "tight"
    else:
        # daily
        if regime == "exploit" and yields_daily and yields_daily[-1] >= 1:
            size = "large"
            rationale_parts.append("exploit confirmation -> large daily")
        else:
            size = "medium"

    # Policy-probe alternation flag selection.
    if regime == "policy_probe" and paper_trigger == "synchrony":
        alt = int(state.get("policy_probe_alternation", 0) or 0)
        if alt % 2 == 0:
            flags.append("--enable-negative-collapse-stabilize")
            rationale_parts.append("probe flag: negative-collapse-stabilize")
        else:
            flags.append("--enable-near-pass-maturity-nudges")
            rationale_parts.append("probe flag: near-pass-maturity")
    if regime == "policy_probe" and observe_streak >= 3:
        flags.append("__conf_rel_probe__")
        rationale_parts.append(f"probe thresholds: conf/rel={CONF_REL_PROBE[0]}/{CONF_REL_PROBE[1]}")

    # MSFGuard A/B alternation. Toggle the guard on/off across consecutive
    # daily explore/exploit cycles so paired evidence accumulates over time.
    # Hold/policy-probe regimes opt out so probes stay isolated. The selector
    # is the existing daily-cycle counter ``msf_ab_alternation`` if present
    # (incremented by the runner), else falls back to len(yields_daily).
    if tier == "daily" and regime in {"explore", "exploit"}:
        msf_alt_raw = state.get("msf_ab_alternation")
        if msf_alt_raw is None:
            msf_alt = len(yields_daily)
        else:
            msf_alt = int(msf_alt_raw or 0)
        if msf_alt % 2 == 1:
            flags.append("__msf_ab_treatment__")
            rationale_parts.append("msf_ab: treatment (--enable-msf-guard)")
        else:
            rationale_parts.append("msf_ab: control (--no-enable-msf-guard)")

    # Coupling-posture adaptive gate profiles (W4 integration). On daily
    # explore/exploit cycles, attach two posture-scoped overrides so the
    # engine relaxes thresholds for weak coupling and tightens MSFGuard for
    # permissive coupling. Hold/policy-probe regimes opt out — those cycles
    # need stable baselines for paired evidence.
    #
    # C2 layers a posture A/B variant over this: independent parity counter
    # `posture_ab_alternation` selects treatment (specs attached) vs control
    # (empty tuple = explicitly disable profiles). Composes orthogonally with
    # the MSF A/B switch above to form a 2x2 randomization grid.
    coupling_posture_profile_specs: tuple[str, ...] | None = None
    if tier == "daily" and regime in {"explore", "exploit"}:
        posture_alt_raw = state.get("posture_ab_alternation")
        posture_alt = 0 if posture_alt_raw is None else int(posture_alt_raw or 0)
        if posture_alt % 2 == 1:
            coupling_posture_profile_specs = (
                "weak:0.45,0.55,none",
                "permissive:none,none,0.05",
            )
            flags.append("__posture_ab_treatment__")
            rationale_parts.append(
                "posture_ab: treatment (coupling_posture_profiles: weak,permissive)"
            )
        else:
            coupling_posture_profile_specs = ()
            rationale_parts.append("posture_ab: control (no coupling_posture_profiles)")

    # Advisory lesson clamp — if the lesson_advisory_writer consumer has
    # populated ``state.advisory_lesson_clamp`` with high-confidence pockets,
    # narrow the explore neighbor lists to that intersection. Empty
    # intersections fall back to the full allowlist (logged in rationale).
    explore_loc_a_override: tuple[float, ...] | None = None
    explore_loc_b_override: tuple[float, ...] | None = None
    explore_drift_override: tuple[float, ...] | None = None
    clamp = state.get("advisory_lesson_clamp")
    if (
        isinstance(clamp, dict)
        and tier == "daily"
        and regime == "explore"
        and (force_size in (None, "auto") or force_size == "medium")
    ):
        filt_a, filt_b, filt_d, status = _apply_lesson_clamp(
            EXPLORE_LOC_A_NEIGHBORS,
            EXPLORE_LOC_B_NEIGHBORS,
            EXPLORE_DRIFT_NEIGHBORS,
            clamp,
        )
        if status == "applied":
            explore_loc_a_override = filt_a
            explore_loc_b_override = filt_b
            explore_drift_override = filt_d
            rationale_parts.append(
                f"lesson_clamp: applied (loc_a={len(filt_a)}, loc_b={len(filt_b)}, drift={len(filt_d)})"
            )
        else:
            rationale_parts.append(f"lesson_clamp: {status}")

    rationale = "; ".join(rationale_parts)
    return NextConfig(
        tier=tier,
        size=size,
        regime=regime,
        rationale=rationale,
        flags=tuple(flags),
        explore_loc_a_override=explore_loc_a_override,
        explore_loc_b_override=explore_loc_b_override,
        explore_drift_override=explore_drift_override,
        coupling_posture_profile_specs=coupling_posture_profile_specs,
    )


def _is_rising(values: Sequence[int]) -> bool:
    tail = list(values)[-3:]
    if len(tail) < 2:
        return False
    return tail[-1] > tail[0] and all(b >= a for a, b in zip(tail, tail[1:], strict=False))


# ---------------------------------------------------------------------------
# CLI builder
# ---------------------------------------------------------------------------


def build_engine_argv(config: NextConfig, run_dir: Path) -> list[str]:
    """Translate a :class:`NextConfig` into the argv passed to
    ``entangled_manifolds.py``.

    The runner always uses sweep mode (even for a single variant) so the
    artifact format is uniform.
    """
    argv: list[str] = [
        "--sweep",
        "--sweep-root-dir",
        str(run_dir),
        "--clean-run-reset",
        "--enable-hint-gate",
        "--enable-bounded-nudges",
        "--persist-summaries",
    ]

    # Base preset + scale.
    argv += ["--runtime-preset", "best-pocket", "--embedding-scale", str(BEST_SCALE)]

    # Confidence/reliability thresholds.
    if "__conf_rel_probe__" in config.flags:
        conf, rel = CONF_REL_PROBE
    else:
        conf, rel = CONF_REL_BASE
    argv += ["--hint-confidence-threshold", str(conf), "--hint-reliability-threshold", str(rel)]

    # Pass through bounded extra flags from the policy.
    for flag in config.flags:
        if flag.startswith("--"):
            argv.append(flag)

    # MSFGuard A/B: explicit on/off so the engine logs which arm produced
    # this sweep regardless of any future default-flip.
    if "__msf_ab_treatment__" in config.flags:
        argv.append("--enable-msf-guard")
    else:
        argv.append("--no-enable-msf-guard")

    # Coupling-posture adaptive gate profiles (W4). One CLI flag per spec.
    if config.coupling_posture_profile_specs:
        for spec in config.coupling_posture_profile_specs:
            argv += ["--coupling-posture-profile", spec]

    if config.size == "tight":
        # 1 variant, short cycles.
        argv += [
            "--cycles",
            "6",
            "--sweep-cycle-counts",
            "6",
            "--sweep-seeds",
            str(BEST_SEED),
            "--sweep-embedding-a-locs",
            str(BEST_LOC_A),
            "--sweep-embedding-b-locs",
            str(BEST_LOC_B),
            "--sweep-embedding-drifts",
            str(BEST_DRIFT),
        ]
    elif config.size == "medium":
        # 4-8 variants.
        if config.regime == "explore":
            loc_a = list(EXPLORE_LOC_A_NEIGHBORS)
            loc_b = list(EXPLORE_LOC_B_NEIGHBORS)
            drifts = list(EXPLORE_DRIFT_NEIGHBORS)
            seeds = list(EXPLORE_SEEDS)
            if config.explore_loc_a_override is not None:
                loc_a = list(config.explore_loc_a_override)
            if config.explore_loc_b_override is not None:
                loc_b = list(config.explore_loc_b_override)
            if config.explore_drift_override is not None:
                drifts = list(config.explore_drift_override)
        else:
            loc_a = [BEST_LOC_A]
            loc_b = [BEST_LOC_B, 0.58]
            drifts = [BEST_DRIFT, 0.08]
            seeds = list(EXPLORE_SEEDS)
        argv += [
            "--cycles",
            str(BEST_CYCLES),
            "--sweep-cycle-counts",
            str(BEST_CYCLES),
        ]
        argv += ["--sweep-embedding-a-locs", *(str(v) for v in loc_a)]
        argv += ["--sweep-embedding-b-locs", *(str(v) for v in loc_b)]
        argv += ["--sweep-embedding-drifts", *(str(v) for v in drifts)]
        argv += ["--sweep-seeds", *(str(v) for v in seeds)]
    elif config.size == "large":
        argv += ["--cycles", str(BEST_CYCLES)]
        argv += ["--sweep-cycle-counts", *(str(v) for v in LARGE_CYCLES)]
        argv += ["--sweep-embedding-a-locs", *(str(v) for v in LARGE_LOC_A)]
        argv += ["--sweep-embedding-b-locs", *(str(v) for v in LARGE_LOC_B)]
        argv += ["--sweep-embedding-drifts", *(str(v) for v in LARGE_DRIFT)]
        argv += ["--sweep-seeds", *(str(v) for v in LARGE_SEEDS)]
    else:
        raise ValueError(f"unknown size {config.size!r}")

    return argv


# ---------------------------------------------------------------------------
# Result parsing
# ---------------------------------------------------------------------------


def parse_results(run_dir: Path) -> dict[str, Any]:
    """Read sweep artifacts under ``run_dir`` and produce a flat summary."""
    jsonl_path = run_dir / "sweep_summary.jsonl"
    records: list[dict[str, Any]] = []
    if jsonl_path.exists():
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    variant_count = len(records)
    natural_entries = sum(1 for r in records if bool(r.get("met_entry_policy", False)))
    paper_triggered = sum(1 for r in records if bool(r.get("paper_uncertainty_triggered", False)))
    diagnosis_counts: dict[str, int] = {}
    coupling_counts: dict[str, int] = {}
    basin_counts: dict[str, int] = {}
    synchrony_counts: dict[str, int] = {}
    profile_used_counts: dict[str, int] = {}
    gate_pass_total = 0
    nudge_applied_total = 0
    positive_window_total = 0
    for r in records:
        diagnosis_counts[str(r.get("diagnosis_label", "unknown"))] = (
            diagnosis_counts.get(str(r.get("diagnosis_label", "unknown")), 0) + 1
        )
        coupling_counts[str(r.get("paper_synchrony_coupling_posture", "unknown"))] = (
            coupling_counts.get(str(r.get("paper_synchrony_coupling_posture", "unknown")), 0) + 1
        )
        basin_counts[str(r.get("paper_basin_fragility", "unknown"))] = (
            basin_counts.get(str(r.get("paper_basin_fragility", "unknown")), 0) + 1
        )
        synchrony_counts[str(r.get("paper_synchrony_basis", "unknown"))] = (
            synchrony_counts.get(str(r.get("paper_synchrony_basis", "unknown")), 0) + 1
        )
        gate_pass_total += int(r.get("gate_pass_count", 0) or 0)
        nudge_applied_total += int(r.get("nudge_applied_count", 0) or 0)
        positive_window_total += int(r.get("nudge_positive_forward_windows", 0) or 0)
        profile_used_key = str(r.get("coupling_posture_profile_used", "none") or "none")
        profile_used_counts[profile_used_key] = profile_used_counts.get(profile_used_key, 0) + 1

    consensus_diagnosis = _argmax(diagnosis_counts)
    coupling_consensus = _argmax(coupling_counts)
    basin_consensus = _argmax(basin_counts)
    synchrony_consensus = _argmax(synchrony_counts)

    if synchrony_consensus == "borderline" and coupling_consensus == "weak":
        paper_trigger = "synchrony"
    elif basin_consensus in {"narrow", "fragile"}:
        paper_trigger = "basin_fragility"
    elif paper_triggered > 0 and synchrony_consensus == "borderline":
        paper_trigger = "synchrony"
    elif paper_triggered > 0:
        paper_trigger = "basin_fragility"
    else:
        paper_trigger = "none"

    handoff_text = ""
    handoff_path = run_dir / "sweep_uncertainty_paper_handoff.md"
    if handoff_path.exists():
        with contextlib.suppress(OSError):
            handoff_text = handoff_path.read_text(encoding="utf-8")

    return {
        "variant_count": variant_count,
        "natural_entries": natural_entries,
        "paper_triggered_count": paper_triggered,
        "paper_trigger": paper_trigger,
        "diagnosis_counts": diagnosis_counts,
        "consensus_diagnosis": consensus_diagnosis or "unknown",
        "coupling_counts": coupling_counts,
        "coupling_consensus": coupling_consensus or "unknown",
        "basin_counts": basin_counts,
        "basin_consensus": basin_consensus or "unknown",
        "synchrony_counts": synchrony_counts,
        "synchrony_consensus": synchrony_consensus or "unknown",
        "gate_pass_total": gate_pass_total,
        "nudge_applied_total": nudge_applied_total,
        "positive_forward_window_total": positive_window_total,
        "coupling_posture_profile_used_counts": profile_used_counts,
        "handoff_excerpt": _first_lines(handoff_text, 12),
    }


def _argmax(counts: dict[str, int]) -> str | None:
    if not counts:
        return None
    return max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0]


def _first_lines(text: str, n: int) -> str:
    if not text:
        return ""
    return "\n".join(text.splitlines()[:n])


# ---------------------------------------------------------------------------
# State update
# ---------------------------------------------------------------------------


def apply_results_to_state(
    state: dict[str, Any],
    *,
    tier: str,
    config: NextConfig,
    results: dict[str, Any],
    argv: Sequence[str],
) -> dict[str, Any]:
    new_state = dict(state)
    consensus = str(results.get("consensus_diagnosis", "unknown"))
    if consensus == new_state.get("diagnosis_streak_label"):
        new_state["diagnosis_streak_count"] = int(new_state.get("diagnosis_streak_count", 0) or 0) + 1
    else:
        new_state["diagnosis_streak_label"] = consensus
        new_state["diagnosis_streak_count"] = 1

    paper_trigger = str(results.get("paper_trigger", "none"))
    coupling = str(results.get("coupling_consensus", "unknown"))
    new_state["last_paper_trigger"] = paper_trigger
    new_state["last_coupling_posture"] = coupling
    if paper_trigger == "synchrony" and coupling == "weak":
        new_state["weak_synchrony_streak"] = int(new_state.get("weak_synchrony_streak", 0) or 0) + 1
    else:
        new_state["weak_synchrony_streak"] = 0

    gate_pass = int(results.get("gate_pass_total", 0) or 0)
    pos = int(results.get("positive_forward_window_total", 0) or 0)
    if gate_pass > 0 and pos == 0:
        new_state["observe_only_streak"] = int(new_state.get("observe_only_streak", 0) or 0) + 1
    else:
        new_state["observe_only_streak"] = 0

    if config.regime == new_state.get("regime"):
        new_state["regime_streak"] = int(new_state.get("regime_streak", 0) or 0) + 1
    else:
        new_state["regime"] = config.regime
        new_state["regime_streak"] = 1

    history_window = int(new_state.get("history_window", 8) or 8)
    yields_key = "recent_yields_pulse" if tier == "pulse" else "recent_yields_daily"
    yields = list(new_state.get(yields_key, []) or [])
    yields.append(int(results.get("natural_entries", 0) or 0))
    new_state[yields_key] = yields[-history_window:]

    if tier == "pulse":
        new_state["last_config_pulse"] = list(argv)
    else:
        new_state["last_config_daily"] = list(argv)

    if config.regime == "policy_probe" and paper_trigger == "synchrony":
        new_state["policy_probe_alternation"] = int(new_state.get("policy_probe_alternation", 0) or 0) + 1

    # Increment the MSF A/B alternation counter on every daily explore/exploit
    # cycle so the next decide_next_config flips the arm. Hold/policy-probe
    # cycles do not bump it (those arms aren't part of the A/B series).
    if tier == "daily" and config.regime in {"explore", "exploit"}:
        new_state["msf_ab_alternation"] = int(new_state.get("msf_ab_alternation", 0) or 0) + 1
        new_state["last_msf_ab_arm"] = (
            "treatment" if "__msf_ab_treatment__" in config.flags else "control"
        )
        # C2: independent posture A/B alternation, also bumped only on daily
        # explore/exploit cycles so it composes orthogonally with the MSF arm.
        new_state["posture_ab_alternation"] = (
            int(new_state.get("posture_ab_alternation", 0) or 0) + 1
        )
        new_state["last_posture_ab_arm"] = (
            "treatment" if "__posture_ab_treatment__" in config.flags else "control"
        )

    # Accumulate W4 coupling-posture profile usage. Counts how many sweep
    # variants applied each named profile (or "none" when no profile matched
    # the row's coupling posture). Cross-cycle telemetry only — does not feed
    # back into the decision policy in C1.
    profile_counts_in = results.get("coupling_posture_profile_used_counts") or {}
    if isinstance(profile_counts_in, dict) and profile_counts_in:
        existing = dict(new_state.get("coupling_posture_profile_usage_counts") or {})
        for key, value in profile_counts_in.items():
            try:
                existing[str(key)] = int(existing.get(str(key), 0)) + int(value or 0)
            except (TypeError, ValueError):
                continue
        new_state["coupling_posture_profile_usage_counts"] = existing

    # Cross-tier safety rule: a pulse-only signal cannot leave the regime in
    # "exploit" by itself.  If the policy chose exploit on a pulse run, demote
    # the persisted regime to "hold" pending daily confirmation.
    if tier == "pulse" and config.regime == "exploit":
        new_state["regime"] = "hold"
        new_state["regime_streak"] = 0

    return new_state


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def render_report(
    *,
    tier: str,
    config: NextConfig,
    results: dict[str, Any],
    state_before: dict[str, Any],
    state_after: dict[str, Any],
    argv: Sequence[str],
    run_dir: Path,
    started_utc: str,
    finished_utc: str,
    engine_returncode: int,
) -> str:
    diag = results.get("diagnosis_counts", {})
    coupling = results.get("coupling_counts", {})
    synch = results.get("synchrony_counts", {})
    basin = results.get("basin_counts", {})
    handoff_excerpt = results.get("handoff_excerpt", "") or "(no handoff artifact)"
    lines: list[str] = []
    lines.append(f"# Snowball {tier} report — {finished_utc}")
    lines.append("")
    lines.append(f"- run_dir: `{run_dir.as_posix()}`")
    lines.append(f"- started_utc: {started_utc}")
    lines.append(f"- engine_returncode: {engine_returncode}")
    lines.append(f"- regime: {state_before.get('regime')} -> {state_after.get('regime')}")
    lines.append(f"- size: {config.size}")
    lines.append(f"- rationale: {config.rationale}")
    lines.append("")
    lines.append("## Outcome")
    lines.append(f"- variants: {results.get('variant_count', 0)}")
    lines.append(f"- natural Stabilizer entries: {results.get('natural_entries', 0)}")
    lines.append(f"- gate passes (sum): {results.get('gate_pass_total', 0)}")
    lines.append(f"- bounded nudges applied (sum): {results.get('nudge_applied_total', 0)}")
    lines.append(f"- positive forward windows (sum): {results.get('positive_forward_window_total', 0)}")
    lines.append(f"- consensus diagnosis: {results.get('consensus_diagnosis')}")
    lines.append(f"- consensus synchrony basis: {results.get('synchrony_consensus')}")
    lines.append(f"- consensus coupling posture: {results.get('coupling_consensus')}")
    lines.append(f"- consensus basin fragility: {results.get('basin_consensus')}")
    lines.append(f"- paper trigger: {results.get('paper_trigger')}")
    lines.append("")
    lines.append("## Counts")
    lines.append(f"- diagnosis: {_format_counts(diag)}")
    lines.append(f"- synchrony: {_format_counts(synch)}")
    lines.append(f"- coupling: {_format_counts(coupling)}")
    lines.append(f"- basin: {_format_counts(basin)}")
    lines.append("")
    lines.append("## State after")
    lines.append(
        f"- diagnosis_streak: {state_after.get('diagnosis_streak_label')} x {state_after.get('diagnosis_streak_count')}"
    )
    lines.append(f"- weak_synchrony_streak: {state_after.get('weak_synchrony_streak')}")
    lines.append(f"- observe_only_streak: {state_after.get('observe_only_streak')}")
    lines.append(f"- recent_yields_pulse: {state_after.get('recent_yields_pulse')}")
    lines.append(f"- recent_yields_daily: {state_after.get('recent_yields_daily')}")
    lines.append("")
    lines.append("## Engine argv")
    lines.append("```")
    lines.append(" ".join(argv))
    lines.append("```")
    lines.append("")
    lines.append("## Handoff excerpt")
    lines.append("```")
    lines.append(handoff_excerpt)
    lines.append("```")
    return "\n".join(lines) + "\n"


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "(none)"
    return ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))


# ---------------------------------------------------------------------------
# Ledger + retention
# ---------------------------------------------------------------------------


def append_ledger_row(
    *,
    tier: str,
    config: NextConfig,
    results: dict[str, Any],
    run_dir: Path,
    state_after: dict[str, Any],
    started_utc: str,
    finished_utc: str,
    engine_returncode: int,
    ledger_path: Path = LEDGER_PATH,
) -> None:
    row = {
        "origin": tier,
        "regime": state_after.get("regime"),
        "size": config.size,
        "rationale": config.rationale,
        "natural_entries": results.get("natural_entries", 0),
        "variant_count": results.get("variant_count", 0),
        "gate_pass_total": results.get("gate_pass_total", 0),
        "nudge_applied_total": results.get("nudge_applied_total", 0),
        "positive_forward_window_total": results.get("positive_forward_window_total", 0),
        "consensus_diagnosis": results.get("consensus_diagnosis"),
        "synchrony_consensus": results.get("synchrony_consensus"),
        "coupling_consensus": results.get("coupling_consensus"),
        "basin_consensus": results.get("basin_consensus"),
        "paper_trigger": results.get("paper_trigger"),
        "run_dir": run_dir.as_posix(),
        "started_utc": started_utc,
        "finished_utc": finished_utc,
        "engine_returncode": engine_returncode,
        "msf_ab_arm": state_after.get("last_msf_ab_arm"),
        "posture_ab_arm": state_after.get("last_posture_ab_arm"),
        "observe_only_streak": state_after.get("observe_only_streak"),
        "coupling_posture_profile_used_counts": results.get(
            "coupling_posture_profile_used_counts", {}
        ),
    }
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(row, sort_keys=True) + "\n")


POSTURE_AB_OUTCOMES_PATH = SNOWBALL_DIR / "posture_ab_outcomes.jsonl"


def summarize_posture_ab_outcomes(
    rows: Sequence[dict[str, Any]],
    *,
    output_path: Path | None = POSTURE_AB_OUTCOMES_PATH,
) -> list[dict[str, Any]]:
    """Pair daily explore/exploit ledger rows by posture A/B arm and emit deltas.

    Walks ``rows`` in order, keeping a buffer of the last unpaired control and
    last unpaired treatment row. When both are available it emits a delta
    record (treatment minus control) and clears the buffer. Rows whose origin
    is not ``daily`` or whose regime is not in ``{explore, exploit}`` are
    skipped. When ``output_path`` is given the delta records are appended as
    JSON lines (parent dirs created on demand). Returns the deltas regardless.
    """
    deltas: list[dict[str, Any]] = []
    buffered: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("origin") != "daily":
            continue
        if row.get("regime") not in {"explore", "exploit"}:
            continue
        arm = row.get("posture_ab_arm")
        if arm not in {"control", "treatment"}:
            continue
        buffered[arm] = row
        if "control" in buffered and "treatment" in buffered:
            ctrl = buffered.pop("control")
            trt = buffered.pop("treatment")
            profile_counts_b = trt.get("coupling_posture_profile_used_counts") or {}
            if isinstance(profile_counts_b, dict) and profile_counts_b:
                profile_used_b = max(
                    profile_counts_b.items(), key=lambda kv: (int(kv[1] or 0), str(kv[0]))
                )[0]
            else:
                profile_used_b = "none"
            deltas.append(
                {
                    "control_finished_utc": ctrl.get("finished_utc"),
                    "treatment_finished_utc": trt.get("finished_utc"),
                    "regime": trt.get("regime"),
                    "delta_natural_entries": int(trt.get("natural_entries", 0) or 0)
                    - int(ctrl.get("natural_entries", 0) or 0),
                    "delta_observe_only_streak": int(trt.get("observe_only_streak", 0) or 0)
                    - int(ctrl.get("observe_only_streak", 0) or 0),
                    "profile_used_b": profile_used_b,
                }
            )
    if output_path is not None and deltas:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("a", encoding="utf-8") as fp:
            for delta in deltas:
                fp.write(json.dumps(delta, sort_keys=True) + "\n")
    return deltas


def prune_old_runs(tier: str, *, retention: int, runs_dir: Path = RUNS_DIR) -> list[Path]:
    tier_dir = runs_dir / tier
    if not tier_dir.exists():
        return []
    children = sorted([p for p in tier_dir.iterdir() if p.is_dir()])
    excess = children[:-retention] if retention > 0 else []
    pruned: list[Path] = []
    for path in excess:
        with contextlib.suppress(OSError):
            shutil.rmtree(path)
            pruned.append(path)
    return pruned


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _utcnow_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc_timestamp_token() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def run_snowball(
    *,
    tier: str,
    force_regime: str | None,
    force_size: str | None,
    dry_run: bool,
) -> int:
    SNOWBALL_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    lock_path = SNOWBALL_DIR / "state.lock"
    with state_lock(lock_path):
        state_before = load_state()
    config = decide_next_config(state_before, tier, force_regime=force_regime, force_size=force_size)

    run_token = _utc_timestamp_token()
    run_dir = RUNS_DIR / tier / run_token
    argv = build_engine_argv(config, run_dir)

    if dry_run:
        print(f"[snowball:{tier}] DRY RUN")
        print(f"  regime: {state_before.get('regime')} -> {config.regime}")
        print(f"  size: {config.size}")
        print(f"  rationale: {config.rationale}")
        print(f"  argv: python entangled_manifolds.py {' '.join(argv)}")
        # Compute next-state preview using empty results so the user can see
        # how the schema would be touched.
        empty_results = parse_results(run_dir) if run_dir.exists() else {}
        if empty_results:
            preview = apply_results_to_state(
                state_before, tier=tier, config=config, results=empty_results, argv=argv
            )
            print(f"  next state regime: {preview.get('regime')}")
        return 0

    run_dir.mkdir(parents=True, exist_ok=True)
    started_utc = _utcnow_iso()
    completed = subprocess.run(
        [sys.executable, str(ENGINE_SCRIPT), *argv],
        cwd=str(EXCITON_ROOT),
        check=False,
    )
    finished_utc = _utcnow_iso()

    results = parse_results(run_dir)
    with state_lock(lock_path):
        state_before_persist = load_state()
        state_after = apply_results_to_state(
            state_before_persist, tier=tier, config=config, results=results, argv=argv
        )
        save_state(state_after)
        append_ledger_row(
            tier=tier,
            config=config,
            results=results,
            run_dir=run_dir,
            state_after=state_after,
            started_utc=started_utc,
            finished_utc=finished_utc,
            engine_returncode=int(completed.returncode),
        )

    report = render_report(
        tier=tier,
        config=config,
        results=results,
        state_before=state_before_persist,
        state_after=state_after,
        argv=argv,
        run_dir=run_dir,
        started_utc=started_utc,
        finished_utc=finished_utc,
        engine_returncode=int(completed.returncode),
    )
    (run_dir / "report.md").write_text(report, encoding="utf-8")
    LATEST_REPORT_PATH.write_text(report, encoding="utf-8")

    retention = PULSE_RETENTION if tier == "pulse" else DAILY_RETENTION
    prune_old_runs(tier, retention=retention)

    print(report)
    return int(completed.returncode)


# ---------------------------------------------------------------------------
# argparse entrypoint
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", choices=VALID_TIERS, required=True)
    parser.add_argument("--force-regime", choices=(*VALID_REGIMES, "auto"), default="auto")
    parser.add_argument("--force-size", choices=(*VALID_SIZES, "auto"), default="auto")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    force_regime = None if args.force_regime == "auto" else args.force_regime
    force_size = None if args.force_size == "auto" else args.force_size
    return run_snowball(
        tier=args.tier,
        force_regime=force_regime,
        force_size=force_size,
        dry_run=bool(args.dry_run),
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
