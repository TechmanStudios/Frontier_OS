# Security Policy

## Supported versions

Frontier_OS is pre-1.0 research software. Only the `main` branch receives security fixes.

| Version | Supported |
| --- | --- |
| `main` | ✅ |
| Tagged releases < v1.0 | ⚠️ Best-effort only |

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Email **security@techmanstudios.dev** with:

1. A description of the issue and its impact.
2. Steps to reproduce (or a proof of concept).
3. Affected commit / version.
4. Your preferred contact and disclosure timeline.

You can expect:

- Acknowledgement within **3 business days**.
- An initial assessment within **10 business days**.
- Coordinated disclosure once a fix is available.

## Scope

In scope:

- Code execution, sandbox escape, or memory-safety issues in any module under [`Exciton-MoA/`](Exciton-MoA/).
- Reproducibility-breaking issues that silently change manifold determinism without a corresponding test failure.
- Dependency vulnerabilities surfaced through `pip` or Dependabot.

Out of scope:

- Theoretical / semantic disagreements with the architecture.
- Issues only reproducible with paywalled or non-redistributable references not tracked in this repo.

## Hardening expectations

- The repo runs **GitHub secret scanning + push protection**.
- CI runs `ruff` and `pytest` on every PR.
- Dependabot opens PRs for vulnerable Python packages weekly.
