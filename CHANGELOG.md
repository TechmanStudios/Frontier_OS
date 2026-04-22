# Changelog

All notable changes to Frontier_OS are documented here. The format is loosely based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) once it reaches v1.0.

## [Unreleased]

## [0.1.0] — 2026-04-22

First public release of Frontier_OS as a self-contained repository. Consolidates the Exciton-MoA flagship runtime, the entangled-pair / paper-ingestion research stack, and the public-development scaffolding.

### Substrate, firmware, telemetry
- Manifold-native `BlankManifoldCore` substrate with reproducible per-manifold seeding and connected-graph repair.
- `StatisticalPrism` transducer compresses N-D embeddings to statistical-moment showers.
- `ExcitonEngine` hosts the seven Giants (Statistician, Optimizer, N-Body, Graph Navigator, Linear Algebraist, Integrator, Aligner).
- `OntologicalOrchestrator` computes the Hotspot Functional with log-compressed density / shear / vorticity channels and emits adaptive-tau threshold bursts persisted to `working_data/adaptive_tau_history.jsonl`.
- `LatentMediator` cross-cycle blackboard and `HippocampalTransducer` burst archival under `working_data/`.

### Entangled-pair runtime
- `EntangledSOLPair` two-manifold runtime with deterministic wormhole registry, damped shared-flux exchange, and per-pair `shared_entanglement_locus_*.json`.
- `EntanglerGiant` actively steers `EntanglementControls` aperture / damping / phase, with a named **Stabilizer** mode and selective wormhole-weight maps.
- `SharedMediator` pair-scoped blackboard preserves hint-bearing summary channels across ticks.
- `HintGatingPolicy` controls bounded nudges, observe-feedback nudges, and an opt-in negative-collapse stabilize branch.
- Reproducibility harness writes `run_checkpoint.json` plus `--clean-run-reset` / `--repeat-run-count` repeat-run comparisons.

### Replay & sweep harness
- `HippocampalReplay` summarizes pair telemetry, hint-gate decisions, nudge outcomes, and threshold-aware first-pass / first-near-pass diagnostics.
- Sweep harness in `entangled_manifolds.py` produces `sweep_summary.{jsonl,csv}`, `sweep_compact_comparison.txt`, ranked summaries, and paper-trigger consensus lines.
- `--runtime-preset best-pocket` exposes the validated `locA=0.50, locB=0.57, drift=0.06, scale=0.08, cycles=12, seed=149` configuration.

### Bounded paper workflow
- `working_mind/` is the manual-first paper inbox with two stabilization papers, applied summaries, and translation notes.
- Paper-linked diagnostics (`synchrony_margin`, `basin_fragility`, coupling-posture) flow through replay and sweep artifacts (`sweep_paper_diagnostics.txt`).
- `sweep_uncertainty_paper_handoff.md` and `paper_handoff.py` bridge sweep uncertainty to `sol-paper-finder` and `sol-paper-synthesizer`.
- Operator runbook lives at `Exciton-MoA/working_mind/sweep-to-paper-runbook.md`.

### Public-development scaffolding (this release)
- AGPL-3.0 license, `COMMERCIAL.md` dual-license contact, and CLA-Assistant workflow under `legal/CLA.md`.
- `README.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CITATION.cff`, `NOTICE` at the repo root.
- GitHub Actions: pytest matrix (Linux + Windows × Python 3.11 + 3.12), ruff lint + format check, CLA bot.
- Issue templates (bug / feature / research-question), PR template with reproducibility checklist, Dependabot config, CODEOWNERS.
- `pyproject.toml` configures ruff and pytest defaults.
- AGPL copyright headers added to every Python source file via `scripts/add_copyright_headers.py`.
- `.gitignore` + `.gitattributes` (Git LFS for `working_data/**`); paywalled PDFs excluded with `*.PLACEHOLDER.md` siblings.
