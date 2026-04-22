## Summary
<!-- One or two sentences describing what this PR changes and why. -->

## Type of change
- [ ] Bug fix
- [ ] New feature / control lever
- [ ] Research diagnostic / paper bridge
- [ ] Reproducibility / harness change
- [ ] Documentation
- [ ] Build / CI / chore

## Reproducibility & determinism
- [ ] No change to manifold construction, scan order, or pair seeding, **or**
- [ ] Determinism changes are accompanied by updated checkpoints / fingerprints / regression coverage.
- [ ] No new control lever defaults to "on" without sweep-backed validation.
- [ ] Telemetry / replay outputs remain read-only relative to live control (or the change is explicitly gated).

## Tests
- [ ] `pytest Exciton-MoA/blank_manifold/pre_check_tests` passes locally.
- [ ] New tests added for the changed behavior (or rationale for none).

## Compliance
- [ ] No copyrighted PDFs or other non-redistributable assets are added.
- [ ] No secrets, tokens, or private contact info are added.
- [ ] I have signed the [CLA](../legal/CLA.md) (the bot will confirm).

## Notes for reviewers
<!-- Anything subtle, anything to look at first, links to related sweeps / runs / issues. -->
