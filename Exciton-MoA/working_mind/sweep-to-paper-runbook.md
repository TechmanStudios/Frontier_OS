# Sweep To Paper Runbook

This note shows the shortest bounded path from a sweep-produced uncertainty signal to a `working_mind` paper intake.

## Purpose
- keep outside-paper discovery tied to real `Exciton-MoA` runtime evidence
- preserve the uncertainty framing across discovery, approval, and intake
- avoid retyping the same bottleneck summary by hand at each step
- place accepted papers into subject folders without turning `working_mind` into a flat archive

## Expected sweep artifacts
After a sweep run, look under the chosen sweep root, typically `working_data/sweep_runs/<run-id>/` or the root passed to `--sweep-root-dir`.

Expected files:
- `sweep_summary.jsonl`
- `sweep_summary.csv`
- `sweep_ranked_summary.txt`
- `sweep_compact_comparison.txt`
- `sweep_paper_diagnostics.txt`
- `sweep_uncertainty_paper_handoff.md`
- `paper_finder_recommendation.md`

The paper workflow starts from `sweep_uncertainty_paper_handoff.md`.

## Step 1: Generate a sweep
Example shape:

```powershell
g:/docs/TechmanStudios/sol/Frontier_OS/.venv/Scripts/python.exe Exciton-MoA/entangled_manifolds.py --sweep --sweep-root-dir Exciton-MoA/working_data/sweep_runs/demo_run --cycles 4 --enable-hint-gate --enable-bounded-nudges --live-embeddings
```

Review these first:
- `sweep_paper_diagnostics.txt`
- `sweep_uncertainty_paper_handoff.md`

If the ranked and compact sweep summaries show a sweep-wide `Paper-trigger consensus:` line with calm but uniformly `borderline` synchrony, do not widen the search space immediately. That is the sign to try the near-pass-maturity policy experiment before assuming a topology change is required.

## Step 1A: Optional near-pass-maturity policy experiment
Use this only when the sweep is telling the same story repeatedly:
- no natural entries
- repeated `low_variance_candidate` diagnoses
- repeated near-pass evidence with small confidence or reliability gaps
- bounded paper handoff still pointing at synchrony-margin or conservative-gating ambiguity

Example shape:

```powershell
g:/docs/TechmanStudios/sol/Frontier_OS/.venv/Scripts/python.exe Exciton-MoA/entangled_manifolds.py --runtime-preset best-pocket --sweep --sweep-root-dir Exciton-MoA/working_data/sweep_runs/near_pass_probe --enable-hint-gate --enable-bounded-nudges --enable-near-pass-maturity-nudges --near-pass-confidence-gap-max 0.10 --near-pass-reliability-gap-max 0.12 --near-pass-sample-gap-max 0 --near-pass-observe-feedback-scale 0.20 --sweep-embedding-a-locs 0.48 0.50 0.52 --sweep-embedding-b-locs 0.56 0.58 --sweep-embedding-drifts 0.04 0.05 0.06 0.07 --sweep-cycle-counts 12 18 --sweep-seeds 149 211
```

What this experiment does:
- keeps the main hint gate honest, so blocked ticks still stay blocked
- allows a tiny `observe`-only feedback nudge when the block is near-pass-mature and the experiment flag is on
- records the experiment settings in sweep JSONL and CSV outputs

What success would look like:
- some runs start showing `observe_via_near_pass_maturity`
- the nudge path produces positive forward coherence windows or clearer separation between conservative gating and structurally poor synchrony pockets

What failure would look like:
- still zero applied maturity nudges, or
- maturity nudges apply but produce no positive windows and no better pocket separation

If it fails, keep the paper path primary and do not reinterpret the result as proof that topology is the next lever.

## Step 2: Invoke the finder from the bounded handoff
Use `.github/prompts/sweep-paper-finder-handoff-template.md` as the operator prompt.

Minimal operator request:

```text
Use sol-paper-finder on Exciton-MoA/working_data/sweep_runs/demo_run/sweep_uncertainty_paper_handoff.md. Keep the search bounded to one paper if possible, return approval-ready metadata, and include a recommendation rationale suitable for paper_handoff.py.
```

Expected finder output:
- one recommended paper or a very small role-distinct set
- stable source URL
- suggested local filename
- title, authors, year, domain tags, subject folder, and source status when clear
- short recommendation rationale
- for unattended flow, prefer a recommendation artifact matching `.github/prompts/paper-finder-recommendation-template.md`

