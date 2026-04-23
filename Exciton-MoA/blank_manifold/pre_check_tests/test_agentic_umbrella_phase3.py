# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""Phase-3 regression coverage for the agentic umbrella (#3 promotion audit).

#6 (round-trip schema smoke) lives in :mod:`test_agent_roundtrip`. This file
covers the promotion-audit consumer.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

EXCITON_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = EXCITON_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

promotion_audit = importlib.import_module("promotion_audit")
agent_handoff_schemas = importlib.import_module("agent_handoff_schemas")
snowball_consumer = importlib.import_module("snowball_consumer")


SAMPLE_LEDGER = """# Frontier-OS Learning Ledger

Some prose.

## synchronization
- Evidence count: 2
- Promotion threshold: 2 corroborating ingests in one subject folder
- Promotion status: candidate knowledge note
- Knowledge note: knowledge_notes/synchronization.knowledge-note.md
- Paper 1: synchronization/PhysRevLett.80.2109.pdf
- Paper 2: synchronization/1208.0045v1.pdf

## basin-stability
- Evidence count: 1
- Promotion threshold: 2 corroborating ingests in one subject folder
- Promotion status: candidate knowledge note
- Paper 1: basin-stability/nphys2516.pdf
"""

SAMPLE_PROMOTIONS = """# Repo Memory Promotions

## synchronization
- Status: ready for repo memory mirror
- Knowledge note: knowledge_notes/synchronization.knowledge-note.md
- Evidence count: 2
- Memory line: - synchronization knowledge candidate: 2 corroborating ingests converge on a synchrony-margin diagnostic.
- Paper 1: synchronization/PhysRevLett.80.2109.pdf
- Paper 2: synchronization/1208.0045v1.pdf

## basin-stability
- Status: candidate knowledge note (not yet ready)
- Memory line: - basin-stability knowledge candidate: 1 ingest, awaiting corroboration.
"""


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def test_parse_learning_ledger_extracts_sections(tmp_path):
    p = tmp_path / "ledger.md"
    p.write_text(SAMPLE_LEDGER, encoding="utf-8")
    parsed = promotion_audit.parse_learning_ledger(p)
    assert set(parsed) == {"synchronization", "basin-stability"}
    assert parsed["synchronization"]["evidence count"] == "2"
    assert parsed["synchronization"]["promotion threshold"] == "2 corroborating ingests in one subject folder"


def test_parse_learning_ledger_missing_returns_empty(tmp_path):
    assert promotion_audit.parse_learning_ledger(tmp_path / "absent.md") == {}


def test_parse_promotions_round_trip(tmp_path):
    p = tmp_path / "promo.md"
    p.write_text(SAMPLE_PROMOTIONS, encoding="utf-8")
    parsed = promotion_audit.parse_promotions(p)
    assert "synchronization" in parsed
    assert "memory line" in parsed["synchronization"]


# ---------------------------------------------------------------------------
# Mirror detection
# ---------------------------------------------------------------------------


def test_is_already_mirrored_anchor_match():
    text = "- synchronization knowledge candidate: pre-existing line."
    assert promotion_audit.is_already_mirrored(text, subject="synchronization", memory_line="something else")


def test_is_already_mirrored_exact_line():
    line = "- exact mirror"
    assert promotion_audit.is_already_mirrored(
        f"some prose\n{line}\nmore prose",
        subject="synchronization",
        memory_line=line,
    )


def test_is_already_mirrored_false_when_absent():
    assert not promotion_audit.is_already_mirrored(
        "unrelated text", subject="synchronization", memory_line="- foo"
    )


# ---------------------------------------------------------------------------
# Subject domain normalization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("synchronization", "synchronization"),
        ("synchrony", "synchronization"),
        ("basin-stability", "basin-stability"),
        ("basin", "basin-stability"),
        ("topology", "topology-design"),
        ("control-policy", "control-policy"),
        ("nonsense", "experiment-design"),
    ],
)
def test_normalize_subject_domain(raw, expected):
    assert promotion_audit._normalize_subject_domain(raw) == expected


# ---------------------------------------------------------------------------
# collect_candidates
# ---------------------------------------------------------------------------


def test_collect_candidates_emits_above_threshold_and_unmirrored(tmp_path):
    learning = promotion_audit.parse_learning_ledger(_write(tmp_path / "ledger.md", SAMPLE_LEDGER))
    promotions = promotion_audit.parse_promotions(_write(tmp_path / "promo.md", SAMPLE_PROMOTIONS))
    candidates = promotion_audit.collect_candidates(
        learning=learning, promotions=promotions, repo_memory_text=""
    )
    subjects = {c["subject_folder"] for c in candidates}
    # synchronization meets threshold (2 >= 2) and is unmirrored.
    assert "synchronization" in subjects
    # basin-stability has evidence 1 < threshold 2 -> excluded.
    assert "basin-stability" not in subjects


def test_collect_candidates_skips_already_mirrored(tmp_path):
    learning = promotion_audit.parse_learning_ledger(_write(tmp_path / "ledger.md", SAMPLE_LEDGER))
    promotions = promotion_audit.parse_promotions(_write(tmp_path / "promo.md", SAMPLE_PROMOTIONS))
    repo_text = "- synchronization knowledge candidate: already there."
    candidates = promotion_audit.collect_candidates(
        learning=learning, promotions=promotions, repo_memory_text=repo_text
    )
    assert candidates == []


