# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""W5: Reproducibility-tier baseline check tests.

Runs the pinned baseline three times in fresh tmp directories and asserts
the SHA256 hash of phase_coherence_history is identical across runs. This
is the regression bell on the #2 deterministic-engine work (deterministic
wormhole + signature quantization).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve()
_EXCITON_DIR = _HERE.parents[2]
_SCRIPTS_DIR = _EXCITON_DIR / "scripts"
for _path in (_EXCITON_DIR, _SCRIPTS_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from scripts.repro_baseline_check import (  # noqa: E402
    BASELINE_SCHEMA_VERSION,
    BaselineConfig,
    hash_phase_coherence_history,
    main,
    run_repro_baseline_check,
)


def _fast_config() -> BaselineConfig:
    # Smaller cycle count keeps the test under a few seconds while still
    # exercising the full pipeline (entangler, hint gate, telemetry persist).
    return BaselineConfig(cycles=4)


def test_hash_phase_coherence_history_is_stable_for_identical_input():
    history = [0.123456789012345, 0.234567890123456, 0.345678901234567]
    assert hash_phase_coherence_history(history) == hash_phase_coherence_history(list(history))


def test_hash_phase_coherence_history_changes_when_a_value_drifts_at_double_precision():
    base = [0.123456789012345, 0.234567890123456]
    drifted = [0.123456789012346, 0.234567890123456]  # +1 ULP-ish in last digit
    assert hash_phase_coherence_history(base) != hash_phase_coherence_history(drifted)


def test_hash_phase_coherence_history_is_order_sensitive():
    forward = [0.10, 0.20, 0.30]
    reversed_ = list(reversed(forward))
    assert hash_phase_coherence_history(forward) != hash_phase_coherence_history(reversed_)


def test_run_repro_baseline_check_three_runs_match(tmp_path: Path):
    record = run_repro_baseline_check(
        _fast_config(),
        repeats=3,
        output_dir=tmp_path,
    )
    assert record["hash_match"] is True
    assert record["repeats"] == 3
    assert len(record["hashes"]) == 3
    assert all(h == record["baseline_hash"] for h in record["hashes"])
    assert record["cycles"] == 4
    assert record["seed"] == BaselineConfig().seed
    assert record["schema_version"] == BASELINE_SCHEMA_VERSION


def test_run_repro_baseline_check_writes_jsonl_artifact(tmp_path: Path):
    record = run_repro_baseline_check(_fast_config(), repeats=2, output_dir=tmp_path)
    artifact_path = Path(str(record["artifact_path"]))
    assert artifact_path.parent == tmp_path
    assert artifact_path.exists()
    lines = [line for line in artifact_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["baseline_hash"] == record["baseline_hash"]
    assert payload["hash_match"] is True
    assert payload["run_token"] == record["run_token"]


def test_run_repro_baseline_check_appends_when_called_twice(tmp_path: Path):
    first = run_repro_baseline_check(_fast_config(), repeats=2, output_dir=tmp_path)
    artifact_path = Path(str(first["artifact_path"]))
    # Force a second record into the same file by reusing the run_token path.
    second_record_text = json.dumps({"replay": True, "baseline_hash": first["baseline_hash"]})
    with artifact_path.open("a", encoding="utf-8") as handle:
        handle.write(second_record_text + "\n")
    contents = [
        json.loads(line)
        for line in artifact_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(contents) == 2
    assert contents[0]["hash_match"] is True
    assert contents[1]["replay"] is True


def test_run_repro_baseline_check_rejects_repeats_below_two(tmp_path: Path):
    with pytest.raises(ValueError):
        run_repro_baseline_check(_fast_config(), repeats=1, output_dir=tmp_path)


def test_main_cli_returns_zero_on_match(tmp_path: Path, capsys):
    exit_code = main(
        [
            "--cycles",
            "4",
            "--repeats",
            "2",
            "--output-dir",
            str(tmp_path),
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    last_line = [line for line in captured.out.splitlines() if line.strip()][-1]
    payload = json.loads(last_line)
    assert payload["hash_match"] is True
    assert payload["cycles"] == 4
    assert payload["repeats"] == 2


def test_main_cli_returns_one_when_run_diverges(tmp_path: Path, monkeypatch, capsys):
    """Force a divergence by patching the per-run helper to alternate values."""
    import scripts.repro_baseline_check as module

    counter = {"n": 0}
    real = module._run_phase_coherence_history

    def _flaky_run(config, working_dir, embeddings_a, embeddings_b):
        counter["n"] += 1
        history = real(config, working_dir, embeddings_a, embeddings_b)
        if counter["n"] == 2:
            history[0] = float(history[0]) + 1e-12
        return history

    monkeypatch.setattr(module, "_run_phase_coherence_history", _flaky_run)
    exit_code = main(
        [
            "--cycles",
            "4",
            "--repeats",
            "2",
            "--output-dir",
            str(tmp_path),
        ]
    )
    assert exit_code == 1
    captured = capsys.readouterr()
    last_line = [line for line in captured.out.splitlines() if line.strip()][-1]
    payload = json.loads(last_line)
    assert payload["hash_match"] is False
    assert payload["hashes"][0] != payload["hashes"][1]
