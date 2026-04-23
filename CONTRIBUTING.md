# Contributing to Frontier_OS

Thanks for your interest in Frontier_OS. This document captures the conventions you need to know to contribute productively.

## Before you start

1. **Read the architecture:** [`README.md`](README.md), [`Exciton-MoA/master_equations.md`](Exciton-MoA/master_equations.md), and [`Exciton-MoA/master_glossary.md`](Exciton-MoA/master_glossary.md).
2. **Sign the CLA.** Non-trivial PRs cannot be merged without a signed [Contributor License Agreement](legal/CLA.md). The CLA bot will prompt you on your first PR. The CLA is what allows the project to dual-license commercially while remaining AGPL-3.0 to the community.
3. **Open an issue first** for substantive changes. For research-style changes (new diagnostics, new policy levers, new paper bridges) use the *Research question* issue template so we can align before code lands.

## Development setup

```bash
git clone https://github.com/TechmanStudios/Frontier_OS.git
cd Frontier_OS
python -m venv .venv
# Windows:  .venv\Scripts\Activate.ps1
# POSIX:    source .venv/bin/activate
pip install -r Exciton-MoA/requirements.txt
pip install ruff==0.15.11 pytest pre-commit
pre-commit install
```

## Tests

The canonical test root is [`Exciton-MoA/blank_manifold/pre_check_tests/`](Exciton-MoA/blank_manifold/pre_check_tests/).

```bash
pytest Exciton-MoA/blank_manifold/pre_check_tests
```

Every PR must keep this suite green. CI runs it on Linux and Windows for Python 3.11 and 3.12.

## Code style

- **Formatter / linter:** `ruff`, pinned to `==0.15.11` in CI ([`.github/workflows/lint.yml`](.github/workflows/lint.yml)). Keep your local install on the same version (`pip install ruff==0.15.11`) so `ruff format` output matches CI; ruff's formatter changes between minor versions and an unpinned local install is the most common source of "green locally, red on CI" drift. A `pre-commit` config is provided ([`.pre-commit-config.yaml`](.pre-commit-config.yaml)) — run `pre-commit install` once and the hook will run `ruff check --fix` and `ruff format` before every commit.
- **Imports:** keep the existing flat-module pattern; the legacy compatibility shims at the project root (`blank_config`, `blank_manifold_core`, `transducer`, `excitons`, `telemetry`, `main`) must continue to import cleanly.
- **Avoid over-engineering.** Don't add abstractions, comments, or type annotations to code you didn't change. Don't add error handling for cases that can't happen.

## Commit / PR conventions

- Branch from `main`. Use short, descriptive branch names (`feature/...`, `fix/...`, `docs/...`).
- Conventional Commits style is encouraged but not enforced (`feat:`, `fix:`, `docs:`, `chore:`).
- Squash-merge by default.
- PR descriptions must mention:
  - what changed and why,
  - which tests cover it,
  - any reproducibility implications (sweep outputs, checkpoint format, telemetry fields).

## Reproducibility & control discipline

Frontier_OS is a research substrate. The following rules exist to keep results trustworthy:

1. **Telemetry is read-only.** Don't let analytics (replay, paper diagnostics) feed back into live control without an explicit policy flag.
2. **New control levers are opt-in.** Add them as `HintGatingPolicy` flags / CLI arguments and default them off until validated by a sweep.
3. **Don't change determinism.** Anything that touches manifold construction, scan order, or pair seeding must preserve the existing fingerprints, or update the comparison harness alongside the change.
4. **Don't commit copyrighted PDFs.** Paywalled references are gitignored (see [`references/README.md`](references/README.md)). Use placeholder markdown + DOI/URL instead.

## Reporting security issues

Do **not** open a public issue for vulnerabilities. Follow [`SECURITY.md`](SECURITY.md).

## Questions

Open a GitHub Discussion or use the *Research question* issue template.
