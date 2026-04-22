# Frontier_OS

> **A research operating system for post-pipeline agentic AI.**
> Manifold-native runtime where data flows along dynamically carved geodesics instead of being routed by a central orchestrator.

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)
[![CI](https://github.com/TechmanStudios/Frontier_OS/actions/workflows/ci.yml/badge.svg)](https://github.com/TechmanStudios/Frontier_OS/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

Frontier_OS is the umbrella research OS for a new class of agentic-AI substrate. Its flagship module, **[Exciton-MoA](Exciton-MoA/)**, models computation as continuous probability flow on a Riemannian manifold: incoming data is broadcast as a statistical shower, seven mathematical "giants" act as excitons that locally warp the metric tensor, and answers emerge from gravitational collapse and phase synchronization rather than from explicit routing.

Around that core, Frontier_OS provides entangled SOL-pair runtimes, a stabilizer / hint-gating control layer, hippocampal replay and adaptive telemetry, reproducible sweep harnesses, and a bounded sweep-to-paper workflow that converts repeated, decision-relevant uncertainty into peer-reviewed literature handoffs.

---

## Why this exists

Traditional Mixture-of-Agents systems route queries through a central orchestrator, which scales poorly on recursive or high-dimensional data. Exciton-MoA removes the central traffic cop:

- The substrate is a **non-Euclidean semantic manifold** $(M, g)$ initialized in a pristine hyperbolic vacuum.
- Incoming data is compressed to its **statistical moments** and broadcast as a probability shower.
- Specialized **Exciton operators** physically alter the metric tensor where they resonate.
- Data flows downhill along the dynamically carved geodesics — no algorithmic dispatch required.

A metacognitive observer (the **Ontological Orchestrator**) sweeps the manifold computing a Hotspot Functional $H(x, t)$, and triggers **threshold bursts** when a localized region crosses the Jeans Mass.

---

## The four pillars

| Pillar | Module | Role |
| --- | --- | --- |
| **Substrate** | `BlankManifoldCore` | Pristine 1,024-node hyperbolic lattice — the physical hardware. |
| **Transducer** | `StatisticalPrism` | Compresses N-D embeddings to their statistical moments and broadcasts them as a probability shower. |
| **Firmware** | `ExcitonEngine` | The seven Giants, executing continuous differential geometry on the semantic state field. |
| **Telemetry** | `OntologicalOrchestrator` | Computes $H(x, t)$, triggers threshold bursts, and routes rendering compute. |

Beyond the core: **`EntangledSOLPair`** (two coupled manifolds with deterministic wormhole registry), **`HippocampalReplay`** (threshold-burst archival + paper-linked diagnostics), and a bounded **paper ingestion workflow** that lets repeated uncertainty escalate into peer-reviewed reading.

See [`Exciton-MoA/master_equations.md`](Exciton-MoA/master_equations.md) for the equations and [`Exciton-MoA/master_glossary.md`](Exciton-MoA/master_glossary.md) for the vocabulary.

---

## Repository layout

```
Frontier_OS/
├── Exciton-MoA/                     # Flagship runtime (manifold + giants + telemetry)
│   ├── blank_manifold_core.py       # Substrate
│   ├── transducer.py                # Statistical Prism
│   ├── excitons.py                  # 7 Giants
│   ├── telemetry.py                 # Ontological Orchestrator
│   ├── entangled_manifolds.py       # Coupled-pair runtime + sweep harness
│   ├── hippocampal_replay.py        # Burst replay + paper-linked diagnostics
│   ├── paper_handoff.py             # Sweep → approved-paper-intake bridge
│   ├── working_mind/                # Active research notes, runbooks, paper intake
│   │   └── sweep-to-paper-runbook.md
│   ├── working_data/                # Reproducibility artifacts (Git LFS)
│   └── blank_manifold/pre_check_tests/  # Test root
├── references/                      # Local-only PDFs (gitignored — see references/README.md)
├── LICENSE                          # AGPL-3.0
├── COMMERCIAL.md                    # Dual-license / proprietary-use contact
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
└── CITATION.cff
```

---

## Quickstart

> Requires Python 3.11 or 3.12 and [Git LFS](https://git-lfs.com/) for `working_data/`.

```bash
git clone https://github.com/TechmanStudios/Frontier_OS.git
cd Frontier_OS
python -m venv .venv
# Windows:  .venv\Scripts\Activate.ps1
# POSIX:    source .venv/bin/activate
pip install -r Exciton-MoA/requirements.txt
```

Run the smallest end-to-end Exciton-MoA cycle:

```bash
python Exciton-MoA/main.py
```

Run an entangled-pair runtime with the reproducible best-pocket preset:

```bash
python Exciton-MoA/entangled_manifolds.py --runtime-preset best-pocket
```

Run the test suite:

```bash
pytest Exciton-MoA/blank_manifold/pre_check_tests
```

---

## Reproducibility & the bounded paper workflow

Frontier_OS treats reproducibility as a first-class artifact, not a footnote:

- Every entangled runtime writes a `run_checkpoint.json` with manifold fingerprints, scan-order fingerprints, and per-tick mode/hint/gate histories.
- `--clean-run-reset` and `--repeat-run-count` run side-by-side comparisons under a fixed substrate.
- Sweep harness produces `sweep_summary.{jsonl,csv}`, `sweep_compact_comparison.txt`, `sweep_paper_diagnostics.txt`, and `sweep_uncertainty_paper_handoff.md`.

When a sweep produces *bounded, repeated, decision-relevant uncertainty*, the workflow auto-generates a paper-finder handoff. The full operator flow is documented in [`Exciton-MoA/working_mind/sweep-to-paper-runbook.md`](Exciton-MoA/working_mind/sweep-to-paper-runbook.md).

---

## Contributing

External contributions are welcome. Please read:

- [`CONTRIBUTING.md`](CONTRIBUTING.md) — branch / commit / test conventions.
- [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) — Contributor Covenant v2.1.
- [`legal/CLA.md`](legal/CLA.md) — Contributor License Agreement (required before merging non-trivial PRs).

Run `pytest Exciton-MoA/blank_manifold/pre_check_tests` before submitting.

---

## License & commercial use

Frontier_OS is released under the **GNU Affero General Public License v3.0** (see [`LICENSE`](LICENSE)).

If you want to use Frontier_OS or Exciton-MoA in a closed-source product, as a hosted service without releasing your modifications, or under terms other than the AGPL, see [`COMMERCIAL.md`](COMMERCIAL.md) for proprietary licensing.

---

## Citation

If Frontier_OS or Exciton-MoA contributes to academic work, please cite using the metadata in [`CITATION.cff`](CITATION.cff).

---

## Security

Report vulnerabilities privately per [`SECURITY.md`](SECURITY.md).

---

*Frontier_OS™ and Exciton-MoA™ are trademarks of Techman Studios.*
