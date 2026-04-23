# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""Reproducibility-tier baseline check for the EntangledSOLPair engine.

Runs a pinned configuration ``--repeats`` times in independent working
directories and asserts the SHA256 hash of the per-tick
``phase_coherence_history`` is identical across all runs. Divergence is a
``#2`` (deterministic-engine) regression and exits non-zero so CI fails loud.

Each invocation appends one record to
``working_data/repro_baseline/<run_token>.jsonl`` for downstream auditing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

_SCRIPTS_DIR = Path(__file__).resolve().parent
_EXCITON_DIR = _SCRIPTS_DIR.parent
for _path in (_EXCITON_DIR, _SCRIPTS_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from blank_config import BlankManifoldConfig  # noqa: E402
from entangled_manifolds import EntangledSOLPair, EntanglementControls  # noqa: E402
from snowball_consumer import utc_timestamp_token, utcnow_iso  # noqa: E402

REPRO_BASELINE_DIR = _EXCITON_DIR / "working_data" / "repro_baseline"
DEFAULT_CYCLES = 12
DEFAULT_SEED = 149
DEFAULT_REPEATS = 3
BASELINE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class BaselineConfig:
    seed: int = DEFAULT_SEED
    cycles: int = DEFAULT_CYCLES
    wormhole_count: int = 6
    base_node_count: int = 96
    dimensionality: int = 3
    embedding_a_loc: float = 0.20
    embedding_b_loc: float = 0.40
    embedding_scale: float = 1.00
    embedding_drift: float = 0.01
    embedding_dim: int = 256
    entangler_mode: str = "active"


def _build_embeddings(config: BaselineConfig) -> tuple[list[np.ndarray], list[np.ndarray]]:
    embeddings_a: list[np.ndarray] = []
    embeddings_b: list[np.ndarray] = []
    for tick in range(config.cycles):
        a = np.linspace(
            config.embedding_a_loc + config.embedding_drift * tick,
            config.embedding_a_loc + config.embedding_scale + config.embedding_drift * tick,
            config.embedding_dim,
        )
        b = np.linspace(
            config.embedding_b_loc + config.embedding_drift * tick,
            config.embedding_b_loc + config.embedding_scale + config.embedding_drift * tick,
            config.embedding_dim,
        )
        embeddings_a.append(a)
        embeddings_b.append(b)
    return embeddings_a, embeddings_b


def _run_phase_coherence_history(
    config: BaselineConfig,
    working_dir: Path,
    embeddings_a: Sequence[np.ndarray],
    embeddings_b: Sequence[np.ndarray],
) -> list[float]:
    manifold_config = BlankManifoldConfig(
        base_node_count=config.base_node_count,
        dimensionality=config.dimensionality,
    )
    pair = EntangledSOLPair(
        config_a=manifold_config,
        config_b=manifold_config,
        controls=EntanglementControls(
            wormhole_count=config.wormhole_count,
            seed=config.seed,
            entangler_mode=config.entangler_mode,
        ),
        working_dir=working_dir,
    )
    history: list[float] = []
    for embedding_a, embedding_b in zip(embeddings_a, embeddings_b):
        result = pair.tick(embedding_a=embedding_a, embedding_b=embedding_b)
        history.append(float(result["pair_metrics"]["phase_coherence"]))
    return history


def hash_phase_coherence_history(history: Sequence[float]) -> str:
    """Stable SHA256 over the per-tick coherence values.

    Uses ``%.17e`` formatting to capture full IEEE-754 double precision so
    bit-level drift in any tick triggers a hash mismatch.
    """
    payload = ",".join(f"{float(value):.17e}" for value in history)
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def run_repro_baseline_check(
    config: BaselineConfig | None = None,
    *,
    repeats: int = DEFAULT_REPEATS,
    output_dir: Path | None = None,
) -> dict[str, object]:
    """Execute the pinned baseline ``repeats`` times and report match status.

    Returns a dict suitable for JSON serialization. ``hash_match`` is False
    when any run's SHA256 differs from the first run's SHA256.
    """
    if repeats < 2:
        raise ValueError("repeats must be >= 2 to detect divergence")
    config = config or BaselineConfig()
    output_dir = output_dir or REPRO_BASELINE_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    embeddings_a, embeddings_b = _build_embeddings(config)
    run_token = utc_timestamp_token()
    hashes: list[str] = []
    histories_lengths: list[int] = []
    with tempfile.TemporaryDirectory(prefix=f"repro_baseline_{run_token}_") as tmp_root:
        tmp_root_path = Path(tmp_root)
        for idx in range(repeats):
            run_dir = tmp_root_path / f"run_{idx}"
            run_dir.mkdir(parents=True, exist_ok=True)
            history = _run_phase_coherence_history(
                config, run_dir, embeddings_a, embeddings_b
            )
            histories_lengths.append(len(history))
            hashes.append(hash_phase_coherence_history(history))

    baseline_hash = hashes[0]
    hash_match = all(h == baseline_hash for h in hashes)
    record: dict[str, object] = {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "run_token": run_token,
        "timestamp": utcnow_iso(),
        "repeats": repeats,
        "cycles": config.cycles,
        "seed": config.seed,
        "wormhole_count": config.wormhole_count,
        "base_node_count": config.base_node_count,
        "dimensionality": config.dimensionality,
        "embedding_dim": config.embedding_dim,
        "entangler_mode": config.entangler_mode,
        "baseline_hash": baseline_hash,
        "hashes": hashes,
        "history_lengths": histories_lengths,
        "hash_match": hash_match,
    }
    out_path = output_dir / f"{run_token}.jsonl"
    with out_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    record["artifact_path"] = str(out_path)
    return record


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=DEFAULT_CYCLES)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    config = BaselineConfig(seed=int(args.seed), cycles=int(args.cycles))
    record = run_repro_baseline_check(
        config,
        repeats=int(args.repeats),
        output_dir=args.output_dir,
    )
    print(json.dumps(record, sort_keys=True))
    return 0 if bool(record.get("hash_match")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
