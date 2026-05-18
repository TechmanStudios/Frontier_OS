# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""Infinity-node result applicator tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
_EXCITON_DIR = _HERE.parents[2]
_SCRIPTS_DIR = _EXCITON_DIR / "scripts"
for _path in (_EXCITON_DIR, _SCRIPTS_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from scripts.infinity_node_results import (  # noqa: E402
    RESULT_SCHEMA_VERSION,
    apply_result_to_system_state,
    build_result_payload,
    discover_junit_files,
    main,
    parse_junit_file,
    write_result_artifacts,
)


def _write_junit(path: Path, *, tests: int, failures: int = 0, errors: int = 0, skipped: int = 0) -> None:
    path.write_text(
        f'<testsuite name="pytest" tests="{tests}" failures="{failures}" '
        f'errors="{errors}" skipped="{skipped}" time="1.25"></testsuite>',
        encoding="utf-8",
    )


def test_parse_junit_file_counts_single_suite(tmp_path: Path):
    junit = tmp_path / "result.xml"
    _write_junit(junit, tests=5, failures=1, skipped=1)

    summary = parse_junit_file(junit)

    assert summary.suites == 1
    assert summary.tests == 5
    assert summary.failures == 1
    assert summary.errors == 0
    assert summary.skipped == 1
    assert summary.passed == 3
    assert summary.time == 1.25


def test_discover_and_build_payload_aggregates_multiple_files(tmp_path: Path):
    first = tmp_path / "a.xml"
    second = tmp_path / "nested" / "b.xml"
    second.parent.mkdir()
    _write_junit(first, tests=4)
    _write_junit(second, tests=3, errors=1)

    paths = discover_junit_files([], [tmp_path])
    payload = build_result_payload([parse_junit_file(path) for path in paths], status="failure", run_id="42")

    assert paths == [first, second]
    assert payload["schema_version"] == RESULT_SCHEMA_VERSION
    assert payload["overall_status"] == "fail"
    assert payload["run_id"] == "42"
    assert payload["totals"] == {
        "suites": 2,
        "tests": 7,
        "passed": 6,
        "failures": 0,
        "errors": 1,
        "skipped": 0,
        "time": 2.5,
    }


def test_write_artifacts_and_apply_system_state(tmp_path: Path):
    junit = tmp_path / "result.xml"
    _write_junit(junit, tests=2)
    payload = build_result_payload([parse_junit_file(junit)], status="success", sha="abc123", branch="main")

    artifact_paths = write_result_artifacts(payload, output_root=tmp_path / "infinity_node")
    state = apply_result_to_system_state(
        payload,
        artifact_paths,
        state_path=tmp_path / "snowball" / "state.json",
        lock_path=tmp_path / "snowball" / "state.lock",
    )

    assert Path(artifact_paths["result_path"]).exists()
    assert (
        Path(artifact_paths["summary_path"])
        .read_text(encoding="utf-8")
        .startswith("# Infinity-node test results")
    )
    ledger_lines = Path(artifact_paths["ledger_path"]).read_text(encoding="utf-8").splitlines()
    assert len(ledger_lines) == 1
    assert json.loads(ledger_lines[0])["kind"] == "infinity_node_test_result"
    assert state["infinity_node_test_results"]["overall_status"] == "pass"
    assert state["infinity_node_test_results"]["sha"] == "abc123"


def test_main_writes_result_without_state_when_disabled(tmp_path: Path, capsys):
    junit_root = tmp_path / "junit"
    junit_root.mkdir()
    _write_junit(junit_root / "result.xml", tests=1)

    exit_code = main(
        [
            "--junit-root",
            str(junit_root),
            "--status",
            "success",
            "--output-root",
            str(tmp_path / "out"),
            "--state-path",
            str(tmp_path / "state.json"),
            "--no-apply-state",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["overall_status"] == "pass"
    assert Path(payload["latest_summary_path"]).exists()
    assert not (tmp_path / "state.json").exists()
