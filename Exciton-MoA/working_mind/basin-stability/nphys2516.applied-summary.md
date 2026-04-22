# Applied Summary: nphys2516

## Paper
- Title: How basin stability complements the linear-stability paradigm
- Authors: Peter J. Menck, Jobst Heitzig, Norbert Marwan, Jurgen Kurths
- Year: 2013
- Source: https://www.nature.com/articles/nphys2516
- Local file: `nphys2516.pdf`

## Why this paper is in `working_mind`
This paper complements the existing synchronization reference by covering the missing question in the current `Exciton-MoA` stabilization work: not just whether a coupled state can synchronize locally, but how globally fragile that state is under meaningful perturbation.

The key value is its argument that linear-stability views are too local for multistable systems. A state can look stable near the operating point and still have a small or fragile basin of attraction. That is a close match for the current ambiguity around `observe_balanced_signal`, where low-variance behavior may mean either a safe-hold regime or a basin that appears calm only because the pair has little room left before falling into a bad attractor.

## Core takeaway
Stability should be treated as basin volume and recovery geometry, not only as local return speed near the current state.

For the current controller, that means a pair should not be judged only by whether the latest hint or coherence value looks locally acceptable. It should also be judged by whether recent trajectories suggest a wide recoverable basin or a narrow, brittle one.

## Direct relevance to current `Exciton-MoA` work
This maps onto the current entangled-manifold control problem in a different way than the first paper:

- `1208.0045v1` is the better frame for synchrony feasibility and margin.
- `nphys2516` is the better frame for fragility once a regime appears locally stable.
- The current pair telemetry already tracks repeated visits to similar coherence and control regimes, which can serve as a first proxy for whether a state is broadly recoverable or only locally sticky.
- The `observe_balanced_signal` decision is currently too coarse because it does not separate wide-basin hold states from narrow-basin stagnation states.

## Engineering implications
1. Add a basin-fragility proxy to replay and sweep summaries.
   Use existing telemetry to estimate whether nearby trajectories converge back into the same regime across perturbation-like variation, instead of relying only on one-step hint confidence or reliability.

2. Split the current `observe` bucket.
   One branch should represent genuinely safe hold states with broad recovery behavior. Another should represent locally quiet but globally fragile states that need a different intervention strategy.

3. Compare natural-entry seeds against near-miss seeds through a basin lens.
   If two seeds have similar local coherence but very different recovery breadth across adjacent ticks or nearby variants, the gating problem may be about basin geometry rather than recommendation quality.

4. Keep future policy changes non-local when possible.
   A recommendation-specific threshold change may still fail if the surrounding basin is too narrow. Basin-aware diagnostics should therefore sit beside hint-gate diagnostics, not under them.

## Best near-term use
The best immediate use of this paper is to define a first repo-specific basin proxy from existing sweep and replay artifacts.

That proxy does not need to be a full formal basin-volume estimate. A useful first version would simply measure whether nearby seeds, neighboring drift settings, or short perturbation windows return to the same coherence regime or fall into different behavioral modes.

## Suggested next translation step
Convert this paper into one repo-specific design note:

`How to approximate basin fragility for EntangledSOLPair from existing replay and sweep telemetry`

That would pair cleanly with the synchrony-margin note suggested by the first paper and give the controller two distinct diagnostics: feasibility of synchronization and breadth of recoverability.