The sweep root now gets a default `paper_finder_recommendation.md` stub automatically. The finder should overwrite that file in place rather than inventing a second recommendation path.

Preferred artifact writer:

```powershell
g:/docs/TechmanStudios/sol/Frontier_OS/.venv/Scripts/python.exe Exciton-MoA/paper_finder_artifact.py --uncertainty-handoff Exciton-MoA/working_data/sweep_runs/demo_run/sweep_uncertainty_paper_handoff.md --source-url https://example.org/paper.pdf --suggested-filename chosen-paper.pdf --title "Chosen Paper" --authors "A. Author; B. Author" --year 2024 --domain-tags "synchrony, control-policy" --recommendation-rationale "Recommended because it best matches the blocked-gate ambiguity while staying narrower than topology-first alternatives."
```

That command writes or overwrites `paper_finder_recommendation.md` in the same sweep-run directory by default.

## Step 3: Prefill intake and proceed by default
Once a paper is chosen, convert the bounded uncertainty handoff plus approved or auto-selected paper metadata into a prefilled intake artifact.

By default, a strong bounded recommendation should continue straight into `working_mind` intake. Only pause for manual approval if you explicitly want to review candidates before synthesis.

Example:

```powershell
g:/docs/TechmanStudios/sol/Frontier_OS/.venv/Scripts/python.exe Exciton-MoA/paper_handoff.py --uncertainty-handoff Exciton-MoA/working_data/sweep_runs/demo_run/sweep_uncertainty_paper_handoff.md --source-url https://example.org/paper.pdf --suggested-filename chosen-paper.pdf --title "Chosen Paper" --authors "A. Author; B. Author" --year 2024 --domain-tags "synchrony, control-policy" --subject-folder synchronization --source-status summary-first-pdf-pending --recommendation-rationale "Recommended because it best matches the blocked-gate ambiguity while staying narrower than topology-first alternatives."
```

Default output:
- `approved_paper_intake_handoff.md` written next to the uncertainty handoff

For unattended bounded intake, add `--auto-ingest` to the same command. That immediately writes the `working_mind` index entry and applied summary scaffold after the handoff is generated.

If the finder already emitted a `PAPER FINDER RECOMMENDATION` artifact, the direct path is:

```powershell
g:/docs/TechmanStudios/sol/Frontier_OS/.venv/Scripts/python.exe Exciton-MoA/paper_handoff.py --uncertainty-handoff Exciton-MoA/working_data/sweep_runs/demo_run/sweep_uncertainty_paper_handoff.md --recommendation-file Exciton-MoA/working_data/sweep_runs/demo_run/paper_finder_recommendation.md --auto-ingest
```

That bypasses manual metadata copying while keeping the same bounded uncertainty frame.

## Step 4: Hand off to synthesis
Use `approved_paper_intake_handoff.md` as the preferred bridge into `sol-paper-synthesizer`.

The synthesizer should then produce:
- `working_mind/papers-index.md` entry
- `<paper-file-base>.applied-summary.md`
- one canonical subject-folder placement for the paper assets
- optional follow-on note if the translation is already concrete

If the PDF is inaccessible but the source is still strong, keep going with summary-first intake:
- write the `papers-index.md` entry with `source status: summary-first-pdf-pending`
- write the applied summary from the stable source and bounded handoff context
- record the intended paper path under the subject folder so the PDF can land later without changing the note structure

If you already have a local PDF path, the unattended writer will copy it into the canonical subject folder and promote `source status` to `pdf-present` on the same pass.

## Promotion layer
Every unattended ingest also updates `frontier-learning-ledger.md`.

Current rule:
- one ingest keeps the lesson in `working_mind`
- two corroborating ingests in one subject folder promote the pattern to a Frontier-OS knowledge candidate in the ledger

Promotion outputs now include:
- `knowledge_notes/<subject-folder>.knowledge-note.md`
- `repo-memory-promotions.md`

When an agent is driving the flow, it should mirror the exact `Memory line` from `repo-memory-promotions.md` into `/memories/repo/frontier-os-exciton-moa.md`.

## What to preserve end to end
- the original bottleneck statement
- the telemetry and replay/sweep signals behind the uncertainty
- the intervention class
- the recommendation rationale for why the chosen paper won

If any of those are lost between steps, the paper is more likely to become a generic reference instead of a working engineering input.