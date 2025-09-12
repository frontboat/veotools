#!/usr/bin/env python3
"""Verify that release tag matches package versions.

Checks:
- Git tag (without leading 'v') equals [project].version in pyproject.toml
- src/veotools/__init__.py __version__ equals pyproject version

Usage: run in CI prior to building/publishing releases.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


def read_pyproject_version(pyproject_path: Path) -> str:
    text = pyproject_path.read_text(encoding="utf-8")
    # Naive parse: find [project] block, then version = "..."
    in_project = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_project = (stripped == "[project]")
            continue
        if in_project and stripped.startswith("version"):
            m = re.search(r'version\s*=\s*"([^"]+)"', stripped)
            if m:
                return m.group(1)
    raise RuntimeError("Unable to locate [project].version in pyproject.toml")


def read_init_version(init_path: Path) -> str:
    text = init_path.read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if not m:
        raise RuntimeError("__version__ not found in src/veotools/__init__.py")
    return m.group(1)


def main() -> None:
    tag = os.environ.get("GITHUB_REF_NAME") or os.environ.get("GITHUB_TAG") or ""
    tag_version = tag.lstrip("v")
    if not tag_version:
        print("Warning: GITHUB_REF_NAME not set; skipping tag comparison", file=sys.stderr)

    repo_root = Path(__file__).resolve().parents[1]
    py_version = read_pyproject_version(repo_root / "pyproject.toml")
    init_version = read_init_version(repo_root / "src" / "veotools" / "__init__.py")

    errors = []
    if tag_version and py_version != tag_version:
        errors.append(f"pyproject version {py_version} != tag {tag_version}")
    if init_version != py_version:
        errors.append(f"__version__ {init_version} != pyproject {py_version}")

    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        sys.exit(1)

    print(f"Version OK: {py_version}")


if __name__ == "__main__":
    main()


