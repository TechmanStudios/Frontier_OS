# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""Infinity-node test result applicator.

Collects pytest JUnit XML outputs from a GitHub Actions matrix, writes a
compact audit artifact under ``working_data/infinity_node/``, and applies the
latest read-only result snapshot into the shared snowball state so downstream
system consumers can see CI health without changing control policy.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EXCITON_ROOT = Path(__file__).resolve().parent.parent
INFINITY_NODE_DIR = EXCITON_ROOT / "working_data" / "infinity_node"
SNOWBALL_STATE_PATH = EXCITON_ROOT / "working_data" / "snowball" / "state.json"
SNOWBALL_STATE_LOCK_PATH = EXCITON_ROOT / "working_data" / "snowball" / "state.lock"
RESULT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class JunitSummary:
    path: str
    suites: int
    tests: int
    failures: int
    errors: int
    skipped: int
    time: float

    @property
    def passed(self) -> int:
        return max(0, self.tests - self.failures - self.errors - self.skipped)


def utc_timestamp_token() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def utcnow_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _int_attr(element: ET.Element, name: str) -> int:
    try:
        return int(float(element.attrib.get(name, "0") or 0))
    except ValueError:
        return 0


def _float_attr(element: ET.Element, name: str) -> float:
    try:
        return float(element.attrib.get(name, "0") or 0.0)
    except ValueError:
        return 0.0


def _strip_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _iter_testsuites(root: ET.Element) -> list[ET.Element]:
    if _strip_namespace(root.tag) == "testsuite":
        return [root]
    return [element for element in root.iter() if _strip_namespace(element.tag) == "testsuite"]


def parse_junit_file(path: Path) -> JunitSummary:
    """Parse one JUnit XML file into a count summary."""
    root = ET.parse(path).getroot()
    suites = _iter_testsuites(root)
    return JunitSummary(
        path=path.as_posix(),
        suites=len(suites),
        tests=sum(_int_attr(suite, "tests") for suite in suites),
        failures=sum(_int_attr(suite, "failures") for suite in suites),
        errors=sum(_int_attr(suite, "errors") for suite in suites),
        skipped=sum(_int_attr(suite, "skipped") for suite in suites),
        time=round(sum(_float_attr(suite, "time") for suite in suites), 6),
    )


def discover_junit_files(paths: Iterable[Path], roots: Iterable[Path]) -> list[Path]:
    discovered = {path for path in paths if path.exists() and path.is_file()}
    for root in roots:
        if root.exists():
            discovered.update(path for path in root.rglob("*.xml") if path.is_file())
    return sorted(discovered, key=lambda p: p.as_posix())


def build_result_payload(
    summaries: Sequence[JunitSummary],
    *,
    status: str,
    run_id: str | None = None,
    run_url: str | None = None,
    sha: str | None = None,
    branch: str | None = None,
    run_token: str | None = None,
) -> dict[str, Any]:
    totals = {
        "suites": sum(summary.suites for summary in summaries),
        "tests": sum(summary.tests for summary in summaries),
        "passed": sum(summary.passed for summary in summaries),
        "failures": sum(summary.failures for summary in summaries),
        "errors": sum(summary.errors for summary in summaries),
        "skipped": sum(summary.skipped for summary in summaries),
        "time": round(sum(summary.time for summary in summaries), 6),
    }
    normalized_status = str(status or "unknown")
    has_test_failure = totals["failures"] > 0 or totals["errors"] > 0
    overall_status = (
        "pass" if summaries and normalized_status == "success" and not has_test_failure else "fail"
    )
    if not summaries:
        overall_status = "no_results"
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "run_token": run_token or utc_timestamp_token(),
        "generated_utc": utcnow_iso(),
        "kind": "infinity_node_test_result",
        "status": normalized_status,
        "overall_status": overall_status,
        "run_id": run_id,
        "run_url": run_url,
        "sha": sha,
        "branch": branch,
        "files_observed": len(summaries),
        "totals": totals,
        "junit_files": [summary.__dict__ | {"passed": summary.passed} for summary in summaries],
    }


