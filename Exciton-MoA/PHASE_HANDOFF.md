# Exciton-MoA — Phase Handoff for Codex

**Repo:** `TechmanStudios/Frontier_OS` · **Subtree:** `Exciton-MoA/` · **Date:** 2026-04-23
**Test baseline:** `370` tests passing in `Exciton-MoA/blank_manifold/pre_check_tests/` (~110 s)

This document is the running build log + scope map for the Exciton-MoA "novel
solutions" track. It exists so any agent (Codex, Copilot, a fresh contributor)
can pick up the work without replaying conversation history. Phases are landed
in order; each phase only **adds** consumers / schemas / state fields and never
mutates existing contracts.

---

## Architectural ground rules (do not break)

1. **Engine CLI is stable.** New behavior lands as snowball-side consumers + a
   `state.json` advisory namespace. Engine flags only grow when an entire phase
   is dedicated to it (W4 was the last such case).
2. **`state.json` extension is additive.** Every new field must be added to
   `default_state()` in [Exciton-MoA/scripts/snowball_experiment.py](Exciton-MoA/scripts/snowball_experiment.py)
   in the same commit, otherwise `load_state` silently drops it (the trap that
   bit W3).
3. **Slab-A consumer pattern.** All new consumers use
   `snowball_consumer.write_consumer_artifact` + `append_consumer_ledger` and
   write under `working_data/snowball/consumers/<consumer_name>/<token>/`.
4. **State writeback is locked.** Use `state_lock(STATE_LOCK_PATH)` +
   `load_state()` + mutate + `save_state()`. Pattern reference:
   [Exciton-MoA/scripts/counterfactual_probe.py](Exciton-MoA/scripts/counterfactual_probe.py).
5. **Schema additions, not bumps.** New `validate_*` functions land in
   [Exciton-MoA/scripts/agent_handoff_schemas.py](Exciton-MoA/scripts/agent_handoff_schemas.py)
   under a new `SCHEMA_VERSIONS[<name>] = 1` entry. Existing contracts stay v1.
6. **Tests live in [Exciton-MoA/blank_manifold/pre_check_tests/](Exciton-MoA/blank_manifold/pre_check_tests/).**
   Each phase ships +N tests; the count is the regression contract.

---

## Phase ledger (landed)

| Phase | Theme | Final commit(s) | Tests | Headline artifact |
|---|---|---|---|---|
| Starter #2 | Reproducibility hardening | (pre-log) | 240 | sorted neighbor iter + `np.round(., 12)` quantization |
| Starter #1 | MSFGuard entangler mode | (pre-log) | 243 | `HintGatingPolicy.enable_msf_guard` + λ̂ surrogate |
| Starter #6 | Cross-pair Lesson Compiler v1 | (pre-log) | 258 | `scripts/lesson_compiler.py` + Mon 10:00 UTC workflow |
| **B / W1** | MSFGuard sweep rollup | (Phase B series) | 261 | `summarize_msf_guard_outcomes` |
| **B / W2** | Paired A/B MSFGuard variant | " | 269 | `msf_ab_alternation` + `__msf_ab_treatment__` |
| **B / W3** | Lesson advisory clamp | " | 286 | `scripts/lesson_advisory_writer.py` + Mon 11:00 UTC workflow |
| **B / W4** | Coupling-posture adaptive gate profiles | " | 293 | `CouplingPostureGateProfile` + `--coupling-posture-profile` CLI |
| **B / W5** | Reproducibility-tier baseline | " | 302 | `scripts/repro_baseline_check.py` + Tue 09:00 UTC workflow |
| **C / C1** | Snowball ships W4 profiles per regime | `102aa14` | ~310 | `DEFAULT_COUPLING_POSTURE_PROFILES` + rationale |
| **C / C2** | Coupling-posture A/B variant | `fa3519f` | ~320 | `posture_ab_alternation` + `summarize_posture_ab_outcomes` |
| **C / C3** | Lesson Compiler v2 (MSF + posture telemetry) | `2ecc6ff` | 329 | `schema_version=2` + `per_profile_natural_entry_means` |
| **D / D1** | Arm-promotion engine | `b78ffb1` | 352 | `scripts/arm_promotion.py` + `state.arm_promotion` |
| **D / D2** | Snowball acts on promotions + recommended profile | `0655ac7` | 364 | promotion-locked arms in `decide_next_config` |
| **D / D3** | Weekly snowball decision report + workflow | `740635e` (Frontier_OS) + `4a808cd3` (parent `.github`) | **370** | `scripts/snowball_decision_report.py` + Wed 09:00 UTC workflow |

