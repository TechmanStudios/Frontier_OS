# Synchrony Margin Proxy Note

This note translates the synchrony-feasibility papers, especially `physrevlett.80.2109`, into a first repo-local diagnostic target.

It does not attempt to reproduce the paper's formal machinery. Its purpose is to define a practical proxy that can be approximated from the telemetry already produced by `EntangledSOLPair` and the current replay stack.

## Current trigger
This note is now driven by two concrete repo signals rather than only a paper translation need:
- the overnight 96-variant sweep held a full bounded consensus at `borderline` synchrony with `low_variance_candidate` diagnosis and no natural entries
- the first near-pass-maturity probe produced real blocked-gate `observe_via_near_pass_maturity` nudges, but still yielded zero positive forward windows and zero entries

That combination means the repo needs a synchrony-margin diagnostic that can say more than "the gate is close" or "the run is calm."

## Goal
Estimate whether a pair appears to be:
- inside a plausibly synchronizable region
- near the boundary of synchronizability
- or operating in a regime where local control quality is less important than structural mismatch between coupling, drift, and phase posture

## Why a proxy is needed
The current controller already sees:
- local hint confidence
- local hint reliability
- coherence trend
- control posture
- near-pass maturity

But it does not yet summarize whether the pair is structurally well-positioned to synchronize at all.

That gap matters because a blocked or inconclusive hint gate may mean at least two different things:
- the local signal is too weak or immature
- the pair is outside a synchronizable region and the signal would not help much anyway

## Existing fields that can support a first proxy
The current telemetry already exposes most of the ingredients needed for a first-pass synchrony estimate:
- `phase_coherence`
- `entangler_coherence_delta`
- `entangler_coherence_status`
- `shared_flux_density`, `shared_flux_shear`, `shared_flux_vorticity`
- `entanglement_strength`
- `wormhole_aperture`
- `damping`
- `phase_offset`
- `entangler_hint_gate_passed`
- `entangler_hint_gate_reason`
- `entangler_hint_gate_near_pass_candidate`
- `entangler_hint_gate_confidence_gap`
- `entangler_hint_gate_reliability_gap`
- `entangler_hint_gate_sample_gap`
- `entangler_nudge_applied`
- `entangler_nudge_reason`
- `entangler_mode`

Replay-side context that should be used with those fields:
- coherence mean, spread, and delta across a run
- mode occupancy and transition counts
- gate pass versus gate block mix
- near-pass count and near-pass-to-nudge conversion count
- nudge positive-window rate and mean future delta
- nearby-variant and nearby-seed behavior from sweep summaries

## Proposed interpretation dimensions
The proxy should stay simple at first and separate four questions.

### 1. Coupling posture
Does the current topology and aperture/damping posture look permissive enough for cross-manifold alignment?

Nearest local signals:
- `wormhole_aperture`
- `damping`
- `phase_offset`
- `entanglement_strength`

### 2. Coherence response
Is the pair moving toward or away from alignment under the present posture?

Nearest local signals:
- `phase_coherence`
- `entangler_coherence_delta`
- `entangler_coherence_status`

### 3. Control contradiction
Are local hint or nudge outcomes telling a story that conflicts with the structural signals?

Nearest local signals:
- `entangler_hint_gate_reason`
- `entangler_hint_gate_passed`
- `entangler_nudge_applied`
- `entangler_mode`

### 4. Boundary behavior
Is the pair merely near the decision boundary, or are near-pass events failing to convert into meaningful forward movement?

Nearest local signals:
- `entangler_hint_gate_near_pass_candidate`
- `entangler_hint_gate_confidence_gap`
- `entangler_hint_gate_reliability_gap`
- `entangler_nudge_reason`
- replay positive-window summaries
- sweep-side near-pass and nudge counts

## First-pass proxy shape
The synchrony-margin proxy does not need to be numerically fancy in the first version. It only needs to create a usable categorical summary.

Recommended output states:
- `synchrony_margin = favorable`
- `synchrony_margin = borderline`
- `synchrony_margin = unfavorable`

Recommended reasoning dimensions:
- coupling posture favorable or weak
- coherence response improving, flat, or decaying
- control contradiction low or high
- boundary behavior converting or non-converting

Recommended companion fields:
- `synchrony_margin_basis`
- `synchrony_margin_evidence`
- `synchrony_margin_contradiction`
- `synchrony_margin_boundary_state`

## Example heuristics for a first implementation
This is deliberately heuristic, not canonical.

Signals that should push the proxy toward `favorable`:
- sustained positive coherence delta
- stable or improving coherence status
- nontrivial entanglement strength under a moderate aperture/damping posture
- occasional gate passes or informative near-passes that convert into positive forward windows rather than flat rejection

Signals that should push the proxy toward `unfavorable`:
- low or declining coherence under seemingly permissive topology
- repeated gate blocks with little improvement in coherence
- high structural flux mismatch or unstable control posture
- repeated near-pass or maturity nudges with no positive-window conversion
- strong local hint churn with no alignment response

Signals that should push the proxy toward `borderline`:
- near-pass behavior in the gate
- moderate coherence gains that do not persist
- sensitivity to small posture changes across nearby sweep variants
- small blocked-gate maturity nudges that produce weak or inconsistent future deltas

## First implementation target
The first implementation should stay summary-first and avoid live control changes.

Status:
- implemented in the replay paper-diagnostic summary
- exported into sweep JSONL and CSV records
- surfaced in ranked sweep summaries and paper diagnostics through `basis`, explicit `coupling posture`, `boundary state`, `contradiction level`, and joined evidence signals

Recommended insertion points:
- replay summaries: expose synchrony-margin state beside hint-gate and nudge summaries
- sweep variant summaries: persist the categorical margin plus a short evidence basis
- ranked/compact sweep reports: surface aggregate counts of favorable, borderline, and unfavorable margin labels

Minimal first scoring sketch:
- start at `borderline`
- move toward `favorable` when coherence trend improves, structural posture is permissive, and near-passes or passes convert into positive windows
- move toward `unfavorable` when structural posture stays weak or when repeated near-pass evidence fails to convert into positive windows across nearby variants

## Best immediate use
The best first use is in replay and sweep summaries, not live control.

Use it to compare:
- natural-entry seeds versus near-miss seeds
- baseline versus nudged variants
- stable pockets versus low-variance candidates

The immediate benchmark case should be `working_data/sweep_runs/near_pass_probe_20260311_a`: it already shows the exact pattern the proxy needs to classify correctly, namely real boundary evidence without recovery conversion.

That comparison can reveal whether the main blocker is structural synchronizability or merely conservative local gating.

## What this proxy should not claim yet
- It should not claim exact synchronizability boundaries.
- It should not override the hint gate directly.
- It should not be promoted as proof without explicit validation against sweep outcomes.

## Expected success condition
The first version is good enough if it cleanly separates three cases in current artifacts:
- true natural-entry pockets
- calm but non-converting near-pass pockets
- clearly weak blocked regimes

## Strong uncertainty trigger for outside-paper escalation
If this proxy repeatedly returns `borderline` or `unfavorable` while local hint and nudge evidence remain contradictory, that is a strong reason to ask for one outside paper on synchronization feasibility, controllability, or topology-aware coupling.