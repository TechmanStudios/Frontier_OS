# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""Agent round-trip schema smoke (umbrella experiment #6).

This is the Phase-3 governance gate: every cross-agent handoff payload that
the umbrella emits must continue to validate, and any agent markdown under
``sol/.github/agents/`` that pins a ``schema_version`` for one of those
handoffs must agree with :data:`SCHEMA_VERSIONS`.

Schema-only — no live LLM calls. If a future change bumps a schema version,
this file fails until both the validator and every referencing agent
markdown are updated together.
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

import pytest

EXCITON_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = EXCITON_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

agent_handoff_schemas = importlib.import_module("agent_handoff_schemas")

# .github/agents lives one workspace folder over from Frontier_OS.
SOL_GITHUB_AGENTS = (EXCITON_ROOT.parent.parent / ".github" / "agents").resolve()


# ---------------------------------------------------------------------------
# Fixtures (one ok + one broken per handoff)
# ---------------------------------------------------------------------------


def _ok_paper_handoff() -> dict:
    return {
        "schema_version": agent_handoff_schemas.SCHEMA_VERSIONS["paper_handoff"],
        "origin": "replay_to_paper",
        "source_run_dir": "Exciton-MoA/working_data/snowball/runs/daily/20260423T061700Z",
        "source_started_utc": "2026-04-23T06:17:00Z",
        "paper_trigger": "synchrony",
        "synchrony_consensus": "borderline",
        "coupling_consensus": "weak",
        "basin_consensus": "broad",
        "handoff_excerpt": "borderline synchrony with weak coupling posture",
        "suggested_domain": "control-policy",
        "generated_utc": "2026-04-23T06:18:00Z",
    }


def _ok_knowledge_promotion_candidate() -> dict:
    return {
        "schema_version": agent_handoff_schemas.SCHEMA_VERSIONS["knowledge_promotion_candidate"],
        "subject_folder": "synchronization",
        "corroboration_count": 2,
        "source_ledger_entries": [
            "working_mind/frontier-learning-ledger.md#synchronization",
            "consumers/replay_to_paper/20260423T061700Z/artifact.json",
        ],
        "proposed_memory_line": "- synchronization knowledge candidate: 2 corroborating ingests converge on a synchrony-margin diagnostic.",
        "generated_utc": "2026-04-23T06:18:00Z",
    }


def _ok_incident_report() -> dict:
    return {
        "schema_version": agent_handoff_schemas.SCHEMA_VERSIONS["incident_report"],
        "kind": "telemetry_drift",
        "severity": "warn",
        "drift_metric": 0.42,
        "threshold": 0.35,
        "baseline_id": "diagnosis_distribution_v1",
        "run_dirs_observed": ["Exciton-MoA/working_data/snowball/runs/daily/abc"],
        "recommended_action": "clamp regime to hold until distributions return under threshold",
        "generated_utc": "2026-04-23T06:18:00Z",
    }


def _ok_tournament_entry() -> dict:
    return {
        "schema_version": agent_handoff_schemas.SCHEMA_VERSIONS["tournament_entry"],
        "tournament_id": "T-20260423T061700Z",
        "candidates": [
            {"variant_id": "v0", "score": 1.5, "components": {"natural_entries": 1.0}},
            {"variant_id": "v1", "score": 0.5, "components": {"natural_entries": 0.0}},
        ],
        "winner_variant_id": "v0",
        "proposed_tilt": {"seed": 149, "embedding_a_loc": 0.5},
        "generated_utc": "2026-04-23T06:18:00Z",
    }


def _ok_knowledge_lesson() -> dict:
    return {
        "schema_version": agent_handoff_schemas.SCHEMA_VERSIONS["knowledge_lesson"],
        "lesson_type": "gate_blocker_pattern",
        "corroboration_count": 3,
        "evidence_run_dirs": [
            "Exciton-MoA/working_data/snowball/runs/daily/20260420T061700Z",
            "Exciton-MoA/working_data/snowball/runs/daily/20260421T061700Z",
            "Exciton-MoA/working_data/snowball/runs/daily/20260422T061700Z",
        ],
        "key_findings": (
            "Across 3 distinct (locA,locB,drift) pockets, weak coupling posture "
            "co-occurs with low_variance_candidate diagnosis."
        ),
        "applicable_constraints": [
            "embedding_a_loc=0.50,embedding_b_loc=0.57,embedding_drift=0.06",
            "embedding_a_loc=0.50,embedding_b_loc=0.58,embedding_drift=0.06",
            "embedding_a_loc=0.50,embedding_b_loc=0.57,embedding_drift=0.08",
        ],
        "contraindications": [
            "embedding_a_loc=0.49,embedding_b_loc=0.57,embedding_drift=0.06",
        ],
        "generated_utc": "2026-04-23T06:18:00Z",
    }


