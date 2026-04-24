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
    "knowledge_lesson": 2,
    "arm_promotion": 1,
}

VALID_PAPER_TRIGGERS = ("synchrony", "basin_fragility")
VALID_LESSON_TYPES = (
    "entrainment_stability",
    "coupling_asymmetry",
    "policy_generalization",
    "gate_blocker_pattern",
    "posture_profile_lift",
)
VALID_SUBJECT_DOMAINS = (
    "synchronization",
    "basin-stability",
    "control-policy",
    "topology-design",
    "experiment-design",
)
VALID_INCIDENT_SEVERITIES = ("info", "warn", "critical")
VALID_ARM_PROMOTION_STATUSES = (
    "favors_treatment",
    "favors_control",
    "no_lift",
    "insufficient_evidence",
)
VALID_ARM_PROMOTION_DEFAULTS = ("treatment", "control")

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


def validate_knowledge_lesson(payload: Any) -> ValidationResult:
    """Validate a cross-pair knowledge_lesson payload.

    A lesson is a cross-pocket regularity detected by ``lesson_compiler``
    over multiple sweep_summary.jsonl artifacts. ``corroboration_count`` is
    the number of distinct pockets (or runs) the regularity was observed in
    and must be >= 2 — a single-pocket pattern is not a transferable lesson.
    """
    required = (
        "schema_version",
        "lesson_type",
        "corroboration_count",
        "evidence_run_dirs",
        "key_findings",
        "applicable_constraints",
        "contraindications",
        "generated_utc",
    )
    errors = _require_keys(payload, required)
    if errors:
        return False, errors
    assert isinstance(payload, dict)
    # knowledge_lesson is the only multi-version schema today: readers accept
    # both v1 (pre-C3) and v2 (C3, adds optional profile_used /
    # msf_status_dominant / per_profile_natural_entry_means fields). Writers
    # emit v2.
    version = payload.get("schema_version")
    if version not in (1, 2):
        errors.append(
            f"schema_version must be 1 or 2 for 'knowledge_lesson', got {version!r}"
        )
    _check_enum(payload, "lesson_type", VALID_LESSON_TYPES, errors)
    _check_int(payload, "corroboration_count", errors, minimum=2)
    _check_list_of_str(payload, "evidence_run_dirs", errors)
    _check_str(payload, "key_findings", errors)
    _check_list_of_str(payload, "applicable_constraints", errors, allow_empty=True)
    _check_list_of_str(payload, "contraindications", errors, allow_empty=True)
    _check_str(payload, "generated_utc", errors)
    return (not errors), errors


def _check_arm_block(payload: Any, key: str, errors: list[str]) -> None:
    if not isinstance(payload, dict) or key not in payload:
        return
    block = payload.get(key)
    if not isinstance(block, dict):
        errors.append(f"{key!r} must be dict")
        return
    for required in ("default_arm", "mean_delta", "paired_count", "source_token", "updated_utc", "status"):
        if required not in block:
            errors.append(f"{key}.{required} missing")
    default_arm = block.get("default_arm")
    if default_arm is not None and default_arm not in VALID_ARM_PROMOTION_DEFAULTS:
        errors.append(
            f"{key}.default_arm must be null or one of {VALID_ARM_PROMOTION_DEFAULTS}, got {default_arm!r}"
        )
    mean_delta = block.get("mean_delta")
    if not isinstance(mean_delta, (int, float)) or isinstance(mean_delta, bool):
        errors.append(f"{key}.mean_delta must be numeric")
    paired = block.get("paired_count")
    if not isinstance(paired, int) or isinstance(paired, bool) or paired < 0:
        errors.append(f"{key}.paired_count must be int >= 0")
    for str_field in ("source_token", "updated_utc"):
        if not isinstance(block.get(str_field), str) or not block.get(str_field):
            errors.append(f"{key}.{str_field} must be non-empty str")
    status = block.get("status")
    if status not in VALID_ARM_PROMOTION_STATUSES:
        errors.append(
            f"{key}.status must be one of {VALID_ARM_PROMOTION_STATUSES}, got {status!r}"
        )


def validate_arm_promotion(payload: Any) -> ValidationResult:
    """Validate the ``arm_promotion`` payload (schema v1).

    Required top-level keys: ``schema_version``, ``msf``, ``posture``,
    ``generated_utc``. Each arm block must have ``default_arm`` (null,
    ``"treatment"``, or ``"control"``), numeric ``mean_delta``, non-negative
    ``paired_count``, non-empty ``source_token`` and ``updated_utc`` strings,
    and a ``status`` from :data:`VALID_ARM_PROMOTION_STATUSES`.
    """
    errors = _require_keys(payload, ("schema_version", "msf", "posture", "generated_utc"))
    if errors:
        return False, errors
    expected = SCHEMA_VERSIONS["arm_promotion"]
    if payload.get("schema_version") != expected:
        errors.append(f"schema_version must be {expected}")
    _check_str(payload, "generated_utc", errors)
    _check_arm_block(payload, "msf", errors)
    _check_arm_block(payload, "posture", errors)
    return (not errors), errors


__all__ = [
    "SCHEMA_VERSIONS",
    "VALID_ARM_PROMOTION_DEFAULTS",
    "VALID_ARM_PROMOTION_STATUSES",
    "VALID_INCIDENT_SEVERITIES",
    "VALID_LESSON_TYPES",
    "VALID_PAPER_TRIGGERS",
    "VALID_SUBJECT_DOMAINS",
    "ValidationResult",
    "validate_arm_promotion",
    "validate_incident_report",
    "validate_knowledge_lesson",
    "validate_knowledge_promotion_candidate",
    "validate_paper_handoff",
    "validate_tournament_entry",
]
