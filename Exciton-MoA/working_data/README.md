# working_data/ — local-only reproducibility artifacts

This directory holds the sweep outputs, hippocampal-burst archives, mediator state, and per-variant telemetry that Frontier_OS produces during research runs. It is **gitignored** because the local tree exceeds 15 GB across 30k+ files — far beyond what is reasonable to clone.

## How to regenerate

The validated reproducible configurations are exposed as CLI presets:

```bash
# Single best-pocket entangled-pair runtime
python Exciton-MoA/entangled_manifolds.py --runtime-preset best-pocket

# Smallest end-to-end smoke
python Exciton-MoA/main.py
```

Sweep harnesses, paper-handoff workflows, and sample sweep CLIs are documented in [`Exciton-MoA/working_mind/sweep-to-paper-runbook.md`](../working_mind/sweep-to-paper-runbook.md).

## What lands here when runs execute

- `adaptive_tau_history.jsonl` — rolling per-scan summaries used by telemetry / replay.
- `hippocampal_burst_*.json` — threshold-burst archives (see `hippocampal_replay.py`).
- `latent_mediator_state*.json` — persistent latent-mediator blackboards.
- `shared_entanglement_locus_*.json` — pair-scoped shared mediator state.
- `sweep_runs/`, `bounded_nudge_sweeps/`, `*_sweep/` — sweep harness outputs (`sweep_summary.{jsonl,csv}`, `sweep_compact_comparison.txt`, `sweep_paper_diagnostics.txt`, `sweep_uncertainty_paper_handoff.md`, plus per-variant `primary/` and `secondary/` manifolds).
- `repro_*` — reproducibility comparison roots from `--clean-run-reset` / `--repeat-run-count`.

If you want to share a specific sweep result for an issue or PR, attach the relevant `sweep_summary.csv` + `sweep_uncertainty_paper_handoff.md` directly to the GitHub thread rather than committing them.