HANDOFF_FIXTURES = {
    "paper_handoff": (
        _ok_paper_handoff,
        agent_handoff_schemas.validate_paper_handoff,
    ),
    "knowledge_promotion_candidate": (
        _ok_knowledge_promotion_candidate,
        agent_handoff_schemas.validate_knowledge_promotion_candidate,
    ),
    "incident_report": (
        _ok_incident_report,
        agent_handoff_schemas.validate_incident_report,
    ),
    "tournament_entry": (
        _ok_tournament_entry,
        agent_handoff_schemas.validate_tournament_entry,
    ),
    "knowledge_lesson": (
        _ok_knowledge_lesson,
        agent_handoff_schemas.validate_knowledge_lesson,
    ),
    "arm_promotion": (
        lambda: {
            "schema_version": agent_handoff_schemas.SCHEMA_VERSIONS["arm_promotion"],
            "msf": {
                "default_arm": "treatment",
                "mean_delta": 0.75,
                "paired_count": 10,
                "source_token": "20260601T000000Z",
                "updated_utc": "2026-06-01T00:00:00Z",
                "status": "favors_treatment",
            },
            "posture": {
                "default_arm": None,
                "mean_delta": 0.0,
                "paired_count": 0,
                "source_token": "20260601T000000Z",
                "updated_utc": "2026-06-01T00:00:00Z",
                "status": "insufficient_evidence",
            },
            "generated_utc": "2026-06-01T00:00:00Z",
        },
        agent_handoff_schemas.validate_arm_promotion,
    ),
}


# ---------------------------------------------------------------------------
# Validator round-trip
# ---------------------------------------------------------------------------


def test_schema_versions_keys_are_complete():
    assert set(agent_handoff_schemas.SCHEMA_VERSIONS) == set(HANDOFF_FIXTURES)
    for v in agent_handoff_schemas.SCHEMA_VERSIONS.values():
        assert isinstance(v, int) and v >= 1


@pytest.mark.parametrize("kind", sorted(HANDOFF_FIXTURES))
def test_ok_fixture_validates(kind):
    builder, validator = HANDOFF_FIXTURES[kind]
    ok, errors = validator(builder())
    assert ok, errors


@pytest.mark.parametrize("kind", sorted(HANDOFF_FIXTURES))
def test_missing_schema_version_is_rejected(kind):
    builder, validator = HANDOFF_FIXTURES[kind]
    payload = builder()
    payload.pop("schema_version", None)
    ok, errors = validator(payload)
    assert not ok and errors


@pytest.mark.parametrize("kind", sorted(HANDOFF_FIXTURES))
def test_wrong_schema_version_is_rejected(kind):
    builder, validator = HANDOFF_FIXTURES[kind]
    payload = builder()
    payload["schema_version"] = agent_handoff_schemas.SCHEMA_VERSIONS[kind] + 99
    ok, errors = validator(payload)
    assert not ok
    assert any("schema_version" in e for e in errors)


def test_paper_handoff_rejects_unknown_trigger():
    payload = _ok_paper_handoff()
    payload["paper_trigger"] = "not_a_trigger"
    ok, errors = agent_handoff_schemas.validate_paper_handoff(payload)
    assert not ok and any("paper_trigger" in e for e in errors)


def test_incident_report_rejects_unknown_severity():
    payload = _ok_incident_report()
    payload["severity"] = "panic"
    ok, errors = agent_handoff_schemas.validate_incident_report(payload)
    assert not ok and any("severity" in e for e in errors)


def test_tournament_entry_rejects_empty_candidates():
    payload = _ok_tournament_entry()
    payload["candidates"] = []
    ok, errors = agent_handoff_schemas.validate_tournament_entry(payload)
    assert not ok and any("candidates" in e for e in errors)


def test_knowledge_promotion_candidate_requires_positive_count():
    payload = _ok_knowledge_promotion_candidate()
    payload["corroboration_count"] = 0
    ok, errors = agent_handoff_schemas.validate_knowledge_promotion_candidate(payload)
    assert not ok and any("corroboration_count" in e for e in errors)


# ---------------------------------------------------------------------------
# Agent markdown contract sweep
# ---------------------------------------------------------------------------


_SCHEMA_LINE = re.compile(r"schema_version\s*[:=]\s*(\d+)", re.IGNORECASE)


def _agent_md_paths() -> list[Path]:
    if not SOL_GITHUB_AGENTS.exists():
        return []
    return sorted(SOL_GITHUB_AGENTS.glob("*.agent.md"))


def test_sol_github_agents_dir_resolvable():
    # Skip — but loudly — when the .github folder isn't checked out alongside.
    if not SOL_GITHUB_AGENTS.exists():
        pytest.skip(f"agents dir not present at {SOL_GITHUB_AGENTS}")
    assert _agent_md_paths(), "expected at least one *.agent.md under .github/agents"


@pytest.mark.parametrize("agent_path", _agent_md_paths(), ids=lambda p: p.name)
def test_agent_markdown_schema_versions_match(agent_path: Path):
    text = agent_path.read_text(encoding="utf-8")
    # Only check sections where a handoff name appears alongside an explicit
    # schema_version line — agents that merely mention a handoff in passing
    # do not need to pin a version.
    for kind, expected in agent_handoff_schemas.SCHEMA_VERSIONS.items():
        if kind not in text:
            continue
        # Look for "<kind> ... schema_version: N" within ~400 chars after the
        # mention. This is a lightweight contract check — strict enough to
        # catch a real mismatch, loose enough to ignore prose mentions.
        for match in re.finditer(re.escape(kind), text):
            window = text[match.start() : match.start() + 400]
            sv = _SCHEMA_LINE.search(window)
            if sv is None:
                continue
            assert int(sv.group(1)) == expected, (
                f"{agent_path.name} pins {kind} schema_version={sv.group(1)} but validators expect {expected}"
            )
