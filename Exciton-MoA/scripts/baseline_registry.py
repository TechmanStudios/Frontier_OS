# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""Baseline + scoring registry for the agentic umbrella (Slab C).

Pinned baselines live under ``working_data/snowball/baselines/<baseline_id>.json``
and describe the reference distribution of key ledger-row fields. Two
consumers share this module:

 * ``pair_tournament.py`` (experiment #2) uses :func:`score_variant` to rank
   candidate ledger rows.
 * ``drift_watch.py`` (experiment #5) uses :func:`distribution_drift` to
   detect when the live distribution has wandered off the baseline.

Scoring is intentionally simple, deterministic, and dependency-free so the
governance layer stays readable. No scipy / numpy.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from snowball_experiment import SNOWBALL_DIR

BASELINES_DIR = SNOWBALL_DIR / "baselines"

# Default score weights — tuned so a clean "natural entry with no paper
# trigger and positive forward windows" beats a noisy/triggered run.
DEFAULT_SCORE_WEIGHTS: dict[str, float] = {
    "natural_entries": 1.0,
    "gate_pass_total": 0.25,
    "positive_forward_window_total": 0.5,
    "paper_trigger_penalty": -0.75,  # applied when paper_trigger != "none"
    "nudge_applied_penalty": -0.05,  # per nudge, capped at -0.5
}

# Baselines we expect to exist in repo; others are allowed but un-enumerated.
KNOWN_BASELINE_IDS = ("diagnosis_distribution_v1", "coupling_distribution_v1")


# ---------------------------------------------------------------------------
# Baseline I/O
# ---------------------------------------------------------------------------


def baseline_path(baseline_id: str, *, root: Path = BASELINES_DIR) -> Path:
    if not baseline_id or "/" in baseline_id or "\\" in baseline_id:
        raise ValueError(f"invalid baseline id {baseline_id!r}")
    return root / f"{baseline_id}.json"


def load_baseline(baseline_id: str, *, root: Path = BASELINES_DIR) -> dict[str, Any] | None:
    path = baseline_path(baseline_id, root=root)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def save_baseline(baseline_id: str, payload: dict[str, Any], *, root: Path = BASELINES_DIR) -> Path:
    path = baseline_path(baseline_id, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".tmp-", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fp:
            json.dump(payload, fp, sort_keys=True, indent=2)
            fp.write("\n")
        tmp_path.replace(path)
    except Exception:
        with contextlib.suppress(FileNotFoundError):
            tmp_path.unlink()
        raise
    return path


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScoredRow:
    variant_id: str
    score: float
    components: dict[str, float]


def score_variant(
    row: dict[str, Any],
    *,
    weights: dict[str, float] | None = None,
    variant_id: str | None = None,
) -> ScoredRow:
    """Score a single ledger row.

    Components (all optional in the row):
     * ``natural_entries``            (int)
     * ``gate_pass_total``            (int)
     * ``positive_forward_window_total`` (int)
     * ``paper_trigger``              ("none" / "synchrony" / "basin_fragility")
     * ``nudge_applied_total``        (int)

    Missing fields contribute zero.
    """
    w = {**DEFAULT_SCORE_WEIGHTS, **(weights or {})}
    components: dict[str, float] = {}

    natural = int(row.get("natural_entries") or 0)
    gates = int(row.get("gate_pass_total") or 0)
    pos_windows = int(row.get("positive_forward_window_total") or 0)
    trigger = str(row.get("paper_trigger") or "none")
    nudges = int(row.get("nudge_applied_total") or 0)

    components["natural_entries"] = natural * w["natural_entries"]
    components["gate_pass_total"] = gates * w["gate_pass_total"]
    components["positive_forward_window_total"] = pos_windows * w["positive_forward_window_total"]
    components["paper_trigger_penalty"] = w["paper_trigger_penalty"] if trigger != "none" else 0.0
    # Per-nudge penalty, floored so one noisy run cannot dominate.
    components["nudge_applied_penalty"] = max(-0.5, nudges * w["nudge_applied_penalty"])

    score = sum(components.values())
    vid = variant_id or str(row.get("run_dir") or row.get("run_token") or row.get("started_utc") or "unknown")
    return ScoredRow(variant_id=vid, score=round(score, 6), components=components)


def rank_variants(
    rows: Sequence[dict[str, Any]],
    *,
    weights: dict[str, float] | None = None,
) -> list[ScoredRow]:
    scored = [score_variant(r, weights=weights) for r in rows]
    # Sort by score descending, break ties deterministically by variant_id.
    scored.sort(key=lambda s: (-s.score, s.variant_id))
    return scored


# ---------------------------------------------------------------------------
# Distribution drift
# ---------------------------------------------------------------------------


def _normalize_counts(counts: dict[str, int] | dict[str, float]) -> dict[str, float]:
    total = float(sum(counts.values()))
    if total <= 0:
        return {k: 0.0 for k in counts}
    return {k: v / total for k, v in counts.items()}


def distribution_drift(
    current: dict[str, int] | dict[str, float],
    baseline: dict[str, int] | dict[str, float],
) -> float:
    """Return total-variation distance between ``current`` and ``baseline``.

    Both inputs are label -> count dicts. Missing keys in either side are
    treated as zero. The result is in ``[0.0, 1.0]`` — 0.0 means identical
    distributions, 1.0 means disjoint.
    """
    cur = _normalize_counts(dict(current))
    base = _normalize_counts(dict(baseline))
    keys = set(cur) | set(base)
    if not keys:
        return 0.0
    tv = 0.5 * sum(abs(cur.get(k, 0.0) - base.get(k, 0.0)) for k in keys)
    return round(tv, 6)


def is_over_threshold(drift: float, threshold: float) -> bool:
    return drift > threshold


# ---------------------------------------------------------------------------
# Ledger -> counts helpers
# ---------------------------------------------------------------------------


def counts_from_rows(rows: Sequence[dict[str, Any]], *, field: str) -> dict[str, int]:
    """Count occurrences of ``row[field]`` across ``rows``.

    Missing or None values are bucketed as ``"unknown"``.
    """
    counts: dict[str, int] = {}
    for r in rows:
        key = str(r.get(field) or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts


__all__ = [
    "BASELINES_DIR",
    "DEFAULT_SCORE_WEIGHTS",
    "KNOWN_BASELINE_IDS",
    "ScoredRow",
    "baseline_path",
    "counts_from_rows",
    "distribution_drift",
    "is_over_threshold",
    "load_baseline",
    "rank_variants",
    "save_baseline",
    "score_variant",
]
