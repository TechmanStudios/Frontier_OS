# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""Validators for cross-agent handoff payloads (Slab B).

Every experiment in the sol umbrella that crosses an agent boundary emits a
payload validated by one of the validators here. Each validator returns
``(ok: bool, errors: list[str])`` — no exceptions, so callers can always log
deterministically.

Schema versions are pinned below; bumping one is a breaking change and
``test_agent_roundtrip.py`` (Phase 3) will fail until every agent markdown
that references the contract is updated.
"""

from __future__ import annotations

from typing import Any

SCHEMA_VERSIONS: dict[str, int] = {
    "paper_handoff": 1,
    "knowledge_promotion_candidate": 1,
    "incident_report": 1,
    "tournament_entry": 1,
}

VALID_PAPER_TRIGGERS = ("synchrony", "basin_fragility")
VALID_SUBJECT_DOMAINS = (
    "synchronization",
    "basin-stability",
    "control-policy",
    "topology-design",
    "experiment-design",
)
VALID_INCIDENT_SEVERITIES = ("info", "warn", "critical")

ValidationResult = tuple[bool, list[str]]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _require_keys(payload: Any, required: tuple[str, ...]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return [f"payload must be dict, got {type(payload).__name__}"]
    for key in required:
        if key not in payload:
            errors.append(f"missing required key {key!r}")
    return errors


def _check_str(payload: dict[str, Any], key: str, errors: list[str]) -> None:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{key!r} must be a non-empty string")


def _check_int(payload: dict[str, Any], key: str, errors: list[str], *, minimum: int | None = None) -> None:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        errors.append(f"{key!r} must be an int")
        return
    if minimum is not None and value < minimum:
        errors.append(f"{key!r} must be >= {minimum}")


def _check_float(payload: dict[str, Any], key: str, errors: list[str]) -> None:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors.append(f"{key!r} must be a number")


def _check_enum(
    payload: dict[str, Any],
    key: str,
    allowed: tuple[str, ...],
    errors: list[str],
) -> None:
    value = payload.get(key)
    if value not in allowed:
        errors.append(f"{key!r} must be one of {allowed!r}, got {value!r}")


def _check_schema_version(payload: dict[str, Any], kind: str, errors: list[str]) -> None:
    expected = SCHEMA_VERSIONS[kind]
    value = payload.get("schema_version")
    if value != expected:
        errors.append(f"schema_version must equal {expected} for {kind!r}, got {value!r}")


def _check_list_of_str(
    payload: dict[str, Any], key: str, errors: list[str], *, allow_empty: bool = False
) -> None:
    value = payload.get(key)
    if not isinstance(value, list):
        errors.append(f"{key!r} must be a list of strings")
        return
    if not allow_empty and not value:
        errors.append(f"{key!r} must be non-empty")
    for i, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{key!r}[{i}] must be a non-empty string")


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def validate_paper_handoff(payload: Any) -> ValidationResult:
    """Validate a paper_handoff payload emitted by replay-to-paper or similar."""
    required = (
        "schema_version",
        "origin",
        "source_run_dir",
        "source_started_utc",
        "paper_trigger",
        "synchrony_consensus",
        "coupling_consensus",
        "basin_consensus",
        "handoff_excerpt",
        "suggested_domain",
        "generated_utc",
    )
    errors = _require_keys(payload, required)
    if errors:
        return False, errors
    assert isinstance(payload, dict)
    _check_schema_version(payload, "paper_handoff", errors)
    _check_str(payload, "origin", errors)
    _check_str(payload, "source_run_dir", errors)
    _check_str(payload, "source_started_utc", errors)
    _check_enum(payload, "paper_trigger", VALID_PAPER_TRIGGERS, errors)
    _check_str(payload, "synchrony_consensus", errors)
    _check_str(payload, "coupling_consensus", errors)
    _check_str(payload, "basin_consensus", errors)
    _check_str(payload, "generated_utc", errors)
    _check_enum(payload, "suggested_domain", VALID_SUBJECT_DOMAINS, errors)
    handoff = payload.get("handoff_excerpt")
    if not isinstance(handoff, str):
        errors.append("'handoff_excerpt' must be a string (may be empty)")
    return (not errors), errors


def validate_knowledge_promotion_candidate(payload: Any) -> ValidationResult:
    required = (
        "schema_version",
        "subject_folder",
        "corroboration_count",
        "source_ledger_entries",
        "proposed_memory_line",
        "generated_utc",
    )
    errors = _require_keys(payload, required)
    if errors:
        return False, errors
    assert isinstance(payload, dict)
    _check_schema_version(payload, "knowledge_promotion_candidate", errors)
    _check_str(payload, "subject_folder", errors)
    _check_int(payload, "corroboration_count", errors, minimum=1)
    _check_list_of_str(payload, "source_ledger_entries", errors)
    _check_str(payload, "proposed_memory_line", errors)
    _check_str(payload, "generated_utc", errors)
    return (not errors), errors


def validate_incident_report(payload: Any) -> ValidationResult:
    required = (
        "schema_version",
        "kind",
        "severity",
        "drift_metric",
        "threshold",
        "baseline_id",
        "run_dirs_observed",
        "recommended_action",
        "generated_utc",
    )
    errors = _require_keys(payload, required)
    if errors:
        return False, errors
    assert isinstance(payload, dict)
    _check_schema_version(payload, "incident_report", errors)
    _check_str(payload, "kind", errors)
    _check_enum(payload, "severity", VALID_INCIDENT_SEVERITIES, errors)
    _check_float(payload, "drift_metric", errors)
    _check_float(payload, "threshold", errors)
    _check_str(payload, "baseline_id", errors)
    _check_list_of_str(payload, "run_dirs_observed", errors, allow_empty=True)
    _check_str(payload, "recommended_action", errors)
    _check_str(payload, "generated_utc", errors)
    return (not errors), errors


def validate_tournament_entry(payload: Any) -> ValidationResult:
    required = (
        "schema_version",
        "tournament_id",
        "candidates",
        "winner_variant_id",
        "proposed_tilt",
        "generated_utc",
    )
    errors = _require_keys(payload, required)
    if errors:
        return False, errors
    assert isinstance(payload, dict)
    _check_schema_version(payload, "tournament_entry", errors)
    _check_str(payload, "tournament_id", errors)
    _check_str(payload, "winner_variant_id", errors)
    _check_str(payload, "generated_utc", errors)
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        errors.append("'candidates' must be a non-empty list")
    else:
        for i, cand in enumerate(candidates):
            if not isinstance(cand, dict):
                errors.append(f"candidates[{i}] must be a dict")
                continue
            for ckey in ("variant_id", "score"):
                if ckey not in cand:
                    errors.append(f"candidates[{i}] missing {ckey!r}")
    tilt = payload.get("proposed_tilt")
    if not isinstance(tilt, dict):
        errors.append("'proposed_tilt' must be a dict")
    return (not errors), errors


__all__ = [
    "SCHEMA_VERSIONS",
    "VALID_INCIDENT_SEVERITIES",
    "VALID_PAPER_TRIGGERS",
    "VALID_SUBJECT_DOMAINS",
    "ValidationResult",
    "validate_incident_report",
    "validate_knowledge_promotion_candidate",
    "validate_paper_handoff",
    "validate_tournament_entry",
]