def test_collect_candidates_skips_when_no_memory_line(tmp_path):
    promo_no_line = """# Repo Memory Promotions\n\n## synchronization\n- Status: candidate\n"""
    learning = promotion_audit.parse_learning_ledger(_write(tmp_path / "ledger.md", SAMPLE_LEDGER))
    promotions = promotion_audit.parse_promotions(_write(tmp_path / "promo.md", promo_no_line))
    candidates = promotion_audit.collect_candidates(
        learning=learning, promotions=promotions, repo_memory_text=""
    )
    assert candidates == []


def test_collect_candidates_payload_validates_against_slab_b(tmp_path):
    learning = promotion_audit.parse_learning_ledger(_write(tmp_path / "ledger.md", SAMPLE_LEDGER))
    promotions = promotion_audit.parse_promotions(_write(tmp_path / "promo.md", SAMPLE_PROMOTIONS))
    candidates = promotion_audit.collect_candidates(
        learning=learning, promotions=promotions, repo_memory_text=""
    )
    assert candidates
    for c in candidates:
        ok, errors = agent_handoff_schemas.validate_knowledge_promotion_candidate(c)
        assert ok, errors


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def test_render_pr_body_is_deterministic_for_fixed_payload():
    payload = {
        "subject_folder": "synchronization",
        "corroboration_count": 2,
        "promotion_threshold": 2,
        "suggested_domain": "synchronization",
        "generated_utc": "2026-04-23T00:00:00Z",
        "proposed_memory_line": "- foo bar",
        "source_ledger_entries": ["a", "b"],
    }
    a = promotion_audit.render_pr_body(payload)
    b = promotion_audit.render_pr_body(payload)
    assert a == b
    assert "synchronization" in a and "- foo bar" in a and "sol-rsi" in a


def test_render_summary_markdown_handles_empty():
    assert "candidates: 0" in promotion_audit.render_summary_markdown([])


# ---------------------------------------------------------------------------
# run_promotion_audit
# ---------------------------------------------------------------------------


def test_run_promotion_audit_noop_when_ledger_missing(tmp_path):
    out = promotion_audit.run_promotion_audit(
        learning_ledger_path=tmp_path / "absent.md",
        promotions_path=tmp_path / "absent_promo.md",
        repo_memory_path=tmp_path / "absent_memory.md",
        dry_run=True,
    )
    assert out["status"] == "noop"


def test_run_promotion_audit_dry_run_returns_candidates(tmp_path):
    ledger = _write(tmp_path / "ledger.md", SAMPLE_LEDGER)
    promo = _write(tmp_path / "promo.md", SAMPLE_PROMOTIONS)
    out = promotion_audit.run_promotion_audit(
        learning_ledger_path=ledger,
        promotions_path=promo,
        repo_memory_path=tmp_path / "absent_memory.md",
        dry_run=True,
    )
    assert out["status"] == "dry_run"
    subjects = [c["subject_folder"] for c in out["candidates"]]
    assert subjects == ["synchronization"]


def test_run_promotion_audit_writes_artifact_and_ledger(monkeypatch, tmp_path):
    ledger = _write(tmp_path / "ledger.md", SAMPLE_LEDGER)
    promo = _write(tmp_path / "promo.md", SAMPLE_PROMOTIONS)
    consumers_root = tmp_path / "consumers"
    monkeypatch.setattr(
        promotion_audit,
        "write_consumer_artifact",
        lambda **kw: snowball_consumer.write_consumer_artifact(root=consumers_root, **kw),
    )
    monkeypatch.setattr(
        promotion_audit,
        "append_consumer_ledger",
        lambda name, row: snowball_consumer.append_consumer_ledger(name, row, root=consumers_root),
    )
    out = promotion_audit.run_promotion_audit(
        learning_ledger_path=ledger,
        promotions_path=promo,
        repo_memory_path=tmp_path / "absent_memory.md",
        dry_run=False,
    )
    assert out["status"] == "ok"
    assert out["written"] and out["written"][0]["subject_folder"] == "synchronization"
    artifact_path = Path(out["written"][0]["artifact_path"])
    assert artifact_path.exists()
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert payload["subject_folder"] == "synchronization"
    pr_body = (artifact_path.parent / "pr_body.md").read_text(encoding="utf-8")
    assert "Promote `synchronization`" in pr_body


def test_run_promotion_audit_skips_when_already_mirrored(tmp_path):
    ledger = _write(tmp_path / "ledger.md", SAMPLE_LEDGER)
    promo = _write(tmp_path / "promo.md", SAMPLE_PROMOTIONS)
    memory = _write(
        tmp_path / "memory.md",
        "- synchronization knowledge candidate: existing mirror line\n",
    )
    out = promotion_audit.run_promotion_audit(
        learning_ledger_path=ledger,
        promotions_path=promo,
        repo_memory_path=memory,
        dry_run=True,
    )
    assert out["status"] == "noop"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