### What the loop does today (post-Phase D)

1. Nightly snowball runs alternating 2×2 A/B grid (MSFGuard × posture-profile).
2. After each daily cycle, `summarize_msf_ab_outcomes` and
   `summarize_posture_ab_outcomes` emit paired ledger rows.
3. `arm_promotion.py` reads rolling window (default N=10), applies threshold
   (default |Δ natural_entries| ≥ 0.5), writes `state.arm_promotion` and a
   consumer artifact. Promotion is **reversible** — regression flips back.
4. `decide_next_config` honors the promotion (locks the winning arm, freezes
   alternation) and, when posture-treatment is locked + the advisory clamp has
   a clear `recommended_profile_counts` winner, narrows specs to that profile.
5. Wed 09:00 UTC `sol-exciton-decision-report-weekly` publishes `report.md` +
   `summary.json` consolidating regime distribution, both arm promotions, the
   advisory clamp, and any active safety_clamp incident.

### Active workflows (CI cadence)

| When | Workflow | Purpose |
|---|---|---|
| Mon 10:00 UTC | `sol-exciton-lessons-weekly.yml` | Lesson Compiler v2 |
| Mon 11:00 UTC | `sol-exciton-lesson-advisory-weekly.yml` | Promote v2 lessons to advisory clamp |
| Tue 09:00 UTC | `sol-exciton-repro-baseline-weekly.yml` | Hash-equality regression on pinned pocket |
| **Wed 09:00 UTC** | **`sol-exciton-decision-report-weekly.yml`** | **Operator-readable summary (NEW in D3)** |
| Nightly | `sol-exciton-snowball.yml` | Daily/hold cycles + paired A/B emission |

All four weekly workflows share the `sol-exciton-snowball-${{ github.ref }}`
concurrency group with `cancel-in-progress: false` so they never trample
nightly snowball or each other.

---

## Phase E — proposed next scope (not started)

Phase D explicitly deferred several items to Phase E. The plan below is a
**menu** — pick one (or a coherent pair) per phase. None of these are blocked
on outside work; all are additive following the rules above.

### Recommended next pick: **E1 — Decision-report regression auto-paging**
**Why first:** the loop is now closed; E1 is the smallest possible step that
gives the loop *teeth*. It detects a real regression on the new Wed 09:00 UTC
report and surfaces it without requiring a human to read the markdown.
- New `scripts/decision_report_monitor.py` consumer, runs after the report.
- Reads the last K (default 4) `summary.json` files from the
  `snowball_decision_report` consumer dir.
- Fires an `incident_report` (existing schema, no bump) when:
  - `msf_promotion` flips from `favors_treatment` → `favors_control` between
    consecutive weeks, or
  - `mean_delta_natural_entries` drops by ≥ 1.0 week-over-week, or
  - `regime_counts["hold"]` exceeds 0.7 of the window.
- Posts a job-summary block + uploads the incident as an actions artifact.
  Workflow chains after the Wed 09:00 UTC report (Wed 09:30 UTC).
- **Scope:** ~250 LoC + 6-8 tests. Single new consumer, no schema work.

### E2 — Twin-pair counterfactual (Tier-2 menu item #4)
**Why:** today basin fragility is only known *after* a sweep finishes. A live
shadow pair gives a per-tick `basin_response_delta`.
- Run a frozen-controls clone of `EntangledSOLPair` every N ticks, share state
  via `SharedMediator`.
- Engine-side change: extends `EntangledSOLPair` (NOT a snowball consumer).
  Larger surface — schedule alone, not bundled with E1.
- New `summarize_basin_response_delta` rollup; new sweep_summary columns.
- **Scope:** ~600 LoC + 12-15 tests. Touches `entangled_manifolds.py`,
  `entangler.py`, `hippocampal.py`, replay.

### E3 — Synchrony-margin surrogate (Tier-2 menu item #5)
**Why:** train a tiny offline model on the existing sweep_summary corpus and
expose a `paper_synchrony_margin_surrogate ∈ [0,1]` for `decide_next_config`
to use as a tiebreaker.
- New `scripts/train_synchrony_surrogate.py` (offline; produces a versioned
  artifact under `working_data/models/`).
- HippocampalReplay loads it lazily; replay emits the surrogate per tick.
- `decide_next_config` uses it to break ties between explore/exploit (does NOT
  override regime).
- **Scope:** ~400 LoC + new dependency on a tiny model lib (sklearn or pure
  NumPy logistic). 10-12 tests. Best done after E1 so the surrogate has the
  monitor's regression signal as a labelled negative class.

