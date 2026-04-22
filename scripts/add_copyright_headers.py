# Copyright (c) 2026 Techman Studios.
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE in the repository root for details.
"""Prepend the Frontier_OS AGPL copyright header to every Python source file.

Idempotent: skips files that already contain the marker line.

Usage (from repo root):

    python scripts/add_copyright_headers.py            # dry run, lists files
    python scripts/add_copyright_headers.py --write    # actually modify files
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HEADER = (
    "# Copyright (c) 2026 Techman Studios.\n"
    "# Licensed under the GNU Affero General Public License v3.0 or later.\n"
    "# See LICENSE in the repository root for details.\n"
)
MARKER = "Licensed under the GNU Affero General Public License"

# Directories to skip entirely.
SKIP_DIR_PARTS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
    "working_data",
}


def iter_python_files(root: Path):
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIR_PARTS for part in path.parts):
            continue
        yield path


def needs_header(path: Path) -> bool:
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:512]
    except OSError:
        return False
    return MARKER not in head


def prepend_header(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if text.startswith("#!"):
        # Preserve shebang on first line.
        first_nl = text.find("\n") + 1
        new_text = text[:first_nl] + HEADER + text[first_nl:]
    else:
        new_text = HEADER + text
    path.write_text(new_text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Modify files in place.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repo root (defaults to parent of scripts/).",
    )
    args = parser.parse_args(argv)

    targets = [p for p in iter_python_files(args.root) if needs_header(p)]
    for path in targets:
        rel = path.relative_to(args.root)
        if args.write:
            prepend_header(path)
            print(f"updated  {rel}")
        else:
            print(f"would update  {rel}")

    if not targets:
        print("All Python files already carry the AGPL header.")
    elif not args.write:
        print(f"\nDry run — {len(targets)} file(s) would be updated. Re-run with --write to apply.")
    else:
        print(f"\nDone — {len(targets)} file(s) updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
