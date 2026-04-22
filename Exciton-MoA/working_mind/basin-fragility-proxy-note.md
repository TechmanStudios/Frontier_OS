# Basin Fragility Proxy Note

This note translates the basin-stability paper into a first repo-local diagnostic target.

Its purpose is to distinguish a genuinely recoverable holding regime from a locally calm but globally brittle regime.

## Goal
Estimate whether the current behavioral regime appears:
- broadly recoverable across nearby variation
- locally sticky but narrow
- or fragile enough that calm telemetry should not be mistaken for safety

## Why a proxy is needed
The current stack can already show calm or balanced behavior without telling us whether that calm state generalizes across nearby seeds, nearby drift values, or short perturbation windows.

That is the key ambiguity around `observe_balanced_signal` and related low-actionability states.

Without a basin-oriented proxy, the system may confuse:
- a safe hold regime that should be preserved
- a narrow basin that merely lacks enough energy or leverage to reveal its fragility immediately

## Existing signals that can support a first proxy
Current telemetry and replay already expose enough local evidence for a first basin proxy:
- `phase_coherence`
- `entangler_mode`
- `entangler_transition_reason`
- `entangler_coherence_status`
- `phonon_hint_pair_stability`
- `phonon_hint_local_stability`
- `phonon_hint_pair_decay`
- `phonon_hint_amplitude_trend`
- `entangler_nudge_applied`
- nearby-variant and nearby-seed outcomes from sweep summaries

Replay-side context that matters most:
- mode re-entry and dwell behavior
- whether nearby runs return to the same regime or fragment into different modes
- recurrence of similar coherence bands under adjacent conditions
- whether small control changes induce collapse, no change, or recovery

## Proposed interpretation dimensions

### 1. Local calm versus durable recovery
Is the regime merely quiet now, or does it repeatedly recover under nearby variation?

Nearest local signals:
- `entangler_coherence_status`
- `phase_coherence`
- `phonon_hint_pair_stability`
- `phonon_hint_local_stability`

### 2. Regime persistence across neighbors
Do nearby seeds, drifts, or minor posture changes preserve the same mode and qualitative outcome?

Nearest local evidence:
- sweep neighbors
- mode occupancy and transition counts
- shared outcome labels across adjacent variants

### 3. Decay sensitivity
Does a small adverse shift quickly push the pair out of the current regime?

Nearest local signals:
- `phonon_hint_pair_decay`
- `phonon_hint_amplitude_trend`
- `entangler_transition_reason`

## First-pass proxy shape
Recommended output states:
- `basin_fragility = broad`
- `basin_fragility = narrow`
- `basin_fragility = fragile`

Recommended reasoning dimensions:
- local calm strength
- neighbor persistence
- decay sensitivity

## Example heuristics for a first implementation
Signals that should push the proxy toward `broad`:
- similar outcomes across nearby seeds or adjacent drift settings
- stable mode occupancy without abrupt transition churn
- calm coherence plus strong replay evidence of return-to-regime behavior

Signals that should push the proxy toward `fragile`:
- strong dependence on a small pocket of seeds or settings
- abrupt mode loss after mild adverse change
- calm local telemetry paired with poor neighborhood persistence
- repeated low-variance states that fail to generalize

Signals that should push the proxy toward `narrow`:
- decent local calm but only partial persistence across nearby variants
- short stabilizer dwell or intermittent regime re-entry
- moderate decay sensitivity with occasional recovery

## Best immediate use
The best first use is to compare:
- natural-entry pockets versus low-variance candidates
- stable seeds versus near-miss seeds
- outcome persistence across adjacent sweep settings

That comparison should help separate true hold basins from deceptive quiet regimes.

## What this proxy should not claim yet
- It should not claim literal basin volume.
- It should not be treated as a full nonlinear stability proof.
- It should not drive autonomous control changes until it has been compared against real sweep behavior.

## Strong uncertainty trigger for outside-paper escalation
If the proxy repeatedly labels regimes as `narrow` or `fragile` while local telemetry remains calm and the controller lacks a convincing explanation, that is a strong reason to request one outside paper on basin stability, multistability, perturbation resilience, or recovery geometry.