### E4 — Cross-pair evidence (Tier-3 #7, partial)
**Why:** today every consumer is single-pair. Cross-pair witness scoring is
the next architectural lift.
- Light version: extend Lesson Compiler to mine across pair_id partitions in
  sweep_summary (currently it groups by pocket only). Schema bump to v3.
- Heavy version: full `EntangledSOLTriad` facade (Tier-3 menu #7) — defer
  until single-pair loop is stable for ≥ 1 month of CI runs.
- **Scope (light):** ~300 LoC + lesson_compiler v3 schema. 8 tests.

### E5 — Tier-3 backlog (deferred-deferred)
- **#8 RL/bandit τ controller** — single seam in `telemetry.py::_compute_adaptive_tau`.
- **#9 Bandit neighbor reordering** — `EXPLORE_*_NEIGHBORS` priority writer.
- **#10 Paper-feedback closed loop** — parses `working_mind/papers-index.md`
  operator markup; advisory only when `consensus_confidence == "high"`.

These are all small individually but each closes a different paper-feedback
gap. Pick based on which gap is hurting most after E1-E3 land.

---

## Best alignment for Codex to continue

**Suggested execution order:**
1. **E1 first.** Smallest scope, sharpest feedback. Without it, regressions
   in the Phase D loop are silent until someone opens the Wed report.
2. **E3 in parallel with E1** if a second agent is available — they touch
   disjoint files (E1: new monitor consumer; E3: replay + new model artifact).
3. **E2 after E1+E3 land.** It's the largest surface and benefits from having
   the monitor catch any twin-pair-induced regressions immediately.
4. **E4 (light) any time after E2** — naturally extends the lesson compiler
   surface E2 will already be exercising.
5. **E5 menu** — pick based on operator pain after E1-E4.

**Per-phase mechanics that have proven reliable (use these):**
- Branch off `main`, work on Frontier_OS subtree.
- Run `python -m pytest blank_manifold/pre_check_tests/ -q` from
  `Exciton-MoA/` after every meaningful edit. Final sweep before commit.
- Commit message format:
  `feat(<area>): <one-liner>` + body with test delta
  (e.g. `tests: 370 → 378 (+8)`).
- For commits that touch the parent `TechmanStudios/sol` repo (e.g. workflow
  YAMLs under the parent's `.github/workflows/`), use the stash-recovery
  pattern that landed `4a808cd3`:
  ```pwsh
  cd .github
  git add workflows/<file>.yml
  git commit -m "..." -m "..."
  git stash --include-untracked
  git pull --rebase
  git push
  git stash pop
  ```
  This avoids the stash sweeping up the target file before the commit lands.

**Reference reading order for a fresh agent:**
1. This file.
2. [Exciton-MoA/scripts/snowball_experiment.py](Exciton-MoA/scripts/snowball_experiment.py) —
   `default_state`, `decide_next_config`, `apply_results_to_state`,
   `build_engine_argv` are the four functions every consumer eventually
   touches.
3. [Exciton-MoA/scripts/agent_handoff_schemas.py](Exciton-MoA/scripts/agent_handoff_schemas.py) —
   `SCHEMA_VERSIONS` table is the contract registry.
4. [Exciton-MoA/scripts/snowball_consumer.py](Exciton-MoA/scripts/snowball_consumer.py) —
   `write_consumer_artifact` / `append_consumer_ledger` / `state_lock` /
   `load_state` / `save_state` are the consumer-kit entry points.
5. [Exciton-MoA/scripts/arm_promotion.py](Exciton-MoA/scripts/arm_promotion.py)
   and [Exciton-MoA/scripts/snowball_decision_report.py](Exciton-MoA/scripts/snowball_decision_report.py) —
   the two newest consumers; copy this shape for E1 / E3 / E4.

---

## Hard "do not" list

- Do NOT mutate existing schemas in
  [Exciton-MoA/scripts/agent_handoff_schemas.py](Exciton-MoA/scripts/agent_handoff_schemas.py).
  Add a new contract instead.
- Do NOT add a new state field without putting it in `default_state()` in the
  same commit. `load_state` will silently drop it.
- Do NOT replace NetworkX / NumPy. Out of scope at every phase.
- Do NOT change the snowball workflow concurrency model.
- Do NOT add new engine CLI flags inside a consumer phase. If a phase needs
  engine surface, that's the whole phase (like W4 was).
- Do NOT make the Wed 09:00 UTC decision-report workflow fail-loud. Missing
  inputs MUST degrade to an empty summary so first-week or low-data runs
  don't break the morning.
