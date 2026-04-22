# Stabilization Paper Translation Note

This note is the first bridge from `working_mind` papers into current `Exciton-MoA` observables.

Its purpose is twofold:
- translate the first two stabilization papers into existing telemetry and SOL concepts
- define a reusable translation pattern for future ingested papers so outside references can later support autonomous-but-bounded discovery

## Why this note exists
The current paper summaries are useful, but they are still one step away from the runtime surface.

If outside literature is going to matter operationally, each paper needs a local attachment point:
- what existing telemetry fields it maps to
- what SOL concepts it sharpens
- what kind of uncertainty should cause the system to revisit it later

That translation layer is what allows `working_mind` to stay curated now while still supporting a more autonomous future later.

## Current telemetry surface for pair stabilization
The present pair telemetry and replay stack already exposes enough structure to support paper translation without inventing new sensors.

Useful current fields include:
- `phase_coherence`
- `wormhole_aperture`
- `damping`
- `phase_offset`
- `shared_flux_density`, `shared_flux_shear`, `shared_flux_vorticity`
- `entanglement_strength`
- `bilateral_burst_count`
- `max_h_cross_domain`
- `entangler_coherence_status`, `entangler_coherence_delta`, `entangler_coherence_target`
- `entangler_mode`, `entangler_next_mode`, `entangler_transition_reason`
- `entangler_hint_gate_*`
- `entangler_nudge_*`
- `phonon_hint_*`
- `entangler_weight_min`, `entangler_weight_max`, `entangler_top_wormholes`

Useful replay summaries already available from the current stack include:
- coherence trend
- mode switching
- local phonon statistics
- advisory hint summaries
- weight drift
- predictive phonon correlations

## Nearest SOL vocabulary
Useful current SOL-side bridge terms include:
- Blank Manifold / entangled manifolds
- wormhole registry / weighted cross-manifold links
- shared flux
- Ontological Orchestrator / telemetry surface
- Latent Mediator / SharedMediator
- Hippocampal Replay
- threshold burst / hotspot functional
- attractor basin
- Entangler control, hint gate, and bounded nudges

## Two-paper mapping

### 1208.0045v1 — synchrony feasibility and margin
Paper role:
This paper is the cleanest current frame for whether a coupled pair is inside a synchronizable region at all.

Best current telemetry anchors:
- `phase_coherence`
- `shared_flux_density`, `shared_flux_shear`, `shared_flux_vorticity`
- `entanglement_strength`
- `wormhole_aperture`
- `damping`
- `phase_offset`
- `entangler_coherence_delta`
- `entangler_hint_gate_passed`, `entangler_hint_gate_reason`

Best SOL concepts:
- coupled oscillator control problem
- effective topology through wormhole links
- synchrony margin
- conservative gating versus structural synchronizability

Best immediate question it helps answer:
- are we failing because the hint is weak, or because the pair is outside a synchronizable region?

Best derived diagnostic direction:
- a synchrony-feasibility or synchrony-margin proxy from coupling, coherence spread, flux balance, drift, and control posture

### nphys2516 — basin fragility and nonlocal stability
Paper role:
This paper is the cleanest current frame for whether a locally calm state is actually broadly recoverable or only narrowly stable.

Best current telemetry anchors:
- `phase_coherence`
- `entangler_mode`
- `entangler_transition_reason`
- `entangler_coherence_status`
- `phonon_hint_pair_stability`
- `phonon_hint_local_stability`
- `phonon_hint_pair_decay`
- `phonon_hint_amplitude_trend`
- `entangler_nudge_applied`
- nearby-variant and nearby-seed behavior from sweep summaries

Best SOL concepts:
- attractor basin
- basin fragility
- threshold burst as evidence of recovery stress
- safe hold versus narrow-basin stagnation

Best immediate question it helps answer:
- is `observe_balanced_signal` describing a healthy holding basin, or a locally quiet but globally brittle regime?

Best derived diagnostic direction:
- a basin-fragility proxy from replay recurrence, neighboring-seed recovery behavior, nearby-drift outcome persistence, and mode re-entry breadth

## Combined controller view
Together, the two papers suggest that the stabilization problem should be decomposed into two distinct diagnostics:

1. Synchrony feasibility:
Can this pair plausibly phase-align under the present topology and control envelope?

2. Basin breadth:
If the pair appears stable now, how wide and recoverable is that regime under nearby perturbation?

That yields a practical four-way interpretation surface:
- feasible + broad basin: hold or stabilize lightly
- feasible + narrow basin: stabilize carefully and monitor fragility
- infeasible + broad local calm: avoid overreading a quiet regime
- infeasible + narrow basin: treat as structurally risky and reconsider topology or experiment design

## New controller experiment path
The overnight consensus sweep added a more precise local question: what should the controller do when the gate is repeatedly close, the regime stays calm, and the sweep never separates conservative gating from structural synchrony limits?

That question now has an explicit local experiment path:
- keep the gate decision truthful
- allow a tiny `observe`-only feedback nudge when the tick is near-pass-mature and the experiment flag is enabled
- use the result to test whether calm borderline regimes are merely over-gated or still fundamentally uninformative

Nearest runtime hooks for that experiment:
- `HintGatingPolicy.enable_near_pass_maturity_nudges`
- `HintGatingPolicy.near_pass_confidence_gap_max`
- `HintGatingPolicy.near_pass_reliability_gap_max`
- `HintGatingPolicy.near_pass_sample_gap_max`
- `HintGatingPolicy.near_pass_observe_feedback_scale`
- entangler nudge reason `observe_via_near_pass_maturity`

Interpretation rule:
- if near-pass-maturity nudges begin to produce positive forward coherence windows, the repo likely needs policy refinement before broader outside-paper escalation
- if they do not, the synchrony-margin paper remains the more important next input because the regime is still calm-but-ambiguous rather than obviously topology-driven

## Reusable translation contract for future papers
Every new paper ingested into `working_mind` should be translated through the same minimum contract.

For each paper, record:
1. Core question:
   What missing decision or uncertainty does the paper speak to?
2. Telemetry anchors:
   Which existing runtime fields, replay summaries, or sweep outputs are closest to the paper's actionable concept?
3. SOL concept anchors:
   Which local names provide the bridge from external language into repo language?
4. Intervention class:
   Does this paper mainly inform diagnostics, control policy, topology design, or experiment design?
5. Uncertainty trigger:
   What recurring runtime pattern should cause the system to re-open or recommend this paper later?

## Autonomous future: bounded outside-paper escalation
The long-term system can use outside references without turning into an always-searching literature bot.

The right pattern is bounded escalation:
- stay local while current telemetry and replay are sufficient
- escalate outward when uncertainty becomes stable, repeated, and decision-relevant

Good future escalation signals:
- persistent blocked-control states where local metrics disagree about what is wrong
- repeated near-pass or near-entry regimes with no explanatory leverage from current diagnostics
- recurrent low-variance or low-actionability states that look calm but do not generalize across nearby variants
- explicit requests for outside-the-box or forward-looking exploration tied to a real bottleneck
- recurring evidence that a needed decision variable is not represented in current telemetry

Bad escalation signals:
- a single failed run
- broad curiosity with no bottleneck
- open-ended literature search with no target decision

## First concrete follow-on notes
The first two follow-on notes now exist:
- `synchrony-margin-proxy-note.md`
- `basin-fragility-proxy-note.md`

Those notes turn the paper layer into concrete diagnostic directions and provide the first local targets for future bounded paper rediscovery.