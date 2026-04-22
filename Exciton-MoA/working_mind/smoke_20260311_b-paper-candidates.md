# Smoke Sweep Paper Candidates

Source handoff: `working_data/sweep_runs/smoke_20260311_b/sweep_uncertainty_paper_handoff.md`

## Trigger snapshot
- Selected variant: `variant_001_a0p490_b0p570_d0p050_c2_s149`
- Current bottleneck: unresolved synchrony uncertainty under a runtime-too-short but still decision-relevant regime
- Intervention class: diagnostics
- Desired paper role: one paper on synchronization feasibility diagnostics for coupled nonlinear systems

## Preferred intake candidate

### Master Stability Functions for Synchronized Coupled Systems
- Authors: Louis M. Pecora, Thomas L. Carroll
- Year: 1998
- Stable URL: https://doi.org/10.1103/PhysRevLett.80.2109
- Suggested filename: `physrevlett.80.2109.pdf`
- Why it fits now: This is the cleanest diagnostic bridge from the current sweep trigger to a bounded outside reference because it turns synchrony feasibility into a stability test on the coupling structure instead of treating blocked alignment as a vague empirical symptom.
- Expected local use: sharpen the meaning of `paper_synchrony_margin`, guide how replay labels distinguish conservative hint gates from structurally poor synchronization regions, and inform whether future sweeps should prioritize coupling diagnostics over more controller relaxation.
- Intake status: approved candidate for prefilled handoff

## Secondary candidate

### Synchronization in Small-World Systems
- Authors: Mauricio Barahona, Louis M. Pecora
- Year: 2002
- Stable URL: https://doi.org/10.1103/PhysRevLett.89.054101
- Suggested filename: `physrevlett.89.054101.pdf`
- Why it fits now: This is a narrower follow-on if the overnight sweep keeps pointing to structural synchronizability limits rather than pure gate conservatism, because it ties synchronization difficulty to topology-sensitive spectral structure.
- Expected local use: help decide whether future pair sweeps should explore more topology-aware or wormhole-placement-sensitive diagnostics instead of only local threshold tuning.
- Intake status: keep as a backup unless the longer sweep reinforces a topology-fragility interpretation.

## Current decision
- Pull first: `Master Stability Functions for Synchronized Coupled Systems`
- Hold second: `Synchronization in Small-World Systems` until overnight evidence says the problem is more structural than local-policy-bound

## Overnight confirmation
- Overnight source handoff: `working_data/sweep_runs/overnight_20260311_a/sweep_uncertainty_paper_handoff.md`
- Sweep result: 96/96 variants triggered the bounded paper rule with unanimous `control policy`, `borderline` synchrony, `broad` basin, and `low_variance_candidate` diagnosis labels.
- Interpretation shift: the current repo gap is no longer just "find a synchrony-feasibility diagnostic"; it is "separate conservative gating from structurally ambiguous synchrony margins under calm-but-uninformative runs."
- Selection quality: the refreshed overnight handoff now picks a representative near-pass-mature variant instead of an arbitrary first variant.
- Decision status: the preferred paper remains unchanged. The overnight run strengthened the case for the master-stability paper and did not justify promoting the small-world topology paper to first position.

## Near-pass maturity probe
- Probe source: `working_data/sweep_runs/near_pass_probe_20260311_a/`
- Runtime result: the new controller path fired real `observe_via_near_pass_maturity` nudges for seed 149 while the main hint gate still stayed blocked, confirming that the experiment is live rather than only scaffolded.
- Outcome quality: the probe still produced 0 natural entries, 0 positive forward coherence windows, and the paired seed 167 variant stayed fully blocked.
- Interpretation update: the repo now has direct evidence that a small conservative-gating edge exists in at least one calm borderline case, but the effect is too weak to displace the paper path or to justify a topology-first interpretation.
- Decision status: the preferred paper remains unchanged. The probe reinforces the need for synchrony-margin diagnostics more than it supports further broad controller relaxation.