def render_summary_markdown(payload: dict[str, Any]) -> str:
    totals = payload["totals"]
    lines = [
        "# Infinity-node test results",
        "",
        f"- overall status: {payload['overall_status']}",
        f"- workflow status: {payload['status']}",
        f"- run id: {payload.get('run_id') or 'unknown'}",
        f"- branch: {payload.get('branch') or 'unknown'}",
        f"- sha: {payload.get('sha') or 'unknown'}",
        f"- generated (UTC): {payload['generated_utc']}",
        "",
        "## Aggregate",
        "",
        f"- files observed: {payload['files_observed']}",
        f"- suites: {totals['suites']}",
        f"- tests: {totals['tests']}",
        f"- passed: {totals['passed']}",
        f"- failures: {totals['failures']}",
        f"- errors: {totals['errors']}",
        f"- skipped: {totals['skipped']}",
        f"- time: {totals['time']}",
        "",
        "## JUnit files",
        "",
    ]
    for file_summary in payload["junit_files"]:
        lines.append(
            f"- `{file_summary['path']}`: tests={file_summary['tests']}, "
            f"failures={file_summary['failures']}, errors={file_summary['errors']}, "
            f"skipped={file_summary['skipped']}"
        )
    if not payload["junit_files"]:
        lines.append("- no JUnit XML files were observed")
    return "\n".join(lines) + "\n"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".tmp-", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, indent=2)
            handle.write("\n")
        tmp_path.replace(path)
    except Exception:
        with contextlib.suppress(FileNotFoundError):
            tmp_path.unlink()
        raise


def write_result_artifacts(
    payload: dict[str, Any], *, output_root: Path = INFINITY_NODE_DIR
) -> dict[str, str]:
    run_token = str(payload["run_token"])
    run_dir = output_root / "runs" / run_token
    result_path = run_dir / "result.json"
    summary_path = run_dir / "summary.md"
    ledger_path = output_root / "ledger.jsonl"
    latest_result_path = output_root / "latest_result.json"
    latest_summary_path = output_root / "latest_summary.md"

    summary = render_summary_markdown(payload)
    _atomic_write_json(result_path, payload)
    summary_path.write_text(summary, encoding="utf-8")
    _atomic_write_json(latest_result_path, payload)
    latest_summary_path.write_text(summary, encoding="utf-8")
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({**payload, "result_path": result_path.as_posix()}, sort_keys=True) + "\n")
    return {
        "result_path": result_path.as_posix(),
        "summary_path": summary_path.as_posix(),
        "ledger_path": ledger_path.as_posix(),
        "latest_result_path": latest_result_path.as_posix(),
        "latest_summary_path": latest_summary_path.as_posix(),
    }


@contextlib.contextmanager
def file_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        with contextlib.suppress(FileNotFoundError):
            lock_path.unlink()
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    try:
        yield
    finally:
        with contextlib.suppress(FileNotFoundError):
            lock_path.unlink()


def apply_result_to_system_state(
    payload: dict[str, Any],
    artifact_paths: dict[str, str],
    *,
    state_path: Path = SNOWBALL_STATE_PATH,
    lock_path: Path = SNOWBALL_STATE_LOCK_PATH,
) -> dict[str, Any]:
    """Apply a read-only CI health snapshot into snowball state."""
    with file_lock(lock_path):
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                state = {}
        else:
            state = {}
        if not isinstance(state, dict):
            state = {}
        state.setdefault("schema_version", 1)
        state["infinity_node_test_results"] = {
            "schema_version": RESULT_SCHEMA_VERSION,
            "run_token": payload["run_token"],
            "generated_utc": payload["generated_utc"],
            "overall_status": payload["overall_status"],
            "status": payload["status"],
            "totals": payload["totals"],
            "files_observed": payload["files_observed"],
            "run_id": payload.get("run_id"),
            "run_url": payload.get("run_url"),
            "sha": payload.get("sha"),
            "branch": payload.get("branch"),
            "result_path": artifact_paths["result_path"],
            "summary_path": artifact_paths["summary_path"],
        }
        state["updated_utc"] = utcnow_iso()
        _atomic_write_json(state_path, state)
        return state


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junit", action="append", type=Path, default=[])
    parser.add_argument("--junit-root", action="append", type=Path, default=[])
    parser.add_argument("--status", default="unknown")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--run-url", default=None)
    parser.add_argument("--sha", default=None)
    parser.add_argument("--branch", default=None)
    parser.add_argument("--output-root", type=Path, default=INFINITY_NODE_DIR)
    parser.add_argument("--state-path", type=Path, default=SNOWBALL_STATE_PATH)
    parser.add_argument("--state-lock-path", type=Path, default=SNOWBALL_STATE_LOCK_PATH)
    parser.add_argument("--no-apply-state", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    junit_files = discover_junit_files(args.junit, args.junit_root)
    summaries = [parse_junit_file(path) for path in junit_files]
    payload = build_result_payload(
        summaries,
        status=args.status,
        run_id=args.run_id,
        run_url=args.run_url,
        sha=args.sha,
        branch=args.branch,
    )
    artifact_paths = write_result_artifacts(payload, output_root=args.output_root)
    if not args.no_apply_state:
        apply_result_to_system_state(
            payload,
            artifact_paths,
            state_path=args.state_path,
            lock_path=args.state_lock_path,
        )
    print(json.dumps({**payload, **artifact_paths}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
