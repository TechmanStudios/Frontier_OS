# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""Shared consumer kit for snowball-ledger-driven experiments (Slab A).

Provides small, pure helpers for reading the snowball ledger, picking a run
of interest, and writing consumer artifacts under
``working_data/snowball/consumers/<consumer_name>/``.

Consumers (e.g. ``replay_to_paper``, ``counterfactual_probe``) all share this
filesystem layout so downstream tooling has exactly one place to look.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from snowball_experiment import LEDGER_PATH, SNOWBALL_DIR

CONSUMERS_DIR = SNOWBALL_DIR / "consumers"

VALID_SELECTORS = ("most_recent", "most_recent_exploit", "highest_uncertainty")


# ---------------------------------------------------------------------------
# Ledger I/O
# ---------------------------------------------------------------------------


def load_ledger_tail(n: int, *, ledger_path: Path = LEDGER_PATH) -> list[dict[str, Any]]:
    """Return the last ``n`` rows of the snowball ledger, oldest first.

    Missing ledger or malformed lines are tolerated: invalid rows are skipped.
    """
    if n <= 0:
        return []
    if not ledger_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in ledger_path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows[-n:]


def select_ledger_row(
    rows: Sequence[dict[str, Any]],
    *,
    selector: str,
) -> dict[str, Any] | None:
    """Pick one row out of ``rows`` according to ``selector``.

    Selectors:
      * ``most_recent`` — last row, whatever it is.
      * ``most_recent_exploit`` — last row with ``regime == "exploit"``.
      * ``highest_uncertainty`` — last row whose ``paper_trigger`` is not
        ``none`` / missing; rows with ``basin_fragility`` beat ``synchrony``
        only when tied on recency, otherwise recency wins.
    """
    if selector not in VALID_SELECTORS:
        raise ValueError(f"unknown selector {selector!r}")
    if not rows:
        return None

    if selector == "most_recent":
        return dict(rows[-1])
    if selector == "most_recent_exploit":
        for row in reversed(rows):
            if str(row.get("regime")) == "exploit":
                return dict(row)
        return None
    # highest_uncertainty
    triggered = [r for r in rows if str(r.get("paper_trigger") or "none") != "none"]
    if not triggered:
        return None
    return dict(triggered[-1])


# ---------------------------------------------------------------------------
# Filesystem layout for consumer artifacts
# ---------------------------------------------------------------------------


def consumer_dir(consumer_name: str, *, root: Path = CONSUMERS_DIR) -> Path:
    if not consumer_name or "/" in consumer_name or "\\" in consumer_name:
        raise ValueError(f"invalid consumer name {consumer_name!r}")
    return root / consumer_name


def consumer_ledger_path(consumer_name: str, *, root: Path = CONSUMERS_DIR) -> Path:
    return consumer_dir(consumer_name, root=root) / "ledger.jsonl"


def utc_timestamp_token() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def utcnow_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class ConsumerArtifact:
    consumer_name: str
    run_token: str
    artifact_path: Path
    ledger_row: dict[str, Any]


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
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


def write_consumer_artifact(
    *,
    consumer_name: str,
    run_token: str,
    payload: dict[str, Any],
    filename: str = "artifact.json",
    extra_files: Iterable[tuple[str, str]] = (),
    root: Path = CONSUMERS_DIR,
) -> ConsumerArtifact:
    """Write ``payload`` under ``<root>/<consumer_name>/<run_token>/<filename>``.

    ``extra_files`` is an iterable of ``(relative_name, text)`` pairs written
    alongside the primary JSON artifact (e.g. a rendered markdown summary).
    Returns a :class:`ConsumerArtifact` the caller can include in its ledger
    row.
    """
    base = consumer_dir(consumer_name, root=root) / run_token
    artifact_path = base / filename
    _atomic_write_json(artifact_path, payload)
    for rel_name, text in extra_files:
        side_path = base / rel_name
        side_path.parent.mkdir(parents=True, exist_ok=True)
        side_path.write_text(text, encoding="utf-8")
    row = {
        "consumer": consumer_name,
        "run_token": run_token,
        "artifact_path": artifact_path.as_posix(),
        "generated_utc": utcnow_iso(),
    }
    return ConsumerArtifact(
        consumer_name=consumer_name,
        run_token=run_token,
        artifact_path=artifact_path,
        ledger_row=row,
    )


def append_consumer_ledger(
    consumer_name: str,
    row: dict[str, Any],
    *,
    root: Path = CONSUMERS_DIR,
) -> Path:
    ledger_path = consumer_ledger_path(consumer_name, root=root)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(row, sort_keys=True) + "\n")
    return ledger_path


__all__ = [
    "CONSUMERS_DIR",
    "VALID_SELECTORS",
    "ConsumerArtifact",
    "append_consumer_ledger",
    "consumer_dir",
    "consumer_ledger_path",
    "load_ledger_tail",
    "select_ledger_row",
    "utc_timestamp_token",
    "utcnow_iso",
    "write_consumer_artifact",
]
