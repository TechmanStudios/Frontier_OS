# Working Mind

`working_mind` is the local research inbox for `Exciton-MoA`.

Its purpose is to hold outside technical sources that can sharpen current engineering work without immediately promoting those sources into permanent repo knowledge.

## Scope
- Raw external sources that are directly relevant to the current development bottleneck
- Short applied summaries that translate a paper into concrete engineering implications for `Exciton-MoA`
- Automatic bounded intake for stable uncertainty handoffs, with optional manual review when needed

## What goes here
- PDFs or source documents for papers that are worth keeping in the current working set
- A short applied summary for each paper
- A lightweight index entry in `papers-index.md`
- Temporary paper-to-SOL translation notes when an outside concept needs to be mapped onto current telemetry or workflow decisions

## What does not go here
- Internal run artifacts: those stay under `working_data`
- Canonical long-lived project knowledge: promote that later into repo knowledge, instructions, or skills once it proves reusable
- Bulk literature dumps with no current engineering tie-in

## Minimal workflow
1. Start from a bounded uncertainty handoff or an explicitly chosen paper.
2. Resolve one canonical subject folder under `working_mind`.
3. Add the raw paper file when present, or record a stable source with `summary-first-pdf-pending` status when the PDF is not yet available.
4. Add one entry to `papers-index.md`.
5. Add one short applied summary named after the paper file, for example `1208.0045v1.applied-summary.md`.
6. If the paper later becomes reusable beyond the current task, promote the distilled insight into repo memory or `.github` customization files.

## Required metadata per paper
- subject folder
- local file path
- title
- authors
- year
- source URL
- ingestion date
- domain tags
- current relevance note
- summary file path
- source status
- trigger artifact or intake provenance

## Naming
- Raw paper: keep the source filename when practical
- Summary note: `<paper-file-base>.applied-summary.md`

## Folder model
- Keep `papers-index.md`, this README, runbooks, and cross-paper translation notes at the `working_mind` root.
- Place paper-specific assets under one canonical subject folder.
- Current subject folders:
  - `synchronization`
  - `basin-stability`
  - `topology-design`
  - `control-policy`
  - `experiment-design`
- If a paper spans multiple themes, store it once and use domain tags for the rest.

## Current papers

- `synchronization/PhysRevLett.80.2109.pdf`
	- Summary: `synchronization/physrevlett.80.2109.applied-summary.md`
	- Local file status: `pdf-present`
- `synchronization/1208.0045v1.pdf`
	- Summary: `synchronization/1208.0045v1.applied-summary.md`
	- Local file status: `pdf-present`
- `basin-stability/nphys2516.pdf`
	- Summary: `basin-stability/nphys2516.applied-summary.md`
	- Local file status: `pdf-present`

## Future automation
Paper-finding and paper-synthesis agents may write into this folder automatically when a bounded uncertainty handoff already justifies outside-paper use. This folder should still remain curated: one strong paper, one canonical subject folder, no bulk dumps.

The unattended writer path is now bounded to the same rule: generate the intake handoff, then synthesize the `papers-index.md` entry and applied summary from that payload. The writer only copies a local PDF when one is already available and otherwise leaves a summary-first scaffold with explicit `source status`.

Repeated ingests in the same subject folder now also update `frontier-learning-ledger.md`, which is the first bounded promotion layer for turning multiple paper intakes into a reusable Frontier-OS knowledge candidate instead of leaving the pattern implicit.

Once a subject folder reaches the corroboration threshold, the writer also creates `knowledge_notes/<subject-folder>.knowledge-note.md` and updates `repo-memory-promotions.md` with the exact repo-memory mirror payload that an agent should store under `/memories/repo/frontier-os-exciton-moa.md`.

## Current working notes
- `stabilization-paper-translation-note.md` bridges the first two stabilization papers into current telemetry fields, SOL concepts, and future uncertainty-driven rediscovery rules.
- `synchrony-margin-proxy-note.md` defines the first local diagnostic target for synchrony feasibility using existing telemetry fields.
- `basin-fragility-proxy-note.md` defines the first local diagnostic target for broad versus brittle recovery behavior using replay and sweep evidence.
- `sweep-to-paper-runbook.md` shows the bounded operator flow from a sweep uncertainty artifact to `sol-paper-finder`, `paper_handoff.py`, and `sol-paper-synthesizer`.
- `smoke_20260311_b-paper-candidates.md` captures the first live sweep-triggered synchronization-feasibility paper shortlist and the current preferred intake candidate.
- `frontier-learning-ledger.md` accumulates repeated subject-folder intakes into reusable Frontier-OS knowledge candidates.
- `knowledge_notes/` stores promoted subject-level knowledge notes derived from repeated corroborating ingests.
- `repo-memory-promotions.md` stores the exact repo-memory mirror lines for promoted knowledge candidates.